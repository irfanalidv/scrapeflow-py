"""Unit tests for retry, rate limiting, robots.txt, monitoring and workflow execution.

No browser and no network: collaborators are faked or patched.
"""

from __future__ import annotations

import asyncio
import logging
import types
from pathlib import Path
from typing import Any

import aiohttp
import pytest

from scrapeflow import ScrapeFlow, Workflow
from scrapeflow.anti_detection import (
    AntiDetectionManager,
    ProxyRotator,
    StealthMode,
    UserAgentRotator,
)
from scrapeflow.browser_runtime import PlaywrightBrowserRuntime
from scrapeflow.config import AntiDetectionConfig, RateLimitConfig, RetryConfig, ScrapeFlowConfig
from scrapeflow.exceptions import (
    ScrapeFlowBlockedError,
    ScrapeFlowConfigurationError,
    ScrapeFlowError,
    ScrapeFlowNotStartedError,
    ScrapeFlowRetryError,
    ScrapeFlowTimeoutError,
)
from scrapeflow.monitoring import Logger, PerformanceMonitor, ScrapeMetrics
from scrapeflow.rate_limiter import AdaptiveRateLimiter, RateLimiter, effective_rate
from scrapeflow.registry import (
    SelectorRegistry,
    get_registry,
    register_job_listing_schema,
    register_product_price_schema,
)
from scrapeflow.retry import ErrorClassifier, RetryHandler
from scrapeflow.robots import RobotsChecker
from tests.test_engine_orchestration import (
    FakeLogger,
    FakeMonitor,
    FakeRateLimiter,
    FakeRobotsChecker,
    FakeRuntime,
)

# --------------------------------------------------------------------------- retry


def no_wait(max_retries: int = 2) -> RetryHandler:
    return RetryHandler(RetryConfig(max_retries=max_retries, initial_delay=0, jitter=False))


async def test_retry_succeeds_after_transient_failures() -> None:
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("boom")
        return "ok"

    assert await no_wait().execute_with_retry(flaky) == "ok"
    assert calls["n"] == 3


async def test_retry_supports_sync_functions_and_args() -> None:
    assert await no_wait().execute_with_retry(lambda a, b=0: a + b, 2, b=3) == 5


async def test_retry_exhaustion_wraps_last_error() -> None:
    async def always_fails() -> None:
        raise ConnectionError("down")

    with pytest.raises(ScrapeFlowRetryError) as info:
        await no_wait(max_retries=1).execute_with_retry(always_fails)
    assert info.value.retry_count == 1
    assert info.value.max_retries == 1
    assert isinstance(info.value.__cause__, ConnectionError)


async def test_retry_non_retryable_error_propagates_immediately() -> None:
    calls = {"n": 0}

    def bad() -> None:
        calls["n"] += 1
        raise KeyError("x")

    with pytest.raises(KeyError):
        await no_wait().execute_with_retry(bad, retryable_exceptions=(ConnectionError,))
    assert calls["n"] == 1


async def test_retry_backoff_delays(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    handler = RetryHandler(
        RetryConfig(max_retries=4, initial_delay=1, max_delay=5, exponential_base=2, jitter=False)
    )

    async def fails() -> None:
        raise TimeoutError

    with pytest.raises(ScrapeFlowRetryError):
        await handler.execute_with_retry(fails)
    assert sleeps == [1, 2, 4, 5]

    jittery = RetryHandler(RetryConfig(initial_delay=10, jitter=True))
    assert 10 <= jittery._add_jitter(10) <= 11


def test_error_classifier() -> None:
    assert ErrorClassifier.is_retryable(ConnectionError())
    assert ErrorClassifier.is_retryable(asyncio.TimeoutError())
    assert ErrorClassifier.is_retryable(ScrapeFlowTimeoutError("t"))
    assert ErrorClassifier.is_retryable(ScrapeFlowRetryError("r"))
    assert ErrorClassifier.is_retryable(ScrapeFlowBlockedError("b"))
    http_503 = types.SimpleNamespace(status_code=503)
    assert ErrorClassifier.is_retryable(http_503)  # type: ignore[arg-type]
    assert not ErrorClassifier.is_retryable(ValueError())
    assert not ErrorClassifier.is_retryable(types.SimpleNamespace(status_code=404))  # type: ignore[arg-type]

    assert ErrorClassifier.get_retry_delay(ScrapeFlowBlockedError("b", retry_after=7)) == 7
    err_429 = types.SimpleNamespace(status_code=429, headers={"Retry-After": "12"})
    assert ErrorClassifier.get_retry_delay(err_429) == 12.0  # type: ignore[arg-type]
    http_date = types.SimpleNamespace(
        status_code=429, headers={"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"}
    )
    assert ErrorClassifier.get_retry_delay(http_date) is None  # type: ignore[arg-type]
    assert ErrorClassifier.get_retry_delay(ValueError()) is None


# --------------------------------------------------------------------------- rate limiting


def test_effective_rate_uses_slower_limit() -> None:
    assert effective_rate(RateLimitConfig(requests_per_second=2)) == 2
    assert effective_rate(RateLimitConfig(requests_per_second=2, requests_per_minute=30)) == 0.5
    assert effective_rate(RateLimitConfig(requests_per_second=None, requests_per_minute=120)) == 2  # type: ignore[arg-type]
    assert effective_rate(RateLimitConfig(requests_per_second=0)) == 1.0


async def test_rate_limiter_burst_then_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    clock = {"t": 100.0}
    monkeypatch.setattr("scrapeflow.rate_limiter.time.monotonic", lambda: clock["t"])

    limiter = RateLimiter(RateLimitConfig(requests_per_second=2, burst_size=2))
    await limiter.acquire()
    await limiter.acquire()
    assert sleeps == []  # burst
    await limiter.acquire()
    assert sleeps == [pytest.approx(0.5)]  # one token every 0.5s

    clock["t"] += 10  # long idle: bucket refills, capped at burst_size
    await limiter.acquire()
    assert limiter.tokens == pytest.approx(1)


def test_adaptive_rate_limiter() -> None:
    limiter = AdaptiveRateLimiter(RateLimitConfig(requests_per_second=1))
    limiter.backoff()
    assert limiter.current_rate == pytest.approx(1 / 1.5)
    for _ in range(20):
        limiter.backoff()
    assert limiter.current_rate == limiter.min_rate
    for _ in range(100):
        limiter.speed_up()
    assert limiter.current_rate == 1
    assert limiter.refill_rate == pytest.approx(1)


# --------------------------------------------------------------------------- robots.txt


def checker_with(response: Any) -> tuple[RobotsChecker, list[str]]:
    checker = RobotsChecker(user_agent="TestBot")
    fetched: list[str] = []

    async def fake_download(url: str) -> tuple[int, str]:
        fetched.append(url)
        if isinstance(response, BaseException):
            raise response
        return response

    checker._download = fake_download  # type: ignore[method-assign]
    return checker, fetched


async def test_robots_rules_are_applied_and_cached() -> None:
    body = "User-agent: *\nDisallow: /private\nCrawl-delay: 3\n"
    checker, fetched = checker_with((200, body))
    assert await checker.can_fetch("https://shop.test/products")
    assert not await checker.can_fetch("https://shop.test/private/x")
    assert await checker.get_crawl_delay("https://shop.test/") == 3.0
    assert fetched == ["https://shop.test/robots.txt"]  # cached per origin


async def test_robots_cache_expires() -> None:
    checker, fetched = checker_with((200, ""))
    checker.cache_ttl = 0
    await checker.can_fetch("https://a.test/")
    await checker.can_fetch("https://a.test/")
    assert len(fetched) == 2


@pytest.mark.parametrize(
    ("response", "allowed"),
    [
        ((404, ""), True),  # RFC 9309: unavailable -> allow
        ((403, ""), True),
        ((503, ""), False),  # RFC 9309: unreachable -> disallow
        (aiohttp.ClientConnectionError("refused"), False),
        (asyncio.TimeoutError(), False),
    ],
)
async def test_robots_fetch_failures_follow_rfc9309(response: Any, allowed: bool) -> None:
    checker, _ = checker_with(response)
    assert await checker.can_fetch("https://site.test/page") is allowed


async def test_robots_non_http_and_disabled() -> None:
    checker, fetched = checker_with((503, ""))
    assert await checker.can_fetch("about:blank")
    assert await checker.can_fetch("data:text/html,<p>hi</p>")
    assert await checker.get_crawl_delay("file:///tmp/x.html") is None
    assert fetched == []

    off = RobotsChecker(respect_robots=False)
    assert await off.can_fetch("https://anything.test/")
    assert await off.get_crawl_delay("https://anything.test/") is None


async def test_robots_download_uses_aiohttp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise the real _download with a fake aiohttp session."""

    class FakeResp:
        status = 200

        async def text(self, errors: str = "strict") -> str:
            return "User-agent: *\nDisallow: /x\n"

        async def __aenter__(self) -> FakeResp:
            return self

        async def __aexit__(self, *a: object) -> None:
            return None

    class FakeSession:
        def __init__(self, timeout: Any) -> None:
            self.timeout = timeout

        def get(self, url: str, headers: dict[str, str]) -> FakeResp:
            assert headers == {"User-Agent": "ScrapeFlow"}
            return FakeResp()

        async def __aenter__(self) -> FakeSession:
            return self

        async def __aexit__(self, *a: object) -> None:
            return None

    monkeypatch.setattr("scrapeflow.robots.aiohttp.ClientSession", FakeSession)
    checker = RobotsChecker()
    assert await checker._download("https://x.test/robots.txt") == (
        200,
        "User-agent: *\nDisallow: /x\n",
    )
    assert not await checker.can_fetch("https://x.test/x/1")


# --------------------------------------------------------------------------- monitoring


def test_metrics_and_success_rate() -> None:
    m = ScrapeMetrics()
    assert m.get_success_rate() == 0.0
    m.record_success(1.0)
    m.record_failure(3.0, ValueError("x"))
    m.record_failure(1.0, None)
    m.record_retry()
    d = m.to_dict()
    assert d["total_requests"] == 3
    assert d["success_rate"] == pytest.approx(100 / 3)
    assert d["average_response_time"] == pytest.approx(5 / 3)
    assert d["errors_by_type"] == {"ValueError": 1, "Unknown": 1}
    assert d["retry_count"] == 1


def test_monitor_alerts_and_rollback() -> None:
    alerts: list[str] = []
    rollbacks: list[int] = []
    mon = PerformanceMonitor(
        alert_on_failure_rate=50,
        alert_on_consecutive_failures=3,
        alert_callback=lambda metrics, reason: alerts.append(reason),
        rollback_callback=lambda metrics: rollbacks.append(metrics.failed_requests) or True,
    )
    for _ in range(2):
        mon.end_request(mon.start_request(), success=True)
    for _ in range(3):
        mon.end_request(mon.start_request(), success=False, error=RuntimeError())
    assert any("3 consecutive failures" in a for a in alerts)
    assert any("below threshold" in a for a in alerts)
    assert rollbacks == [3]
    mon.record_retry()
    assert mon.get_metrics().retry_count == 1
    assert mon.get_metrics().end_time is not None
    mon.reset()
    assert mon.get_metrics().total_requests == 0


def test_logger_replaces_and_closes_handlers(tmp_path: Path) -> None:
    log_file = tmp_path / "sf.log"
    first = Logger(name="scrapeflow.test", level="DEBUG", log_file=str(log_file))
    file_handler = next(h for h in first.logger.handlers if isinstance(h, logging.FileHandler))
    first.debug("d")
    first.info("i")
    first.warning("w")
    first.error("e")
    try:
        raise ValueError("boom")
    except ValueError:
        first.exception("x")
    second = Logger(name="scrapeflow.test", level="INFO")
    assert file_handler not in second.logger.handlers
    assert file_handler.stream is None  # closed, so no leaked file descriptor
    assert "boom" in log_file.read_text()
    second.logger.handlers.clear()


# --------------------------------------------------------------------------- engine + workflows


def make_engine(**kw: Any) -> ScrapeFlow:
    return ScrapeFlow(
        ScrapeFlowConfig(retry=RetryConfig(max_retries=2, initial_delay=0, jitter=False)),
        runtime=kw.pop("runtime", FakeRuntime()),
        rate_limiter=FakeRateLimiter(),
        logger=FakeLogger(),
        monitor=kw.pop("monitor", FakeMonitor()),
        robots_checker=FakeRobotsChecker(allowed=True),
        **kw,
    )


async def test_workflow_conditions_callbacks_and_required() -> None:
    events: list[str] = []

    async def ok(page: Any, context: dict[str, Any], label: str = "") -> str:
        return label

    def sync_ok(page: Any, context: dict[str, Any]) -> int:
        return 42

    async def broken(page: Any, context: dict[str, Any]) -> None:
        raise ValueError("bad data")

    def bad_condition(ctx: dict[str, Any]) -> bool:
        raise KeyError("missing")

    async def on_error(err: Exception, ctx: dict[str, Any]) -> None:
        events.append(f"error:{err}")

    def failing_callback(result: Any, ctx: dict[str, Any]) -> None:
        raise RuntimeError("callback bug")  # must be swallowed

    wf = (
        Workflow("demo")
        .add_step("a", ok, label="A", on_success=lambda r, c: events.append(f"ok:{r}"))
        .add_step("b", sync_ok, on_success=failing_callback)
        .add_step("c", broken, required=False, on_error=on_error)
        .add_step("d", ok, condition=bad_condition)
        .add_step("e", ok, condition=lambda ctx: "scraper" in ctx, label="E")
    )
    wf.set_context("user", "u")
    assert wf.get_context("user") == "u"
    assert wf.get_context("nope", 1) == 1

    engine = make_engine()
    result = await engine.run_workflow(wf)
    assert result.steps_completed == ["a", "b", "e"]
    assert result.steps_failed == ["c"]
    assert not result.success
    assert result.final_data == "E"
    assert events == ["ok:A", "error:bad data"]

    stop = Workflow("stop").add_step("x", broken).add_step("y", ok)
    res = await stop.execute(engine)
    assert res.steps_completed == []
    assert isinstance(res.error, ValueError)


async def test_retryable_step_is_retried_on_transient_errors() -> None:
    monitor = FakeMonitor()
    retries = {"n": 0}
    monitor.record_retry = lambda: retries.__setitem__("n", retries["n"] + 1)  # type: ignore[method-assign]
    engine = make_engine(monitor=monitor)
    calls = {"n": 0}

    async def flaky(page: Any, context: dict[str, Any]) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("reset")
        return "done"

    result = await engine.run_workflow(Workflow().add_step("flaky", flaky))
    assert result.success and result.final_data == "done"
    assert calls["n"] == 2
    assert retries["n"] == 1

    calls["n"] = 0
    no_retry = await engine.run_workflow(Workflow().add_step("flaky", flaky, retryable=False))
    assert not no_retry.success and calls["n"] == 1

    async def value_error(page: Any, context: dict[str, Any]) -> None:
        calls["n"] += 1
        raise ValueError("not transient")

    calls["n"] = 0
    await engine.run_workflow(Workflow().add_step("v", value_error))
    assert calls["n"] == 1  # non-transient errors are not retried


async def test_step_timeout_raises_scrapeflow_timeout() -> None:
    async def slow(page: Any, context: dict[str, Any]) -> None:
        await asyncio.sleep(1)

    engine = make_engine()
    step = Workflow().add_step("slow", slow, timeout=0.01, retryable=False).steps[0]
    with pytest.raises(ScrapeFlowTimeoutError, match="timed out"):
        await engine.execute_step(step, {})

    retried = Workflow().add_step("slow", slow, timeout=0.01).steps[0]
    with pytest.raises(ScrapeFlowRetryError) as info:
        await engine.execute_step(retried, {})
    assert isinstance(info.value.__cause__, ScrapeFlowTimeoutError)


async def test_engine_lifecycle_and_navigate_failure() -> None:
    runtime = FakeRuntime()
    monitor = FakeMonitor()
    engine = make_engine(runtime=runtime, monitor=monitor)
    async with engine as sf:
        assert runtime.started
        await sf.start()  # idempotent
        await sf.navigate("https://x.test/", timeout=0)
        assert runtime.last_goto == ("https://x.test/", "load", 0)  # 0 is not replaced

        async def broken_goto(url: str, wait_until: str, timeout: int) -> None:
            raise ConnectionError("dns")

        runtime.goto = broken_goto  # type: ignore[method-assign]
        with pytest.raises(ScrapeFlowRetryError):
            await sf.navigate("https://x.test/fail")
        assert monitor.failure == 1
        assert sf.get_metrics() == {"success": 1, "failure": 1}
        sf.reset_metrics()
        with pytest.raises(ScrapeFlowNotStartedError, match="save_storage_state"):
            await sf.save_storage_state("x.json")
    assert runtime.closed
    await engine.close()  # idempotent


def test_exception_hierarchy_is_backward_compatible() -> None:
    assert issubclass(ScrapeFlowNotStartedError, ScrapeFlowError)
    assert issubclass(ScrapeFlowNotStartedError, RuntimeError)
    assert issubclass(ScrapeFlowConfigurationError, ValueError)


# --------------------------------------------------------------------------- browser runtime


async def test_runtime_failed_launch_tears_down(monkeypatch: pytest.MonkeyPatch) -> None:
    stopped: list[str] = []

    class FakeLauncher:
        async def launch(self, **kwargs: Any) -> None:
            raise RuntimeError("no browser binary")

    class FakePlaywright:
        chromium = firefox = webkit = FakeLauncher()

        async def stop(self) -> None:
            stopped.append("stopped")

    class Starter:
        async def start(self) -> FakePlaywright:
            return FakePlaywright()

    monkeypatch.setattr("scrapeflow.browser_runtime.async_playwright", lambda: Starter())
    config = ScrapeFlowConfig()
    runtime = PlaywrightBrowserRuntime(config, AntiDetectionManager(config.anti_detection))
    with pytest.raises(RuntimeError, match="no browser binary"):
        await runtime.start()
    assert stopped == ["stopped"]
    assert runtime.playwright is None
    with pytest.raises(ScrapeFlowNotStartedError):
        await runtime.goto("https://x.test", "load", 1000)
    with pytest.raises(ScrapeFlowNotStartedError):
        await runtime.save_storage_state("x.json")
    await runtime.close()  # no-op when not running


# --------------------------------------------------------------------------- anti-detection


async def test_anti_detection_components() -> None:
    ua = UserAgentRotator()
    assert ua.get(0) == UserAgentRotator.DEFAULT_USER_AGENTS[0]
    assert ua.get(len(ua.user_agents)) == ua.user_agents[0]
    assert ua.get() in ua.user_agents
    ua.user_agents.append("custom")
    assert "custom" not in UserAgentRotator.DEFAULT_USER_AGENTS  # no shared mutable state

    proxies = ProxyRotator([{"server": "a"}, {"server": "b"}])
    assert [proxies.get_next()["server"] for _ in range(3)] == ["a", "b", "a"]  # type: ignore[index]
    assert proxies.get_random() in proxies.proxies
    assert ProxyRotator([]).get_next() is None
    assert ProxyRotator([]).get_random() is None

    mgr = AntiDetectionManager(
        AntiDetectionConfig(
            user_agents=["UA"], rotate_proxies=True, proxies=[{"server": "p"}], stealth_mode=True
        )
    )
    assert mgr.get_user_agent() == "UA"
    assert mgr.get_proxy() == {"server": "p"}
    off = AntiDetectionManager(AntiDetectionConfig(rotate_user_agents=False, stealth_mode=False))
    assert off.get_user_agent() is None
    assert off.get_proxy() is None

    scripts: list[str] = []

    class FakePage:
        async def add_init_script(self, script: str) -> None:
            scripts.append(script)

    await mgr.apply_stealth(FakePage())
    assert len(scripts) == 5 and "webdriver" in scripts[0]
    scripts.clear()
    await off.apply_stealth(FakePage())
    assert scripts == []
    await StealthMode.apply_stealth(FakePage())
    assert len(scripts) == 5


# --------------------------------------------------------------------------- registry


def test_registry_components() -> None:
    reg = (
        SelectorRegistry()
        .register_selector("price", ".price", description="Price", version="2.0")
        .register_schema("custom", {"a": "b"})
    )
    assert reg.get_selector("price").version == "2.0"  # type: ignore[union-attr]
    assert reg.get_selector("missing") is None
    assert reg.list_selectors() == ["price"]
    register_product_price_schema(reg)
    register_job_listing_schema(reg)
    assert reg.list_schemas() == ["custom", "product_price", "job_listing"]
    assert reg.get_schema("product_price")["products"].items_selector.startswith("article")  # type: ignore[index]
    reg.register_login("l", "#u", "#p", "#s")
    assert reg.get_login("l").success_selector is None  # type: ignore[union-attr]
    assert reg.get_pagination("none") is None
    assert get_registry() is get_registry()

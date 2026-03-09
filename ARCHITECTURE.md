# ScrapeFlow Architecture

This document describes the architecture layout and design principles used in ScrapeFlow.

## Design Principles

- **Dependency inversion**: `ScrapeFlow` depends on protocol ports, not concrete infra.
- **Separation of concerns**:
  - orchestration in `engine.py`
  - browser infrastructure in `browser_runtime.py`
  - workflow execution in `workflow_executor.py`
  - data extraction/spec modeling in `specifications.py`
  - reusable component registry in `registry.py`
- **Backwards compatibility**: public API remains stable while internals are refactored.
- **Testability first**: orchestration paths can be tested with injected fakes.

## Module Layout

- `scrapeflow/engine.py`  
  Application facade and orchestration entrypoint.

- `scrapeflow/ports.py`  
  Protocol-based architecture seams for DI and testing.

- `scrapeflow/browser_runtime.py`  
  Playwright runtime adapter (browser lifecycle + navigation).

- `scrapeflow/workflow.py`  
  Workflow entity model (`Workflow`, `Step`, `WorkflowResult`).

- `scrapeflow/workflow_executor.py`  
  Workflow execution service.

- `scrapeflow/registry.py`  
  Shared selectors/login/pagination registry.

- `scrapeflow/schema_library.py`  
  Built-in reusable extraction schemas.

## Dependency Direction

- Core orchestration (`engine.py`, `workflow_executor.py`) -> **ports**
- Infrastructure adapters (`browser_runtime.py`, `rate_limiter.py`, `retry.py`, `robots.py`) -> concrete implementations
- Public API (`__init__.py`) exposes stable facade and components

This enables replacing infrastructure implementations with mocks/fakes during tests and future adapters (MCP, remote browser, etc.).

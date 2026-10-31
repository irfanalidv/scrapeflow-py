"""Workflow engine for defining and executing scraping workflows."""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StepStatus(str, Enum):
    """Status of a workflow step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Step:
    """A single step in a workflow."""

    name: str
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict)
    retryable: bool = True
    required: bool = True
    on_success: Callable | None = None
    on_error: Callable | None = None
    condition: Callable | None = None
    timeout: float | None = None

    def should_execute(self, context: dict[str, Any]) -> bool:
        """Check if step should be executed based on condition."""
        if self.condition is None:
            return True
        try:
            return bool(self.condition(context))
        except Exception:
            return False


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""

    success: bool
    steps_completed: list[str]
    steps_failed: list[str]
    final_data: Any = None
    context: dict[str, Any] = field(default_factory=dict)
    error: Exception | None = None


class Workflow:
    """Defines and executes a scraping workflow."""

    def __init__(self, name: str = "default"):
        self.name = name
        self.steps: list[Step] = []
        self.context: dict[str, Any] = {}

    def add_step(
        self,
        name: str,
        func: Callable,
        *args,
        retryable: bool = True,
        required: bool = True,
        on_success: Callable | None = None,
        on_error: Callable | None = None,
        condition: Callable | None = None,
        timeout: float | None = None,
        **kwargs,
    ) -> "Workflow":
        """Add a step to the workflow."""
        step = Step(
            name=name,
            func=func,
            args=args,
            kwargs=kwargs,
            retryable=retryable,
            required=required,
            on_success=on_success,
            on_error=on_error,
            condition=condition,
            timeout=timeout,
        )
        self.steps.append(step)
        return self

    def set_context(self, key: str, value: Any):
        """Set a value in the workflow context."""
        self.context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get a value from the workflow context."""
        return self.context.get(key, default)

    async def execute(self, engine) -> WorkflowResult:
        """Execute workflow through the dedicated executor service."""
        from scrapeflow.workflow_executor import WorkflowExecutor

        executor = WorkflowExecutor()
        return await executor.execute(self, engine)

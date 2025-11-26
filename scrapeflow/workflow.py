"""Workflow engine for defining and executing scraping workflows."""

from typing import Callable, Any, Optional, Dict, List
from dataclasses import dataclass, field
from enum import Enum


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
    kwargs: Dict[str, Any] = field(default_factory=dict)
    retryable: bool = True
    required: bool = True
    on_success: Optional[Callable] = None
    on_error: Optional[Callable] = None
    condition: Optional[Callable] = None
    timeout: Optional[float] = None

    def should_execute(self, context: Dict[str, Any]) -> bool:
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
    steps_completed: List[str]
    steps_failed: List[str]
    final_data: Any = None
    context: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Exception] = None


class Workflow:
    """Defines and executes a scraping workflow."""

    def __init__(self, name: str = "default"):
        self.name = name
        self.steps: List[Step] = []
        self.context: Dict[str, Any] = {}

    def add_step(
        self,
        name: str,
        func: Callable,
        *args,
        retryable: bool = True,
        required: bool = True,
        on_success: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        condition: Optional[Callable] = None,
        timeout: Optional[float] = None,
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
        """Execute the workflow using the provided engine."""
        steps_completed = []
        steps_failed = []
        final_data = None
        
        # Add engine (scraper) to context for step functions
        self.context["scraper"] = engine

        for step in self.steps:
            if not step.should_execute(self.context):
                continue

            try:
                # Execute step through engine
                result = await engine.execute_step(step, self.context)
                final_data = result
                steps_completed.append(step.name)

                # Call on_success callback if provided
                if step.on_success:
                    await engine._safe_call(step.on_success, result, self.context)

            except Exception as e:
                steps_failed.append(step.name)

                # Call on_error callback if provided
                if step.on_error:
                    try:
                        await engine._safe_call(step.on_error, e, self.context)
                    except Exception:
                        pass

                # If step is required, stop workflow
                if step.required:
                    return WorkflowResult(
                        success=False,
                        steps_completed=steps_completed,
                        steps_failed=steps_failed,
                        context=self.context,
                        error=e,
                    )

        return WorkflowResult(
            success=len(steps_failed) == 0,
            steps_completed=steps_completed,
            steps_failed=steps_failed,
            final_data=final_data,
            context=self.context,
        )


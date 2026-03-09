"""Workflow execution service."""

from typing import Any

from scrapeflow.workflow import WorkflowResult


class WorkflowExecutor:
    """Application service for executing workflows."""

    async def execute(self, workflow: Any, engine: Any) -> WorkflowResult:
        steps_completed = []
        steps_failed = []
        final_data = None

        workflow.context["scraper"] = engine

        for step in workflow.steps:
            if not step.should_execute(workflow.context):
                continue

            try:
                result = await engine.execute_step(step, workflow.context)
                final_data = result
                steps_completed.append(step.name)

                if step.on_success:
                    await engine._safe_call(step.on_success, result, workflow.context)

            except Exception as e:
                steps_failed.append(step.name)
                if step.on_error:
                    await engine._safe_call(step.on_error, e, workflow.context)
                if step.required:
                    return WorkflowResult(
                        success=False,
                        steps_completed=steps_completed,
                        steps_failed=steps_failed,
                        context=workflow.context,
                        error=e,
                    )

        return WorkflowResult(
            success=len(steps_failed) == 0,
            steps_completed=steps_completed,
            steps_failed=steps_failed,
            final_data=final_data,
            context=workflow.context,
        )

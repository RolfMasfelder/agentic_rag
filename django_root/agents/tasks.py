"""Celery tasks for async agent execution."""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="agents.tasks.run_agent_task")
def run_agent_task(self, task_id: str, query: str, max_iterations: int = 5) -> None:
    """Execute an agent query asynchronously and persist the result.

    The *task_id* must be the UUID (as string) of an existing
    ``apps.agent.models.AgentTask`` row in *pending* status.
    """
    from agents.orchestrator import run_agent
    from apps.agent.models import AgentTask

    try:
        task = AgentTask.objects.get(pk=task_id)
    except AgentTask.DoesNotExist:
        logger.error("AgentTask %s not found.", task_id)
        return

    task.status = AgentTask.Status.RUNNING
    task.save(update_fields=["status", "updated_at"])

    try:
        raw = run_agent(query, max_iterations=max_iterations)
        # conversation list is not JSON-safe as-is when it contains non-text;
        # store only the summary fields.
        task.result = {
            "answer": raw["answer"],
            "plan": raw.get("plan", ""),
            "iterations": raw["iterations"],
        }
        task.status = AgentTask.Status.DONE
        task.save(update_fields=["status", "result", "updated_at"])
    except Exception as exc:  # noqa: BLE001
        logger.exception("AgentTask %s failed.", task_id)
        task.error = str(exc)
        task.status = AgentTask.Status.FAILED
        task.save(update_fields=["status", "error", "updated_at"])
        raise  # re-raise so Celery marks the task as FAILURE

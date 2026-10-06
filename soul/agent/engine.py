from __future__ import annotations

import asyncio

from soul.agent.task import AgentTask, TaskStatus
from soul.core.state import State


class TaskEngine:
    """Tracks one turn; Gemini remains responsible for dynamic tool selection."""

    def __init__(self, client, executor=None, vision=None, events=None, state=None):
        self.client, self.executor, self.vision = client, executor, vision
        self.events = events
        self.state = state or getattr(executor, "state", None)
        self.current_task: AgentTask | None = None
        self.last_task: AgentTask | None = None
        self._running: asyncio.Task | None = None

    def publish(self, name: str, task: AgentTask, payload=None):
        events = self.events or getattr(getattr(self.executor, "state", None), "events", None)
        if events:
            events.publish(name, payload or {}, task_id=task.task_id)

    def _outcome_state(self, status):
        if self.state and self.state.current != State.SHUTTING_DOWN:
            self.state.set({TaskStatus.COMPLETED: State.SUCCESS, TaskStatus.INTERRUPTED: State.INTERRUPTED,
                            TaskStatus.FAILED: State.ERROR, TaskStatus.PARTIAL: State.IDLE}[status])

    def cancel(self, reason="User interrupted the task"):
        task = self.current_task
        if task:
            task.cancelled = True
            task.interruption_reason = reason
        if self.executor:
            self.executor.stop(reason)
        if self._running and not self._running.done():
            self._running.cancel()

    async def run(self, goal, messages, system, on_chunk, metrics):
        if self.current_task:
            raise RuntimeError("A task is already running")
        task = self.current_task = AgentTask(goal)
        metrics.task_id = task.task_id
        self._running = asyncio.current_task()
        if self.executor:
            self.executor.task = task
        self.publish("TaskStarted", task, {"goal": goal})
        try:
            if self.executor:
                response = await self.client.tool_conversation(messages, system, on_chunk, metrics, self.executor)
            else:
                response = await self.client.respond(messages, system, on_chunk, metrics)
            task.finish(response)
            self._outcome_state(task.status)
            event = "TaskInterrupted" if task.status == TaskStatus.INTERRUPTED else "TaskCompleted"
            self.publish(event, task, {"status": task.status.value,
                         "verification_status": task.verification_status, "receipt_count": len(task.tool_receipts)})
            return response
        except asyncio.CancelledError:
            task.cancelled = True
            task.status = TaskStatus.INTERRUPTED
            task.interruption_reason = task.interruption_reason or "Task cancelled"
            self._outcome_state(task.status)
            self.publish("TaskInterrupted", task, {"reason": task.interruption_reason, "receipt_count": len(task.tool_receipts)})
            raise
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.interruption_reason = type(exc).__name__
            self._outcome_state(task.status)
            self.publish("TaskFailed", task, {"error": type(exc).__name__, "receipt_count": len(task.tool_receipts)})
            raise
        finally:
            # Visual state is ephemeral and cannot remain actionable after the task.
            if self.vision:
                task.visual_context = {key: value for key, value in self.vision.recent_context.items()
                                       if key not in {"image", "png", "target", "target_id"}}
                self.vision.clear()
            self.last_task, self.current_task, self._running = task, None, None
            if self.executor:
                self.executor.task = None

"""Bounded task coordination around SOUL's existing Gemini tool loop."""

from soul.agent.task import AgentTask, TaskStatus
from soul.agent.engine import TaskEngine

__all__ = ["AgentTask", "TaskStatus", "TaskEngine"]

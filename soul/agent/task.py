from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from soul.tools.models import ToolResult


class TaskStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass
class AgentTask:
    current_goal: str
    task_id: str = field(default_factory=lambda: uuid4().hex)
    status: TaskStatus = TaskStatus.RUNNING
    completed_steps: list[str] = field(default_factory=list)
    pending_step: str | None = None
    tool_receipts: list[dict[str, Any]] = field(default_factory=list)
    visual_context: dict[str, Any] = field(default_factory=dict)
    failure_count: int = 0
    requires_confirmation: bool = False
    verification_status: str = "not_required"
    retries: dict[str, int] = field(default_factory=dict)
    cancelled: bool = False
    interruption_reason: str | None = None
    final_response: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def user_goal(self) -> str:
        return self.current_goal

    @property
    def current_state(self) -> str:
        return self.status.value

    @property
    def active_application(self):
        return self.visual_context.get("application") or self.visual_context.get("active_window")

    def add_receipt(self, result: ToolResult) -> None:
        receipt = result.payload()
        self.tool_receipts.append(receipt)
        outcome_unverified = result.desired_result_verified is False and (
            result.action_dispatched or result.data.get("verified_execution_id"))
        if not result.success or outcome_unverified:
            self.failure_count += 1
        if result.success and not outcome_unverified and (not result.action_dispatched or result.desired_result_verified is True):
            if result.tool_name != "finalize_task":
                self.completed_steps.append(result.summary)
            # A successful fresh localization/read can resolve a pre-dispatch failure.
            # An uncertain physical action always needs an explicit verification receipt.
            for earlier in self.tool_receipts[:-1]:
                if (earlier.get("tool_name") == result.tool_name and not earlier.get("success")
                        and not earlier.get("action_dispatched")
                        and not earlier.get("data", {}).get("side_effects_unknown")):
                    earlier["recovered_by_execution_id"] = result.execution_id
        # Verification is associated with a specific execution, never inferred from a screenshot.
        verified_id = result.data.get("verified_execution_id")
        if result.success and result.desired_result_verified is True and verified_id:
            for earlier in self.tool_receipts[:-1]:
                if earlier.get("execution_id") == verified_id:
                    earlier["desired_result_verified"] = True
                    earlier["observation_required"] = False
                    earlier["recovered_by_execution_id"] = result.execution_id
                    self.completed_steps.append(earlier["summary"])
                    break
        self.pending_step = None
        self.requires_confirmation = False
        self.update_verification()

    def update_verification(self) -> None:
        actions = [receipt for receipt in self.tool_receipts if receipt.get("action_dispatched")]
        uncertain = any(receipt.get("data", {}).get("side_effects_unknown") and not receipt.get("recovered_by_execution_id")
                        for receipt in self.tool_receipts)
        if uncertain:
            self.verification_status = "unverified"
        elif not actions:
            self.verification_status = "not_required"
        elif all(receipt.get("desired_result_verified") is True for receipt in actions):
            self.verification_status = "verified"
        elif any(receipt.get("desired_result_verified") is False for receipt in actions):
            self.verification_status = "unverified"
        else:
            self.verification_status = "pending"

    def finish(self, response: str) -> None:
        self.final_response = response
        self.pending_step = None
        if self.cancelled:
            self.status = TaskStatus.INTERRUPTED
        elif (any(not receipt.get("success") and not receipt.get("recovered_by_execution_id")
                  for receipt in self.tool_receipts) or self.verification_status in {"pending", "unverified"}):
            self.status = TaskStatus.PARTIAL
        else:
            self.status = TaskStatus.COMPLETED

    def context(self) -> dict[str, Any]:
        """Small execution context; images and sensitive input arguments never enter it."""
        receipts = [{key: receipt.get(key) for key in (
            "tool_name", "execution_id", "success", "summary", "error_code",
            "action_dispatched", "desired_result_verified", "observation_required"
        )} for receipt in self.tool_receipts[-8:]]
        return {
            "task_id": self.task_id, "current_goal": self.current_goal,
            "status": self.status.value, "completed_steps": self.completed_steps[-8:],
            "pending_step": self.pending_step, "failure_count": self.failure_count,
            "requires_confirmation": self.requires_confirmation,
            "verification_status": self.verification_status, "latest_receipts": receipts,
            "active_application": self.active_application,
            "visual_context": self.visual_context,
        }

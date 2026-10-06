from __future__ import annotations

from soul.tools.models import ToolResult


class RecoveryPolicy:
    """Advise the model, without blindly replaying actions with possible side effects."""

    HALT = {"EMERGENCY_STOP", "USER_TAKEOVER", "USER_DECLINED", "TOOL_TIMEOUT", "WORKER_FAILED", "ACTION_LIMIT",
            "TOOLS_DISABLED", "VISION_DISABLED", "AUTOMATION_DISABLED", "RESTRICTED", "RESTRICTED_WINDOW",
            "RESTRICTED_FILE_TYPE", "SENSITIVE_INPUT", "CLOSE_PENDING"}
    STRATEGIES = {
        "TARGET_NOT_FOUND": "Observe again and locate using a broader description; do not guess coordinates.",
        "TARGET_UNCERTAIN": "Observe or use accessible metadata. Ask for clarification if ambiguity remains.",
        "TARGET_AMBIGUOUS": "Use a more specific target description or ask the user to choose.",
        "SCREEN_CHANGED": "Capture the current screen and locate a new single-use target before acting.",
        "STALE_TARGET": "Locate a fresh target. Never reuse an expired or consumed target ID.",
        "APPLICATION_NOT_FOUND": "Inspect installed/running application identities or ask for the exact application.",
        "WINDOW_NOT_READY": "Inspect running applications and observe the window before proceeding.",
        "FOCUS_LOST": "Inspect the foreground window, then refocus the requested application and re-observe.",
        "WINDOW_CHANGED": "Observe the new foreground window and ground a fresh target before acting.",
        "APP_NOT_RUNNING": "Inspect running applications; open the user-requested application before focusing it.",
        "AMBIGUOUS_WINDOW": "Ask the user to select the desired application window before proceeding.",
        "LAUNCH_UNVERIFIED": "Launch was already requested. Inspect running applications and observe; do not blindly launch again.",
        "INPUT_TARGET_UNCERTAIN": "Locate an unambiguous editable field before typing; do not guess keyboard focus.",
        "INPUT_FOCUS_UNSAFE": "Observe and ground a safe editable field. Protected fields must be handled by the user.",
        "ACTION_NOT_VERIFIED": "Observe the resulting state before considering another action. Never blindly replay the action.",
        "CONFIRMATION_REQUIRED": "Request explicit confirmation for the stated consequence before proceeding.",
    }

    def __init__(self, max_retries: int = 2):
        self.max_retries = max(0, min(int(max_retries), 5))
        self.counts: dict[str, int] = {}

    def reset(self):
        self.counts.clear()

    def advise(self, result: ToolResult) -> dict | None:
        code = result.error_code
        if (not code and result.desired_result_verified is False
                and (result.action_dispatched or result.data.get("verified_execution_id"))):
            code = "ACTION_NOT_VERIFIED"
        if code in self.HALT:
            return {"failure_class": code, "retry_allowed": False, "stop": True,
                    "instruction": "Stop automation. Report actual receipts and any uncertain side effects."}
        if code not in self.STRATEGIES:
            return None
        self.counts[code] = self.counts.get(code, 0) + 1
        allowed = self.counts[code] <= self.max_retries
        return {"failure_class": code, "retry_allowed": allowed, "stop": not allowed,
                "remaining_retries": max(0, self.max_retries - self.counts[code] + 1),
                "instruction": self.STRATEGIES[code] if allowed else "Recovery budget exhausted. Report the unresolved step; stop automation."}

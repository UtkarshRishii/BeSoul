from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from pydantic import ValidationError

from soul.agent.recovery import RecoveryPolicy
from soul.core.state import State
from soul.tools.models import NoArguments, Risk, Tool, ToolError, ToolResult


class ToolExecutor:
    def __init__(self, registry, state, confirm: Callable[[str], Awaitable[bool]],
                 renderer=None, max_calls=24, max_failures=3, desktop=None):
        self.registry, self.state, self.confirm = registry, state, confirm
        if "finalize_task" not in registry.tools:
            registry.register(Tool(
                "finalize_task", "After using tools, call this tool ALONE when ready to report the results. "
                "For ordinary conversation that needs no tools, answer directly instead. "
                "It requests a final streamed report from current receipts; it does not prove success or authorize more actions.",
                NoArguments, Risk.READ_ONLY, self._finalize_task,
            ))
        self.renderer, self.desktop = renderer, desktop
        self.max_calls, self.max_failures = max_calls, max_failures
        self.settings = getattr(desktop, "settings", None)
        settings = self.settings
        self.max_parallel_reads = max(1, min(getattr(settings, "soul_max_parallel_reads", 4), 8))
        self.recovery = RecoveryPolicy(getattr(settings, "soul_max_retries", 2))
        self.task = None
        self._active: set[asyncio.Task] = set()
        self.reset()

    def reset(self):
        if self.settings:
            self.max_parallel_reads = max(1, min(getattr(self.settings, "soul_max_parallel_reads", 4), 8))
            self.recovery.max_retries = max(0, min(getattr(self.settings, "soul_max_retries", 2), 5))
        self.calls = self.failures = 0
        self.stopped = False
        self.request_final_report = False
        self.stop_reason = None
        self.records: list[dict] = []
        self.recovery.reset()
        if self.desktop:
            self.desktop.reset_turn()

    def stop(self, reason="Automation interrupted"):
        self.stopped, self.stop_reason = True, reason
        try:
            current = asyncio.current_task()
        except RuntimeError:
            current = None
        for running in tuple(self._active):
            if running is not current and not running.done():
                running.cancel()
        if self.desktop:
            self.desktop.clear()

    async def _finalize_task(self, args):
        self.request_final_report = True
        return ToolResult(success=True, message="Final report requested. Describe only actual receipts and distinguish verified results from dispatched or uncertain actions.")

    def _publish(self, name, payload):
        events = getattr(self.state, "events", None)
        if events:
            events.publish(name, payload, task_id=getattr(self.task, "task_id", None))

    def _record(self, name, result, started, execution_id, tool, handler_started):
        elapsed = time.perf_counter() - started
        result.tool_name, result.execution_id = name, execution_id
        result.duration_ms, result.summary = round(elapsed * 1000, 2), result.message
        # Legacy worker metadata is authoritative when explicitly supplied.
        for key in ("action_dispatched", "desired_result_verified", "observation_required"):
            if key in result.data:
                setattr(result, key, result.data[key])
        if tool and tool.risk != Risk.READ_ONLY:
            if handler_started and result.error_code in {"LAUNCH_UNVERIFIED", "CLOSE_PENDING"}:
                result.action_dispatched = True
                result.desired_result_verified = False
            if result.success and "action_dispatched" not in result.data and "action_dispatched" not in result.model_fields_set:
                result.action_dispatched = True
            if result.action_dispatched and result.desired_result_verified is not True:
                result.observation_required = True
            if handler_started and result.error_code in {"TOOL_TIMEOUT", "WORKER_FAILED", "CANCELLED", "TOOL_ERROR", "OS_ERROR", "INVALID_RECEIPT"}:
                result.data["side_effects_unknown"] = True
                result.observation_required = True
        if not result.success and not result.error_message:
            result.error_message = result.message
        advice = self.recovery.advise(result)
        if advice:
            result.data["recovery"] = advice
            if self.task:
                self.task.retries = dict(self.recovery.counts)
            if advice["stop"]:
                self.stopped, self.stop_reason = True, result.error_code or "RECOVERY_LIMIT"
                if result.error_code in {"EMERGENCY_STOP", "USER_TAKEOVER"} and self.task:
                    self.task.cancelled = True
                    self.task.interruption_reason = result.message
                if self.desktop:
                    self.desktop.clear()
                self._publish("RecoveryStopped", {"tool_name": name, **advice})
        if (not result.success or (result.desired_result_verified is False
                and (result.action_dispatched or result.data.get("verified_execution_id")))):
            self.failures += 1
        if self.failures >= self.max_failures:
            self.stopped, self.stop_reason = True, "FAILURE_LIMIT"
        self.records.append({
            "name": name, "success": result.success, "seconds": elapsed, "error_code": result.error_code,
            "message": result.message, "execution_id": execution_id, "summary": result.summary,
            "duration_ms": result.duration_ms, "action_dispatched": result.action_dispatched,
            "desired_result_verified": result.desired_result_verified,
            "observation_required": result.observation_required,
        })
        if self.task:
            if self.desktop:
                self.task.visual_context = {key: value for key, value in getattr(self.desktop, "recent_context", {}).items()
                                            if key not in {"image", "png", "target", "target_id"}}
            self.task.add_receipt(result)
        logging.getLogger("soul").info("tool_result name=%s success=%s code=%s duration=%.3f", name, result.success, result.error_code, elapsed)
        self._publish("ToolCompleted" if result.success else "ToolFailed", {
            key: getattr(result, key) for key in ("tool_name", "execution_id", "success", "summary", "error_code",
                                                "duration_ms", "action_dispatched", "desired_result_verified", "observation_required")
        })
        if self.renderer:
            self.renderer.tool_finished(name, result, elapsed)
        if getattr(self.state, "current", None) != State.SHUTTING_DOWN:
            interrupted = result.error_code in {"EMERGENCY_STOP", "USER_TAKEOVER", "CANCELLED"}
            self.state.set(State.INTERRUPTED if interrupted else State.THINKING)
        return result

    async def execute(self, name: str, arguments: dict, *, reject_batch=False) -> ToolResult:
        started, execution_id = time.perf_counter(), uuid4().hex
        tool, handler_started = self.registry.tools.get(name), False
        running = asyncio.current_task()
        self._active.add(running)
        self.calls += 1
        self.state.set(State.CALLING_TOOL)
        self._publish("ToolStarted", {"tool_name": name, "execution_id": execution_id})
        if self.task:
            self.task.pending_step = name
        if self.renderer:
            self.renderer.tool_started(name)
        try:
            settings = self.settings or getattr(self.desktop, "settings", None)
            if settings and not getattr(settings, "soul_tools_enabled", True):
                raise ToolError("TOOLS_DISABLED", "Desktop tools are disabled in preferences. Stop this workflow.")
            if self.stopped or self.calls > self.max_calls or (self.task and self.task.cancelled):
                raise ToolError("ACTION_LIMIT", "Action budget exhausted or automation interrupted. Stop this workflow.")
            if tool is None:
                raise ToolError("UNKNOWN_TOOL", "Requested tool is not registered.")
            if reject_batch:
                raise ToolError("INVALID_FINALIZATION", "finalize_task must be called alone. No tool in this batch was executed; split the workflow into separate requests.")
            args = tool.arguments.model_validate(arguments)
            if tool.risk == Risk.RESTRICTED:
                raise ToolError("RESTRICTED", "This capability is disabled.")
            if tool.risk == Risk.CONFIRMATION_REQUIRED:
                self.state.set(State.WAITING_FOR_TOOL)
                if self.task:
                    self.task.requires_confirmation = True
                # No raw input content is exposed through events or receipts.
                self._publish("ConfirmationRequested", {"tool_name": name, "execution_id": execution_id})
                if not await self.confirm(f"Allow {name}: {args.model_dump_json()}?"):
                    raise ToolError("USER_DECLINED", "User declined this action. Do not retry it.")
                if self.task:
                    self.task.requires_confirmation = False
                if self.stopped or (self.task and self.task.cancelled):
                    raise ToolError("ACTION_LIMIT", "Automation stopped while awaiting confirmation.")
                if settings and not getattr(settings, "soul_tools_enabled", True):
                    raise ToolError("TOOLS_DISABLED", "Desktop tools were disabled while awaiting confirmation.")
            self.state.set(State.EXECUTING_TOOL)
            handler_started = True
            async with asyncio.timeout(tool.timeout):
                result = await tool.handler(args)
            if not isinstance(result, ToolResult):
                raise ToolError("INVALID_RECEIPT", "Tool returned an invalid execution receipt.")
        except ValidationError:
            result = ToolResult.fail("INVALID_ARGUMENTS", "Arguments did not match the declared tool schema.")
        except ToolError as exc:
            result = ToolResult.fail(exc.code, str(exc), **exc.data)
        except TimeoutError:
            result = ToolResult.fail("TOOL_TIMEOUT", "Tool timed out and was cancelled. Side effects may have occurred; inspect before retrying.")
        except asyncio.CancelledError:
            self.stopped, self.stop_reason = True, "CANCELLED"
            self._record(name, ToolResult.fail("CANCELLED", "Tool interrupted. Any dispatched input must be inspected before continuing."),
                         started, execution_id, tool, handler_started)
            raise
        except Exception:
            logging.getLogger("soul").exception("tool_failed name=%s", name)
            result = ToolResult.fail("TOOL_ERROR", "Tool failed. See diagnostic log for details.")
        finally:
            self._active.discard(running)
        return self._record(name, result, started, execution_id, tool, handler_started)

    def _parallel_read(self, name):
        tool = self.registry.tools.get(name)
        return bool(tool and tool.risk == Risk.READ_ONLY and tool.parallel_safe)

    async def execute_many(self, calls: list[tuple[str, dict]]) -> list[ToolResult]:
        """Only contiguous, explicitly independent reads run together; all input stays ordered."""
        if len(calls) > 1 and any(name == "finalize_task" for name, _ in calls):
            return [await self.execute(name, args, reject_batch=True) for name, args in calls]
        results, position = [], 0
        while position < len(calls):
            if self._parallel_read(calls[position][0]):
                end = position
                while end < len(calls) and end - position < self.max_parallel_reads and self._parallel_read(calls[end][0]):
                    end += 1
                results.extend(await asyncio.gather(*(self.execute(name, args) for name, args in calls[position:end])))
                position = end
            else:
                name, args = calls[position]
                results.append(await self.execute(name, args))
                position += 1
        return results

from __future__ import annotations
import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from pydantic import ValidationError
from soul.core.state import State
from soul.tools.models import Risk, ToolError, ToolResult


class ToolExecutor:
    def __init__(self, registry, state, confirm: Callable[[str], Awaitable[bool]],
                 renderer=None, max_calls=24, max_failures=3, desktop=None):
        self.registry, self.state, self.confirm = registry, state, confirm
        self.renderer, self.desktop = renderer, desktop
        self.max_calls, self.max_failures = max_calls, max_failures
        self.reset()

    def reset(self):
        self.calls = self.failures = 0
        self.stopped = False
        self.records: list[dict] = []
        if self.desktop:
            self.desktop.reset_turn()

    async def execute(self, name: str, arguments: dict) -> ToolResult:
        start = time.perf_counter()
        tool = self.registry.tools.get(name)
        self.calls += 1
        self.state.set(State.CALLING_TOOL)
        if self.renderer:
            self.renderer.tool_started(name)
        try:
            if self.stopped or self.calls > self.max_calls:
                raise ToolError("ACTION_LIMIT", "Action budget exhausted or emergency stop active. Stop this workflow.")
            if tool is None:
                raise ToolError("UNKNOWN_TOOL", "Requested tool is not registered.")
            args = tool.arguments.model_validate(arguments)
            if tool.risk == Risk.RESTRICTED:
                raise ToolError("RESTRICTED", "This capability is disabled.")
            if tool.risk == Risk.CONFIRMATION_REQUIRED:
                self.state.set(State.WAITING_FOR_TOOL)
                if not await self.confirm(f"Allow {name}: {args.model_dump_json()}?"):
                    raise ToolError("USER_DECLINED", "User declined this action. Do not retry it.")
            self.state.set(State.EXECUTING_TOOL)
            async with asyncio.timeout(tool.timeout):
                result = await tool.handler(args)
        except ValidationError:
            result = ToolResult.fail("INVALID_ARGUMENTS", "Arguments did not match the declared tool schema.")
        except ToolError as exc:
            result = ToolResult.fail(exc.code, str(exc))
        except TimeoutError:
            result = ToolResult.fail("TOOL_TIMEOUT", "Tool timed out and its worker was stopped. Side effects may have occurred; inspect before retrying.")
        except asyncio.CancelledError:
            self.stopped = True
            raise
        except Exception:
            logging.getLogger("soul").exception("tool_failed name=%s", name)
            result = ToolResult.fail("TOOL_ERROR", "Tool failed. See diagnostic log for details.")
        if not result.success:
            self.failures += 1
        if result.error_code in {"EMERGENCY_STOP", "USER_DECLINED", "TOOL_TIMEOUT", "WORKER_FAILED"} or self.failures >= self.max_failures:
            self.stopped = True
        elapsed = time.perf_counter() - start
        self.records.append({"name": name, "success": result.success, "seconds": elapsed, "error_code": result.error_code,
                             "message": result.message, "desired_result_verified": result.data.get("desired_result_verified")})
        logging.getLogger("soul").info("tool_result name=%s success=%s code=%s duration=%.3f", name, result.success, result.error_code, elapsed)
        if self.renderer:
            self.renderer.tool_finished(name, result, elapsed)
        self.state.set(State.THINKING)
        return result

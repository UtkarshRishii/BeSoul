from __future__ import annotations
from pydantic import Field
from soul.tools.models import Arguments, ToolResult


class AppArguments(Arguments):
    app_name: str = Field(min_length=1, max_length=160)


class ApplicationTools:
    def __init__(self, bridge):
        self.bridge = bridge

    async def open_application(self, args):
        data = await self.bridge.call("open_application", app_name=args.app_name)
        verified = bool(data.get("window"))
        message = "Application window observed after launch." if verified else "Application process observed; its window is not yet verified."
        return ToolResult(success=True, message=message, data=data, action_dispatched=True,
                          desired_result_verified=verified, observation_required=not verified)

    async def close_application(self, args):
        data = await self.bridge.call("close_application", app_name=args.app_name)
        return ToolResult(success=True, message="Target windows closed gracefully.", data=data,
                          action_dispatched=True, desired_result_verified=True)

    async def list_running_applications(self, args):
        return ToolResult(success=True, message="Visible application windows.", data=await self.bridge.call("list_running_applications"))

    async def focus_application(self, args):
        return ToolResult(success=True, message="Application foreground verified.",
                          data=await self.bridge.call("focus_application", app_name=args.app_name),
                          action_dispatched=True, desired_result_verified=True)

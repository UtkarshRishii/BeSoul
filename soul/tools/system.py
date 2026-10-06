from __future__ import annotations
from pydantic import Field
from soul.tools.models import Arguments, ToolResult


class VolumeArguments(Arguments):
    level: int = Field(ge=0, le=100, strict=True)


class PathArguments(Arguments):
    path: str = Field(min_length=1, max_length=2048)


class SystemTools:
    def __init__(self, bridge):
        self.bridge = bridge

    def handler(self, operation):
        async def run(args):
            data = await self.bridge.call(operation, **args.model_dump())
            labels = {
                "get_system_info": "System information read.",
                "get_current_time": "Current local time read.",
                "get_current_date": "Current local date read.",
                "get_battery_status": "Battery state read; desktops may have no battery.",
                "get_volume": "Speaker volume and mute state read.",
                "get_active_window": "Foreground window metadata read.",
                "read_clipboard": "Requested clipboard text read; contents remain private in telemetry.",
                "write_clipboard": "Requested text placed on the clipboard.",
                "open_file_or_folder": "File or folder handed to Windows; its window is not yet verified.",
            }
            verified = None
            if operation == "set_volume":
                verified = data.get("level") == args.level
                message = f"Speaker volume read back as {data.get('level')} percent."
            elif operation in {"mute_audio", "unmute_audio"}:
                verified = data.get("muted") is (operation == "mute_audio")
                message = "Speaker mute state read back after the change."
            else:
                message = labels.get(operation, "System state returned.")
            dispatched = operation in {"set_volume", "mute_audio", "unmute_audio", "write_clipboard", "open_file_or_folder"}
            return ToolResult(success=True, message=message, data=data, action_dispatched=dispatched,
                              desired_result_verified=verified,
                              observation_required=dispatched and verified is not True)
        return run

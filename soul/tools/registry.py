from __future__ import annotations
from soul.tools.models import Tool


class ToolRegistry:
    def __init__(self):
        self.tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self.tools:
            raise ValueError(f"Duplicate tool: {tool.name}")
        self.tools[tool.name] = tool

    def declarations(self) -> list[dict]:
        return [{"name": tool.name, "description": tool.description,
                 "parameters_json_schema": tool.arguments.model_json_schema()}
                for tool in self.tools.values()]

from typing import Dict, List, Optional
from .base import BaseTool, ToolResult
from .bash_tool import BashTool
from .file_tool import ReadFileTool, WriteFileTool, ListDirectoryTool


class ToolRegistry:
    """Central registry managing all active tools for the agent."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[BaseTool]:
        return list(self._tools.values())

    def to_ollama_tools(self) -> List[dict]:
        return [tool.to_ollama_format() for tool in self._tools.values()]


def create_default_registry(approval_callback=None) -> ToolRegistry:
    """Factory to create a standard registry with system tools."""
    registry = ToolRegistry()
    registry.register(BashTool(approval_callback=approval_callback))
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(ListDirectoryTool())
    return registry

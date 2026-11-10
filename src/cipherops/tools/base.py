from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None
    exit_code: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_string(self) -> str:
        if self.success:
            return self.output
        return f"ERROR (Exit Code {self.exit_code}): {self.error or self.output}"


class BaseTool(ABC):
    """Abstract Base Class for all CipherOps agent tools."""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Synchronously execute the tool with validated arguments."""

    def to_provider_format(self) -> dict[str, Any]:
        """Convert tool schema into the common function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_ollama_format(self) -> dict[str, Any]:
        """Backward-compatible alias for older callers."""
        return self.to_provider_format()

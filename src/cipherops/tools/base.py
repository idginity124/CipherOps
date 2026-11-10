from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ToolResult:
    success: bool
    output: str
    error: Optional[str] = None
    exit_code: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_string(self) -> str:
        if self.success:
            return self.output
        return f"ERROR (Exit Code {self.exit_code}): {self.error or self.output}"


class BaseTool(ABC):
    """Abstract Base Class for all CipherOps agent tools."""

    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Synchronously execute the tool with validated arguments."""
        pass

    def to_ollama_format(self) -> Dict[str, Any]:
        """Convert tool schema into Ollama / OpenAI standard tool definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

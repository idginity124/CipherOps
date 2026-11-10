import json
from collections.abc import Callable
from typing import Any

from ..audit.logger import AuditLevel, AuditLogger
from ..guardrails.pii_sanitizer import PIISanitizer
from ..tools.base import ToolResult
from ..tools.registry import ToolRegistry, create_default_registry
from .llm import OllamaClient

SYSTEM_PROMPT = """You are CipherOps, an elite autonomous AI Operations and Software Engineer agent.
You run locally on the host machine to diagnose issues, maintain systems, inspect code, and solve technical problems.

Core Operational Rules:
1. When asked to fix or investigate something, use your tools (execute_bash, read_file, write_file, list_directory).
2. Inspect before you act. Read files or check current state before modifying code.
3. Be concise and precise. Explain what you are doing before calling a tool.
4. If a tool execution fails or returns an error, analyze the error output and adjust your plan immediately.
5. All sensitive Personally Identifiable Information (PII) has been sanitized by the security boundary.
6. When the goal is completed, give a final clear summary of what was done.
"""


class AgentEvent:
    def __init__(self, event_type: str, data: Any = None):
        self.event_type = (
            event_type  # "thinking", "tool_call", "tool_result", "message", "pii_alert", "error"
        )
        self.data = data


class CipherAgent:
    """The Autonomous ReAct Agent Core for CipherOps."""

    # Keep at most this many non-system messages in the context window.
    # Older messages are pruned to prevent Ollama context overflow.
    MAX_CONTEXT_MESSAGES = 40

    def __init__(
        self,
        llm_client: OllamaClient | None = None,
        registry: ToolRegistry | None = None,
        sanitizer: PIISanitizer | None = None,
        audit_logger: AuditLogger | None = None,
        max_iterations: int = 15,
        event_callback: Callable[[AgentEvent], None] | None = None,
    ):
        self.llm = llm_client or OllamaClient()
        self.sanitizer = sanitizer or PIISanitizer()
        self.audit = audit_logger or AuditLogger()
        self.registry = registry or create_default_registry()
        self.max_iterations = max_iterations
        self.event_callback = event_callback

        self.messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    def _trim_context(self) -> None:
        """Keep the system prompt and the most recent MAX_CONTEXT_MESSAGES messages.

        This prevents unbounded context growth during long chat sessions that
        would eventually exceed the model's context window and cause Ollama errors.
        """
        system_msgs = [m for m in self.messages if m["role"] == "system"]
        non_system = [m for m in self.messages if m["role"] != "system"]

        if len(non_system) > self.MAX_CONTEXT_MESSAGES:
            trimmed = len(non_system) - self.MAX_CONTEXT_MESSAGES
            non_system = non_system[trimmed:]
            self._emit("context_trimmed", {"dropped_messages": trimmed})

        self.messages = system_msgs + non_system

    def reset(self) -> None:
        """Clear conversation history, keeping the system prompt."""
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def _emit(self, event_type: str, data: Any = None) -> None:
        if self.event_callback:
            self.event_callback(AgentEvent(event_type, data))

    async def run(self, user_prompt: str) -> str:
        """Execute a user goal through autonomous ReAct iterations."""
        # 1. PII Redaction Guardrail
        sanitized_prompt, pii_matches = self.sanitizer.sanitize(user_prompt)
        if pii_matches:
            self._emit(
                "pii_alert",
                {"count": len(pii_matches), "types": [m.pii_type for m in pii_matches]},
            )
            for match in pii_matches:
                self.audit.log_security_violation(
                    event_type="pii_redacted",
                    command_or_input=user_prompt,
                    reason=f"Detected {match.pii_type}",
                    level=AuditLevel.SECURITY,
                )

        self.messages.append({"role": "user", "content": sanitized_prompt})

        # 2. Trim context to prevent context window overflow
        self._trim_context()

        tools_spec = self.registry.to_ollama_tools()

        for iteration in range(self.max_iterations):
            self._emit("thinking", {"iteration": iteration + 1})

            # Call LLM
            try:
                response = await self.llm.chat(self.messages, tools=tools_spec)
            except Exception as e:
                err_msg = f"LLM Inference failed: {e!s}"
                self._emit("error", err_msg)
                return err_msg

            # Append assistant response to messages
            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": response.content,
            }
            if response.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments,
                        },
                    }
                    for tc in response.tool_calls
                ]
            self.messages.append(assistant_msg)

            # If there's content to share with the user
            if response.content:
                self._emit("message", response.content)

            # If no tools called, we're done
            if not response.tool_calls:
                return response.content

            # Execute tool calls
            for tc in response.tool_calls:
                self._emit("tool_call", {"name": tc.name, "arguments": tc.arguments})
                tool = self.registry.get(tc.name)

                if not tool:
                    tool_output = f"Error: Tool '{tc.name}' not found in registry."
                    result = ToolResult(success=False, output="", error=tool_output, exit_code=1)
                else:
                    try:
                        result = tool.execute(**tc.arguments)
                    except Exception as e:
                        result = ToolResult(
                            success=False,
                            output="",
                            error=f"Execution exception: {e!s}",
                            exit_code=1,
                        )

                output_str = result.to_string()
                self._emit(
                    "tool_result",
                    {
                        "name": tc.name,
                        "success": result.success,
                        "output": output_str,
                        "exit_code": result.exit_code,
                    },
                )

                # Log to audit trail
                self.audit.log_tool_run(
                    tool_name=tc.name,
                    command_or_input=json.dumps(tc.arguments),
                    parameters=tc.arguments,
                    output=output_str,
                    exit_code=result.exit_code,
                    human_approved=result.metadata.get("approved", True),
                    level=AuditLevel.INFO if result.success else AuditLevel.WARNING,
                )

                # Feed tool result back into context
                self.messages.append(
                    {
                        "role": "tool",
                        "content": output_str,
                    }
                )

        return "Iteration limit reached. Please review current progress."

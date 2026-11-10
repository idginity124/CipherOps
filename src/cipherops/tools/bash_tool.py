import subprocess
from collections.abc import Callable

from ..guardrails.command_validator import CommandValidator, RiskLevel
from .base import BaseTool, ToolResult


class BashTool(BaseTool):
    """Executes system shell commands safely within enterprise security boundaries."""

    name = "execute_bash"
    description = (
        "Execute a terminal shell command on the host system to run scripts, "
        "inspect processes, check system status, or test code. Use safe, standard Linux commands."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The exact shell command to execute.",
            }
        },
        "required": ["command"],
    }

    def __init__(
        self,
        validator: CommandValidator | None = None,
        approval_callback: Callable[[str, RiskLevel, str], bool] | None = None,
    ):
        self.validator = validator or CommandValidator()
        self.approval_callback = approval_callback

    def execute(self, command: str, **kwargs) -> ToolResult:
        # 1. Security & Guardrail Check
        validation = self.validator.validate(command)

        if validation.risk_level == RiskLevel.BLOCKED:
            return ToolResult(
                success=False,
                output="",
                error=f"SECURITY BLOCK: {validation.reason}",
                exit_code=126,
                metadata={"risk_level": validation.risk_level.value, "blocked": True},
            )

        # 2. Human-in-the-Loop Approval Check
        if validation.requires_approval:
            if self.approval_callback is None:
                # No callback configured: fail-safe — block execution rather than silently approve
                return ToolResult(
                    success=False,
                    output="",
                    error=(
                        f"Command requires human approval (risk: {validation.risk_level.value}) "
                        "but no approval_callback is configured. "
                        "Pass an approval_callback to BashTool or use create_default_registry()."
                    ),
                    exit_code=130,
                    metadata={
                        "risk_level": validation.risk_level.value,
                        "approved": False,
                    },
                )
            approved = self.approval_callback(command, validation.risk_level, validation.reason)
            if not approved:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Human operator REJECTED command execution: {command}",
                    exit_code=130,
                    metadata={
                        "risk_level": validation.risk_level.value,
                        "approved": False,
                    },
                )

        # 3. Execution
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
            output = result.stdout
            if result.stderr:
                if output:
                    output += "\n--- STDERR ---\n" + result.stderr
                else:
                    output = result.stderr

            return ToolResult(
                success=result.returncode == 0,
                output=output.strip() or "(Command executed with no output)",
                error=result.stderr.strip() if result.returncode != 0 else None,
                exit_code=result.returncode,
                metadata={"risk_level": validation.risk_level.value},
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error="Command execution timed out after 120 seconds",
                exit_code=124,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Subprocess execution error: {e!s}",
                exit_code=1,
            )

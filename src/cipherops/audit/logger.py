import json
import threading
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class AuditLevel(str, Enum):
    INFO = "INFO"
    SECURITY = "SECURITY"
    WARNING = "WARNING"
    BLOCKED = "BLOCKED"
    CRITICAL = "CRITICAL"


class AuditEvent(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_type: (
        str  # e.g., "tool_execution", "pii_detected", "command_blocked", "user_confirmation"
    )
    level: AuditLevel = AuditLevel.INFO
    tool_name: str | None = None
    command_or_input: str | None = None
    parameters: dict[str, Any] | None = None
    output_summary: str | None = None
    exit_code: int | None = None
    human_approved: bool | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditLogger:
    """Enterprise-grade audit logger writing structured immutable JSON Lines logs."""

    def __init__(self, log_dir: Path | None = None):
        if log_dir is None:
            self.log_dir = Path.home() / ".cipherops" / "audit"
        else:
            self.log_dir = Path(log_dir)

        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = (
            self.log_dir / f"audit_{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"
        )
        self._lock = threading.Lock()

    def log(self, event: AuditEvent) -> None:
        """Write an audit event synchronously with thread safety."""
        data = event.model_dump(mode="json")
        line = json.dumps(data, ensure_ascii=False) + "\n"

        with self._lock, open(self.log_file, "a", encoding="utf-8") as f:
            f.write(line)

    def log_tool_run(
        self,
        tool_name: str,
        command_or_input: str,
        parameters: dict[str, Any] | None,
        output: str,
        exit_code: int,
        human_approved: bool,
        level: AuditLevel = AuditLevel.INFO,
    ) -> None:
        """Convenience method for tool execution audit."""
        summary = output[:500] + ("... [truncated]" if len(output) > 500 else "")
        event = AuditEvent(
            event_type="tool_execution",
            level=level,
            tool_name=tool_name,
            command_or_input=command_or_input,
            parameters=parameters,
            output_summary=summary,
            exit_code=exit_code,
            human_approved=human_approved,
        )
        self.log(event)

    def log_security_violation(
        self,
        event_type: str,
        command_or_input: str,
        reason: str,
        level: AuditLevel = AuditLevel.BLOCKED,
    ) -> None:
        """Convenience method for security blocks or PII redacting."""
        event = AuditEvent(
            event_type=event_type,
            level=level,
            command_or_input=command_or_input,
            metadata={"reason": reason},
            human_approved=False,
        )
        self.log(event)

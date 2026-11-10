"""Tests for AuditLogger."""
import json
from pathlib import Path

import pytest

from cipherops.audit.logger import AuditLogger, AuditLevel, AuditEvent


class TestAuditLogger:
    def test_log_creates_file(self, tmp_path):
        logger = AuditLogger(log_dir=tmp_path)
        event = AuditEvent(event_type="test_event")
        logger.log(event)
        log_files = list(tmp_path.glob("audit_*.jsonl"))
        assert len(log_files) == 1

    def test_log_writes_valid_json(self, tmp_path):
        logger = AuditLogger(log_dir=tmp_path)
        event = AuditEvent(event_type="tool_execution", level=AuditLevel.INFO, tool_name="execute_bash")
        logger.log(event)
        log_file = list(tmp_path.glob("audit_*.jsonl"))[0]
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["event_type"] == "tool_execution"
        assert data["tool_name"] == "execute_bash"

    def test_multiple_events_appended(self, tmp_path):
        logger = AuditLogger(log_dir=tmp_path)
        for i in range(5):
            logger.log(AuditEvent(event_type=f"event_{i}"))
        log_file = list(tmp_path.glob("audit_*.jsonl"))[0]
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 5

    def test_log_tool_run_convenience(self, tmp_path):
        logger = AuditLogger(log_dir=tmp_path)
        logger.log_tool_run(
            tool_name="read_file",
            command_or_input="/tmp/test.txt",
            parameters={"file_path": "/tmp/test.txt"},
            output="file content",
            exit_code=0,
            human_approved=True,
        )
        log_file = list(tmp_path.glob("audit_*.jsonl"))[0]
        data = json.loads(log_file.read_text().strip())
        assert data["event_type"] == "tool_execution"
        assert data["tool_name"] == "read_file"
        assert data["human_approved"] is True
        assert data["exit_code"] == 0

    def test_log_security_violation(self, tmp_path):
        logger = AuditLogger(log_dir=tmp_path)
        logger.log_security_violation(
            event_type="pii_redacted",
            command_or_input="my TCKN is 10000000146",
            reason="Detected TCKN",
            level=AuditLevel.SECURITY,
        )
        log_file = list(tmp_path.glob("audit_*.jsonl"))[0]
        data = json.loads(log_file.read_text().strip())
        assert data["event_type"] == "pii_redacted"
        assert data["level"] == "SECURITY"

    def test_long_output_is_truncated_in_summary(self, tmp_path):
        logger = AuditLogger(log_dir=tmp_path)
        long_output = "x" * 1000
        logger.log_tool_run(
            tool_name="execute_bash",
            command_or_input="ls -la",
            parameters={},
            output=long_output,
            exit_code=0,
            human_approved=True,
        )
        log_file = list(tmp_path.glob("audit_*.jsonl"))[0]
        data = json.loads(log_file.read_text().strip())
        # output_summary should be truncated to ≤ 500 + "[truncated]"
        assert len(data["output_summary"]) <= 520
        assert "truncated" in data["output_summary"]

    def test_thread_safety(self, tmp_path):
        """Multiple threads writing simultaneously must not corrupt the log."""
        import threading
        logger = AuditLogger(log_dir=tmp_path)
        errors = []

        def write_events():
            try:
                for _ in range(20):
                    logger.log(AuditEvent(event_type="concurrent_event"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_events) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        log_file = list(tmp_path.glob("audit_*.jsonl"))[0]
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 100  # 5 threads × 20 events
        # Every line must be valid JSON
        for line in lines:
            json.loads(line)

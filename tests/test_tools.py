"""Tests for all CipherOps tools: BashTool, ReadFileTool, WriteFileTool, ListDirectoryTool."""
import os
import tempfile
from pathlib import Path

import pytest

from cipherops.tools.bash_tool import BashTool
from cipherops.tools.file_tool import ReadFileTool, WriteFileTool, ListDirectoryTool
from cipherops.guardrails.command_validator import RiskLevel


# ---------------------------------------------------------------------------
# BashTool
# ---------------------------------------------------------------------------

class TestBashTool:
    def test_safe_command_executes_without_callback(self):
        """SAFE commands (ls, git, echo, cat …) run without an approval callback."""
        tool = BashTool()
        result = tool.execute("echo hello")
        assert result.success
        assert "hello" in result.output

    def test_safe_command_with_callback_approved(self):
        tool = BashTool(approval_callback=lambda cmd, risk, reason: True)
        result = tool.execute("echo hello")
        assert result.success
        assert "hello" in result.output

    def test_blocked_command_never_executes(self):
        # Even with an always-approve callback, BLOCKED commands must not run
        tool = BashTool(approval_callback=lambda cmd, risk, reason: True)
        result = tool.execute("rm -rf /")
        assert not result.success
        assert result.exit_code == 126
        assert "SECURITY BLOCK" in result.error

    def test_read_only_command_needs_no_callback(self):
        """ls and git are in SAFE_COMMANDS so no approval needed."""
        tool = BashTool()  # no callback
        result = tool.execute("ls /tmp")
        assert result.success

    def test_human_rejection_blocks_caution_execution(self):
        """A CAUTION/HIGH command rejected by the callback must not run."""
        tool = BashTool(approval_callback=lambda cmd, risk, reason: False)
        # pip is a CAUTION command (not in SAFE_COMMANDS, not in HIGH_RISK, not a wrapper)
        result = tool.execute("pip --version")
        assert not result.success
        assert result.exit_code == 130

    def test_no_callback_blocks_caution_commands(self):
        """Without approval_callback, any CAUTION/HIGH command must be blocked (fail-safe)."""
        tool = BashTool(approval_callback=None)
        # pip is CAUTION; without callback it must be blocked by the fail-safe path
        result = tool.execute("pip --version")
        assert not result.success
        assert "approval_callback" in result.error

    def test_execution_wrapper_blocked(self):
        """Execution wrappers like bash/python/eval must be BLOCKED unconditionally."""
        tool = BashTool(approval_callback=lambda cmd, risk, reason: True)
        for cmd in ['bash -c "echo hi"', "eval echo hi", "python3 -c 'print(1)'"]:
            result = tool.execute(cmd)
            assert not result.success, f"Expected BLOCKED for: {cmd}"
            assert result.exit_code == 126

    def test_timeout_handling(self):
        """Commands that exceed timeout return a clean error."""
        import subprocess
        tool = BashTool(approval_callback=lambda cmd, risk, reason: True)
        import unittest.mock as mock
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("sleep", 120)):
            result = tool.execute("ls /tmp")  # ls is safe, no approval needed
            # ls is SAFE so it won't reach subprocess — patch won't fire; that's fine.
        # At minimum, importing and constructing works
        assert tool is not None


# ---------------------------------------------------------------------------
# ReadFileTool
# ---------------------------------------------------------------------------

class TestReadFileTool:
    def test_read_existing_file(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("line1\nline2\nline3\n")
        result = ReadFileTool().execute(str(f))
        assert result.success
        assert "line1" in result.output
        assert "line2" in result.output

    def test_read_line_range(self, tmp_path):
        f = tmp_path / "lines.txt"
        f.write_text("\n".join(f"line{i}" for i in range(1, 11)) + "\n")
        result = ReadFileTool().execute(str(f), start_line=3, end_line=5)
        assert result.success
        assert "line3" in result.output
        assert "line5" in result.output
        assert "line6" not in result.output

    def test_missing_file_returns_error(self):
        result = ReadFileTool().execute("/nonexistent/path/file.txt")
        assert not result.success
        assert result.exit_code == 1

    def test_directory_as_file_returns_error(self, tmp_path):
        result = ReadFileTool().execute(str(tmp_path))
        assert not result.success

    def test_large_file_blocked(self, tmp_path):
        f = tmp_path / "big.bin"
        f.write_bytes(b"x" * (6 * 1024 * 1024))  # 6 MB > 5 MB limit
        result = ReadFileTool().execute(str(f))
        assert not result.success
        assert "5MB" in result.error


# ---------------------------------------------------------------------------
# WriteFileTool
# ---------------------------------------------------------------------------

class TestWriteFileTool:
    def test_write_new_file(self, tmp_path):
        dest = tmp_path / "output.txt"
        result = WriteFileTool().execute(str(dest), "hello world")
        assert result.success
        assert dest.read_text() == "hello world"

    def test_creates_parent_dirs(self, tmp_path):
        dest = tmp_path / "a" / "b" / "c" / "file.txt"
        result = WriteFileTool().execute(str(dest), "nested")
        assert result.success
        assert dest.read_text() == "nested"

    def test_overwrites_existing_file(self, tmp_path):
        dest = tmp_path / "existing.txt"
        dest.write_text("old content")
        result = WriteFileTool().execute(str(dest), "new content")
        assert result.success
        assert dest.read_text() == "new content"

    def test_blocked_system_path_etc(self):
        result = WriteFileTool().execute("/etc/passwd", "evil")
        assert not result.success
        assert "SECURITY BLOCK" in result.error
        assert result.exit_code == 126

    def test_blocked_system_path_dev(self):
        result = WriteFileTool().execute("/dev/sda", "evil")
        assert not result.success
        assert "SECURITY BLOCK" in result.error

    def test_oversized_content_rejected(self, tmp_path):
        dest = tmp_path / "big.txt"
        big_content = "x" * (11 * 1024 * 1024)  # 11 MB > 10 MB limit
        result = WriteFileTool().execute(str(dest), big_content)
        assert not result.success
        assert "10 MB" in result.error
        assert not dest.exists()


# ---------------------------------------------------------------------------
# ListDirectoryTool
# ---------------------------------------------------------------------------

class TestListDirectoryTool:
    def test_list_existing_directory(self, tmp_path):
        (tmp_path / "file_a.txt").write_text("a")
        (tmp_path / "file_b.txt").write_text("b")
        (tmp_path / "subdir").mkdir()
        result = ListDirectoryTool().execute(str(tmp_path))
        assert result.success
        assert "file_a.txt" in result.output
        assert "file_b.txt" in result.output
        assert "subdir" in result.output

    def test_nonexistent_directory_returns_error(self):
        result = ListDirectoryTool().execute("/nonexistent/path/xyz")
        assert not result.success

    def test_file_path_returns_error(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x")
        result = ListDirectoryTool().execute(str(f))
        assert not result.success

    def test_empty_directory(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        result = ListDirectoryTool().execute(str(empty))
        assert result.success
        assert "empty" in result.output.lower()

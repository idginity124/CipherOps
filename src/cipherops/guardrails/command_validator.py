import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class RiskLevel(str, Enum):
    SAFE = "SAFE"            # Read-only or harmless commands
    CAUTION = "CAUTION"      # Modifies local files, builds, installs packages
    HIGH = "HIGH"            # Destructive file operations, killing processes
    BLOCKED = "BLOCKED"      # Forbidden commands that can destroy OS / hardware


@dataclass
class ValidationResult:
    command: str
    risk_level: RiskLevel
    reason: str
    requires_approval: bool
    blocked_pattern: Optional[str] = None


class CommandValidator:
    """Enterprise command validator and firewall preventing unauthorized or destructive OS executions."""

    # Catastrophic patterns strictly blocked unconditionally
    BLOCKED_PATTERNS = [
        (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\s+/\s*$", "Root directory deletion (rm -rf /) is prohibited"),
        (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\s+/\*", "Root directory wildcard deletion is prohibited"),
        (r"\bmkfs\b", "Disk formatting (mkfs) is prohibited"),
        (r"\bdd\s+if=.*of=/dev/(?:sd[a-z]|nvme[0-9]|hd[a-z])", "Direct raw disk overwrites via dd are prohibited"),
        (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "Fork bomb attempt detected"),
        (r">/dev/sd[a-z]", "Raw disk redirect write is prohibited"),
        (r">\s*/dev/nvme", "Raw disk redirect write is prohibited"),
        (r"\bshutdown\b", "System shutdown is prohibited in autonomous agent mode"),
        (r"\breboot\b", "System reboot is prohibited in autonomous agent mode"),
        (r"\bchmod\s+-R\s+777\s+/\s*$", "Global recursive 777 permissions on root is prohibited"),
    ]

    # Base command names that are safe (read-only / diagnostics)
    SAFE_COMMANDS = {
        "ls", "pwd", "whoami", "uname", "cat", "grep", "head", "tail", "wc",
        "date", "uptime", "free", "df", "ps", "top", "which", "echo", "git",
        "find", "stat", "file", "less", "more", "sort", "uniq", "cut", "tr",
        "du", "id", "env", "printenv", "lscpu", "lsblk", "lspci", "lsusb",
        "dmesg", "journalctl", "systemctl"
    }

    # Base command names that are HIGH risk (need approval, not blocked)
    HIGH_RISK_COMMANDS = {
        "rm", "rmdir", "kill", "pkill", "killall", "chmod", "chown",
        "sudo", "userdel", "groupdel", "iptables", "ufw"
    }

    def validate(self, command_str: str) -> ValidationResult:
        cmd_clean = command_str.strip()

        if not cmd_clean:
            return ValidationResult(
                command=cmd_clean,
                risk_level=RiskLevel.SAFE,
                reason="Empty command",
                requires_approval=False,
            )

        # 1. Check against BLOCKED patterns
        for pattern, reason in self.BLOCKED_PATTERNS:
            if re.search(pattern, cmd_clean, re.IGNORECASE):
                return ValidationResult(
                    command=cmd_clean,
                    risk_level=RiskLevel.BLOCKED,
                    reason=f"Security Policy Violation: {reason}",
                    requires_approval=False,
                    blocked_pattern=pattern,
                )

        # 2. Extract base commands from compound command
        base_tokens = self._extract_base_commands(cmd_clean)

        # 3. Check HIGH risk base commands
        for token in base_tokens:
            if token in self.HIGH_RISK_COMMANDS:
                return ValidationResult(
                    command=cmd_clean,
                    risk_level=RiskLevel.HIGH,
                    reason=f"Command contains high-risk operation: '{token}'",
                    requires_approval=True,
                )

        # 4. Check if ALL base commands are SAFE
        if all(token in self.SAFE_COMMANDS for token in base_tokens):
            return ValidationResult(
                command=cmd_clean,
                risk_level=RiskLevel.SAFE,
                reason="Read-only diagnostic command",
                requires_approval=False,
            )

        # 5. Default to CAUTION for builds, package management, mutations
        return ValidationResult(
            command=cmd_clean,
            risk_level=RiskLevel.CAUTION,
            reason="State-altering execution requires human confirmation",
            requires_approval=True,
        )

    def _extract_base_commands(self, cmd: str) -> List[str]:
        """Extract ONLY the binary names (base commands) from a compound command string."""
        tokens = []
        # Split by command separators (;, &&, ||, |)
        sub_cmds = re.split(r"[;&|]+", cmd)
        for sub in sub_cmds:
            sub = sub.strip()
            if not sub:
                continue
            parts = sub.split()
            if parts:
                base = parts[0].split("/")[-1]  # strip path prefix e.g. /usr/bin/ls -> ls
                tokens.append(base)
        return tokens

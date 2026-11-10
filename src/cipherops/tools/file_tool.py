import os
from pathlib import Path
from typing import Optional
from .base import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    """Tool to read contents of local files safely."""

    name = "read_file"
    description = "Read the contents of a text file from the filesystem. Supports line ranges."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute or relative path to the file.",
            },
            "start_line": {
                "type": "integer",
                "description": "Optional starting line number (1-indexed).",
            },
            "end_line": {
                "type": "integer",
                "description": "Optional ending line number (inclusive).",
            },
        },
        "required": ["file_path"],
    }

    def execute(self, file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None, **kwargs) -> ToolResult:
        try:
            path = Path(file_path).expanduser().resolve()
            if not path.exists():
                return ToolResult(success=False, output="", error=f"File not found: {file_path}", exit_code=1)

            if path.is_dir():
                return ToolResult(success=False, output="", error=f"Target path is a directory, not a file: {file_path}", exit_code=1)

            # File size limit (e.g. 5 MB) to avoid memory overload
            if path.stat().st_size > 5 * 1024 * 1024:
                return ToolResult(success=False, output="", error="File exceeds 5MB safety limit", exit_code=1)

            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            s_idx = max(0, (start_line - 1)) if start_line else 0
            e_idx = min(total_lines, end_line) if end_line else total_lines

            selected_lines = lines[s_idx:e_idx]
            numbered = [f"{i + 1:4d} | {line}" for i, line in enumerate(selected_lines, start=s_idx)]
            content = "".join(numbered)

            return ToolResult(
                success=True,
                output=content if content else "(Empty file)",
                metadata={"total_lines": total_lines, "returned_lines": len(selected_lines)},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Failed to read file: {str(e)}", exit_code=1)


class WriteFileTool(BaseTool):
    """Tool to create or overwrite files safely with parent directory auto-creation."""

    name = "write_file"
    description = "Write content to a file. Creates parent directories if they don't exist."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the destination file.",
            },
            "content": {
                "type": "string",
                "description": "Content to write into the file.",
            },
        },
        "required": ["file_path", "content"],
    }

    def execute(self, file_path: str, content: str, **kwargs) -> ToolResult:
        try:
            path = Path(file_path).expanduser().resolve()
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            return ToolResult(
                success=True,
                output=f"Successfully wrote {len(content)} characters to {path}",
                metadata={"path": str(path), "bytes": len(content.encode('utf-8'))},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Failed to write file: {str(e)}", exit_code=1)


class ListDirectoryTool(BaseTool):
    """Tool to inspect directories."""

    name = "list_directory"
    description = "List files and subdirectories inside a directory path."
    parameters = {
        "type": "object",
        "properties": {
            "directory_path": {
                "type": "string",
                "description": "Path to the directory to list (defaults to current directory).",
            }
        },
    }

    def execute(self, directory_path: str = ".", **kwargs) -> ToolResult:
        try:
            path = Path(directory_path).expanduser().resolve()
            if not path.exists():
                return ToolResult(success=False, output="", error=f"Directory not found: {directory_path}", exit_code=1)

            if not path.is_dir():
                return ToolResult(success=False, output="", error=f"Path is not a directory: {directory_path}", exit_code=1)

            entries = []
            for item in sorted(path.iterdir()):
                item_type = "[DIR]" if item.is_dir() else "[FILE]"
                size = f"({item.stat().st_size} bytes)" if item.is_file() else ""
                entries.append(f"{item_type:6s} {item.name} {size}".strip())

            return ToolResult(
                success=True,
                output="\n".join(entries) if entries else "(Directory is empty)",
                metadata={"count": len(entries)},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Failed to list directory: {str(e)}", exit_code=1)

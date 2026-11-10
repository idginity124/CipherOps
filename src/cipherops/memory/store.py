"""SQLite-backed memory explicitly managed by the user."""

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class Memory:
    id: int
    title: str
    content: str
    created_at: str
    updated_at: str


class MemoryStore:
    """Store user-authored facts and preferences in a local SQLite database."""

    MAX_TITLE_LENGTH = 120
    MAX_CONTENT_LENGTH = 4000

    def __init__(self, path: Path | None = None):
        self.path = path or Path.home() / ".cipherops" / "memory.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name == "posix":
            os.chmod(self.path.parent, 0o700)
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        self._secure_file_permissions()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5.0)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _secure_file_permissions(self) -> None:
        if os.name == "posix" and self.path.exists():
            os.chmod(self.path, 0o600)

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def _validate(cls, title: str, content: str) -> tuple[str, str]:
        title = title.strip()
        content = content.strip()
        if not title:
            raise ValueError("Hafıza başlığı boş olamaz.")
        if not content:
            raise ValueError("Hafıza içeriği boş olamaz.")
        if len(title) > cls.MAX_TITLE_LENGTH:
            raise ValueError(f"Başlık en fazla {cls.MAX_TITLE_LENGTH} karakter olabilir.")
        if len(content) > cls.MAX_CONTENT_LENGTH:
            raise ValueError(f"İçerik en fazla {cls.MAX_CONTENT_LENGTH} karakter olabilir.")
        return title, content

    @staticmethod
    def _from_row(row: tuple) -> Memory:
        return Memory(
            id=row[0],
            title=row[1],
            content=row[2],
            created_at=row[3],
            updated_at=row[4],
        )

    def add(self, title: str, content: str) -> Memory:
        title, content = self._validate(title, content)
        timestamp = self._timestamp()
        with self._connection() as connection:
            cursor = connection.execute(
                "INSERT INTO memories (title, content, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (title, content, timestamp, timestamp),
            )
            memory_id = cursor.lastrowid
            row = connection.execute(
                "SELECT id, title, content, created_at, updated_at FROM memories WHERE id = ?",
                (memory_id,),
            ).fetchone()
        self._secure_file_permissions()
        return self._from_row(row)

    def list_memories(self) -> list[Memory]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT id, title, content, created_at, updated_at "
                "FROM memories ORDER BY updated_at DESC, id DESC"
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def get(self, memory_id: int) -> Memory | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT id, title, content, created_at, updated_at FROM memories WHERE id = ?",
                (memory_id,),
            ).fetchone()
        return self._from_row(row) if row else None

    def update(
        self,
        memory_id: int,
        title: str | None = None,
        content: str | None = None,
    ) -> Memory | None:
        current = self.get(memory_id)
        if current is None:
            return None
        new_title, new_content = self._validate(
            current.title if title is None else title,
            current.content if content is None else content,
        )
        with self._connection() as connection:
            connection.execute(
                "UPDATE memories SET title = ?, content = ?, updated_at = ? WHERE id = ?",
                (new_title, new_content, self._timestamp(), memory_id),
            )
        self._secure_file_permissions()
        return self.get(memory_id)

    def delete(self, memory_id: int) -> bool:
        with self._connection() as connection:
            cursor = connection.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return cursor.rowcount > 0

    def clear(self) -> int:
        with self._connection() as connection:
            cursor = connection.execute("DELETE FROM memories")
        return cursor.rowcount

    def context_text(self, max_chars: int = 8000) -> str:
        """Format saved items for inference, bounded to avoid bloating context."""
        memories = self.list_memories()
        sections = []
        used = 0
        for memory in memories:
            section = f"- {memory.title}: {memory.content}"
            extra = len(section) + (1 if sections else 0)
            if used + extra > max_chars:
                break
            sections.append(section)
            used += extra
        return "\n".join(sections)

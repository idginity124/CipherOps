"""Tests for explicitly managed persistent memory."""

import os
import stat

import pytest

from cipherops.audit.logger import AuditLogger
from cipherops.core.agent import CipherAgent
from cipherops.core.llm import LLMResponse
from cipherops.memory import MemoryStore


def test_memory_survives_store_recreation(tmp_path):
    database = tmp_path / "memory.sqlite3"
    first_store = MemoryStore(database)
    created = first_store.add("Language", "Prefer Turkish replies")

    second_store = MemoryStore(database)

    assert second_store.get(created.id) == created


def test_memory_can_be_updated_deleted_and_cleared(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    first = store.add("Language", "Turkish")
    second = store.add("Style", "Concise")

    updated = store.update(first.id, content="Use Turkish unless asked otherwise")
    assert updated is not None
    assert updated.content == "Use Turkish unless asked otherwise"
    assert store.delete(second.id)
    assert not store.delete(second.id)
    assert store.clear() == 1
    assert store.list_memories() == []


def test_memory_rejects_empty_or_oversized_fields(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")

    with pytest.raises(ValueError):
        store.add(" ", "some content")
    with pytest.raises(ValueError):
        store.add("title", " ")
    with pytest.raises(ValueError):
        store.add("x" * (store.MAX_TITLE_LENGTH + 1), "content")
    with pytest.raises(ValueError):
        store.add("title", "x" * (store.MAX_CONTENT_LENGTH + 1))


def test_context_text_respects_character_limit(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.add("First", "one")
    store.add("Second", "two")

    context = store.context_text(max_chars=13)

    assert len(context) <= 13
    assert context


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits are platform-specific")
def test_memory_database_is_owner_only(tmp_path):
    database = tmp_path / "memory.sqlite3"
    MemoryStore(database).add("Language", "Turkish")

    assert stat.S_IMODE(database.stat().st_mode) == 0o600


class CapturingLLM:
    model = "test-model"

    def __init__(self):
        self.requests = []

    async def chat(self, messages, tools=None, temperature=0.2):
        self.requests.append(messages)
        return LLMResponse(content="Ready")

    async def check_health(self):
        return True

    async def list_local_models(self):
        return [self.model]


@pytest.mark.asyncio
async def test_agent_uses_memory_only_when_store_is_explicitly_provided(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.add("Preferred language", "Turkish")
    store.add("Example ID", "10000000146")
    llm = CapturingLLM()
    agent = CipherAgent(
        llm_client=llm,
        memory_store=store,
        audit_logger=AuditLogger(tmp_path / "audit"),
    )

    await agent.run("Hello")

    system_prompt = llm.requests[0][0]["content"]
    assert "Preferred language: Turkish" in system_prompt
    assert "[REDACTED_TCKN]" in system_prompt
    assert "10000000146" not in system_prompt
    assert len(store.list_memories()) == 2


@pytest.mark.asyncio
async def test_agent_does_not_include_memory_without_opt_in(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.add("Preferred language", "Turkish")
    llm = CapturingLLM()
    agent = CipherAgent(
        llm_client=llm,
        audit_logger=AuditLogger(tmp_path / "audit"),
    )

    await agent.run("Hello")

    assert "Preferred language" not in llm.requests[0][0]["content"]

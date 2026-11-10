import json
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_response: dict[str, Any] = field(default_factory=dict)


class OllamaClient:
    """Async client communicating with local Ollama or OpenAI-compatible endpoints."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5-coder:14b",
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def check_health(self) -> bool:
        """Check if local Ollama daemon is active."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    async def list_local_models(self) -> list[str]:
        """Return list of downloaded model tags in Ollama."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    return [m["name"] for m in data.get("models", [])]
                return []
        except Exception:
            return []

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Send chat messages and tool specifications to Ollama."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }

        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            if response.status_code != 200:
                raise RuntimeError(
                    f"Ollama API request failed [{response.status_code}]: {response.text}"
                )

            data = response.json()
            message = data.get("message", {})
            content = message.get("content", "") or ""

            tool_calls: list[ToolCall] = []
            if "tool_calls" in message:
                for tc in message["tool_calls"]:
                    fn = tc.get("function", {})
                    name = fn.get("name", "")
                    args = fn.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {"raw": args}
                    tool_calls.append(ToolCall(name=name, arguments=args))

            return LLMResponse(content=content, tool_calls=tool_calls, raw_response=data)

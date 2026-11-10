"""Adapters for local model servers supported by CipherOps."""

import json
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    call_id: str | None = None


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_response: dict[str, Any] = field(default_factory=dict)


class LLMClient(Protocol):
    """Common interface used by the agent, independent of the local server."""

    model: str

    async def check_health(self) -> bool: ...

    async def list_local_models(self) -> list[str]: ...

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
    ) -> LLMResponse: ...


def _validate_local_url(base_url: str) -> str:
    """Only allow loopback endpoints so provider configuration remains local-only."""
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise ValueError(
            "CipherOps yalnızca bu bilgisayardaki yerel sunuculara bağlanır "
            "(localhost, 127.0.0.1 veya ::1)."
        )
    if parsed.username or parsed.password:
        raise ValueError("Sunucu adresine kullanıcı adı/parola eklemeyin.")
    return base_url.rstrip("/")


class OllamaClient:
    """Client for Ollama's native local HTTP API."""

    provider_name = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5-coder:14b",
        timeout: float = 120.0,
    ):
        self.base_url = _validate_local_url(base_url)
        self.model = model
        self.timeout = timeout

    async def check_health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def list_local_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                return [item["name"] for item in data.get("models", []) if "name" in item]
        except (httpx.HTTPError, ValueError, KeyError):
            return []

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": _messages_for_ollama(messages),
            "stream": False,
            "options": {"temperature": temperature},
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            if response.status_code != 200:
                raise RuntimeError(
                    f"Ollama API isteği başarısız [{response.status_code}]: {response.text}"
                )
            data = response.json()
        message = data.get("message", {})
        return LLMResponse(
            content=message.get("content", "") or "",
            tool_calls=_parse_tool_calls(message.get("tool_calls", [])),
            raw_response=data,
        )


class OpenAICompatibleLocalClient:
    """Client for local servers exposing the OpenAI-compatible chat API.

    Works with servers such as llama.cpp, LM Studio, and vLLM when their
    OpenAI-compatible API and tool calling are enabled.
    """

    provider_name = "openai-compatible"

    def __init__(
        self,
        base_url: str = "http://localhost:1234/v1",
        model: str = "",
        timeout: float = 120.0,
        api_key: str | None = None,
    ):
        self.base_url = _validate_local_url(base_url)
        self.model = model
        self.timeout = timeout
        self.api_key = api_key

    @property
    def api_root(self) -> str:
        return self.base_url if urlparse(self.base_url).path.rstrip("/").endswith("/v1") else f"{self.base_url}/v1"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def check_health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{self.api_root}/models", headers=self._headers())
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def list_local_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.api_root}/models", headers=self._headers())
                response.raise_for_status()
                data = response.json()
                return [item["id"] for item in data.get("data", []) if "id" in item]
        except (httpx.HTTPError, ValueError, KeyError):
            return []

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        if not self.model:
            raise ValueError("OpenAI uyumlu yerel sunucu için --model belirtilmeli.")

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": _messages_for_openai(messages),
            "temperature": temperature,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.api_root}/chat/completions",
                json=payload,
                headers=self._headers(),
            )
            if response.status_code != 200:
                raise RuntimeError(
                    "Yerel OpenAI uyumlu API isteği başarısız "
                    f"[{response.status_code}]: {response.text}"
                )
            data = response.json()

        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("Yerel sunucu geçerli bir chat completion yanıtı döndürmedi.")
        message = choices[0].get("message", {})
        return LLMResponse(
            content=message.get("content") or "",
            tool_calls=_parse_tool_calls(message.get("tool_calls", [])),
            raw_response=data,
        )


def _parse_tool_calls(raw_calls: list[dict[str, Any]]) -> list[ToolCall]:
    calls = []
    for raw_call in raw_calls:
        function = raw_call.get("function", {})
        arguments = function.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as exc:
                raise RuntimeError("Model geçersiz JSON araç argümanı döndürdü.") from exc
        if not isinstance(arguments, dict):
            raise RuntimeError("Modelin araç argümanları JSON nesnesi olmalı.")
        calls.append(
            ToolCall(
                name=function.get("name", ""),
                arguments=arguments,
                call_id=raw_call.get("id"),
            )
        )
    return calls


def _messages_for_ollama(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert the agent's common tool-call history to Ollama's native format."""
    converted = []
    for message in messages:
        item = dict(message)
        if item.get("role") == "assistant" and item.get("tool_calls"):
            item["tool_calls"] = [
                {
                    "type": "function",
                    "function": {
                        "name": call["function"]["name"],
                        "arguments": call["function"]["arguments"],
                    },
                }
                for call in item["tool_calls"]
            ]
        if item.get("role") == "tool":
            item = {"role": "tool", "content": item.get("content", "")}
        converted.append(item)
    return converted


def _messages_for_openai(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Serialize canonical tool arguments as required by OpenAI-style APIs."""
    converted = []
    for message in messages:
        item = dict(message)
        if item.get("role") == "assistant" and item.get("tool_calls"):
            item["tool_calls"] = [
                {
                    **call,
                    "function": {
                        **call["function"],
                        "arguments": json.dumps(
                            call["function"]["arguments"], ensure_ascii=False
                        ),
                    },
                }
                for call in item["tool_calls"]
            ]
        converted.append(item)
    return converted


def create_llm_client(
    provider: str = "ollama",
    base_url: str | None = None,
    model: str | None = None,
    timeout: float = 120.0,
    api_key: str | None = None,
) -> LLMClient:
    """Build a local provider adapter from CLI/configuration values."""
    normalized = provider.strip().lower()
    if normalized == "ollama":
        return OllamaClient(
            base_url=base_url or "http://localhost:11434",
            model=model or "qwen2.5-coder:14b",
            timeout=timeout,
        )
    if normalized in {"openai-compatible", "openai_compatible", "openai"}:
        return OpenAICompatibleLocalClient(
            base_url=base_url or "http://localhost:1234/v1",
            model=model or "",
            timeout=timeout,
            api_key=api_key,
        )
    raise ValueError(
        f"Bilinmeyen sağlayıcı: {provider}. Desteklenenler: ollama, openai-compatible."
    )

"""Contract tests for supported local model-server adapters."""

import json

import httpx
import pytest

from cipherops.core.llm import (
    OllamaClient,
    OpenAICompatibleLocalClient,
    create_llm_client,
)


def test_provider_factory_selects_supported_local_adapters():
    assert isinstance(create_llm_client("ollama"), OllamaClient)
    assert isinstance(create_llm_client("openai-compatible"), OpenAICompatibleLocalClient)


def test_provider_factory_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Bilinmeyen sağlayıcı"):
        create_llm_client("remote-cloud")


@pytest.mark.parametrize("url", ["https://example.com/v1", "http://192.168.1.8:1234/v1"])
def test_providers_reject_non_loopback_endpoints(url):
    with pytest.raises(ValueError, match="yalnızca"):
        OpenAICompatibleLocalClient(base_url=url, model="test")


@pytest.mark.asyncio
async def test_openai_compatible_client_lists_models_and_parses_tool_calls(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "local-qwen"}]})
        payload = json.loads(request.content)
        assert payload["model"] == "local-qwen"
        assert payload["tool_choice"] == "auto"
        assert payload["messages"][1]["tool_calls"][0]["function"]["arguments"] == (
            '{"file_path": "notes.txt"}'
        )
        assert payload["messages"][2]["tool_call_id"] == "call_previous"
        assert request.headers["authorization"] == "Bearer local-test-token"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_next",
                                    "type": "function",
                                    "function": {
                                        "name": "list_directory",
                                        "arguments": '{"directory_path": "src"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "cipherops.core.llm.httpx.AsyncClient",
        lambda **kwargs: real_async_client(transport=transport, **kwargs),
    )
    client = OpenAICompatibleLocalClient(
        base_url="http://localhost:1234/v1",
        model="local-qwen",
        api_key="local-test-token",
    )

    assert await client.check_health()
    assert await client.list_local_models() == ["local-qwen"]
    response = await client.chat(
        messages=[
            {"role": "user", "content": "Inspect this"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_previous",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": {"file_path": "notes.txt"},
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_previous",
                "name": "read_file",
                "content": "note text",
            },
        ],
        tools=[{"type": "function", "function": {"name": "list_directory"}}],
    )

    assert len(requests) == 3
    assert response.tool_calls[0].name == "list_directory"
    assert response.tool_calls[0].arguments == {"directory_path": "src"}
    assert response.tool_calls[0].call_id == "call_next"

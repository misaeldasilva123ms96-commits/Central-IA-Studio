from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from studio.config import Settings
from studio.app import app, sse

client = TestClient(app, base_url="http://127.0.0.1")


def test_home():
    response = client.get("/")
    assert response.status_code == 200
    assert "Central IA Studio" in response.text


def test_local_api_restrictions():
    for url in ["https://api.example.com/v1", "http://192.168.0.2:5001/v1", "http://localhost:5001/other"]:
        try:
            Settings(api_base_url=url)
            assert False, "URL remota foi aceita"
        except ValidationError:
            pass
    assert Settings(api_base_url="http://localhost:5001").api_base_url.endswith("/v1")


def test_generation_limit_is_not_2048():
    assert Settings(max_tokens=8192).max_tokens == 8192
    assert Settings(max_tokens=32768).max_tokens == 32768


def test_config_route(tmp_path):
    with patch("studio.config.CONFIG_FILE", tmp_path / "settings.json"):
        result = client.get("/api/config")
        assert result.status_code == 200
        obj = result.json()
        obj["temperature"] = 0.4
        result = client.put("/api/config", json=obj)
        assert result.status_code == 200
        assert client.get("/api/config").json()["temperature"] == 0.4


def test_invalid_message():
    assert client.post("/api/chat", json={"messages": [{"role": "system", "content": ""}]}).status_code == 422


def test_sse_format():
    assert sse("token", {"text": "Olá"}) == 'event: token\ndata: {"text": "Olá"}\n\n'


def test_trusted_host():
    assert client.get("/", headers={"host": "untrusted.example.com"}).status_code == 400


def test_streaming_proxy_from_mock_engine():
    import httpx

    original = httpx.AsyncClient
    captured = {}

    def respond(request):
        captured["body"] = __import__("json").loads(request.content.decode())
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=(
            'data: {"choices":[{"delta":{"content":"Olá "},"finish_reason":null}]}\n\n'
            'data: {"choices":[{"delta":{"content":"mundo"},"finish_reason":null}]}\n\n'
            'data: [DONE]\n\n'))

    def fake_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(respond)
        return original(*args, **kwargs)

    with patch("studio.app.httpx.AsyncClient", side_effect=fake_client):
        result = client.post("/api/chat", json={"messages": [{"role": "user", "content": "Oi"}]})
    assert result.status_code == 200
    assert '"text": "Olá "' in result.text
    assert '"text": "mundo"' in result.text
    assert "event: done" in result.text
    assert captured["body"]["messages"][0]["role"] == "system"
    assert captured["body"]["messages"][1]["content"] == "Oi"


def test_streaming_engine_error_from_mock():
    import httpx
    original = httpx.AsyncClient
    def fake_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(lambda request: httpx.Response(503, text="not ready"))
        return original(*args, **kwargs)
    with patch("studio.app.httpx.AsyncClient", side_effect=fake_client):
        result = client.post("/api/chat", json={"messages": [{"role": "user", "content": "Oi"}]})
    assert result.status_code == 200  # errors during an SSE response are events
    assert "event: error" in result.text
    assert "HTTP 503" in result.text

"""API e aplicação web local do Central IA Studio."""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field

from .config import Settings, load_settings, save_settings, local_models
from .engine import EngineManager

WEB_DIR = Path(__file__).parent / "web"
engine = EngineManager()

@asynccontextmanager
async def lifespan(application: FastAPI):
    yield
    if engine.running():
        engine.stop()

app = FastAPI(title="Central IA Studio", version="0.1.0", docs_url=None, redoc_url=None, lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"])
app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=150000)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=100)


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/config")
def get_config():
    return load_settings()


@app.put("/api/config")
def put_config(settings: Settings):
    if engine.running():
        old = load_settings()
        fields = ("provider", "engine_executable", "models_dir", "model_file", "engine_port", "ctx_size", "threads", "gpu_layers")
        if any(getattr(old, field) != getattr(settings, field) for field in fields):
            raise HTTPException(status_code=409, detail="Pare o motor antes de alterar as configurações de execução.")
    save_settings(settings)
    return settings


@app.get("/api/models")
def list_models():
    return {"items": local_models(load_settings())}


@app.get("/api/status")
async def status():
    settings = load_settings()
    info = {"online": False, "provider": settings.provider,
            "endpoint": settings.api_base_url, "managed_running": engine.running(), "models": []}
    try:
        async with httpx.AsyncClient(timeout=1.8, trust_env=False) as client:
            response = await client.get(f"{settings.api_base_url}/models")
        if response.is_success:
            info["online"] = True
            models = response.json().get("data", [])
            info["models"] = [str(m.get("id", "")) for m in models if isinstance(m, dict)][:30]
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        pass
    return info


@app.post("/api/engine/start")
def engine_start():
    try:
        return engine.start(load_settings())
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/engine/stop")
def engine_stop():
    try:
        return engine.stop()
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/engine/logs")
def engine_logs():
    return {"text": engine.logs()}


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/chat")
async def chat(request: ChatRequest):
    settings = load_settings()
    messages = [m.model_dump() for m in request.messages]
    if settings.system_prompt:
        messages.insert(0, {"role": "system", "content": settings.system_prompt})

    payload = {"model": settings.model_id or "local-model", "messages": messages,
               "temperature": settings.temperature, "top_p": settings.top_p,
               "max_tokens": settings.max_tokens, "stream": True,
               "top_k": settings.top_k, "min_p": settings.min_p,
               "repeat_penalty": settings.repeat_penalty}

    async def events():
        finished = False
        try:
            timeout = httpx.Timeout(connect=10, read=None, write=25, pool=5)
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                async with client.stream("POST", f"{settings.api_base_url}/chat/completions", json=payload) as response:
                    if response.status_code >= 400:
                        msg = (await response.aread()).decode("utf-8", errors="replace")[:800]
                        yield sse("error", {"message": f"Motor retornou HTTP {response.status_code}: {msg}"})
                        return
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            finished = True
                            break
                        try:
                            chunk = json.loads(data)
                            choice = chunk.get("choices", [{}])[0]
                            delta = choice.get("delta", {})
                            content = delta.get("content") if isinstance(delta, dict) else None
                            if isinstance(content, str) and content:
                                yield sse("token", {"text": content})
                            if choice.get("finish_reason"):
                                yield sse("finish", {"reason": choice["finish_reason"]})
                        except (json.JSONDecodeError, ValueError, IndexError, AttributeError, TypeError):
                            continue
        except httpx.HTTPError as exc:
            yield sse("error", {"message": f"Não foi possível conversar com o motor: {exc}"})
            return
        if finished:
            yield sse("done", {})
        else:
            yield sse("done", {"warning": "O motor encerrou o fluxo sem sinalizador [DONE]."})

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


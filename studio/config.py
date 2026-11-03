"""Configuração persistente, validada e limitada à máquina local."""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

DATA_DIR = Path(os.environ.get("CENTRAL_IA_STUDIO_DATA_DIR", Path.home() / ".central-ia-studio")).expanduser()
CONFIG_FILE = DATA_DIR / "settings.json"


class Settings(BaseModel):
    provider: Literal["koboldcpp", "llama-external", "llama-managed"] = "koboldcpp"
    api_base_url: str = "http://127.0.0.1:5001/v1"
    model_id: str = ""
    models_dir: str = ""
    model_file: str = ""
    engine_executable: str = ""
    engine_port: int = Field(8081, ge=1024, le=65535)
    ctx_size: int = Field(4096, ge=512, le=131072)
    threads: int = Field(4, ge=1, le=128)
    gpu_layers: int = Field(0, ge=0, le=1000)
    temperature: float = Field(0.7, ge=0, le=2)
    top_p: float = Field(0.92, gt=0, le=1)
    top_k: int = Field(40, ge=0, le=1000)
    min_p: float = Field(0.05, ge=0, le=1)
    repeat_penalty: float = Field(1.05, ge=0.5, le=2)
    max_tokens: int = Field(1024, ge=1, le=65536)
    system_prompt: str = Field("Você é um assistente útil, objetivo e responde em português do Brasil.", max_length=16000)

    @field_validator("api_base_url")
    @classmethod
    def only_loopback(cls, url: str) -> str:
        parsed = urlparse(url.strip())
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path.rstrip("/") not in {"", "/v1"}):
            raise ValueError("Nesta versão, a API precisa usar HTTP local (127.0.0.1, localhost ou ::1), com caminho /v1.")
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Porta da API inválida.") from exc
        if port is None:
            raise ValueError("Informe a porta da API (ex.: 5001).")
        return url.strip().rstrip("/") if parsed.path.rstrip("/") == "/v1" else url.strip().rstrip("/") + "/v1"

    @model_validator(mode="after")
    def sync_managed_url(self):
        if self.provider == "llama-managed":
            self.api_base_url = f"http://127.0.0.1:{self.engine_port}/v1"
        return self


def load_settings() -> Settings:
    try:
        return Settings.model_validate_json(CONFIG_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        return Settings()


def save_settings(settings: Settings) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp = CONFIG_FILE.with_suffix(".tmp")
    temp.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
    temp.replace(CONFIG_FILE)


def local_models(settings: Settings) -> list[dict]:
    if not settings.models_dir:
        return []
    root = Path(settings.models_dir).expanduser()
    if not root.is_dir():
        return []
    items = []
    try:
        for path in root.rglob("*.gguf"):
            if len(items) >= 500:
                break
            if path.is_file():
                items.append({"name": path.name, "path": str(path), "size_gb": round(path.stat().st_size / (1024 ** 3), 2)})
    except (OSError, PermissionError):
        pass
    return sorted(items, key=lambda item: item["name"].lower())

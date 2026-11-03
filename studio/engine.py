"""Gerencia somente processos llama-server iniciados por este aplicativo."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from .config import Settings, DATA_DIR


class EngineManager:
    def __init__(self):
        self.process: subprocess.Popen | None = None

    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self, settings: Settings) -> dict:
        if settings.provider != "llama-managed":
            raise ValueError("Selecione 'llama.cpp gerenciado' para iniciar um motor.")
        if self.running():
            raise ValueError("Um motor já foi iniciado pelo Studio.")
        if not settings.engine_executable or not settings.models_dir or not settings.model_file:
            raise ValueError("Defina o executável, a pasta de modelos e o modelo GGUF.")

        exe = Path(settings.engine_executable).expanduser()
        executable = str(exe.resolve()) if exe.is_file() else shutil.which(settings.engine_executable)
        if not executable:
            raise ValueError("Executável llama-server não encontrado.")

        root = Path(settings.models_dir).expanduser().resolve(strict=True)
        model = Path(settings.model_file).expanduser().resolve(strict=True)
        if not model.is_file() or model.suffix.lower() != ".gguf" or not model.is_relative_to(root):
            raise ValueError("O arquivo GGUF precisa estar dentro da pasta de modelos configurada.")

        cmd = [executable, "--model", str(model), "--host", "127.0.0.1",
               "--port", str(settings.engine_port), "--ctx-size", str(settings.ctx_size),
               "--threads", str(settings.threads), "--n-gpu-layers", str(settings.gpu_layers)]
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with (DATA_DIR / "engine.log").open("ab") as out:
                self.process = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT,
                                                stdin=subprocess.DEVNULL, cwd=str(Path(executable).resolve().parent))
        except OSError as exc:
            raise ValueError(f"Não foi possível iniciar llama-server: {exc}") from exc
        return {"running": self.running(), "pid": self.process.pid if self.process else None}

    def stop(self) -> dict:
        if not self.running():
            self.process = None
            return {"running": False}
        assert self.process is not None
        self.process.terminate()
        try:
            self.process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        self.process = None
        return {"running": False}

    def logs(self) -> str:
        path = DATA_DIR / "engine.log"
        if not path.exists():
            return ""
        with path.open("rb") as file:
            file.seek(max(0, path.stat().st_size - 25000))
            return file.read().decode("utf-8", errors="replace")

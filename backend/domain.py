import os
from pathlib import Path
from urllib.parse import urlsplit
from pydantic import BaseModel, Field, ConfigDict, field_validator

class Profile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    context: int = Field(4096, ge=256, le=524288)
    max_output: int = Field(4096, ge=1, le=524288)
    temperature: float = Field(.7, ge=0, le=5, allow_inf_nan=False)
    top_p: float = Field(.95, ge=0, le=1, allow_inf_nan=False)
    top_k: int = Field(40, ge=0, le=10000)
    min_p: float = Field(.05, ge=0, le=1, allow_inf_nan=False)
    repetition_penalty: float = Field(1.1, ge=1, le=3, allow_inf_nan=False)
    threads: int = Field(2, ge=1, le=256)
    blas_threads: int = Field(2, ge=1, le=256)
    batch_size: int = 128
    gpu_layers: int = Field(0, ge=0, le=1000)
    cache_kv: str = 'q8_0'
    flash_attention: bool = True
    template: str = ''
    thinking: str = 'default'
    mode: str = 'personalizado'

    @field_validator('batch_size')
    @classmethod
    def batch(cls, v):
        if v not in [-1,16,32,64,128,256,512,1024,2048,4096]:
            raise ValueError('Lote não suportado pelo KoboldCpp 1.124.2')
        return v

    @field_validator('cache_kv')
    @classmethod
    def kv(cls, v):
        if v not in ['f16','bf16','q8_0','q5_1','q4_0']:
            raise ValueError('Tipo de cache não suportado')
        return v

    @field_validator('thinking')
    @classmethod
    def think(cls, v):
        if v not in ['default','on','off']:
            raise ValueError('Thinking inválido')
        return v

    @field_validator('mode')
    @classmethod
    def modes(cls, v):
        if v not in ['rapido','profundo','personalizado']:
            raise ValueError('Modo inválido')
        return v

class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    engine_url: str = 'http://127.0.0.1:5001'
    executable: str = ''
    folders: list[str] = Field(default_factory=list, max_length=64)

    @field_validator('engine_url')
    @classmethod
    def loopback(cls, v):
        u = urlsplit(v)
        if (u.scheme != 'http' or u.hostname not in ['127.0.0.1','localhost','::1']
                or u.username or u.password or u.query or u.fragment or u.path not in ['', '/']):
            raise ValueError('Use uma URL HTTP local, sem caminho ou credenciais')
        if u.port is None or not 1024 <= u.port <= 65535:
            raise ValueError('Informe porta entre 1024 e 65535')
        return v.rstrip('/')

    @field_validator('folders')
    @classmethod
    def dirs(cls, values):
        return list(dict.fromkeys(str(Path(v).expanduser().resolve()) for v in values if v.strip()))

RESTART_FIELDS = ['context','threads','blas_threads','batch_size','gpu_layers','cache_kv','flash_attention','template']

def thinking_value(p):
    return 'off' if p.mode == 'rapido' else 'on' if p.mode == 'profundo' else p.thinking

def build_command(executable, model, profile, port):
    exe = Path(executable).expanduser().resolve()
    if not exe.is_file() or (os.name == 'nt' and exe.suffix.lower() != '.exe'):
        raise ValueError('Selecione um executável KoboldCpp existente')
    path = Path(model).resolve()
    if not path.is_file() or path.suffix.lower() != '.gguf':
        raise ValueError('Modelo GGUF inexistente')
    p = profile
    args = [str(exe), '--model', str(path), '--host', '127.0.0.1', '--port', str(port),
            '--contextsize', str(p.context), '--threads', str(p.threads), '--blasthreads', str(p.blas_threads),
            '--blasbatchsize', str(p.batch_size), '--gpulayers', str(p.gpu_layers), '--quantkv', p.cache_kv,
            '--jinja']
    if not p.flash_attention:
        args.append('--noflashattention')
    if p.template:
        tmpl = Path(p.template).expanduser().resolve()
        if not tmpl.is_file() or tmpl.suffix.lower() not in ['.jinja','.j2'] or tmpl.stat().st_size > 1048576:
            raise ValueError('Template deve ser arquivo .jinja/.j2 existente de até 1 MiB')
        args += ['--jinjatemplate', str(tmpl)]
    return args

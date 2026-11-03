# Central IA Studio · v0.1.0

**Um estúdio de IA local em português, com chat e ajustes avançados para motores GGUF.**

> Base inicial independente da Central IA anterior e do executável KoboldCpp. Não altera nem extrai arquivos do KoboldCpp; usa a API local documentada. Projeto experimental, sem garantias de desempenho com todos os modelos.

## Funcionalidades da base

- Interface web em português, responsiva, sem frontend pesado ou build Node.
- Conversas locais com persistência no navegador e exportação JSON.
- Streaming de texto, interrupção de respostas e indicação de conexão.
- Integração com **KoboldCpp** existente via API OpenAI compatível (padrão `127.0.0.1:5001/v1`).
- Integração com **llama.cpp / llama-server** existente via API compatível.
- Iniciar e parar um **llama-server** diretamente pelo Studio (quando configurado).
- Seleção de GGUF na biblioteca local, sem copiar ou modificar modelos.
- Parâmetros ajustáveis: `max_tokens` até 65.536 no campo, `temperature`, `top_p`, `top_k`, `min_p`, `repeat_penalty`; além de contexto, threads, camadas GPU e prompt de sistema.
- Motor e Studio vinculados a `127.0.0.1`: sem login, sem exposição pública e sem nuvem para inferência.
- API FastAPI validada, testes e GitHub Actions.

**Importante:** permitir o envio de `max_tokens` acima de 2048 não aumenta a janela de contexto do modelo, a memória física nem a capacidade do próprio motor. O motor pode limitar a saída ou parar antes. Nem todos os provedores obedecem a todos os parâmetros opcionais.

## Iniciar no Windows / Linux / WSL

Instale Python 3.11 ou superior e execute, **dentro da pasta do projeto**:

```bash
python -m venv .venv
```

No Windows (PowerShell):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

No Linux / WSL:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run.py
```

Abra **http://127.0.0.1:8765**.

### Opção A — usar KoboldCpp já instalado

1. Execute o KoboldCpp e carregue o modelo GGUF nele normalmente.
2. Confirme se a API local está em `http://127.0.0.1:5001/v1` (porta padrão; se mudou, ajuste).
3. Abra Central IA Studio > Configurações > Tipo de motor: *KoboldCpp — conectar ao existente*.
4. Salve, confira **Motor conectado** e converse.

O limite de geração na interface do Studio é configurável e independente do campo da interface do KoboldCpp. A API, o modelo, o contexto e a implementação da inferência continuam determinando o máximo efetivo.

### Opção B — usar llama-server já rodando

1. Inicie manualmente `llama-server` em localhost (por exemplo porta 8081), carregando um GGUF.
2. Selecione *llama.cpp — conectar ao existente* e defina o endereço `http://127.0.0.1:8081/v1`.
3. Salve e converse.

### Opção C — gerenciar o llama-server pelo Studio

1. Baixe/compile um `llama-server` compatível com seu PC, por fonte oficial.
2. Em Configurações, selecione *llama.cpp — iniciar pelo Studio*.
3. Informe o caminho para o executável, pasta de GGUF e arquivo `.gguf` dentro dela.
4. Use `ctx_size=4096`, `gpu_layers=0` e poucos threads inicialmente no PC com 8 GB de RAM.
5. Salve e clique em **Iniciar llama-server** na tela Modelos e motor.

**Atenção:** o executável `llama-server` e o GGUF **não estão incluídos** no ZIP. O Studio não baixa modelos automaticamente. O modo gerenciado só inicia binários que você configurar; execute apenas binários confiáveis.

## Estrutura

```text
Central_IA_Studio_Base/
├── studio/
│   ├── app.py            # API local, proxy SSE
│   ├── config.py         # Configuração e busca de GGUF
│   ├── engine.py         # Processo llama-server, logs
│   └── web/
│       ├── index.html    # Interface em pt-BR
│       └── assets/
│           ├── style.css
│           └── app.js
├── tests/test_api.py
├── docs/ROADMAP.md
├── PROMPT_CODEX_CLOUD.md
├── requirements.txt
└── run.py
```

Configurações em `~/.central-ia-studio/settings.json` (diretório do perfil do usuário). Conversas ficam no `localStorage` do navegador e são apagadas quando o navegador limpa seus dados. Não há autenticação: **não exponha a porta 8765 na rede ou internet**.

## Executar testes

```bash
python -m pip install -r requirements.txt pytest
python -m pytest -q
```

## Próximos passos

Leia [docs/ROADMAP.md](docs/ROADMAP.md) e [PROMPT_CODEX_CLOUD.md](PROMPT_CODEX_CLOUD.md).

## Referências técnicas

- [llama.cpp — documentação do servidor](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- [KoboldCpp — API](https://koboldcpp.net/docs/api/overview/)
- [KoboldCpp — streaming](https://koboldcpp.net/docs/api/streaming/)

## Limitações da versão 0.1.0

- Não gerencia diretamente o processo KoboldCpp nem altera sua interface interna.
- Sem instalação em um clique, sem binário EXE próprio e sem gerenciamento de downloads de GGUF.
- Sem autenticação, login remoto, nuvem, RAG, ferramentas de agentes ou multimodalidade.
- Algumas versões de motor ignoram opções de amostragem extras.
- Por segurança a API externa só é aceita via loopback, não na internet nem em outros dispositivos.
- A conexão com a API do KoboldCpp requer que o KoboldCpp já esteja iniciado com um modelo.
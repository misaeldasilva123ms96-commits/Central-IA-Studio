# Central IA Studio

Prévia funcional 0.1.0 de um gerenciador leve de IA local em português brasileiro.
Interface React compilada, API Python, SQLite e adaptador HTTP/CLI para KoboldCpp.
Sem Electron, Docker, Node.js em produção, telemetria ou downloads automáticos.

## Executar a entrega de fontes no Windows

1. Extraia o ZIP em uma pasta gravável. Instale Python **3.12 x64** se necessário.
2. Execute `PREPARAR_WINDOWS.cmd` uma vez e autorize nele o download de dependências.
3. Abra `INICIAR_CENTRAL_IA_STUDIO.cmd`. O navegador abrirá em `http://127.0.0.1:8765`.
4. Em **Configurações**, informe a URL do KoboldCpp ou o caminho do executável confiável que você já possui.
5. Em **Modelos**, adicione sua pasta (sugestão: `D:\MODELO LOCAL`), selecione um GGUF,
   ajuste o perfil e clique **Iniciar**. Se outro modelo estiver ativo, pare o motor gerenciado primeiro.
6. Converse. Para interromper, use o botão do chat. Para sair, feche o gerenciador com Ctrl+C na janela do console.

O frontend já vem compilado. Não é necessário npm no computador de uso.
O ZIP de fontes **não é um executável Windows autossuficiente**. O workflow manual
`.github/workflows/windows.yml` prepara esse pacote em runner Windows, sem publicar release.
Não foi acionado nesta sessão. Consulte [instalação](docs/INSTALACAO_WINDOWS.md).

## Funcionalidades entregues

- Descoberta recursiva e leitura limitada de metadados GGUF, sem copiar modelos.
- Início/parada do motor próprio, porta ocupada, logs, perfis por caminho do modelo.
- Chat streaming, sistema, histórico pesquisável, edição, regeneração, continuação, Markdown/código e cópia.
- Saída numérica acima de 2048, contagem pelo template do backend, limites explícitos, aviso de truncamento.
- Pedidos de thinking por modo/template; raciocínio separado quando retornado pelo motor.
- Benchmarks opt-in, resultado integral, comparação, CSV/JSON, métricas reais do sistema.
- SQLite com integridade referencial, backup, importação/exportação de perfis, tema claro/escuro.

## Desenvolver na nuvem/Linux

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt pytest==8.3.5
npm ci --prefix frontend
npm run build --prefix frontend
.venv/bin/python -m pytest -q
.venv/bin/python run.py --no-browser
```

No Windows, use `.venv\Scripts\python.exe`. Não execute o EXE Windows em Linux.
`python scripts/package_source.py` gera o ZIP de fontes. Para preparar o pacote
Windows, consulte o script PowerShell e a documentação de instalação.

## Limites desta entrega

Sem inferência real ou benchmark real de GGUF na nuvem. Compatibilidade das famílias
Qwen, DeepSeek, MiniCPM, Granite, Ministral e LFM não foi certificada por nome.
O parser informa o que consta no arquivo; o carregamento real decide a compatibilidade.
O desempenho no i5-7200U/8 GB e o duplo clique Windows **aguardam validação no hardware**.
Nenhuma promessa de contexto ilimitado. Comece com 1,5–3B quantizado, contexto 4096,
2 threads e GPU layers 0; estas são sugestões, não resultados medidos.

Personagens, cenários, World Info, ferramentas, MCP e multimodalidade constam no
[mapa de paridade](docs/MAPA_FUNCIONALIDADES.md), sem telas falsas.
Veja [resultados de testes](docs/RESULTADO_TESTES.md), [pendências](docs/PENDENCIAS.md)
e [engenharia reversa](docs/ENGENHARIA_REVERSA.md).

Licença AGPL-3.0-or-later. Consulte LICENSE, NOTICES.md e docs/LICENCAS_E_ORIGENS.md.

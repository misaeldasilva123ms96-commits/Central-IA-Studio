# Entrega Central IA Studio 0.1.0

Implementação funcional de um gerenciador local em português: frontend compilado,
API Python, adaptador KoboldCpp, SQLite, leitura GGUF, processos, chat com streaming,
controle de parâmetros/contexto, histórico, benchmarks opt-in, métricas e logs.

Branch criada: `feat/central-ia-studio`. Nenhum merge, push, PR remoto ou release.
O projeto inicialmente continha somente .gitkeep; ele foi preservado. Toda a
implementação foi feita neste repositório e os anexos originais não foram alterados.

## Grupos de arquivos adicionados

- backend/: app.py (rotas/SSE), domain.py (validação/argv), engine.py (motor),
  gguf.py (leitor), storage.py (SQLite), __init__.py.
- frontend/: fontes React/CSS, package.json, lock e dist compilado.
- run.py, INICIAR_CENTRAL_IA_STUDIO.cmd, PREPARAR_WINDOWS.cmd.
- scripts/: build Windows, empacotamento de fontes e inventário de licenças Python.
- tests/: 19 testes pytest e dois roteiros de navegador; pytest.ini.
- .github/workflows/windows.yml: execução manual, testes, PyInstaller, smoke e artefatos.
- README, LICENSE, NOTICES, avisos de dependências, requirements e .gitignore.
- docs/: engenharia reversa, fontes/hash, arquitetura original e nova, APIs/parâmetros,
  paridade, instalação Windows, resultados, pendências, design e changelog.

## Resultado verificado

19 testes de API/domínio/persistência/processo passaram com dependências fixadas.
Build do frontend e dois fluxos de navegador passaram. Chat E2E usa uma API de
fixture explícita e comprovou envio de `max_tokens=5000`. Arquivos e hashes exatos
da entrega estão em SHA256SUMS.txt; o ZIP de fontes passou verificação de integridade.
Capturas de design e teste estão em docs/design; chat-fixture.png representa teste,
não uma inferência real. Detalhes dos comandos/falhas em RESULTADO_TESTES.md.

## Como experimentar no Windows

Extraia o pacote, execute PREPARAR_WINDOWS.cmd (requer Python 3.12 x64 e confirmação
para baixar dependências) e depois INICIAR_CENTRAL_IA_STUDIO.cmd. Configure o motor
confiável e a pasta dos modelos que você já possui. Frontend pronto, sem npm no uso.
O pacote autossuficiente de Windows ainda precisa ser gerado pelo workflow/manual.

## Critérios do pedido

| Critério | Situação |
|---|---|
| Duplo clique Windows | Scripts preparados; não validado em Windows |
| Interface português | Verificada no navegador Linux |
| GGUF reais | Parser validado por fixtures; seus modelos não foram disponibilizados |
| Conexão KoboldCpp | Adaptador baseado na fonte e testado contra fixture; motor real pendente |
| Streaming | Verificado no transporte HTTP e navegador com fixture |
| Saída >2048 | Envio 5000 confirmado por API e browser com fixture; modelo real pendente |
| Thinking modelo/template | Pedido de kwargs verificado; efeito real por modelo pendente |
| Conversas e parâmetros | Persistência/exportação testadas |
| Informações verdadeiras | Métricas do sistema reais; ausências indicadas; testes artificiais identificados |
| Leve no notebook 8 GB | Arquitetura sem Electron/Node runtime; desempenho do notebook não medido |

O EXE anexado excedeu o limite de transferência de 32 MiB. Não foi possível validar
seu hash, versão ou estrutura. A fonte v1.124.2 foi analisada no commit imutável
referenciado em docs, sem executar binário desconhecido. Não foram baixados modelos.

Não há paridade completa: Story/Adventure, personagens, World Info, MCP e
multimodalidade continuam planejados. O mapa registra IMPLEMENTADA/PARCIAL/PLANEJADA
sem oferecer controles falsos. A aprovação definitiva permanece no Windows do usuário.

O ZIP está na raiz do repositório como `central-ia-studio-source.zip` (~1,8 MB),
com `SHA256SUMS.txt` ao lado. A pasta de downloads designada para esta conversa
não pôde ser criada por permissão do ambiente; não foi fornecido link inexistente.
O pacote foi extraído em diretório limpo e o servidor e os assets compilados
foram carregados com sucesso em smoke test Linux.

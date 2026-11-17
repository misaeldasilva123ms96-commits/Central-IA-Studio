# Auditoria anterior à implementação dual

Base: main após PR #10 (9b6f2e2). Escopo: launcher, backend, armazenamento,
processos, empacotamento, frontend, testes, workflow e documentação existentes.

- build_windows.ps1 constrói apenas ONEDIR. package_windows.py copia o motor para
  a pasta engine ao lado do EXE. O workflow só inicia/testa um formato.
- backend/app.py encontra frontend/fontes via __file__, que funciona sob o diretório
  de recursos do PyInstaller. domain.bundled_engine usa sys.executable, que não
  aponta para recursos extraídos no ONEFILE. Precisam de um resolvedor comum.
- run.py usa dados junto ao EXE congelado, sem pasta compartilhada entre instalações,
  migração, bloqueio por base ou distinção explícita de portátil. App direto usa
  ROOT/data, inadequado se ROOT for a pasta temporária de extração.
- engine.start já impede duplicação por porta e só stop() encerra seu próprio
  Popen. Não há garantia de árvore de processos em encerramento abrupto Windows.
- HTTPX é recriado em cada consulta ao motor. O parser GGUF relê cabeçalhos em
  cada varredura; já tem limites e não carrega tensores. Ambos permitem otimização
  verificável sem tocar no algoritmo de inferência.
- run.py importa backend/uvicorn antes de freeze_support. attachments importa
  Pillow e pypdf também no gerenciador, apesar de parsing isolado em workers.
- Perfis, conversas, anexos, revisões, memória, extensões e conexões MCP ficam no
  SQLite. Recursos materializados de plugins ficam sob data/extensions. GGUFs e
  projetos permanecem externos. Backup SQLite já usa a API de snapshot.
- O frontend já oferece seleção de pastas, perfis por caminho, diagnósticos GGUF,
  capacidade de visão/ferramentas, histórico e benchmark opt-in. Preservar o design;
  acrescentar identificação do build, diretório persistente e saída controlada.
- Versão é repetida no bootstrap e rodapé. Falta commit/identidade verificável.
- Publicação é manual em workflow_dispatch; deve exigir os dois resultados e
  hashes correspondentes antes de disponibilizar futuros releases autorizados.

Decisão: PyInstaller em dois modos com argumentos/recursos comuns; dados Windows
em LocalAppData por padrão; portátil explícito; migração sem overwrite; Job Object
para os descendentes do gerenciador; testes Windows reais e relatório JSON medido.
ONEFILE extrai para temporário antes do Python: não é execução em memória. Falha
pré-Python e limpeza após morte abrupta são limitações do bootloader, documentadas.

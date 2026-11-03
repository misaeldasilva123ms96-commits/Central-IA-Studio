# Arquitetura do Central IA Studio

Frontend React/Vite compilado → API FastAPI → adaptador HTTP/CLI KoboldCpp.
SQLite mantém configurações, perfis, conversas, mensagens e avaliações; psutil lê
métricas reais. O navegador e o motor não acessam o SQLite diretamente.

| Componente | Arquivos | Responsabilidade |
|---|---|---|
| Interface | frontend/src/{main,Chat,Parameters,Modules}.jsx | Navegação, chat, formulários e apresentação |
| API | backend/app.py | Validação, SSE, limites e persistência de resultados |
| Motor | backend/engine.py | Conexão HTTP local, tokens, streaming, processo próprio |
| Domínio | backend/domain.py | Parâmetros tipados e CLI sem shell |
| Modelos | backend/gguf.py | Leitura limitada de cabeçalho; nunca carrega tensores |
| Persistência | backend/storage.py | SQLite WAL, transações, FK, backup |
| Inicialização | run.py, arquivos CMD | Loopback, porta, navegador e encerramento |

O adaptador concentra particularidades KoboldCpp. Um futuro llama.cpp server
precisará implementar capacidades, contagem/template, geração, abort e identificação;
não é seguro trocar só a URL assumindo compatibilidade de todas as APIs nativas.

Uma geração por instância é permitida. Edição e troca de conexão durante geração
são rejeitadas. Um lock serializa geração; outro serializa start/stop. Cada conexão
SQLite é curta, transacional e tem foreign_keys ativado. Uma falha após início
salva resposta parcial com motivo erro. Regeneração arquiva a resposta anterior
em avaliações, preservando evidência. Continuação cria uma nova mensagem assistente,
com o histórico terminando em assistente, conforme suporte do backend.

Limites: outros clientes podem alterar o motor externo; não há isolamento de sessão
no próprio KoboldCpp nem lock distribuído. O motor externo não é encerrado pelo
Central. RAM de processo externo não é inferida por nome; aparece indisponível.

## Segurança implementada

CLI usa lista de argumentos e shell=False, caminho de GGUF deve estar na biblioteca,
template deve existir e ter extensão/tamanho permitido. Executável é uma escolha
explícita do usuário. Nenhuma função executa código retornado pela IA. Host/Origin
e token por execução reduzem ataques de navegador contra o serviço local. HTTPX
ignora proxies do ambiente e redirects, e a URL só aceita loopback HTTP e porta alta.
Renderização Markdown não permite HTML bruto; CSP bloqueia scripts externos e frames.
CSV neutraliza fórmulas em células. O parser limita leitura a 64 MiB de cabeçalho.

Não é sandbox contra programas locais maliciosos ou contra executáveis escolhidos
pelo usuário. Logs do motor podem conter prompts porque o motor imprime seu próprio
stdout. Não publique logs/banco sem revisá-los. O log do gerenciador é rotativo;
engine.log ainda requer rotação manual entre sessões.

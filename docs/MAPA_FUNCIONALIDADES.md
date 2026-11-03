# Mapa de funcionalidades e paridade

Status funcional desta versão, não certificação no hardware de destino.
IMPLEMENTADA significa código conectado a uma operação real e teste pertinente;
PARCIAL indica uma fronteira ou validação ainda faltante. Nada foi marcado como
INCOMPATÍVEL sem evidência de impossibilidade.

| Recurso | Status | Limite / evidência |
|---|---|---|
| Interface pt-BR, temas, responsividade | IMPLEMENTADA | Build e navegador desktop/mobile |
| Descoberta recursiva GGUF, tamanho, caminho | IMPLEMENTADA | Fixtures v3, inválidos, deduplicação |
| Metadados/diagnóstico por modelo | PARCIAL | v2/v3 little endian, cabeçalho limitado, não certifica execução |
| Pastas configuráveis, preservação de modelos | IMPLEMENTADA | Somente leitura, sem mover/sobrescrever arquivos |
| Iniciar/parar/trocar modelo | PARCIAL | Processo próprio testado em fixture POSIX; Windows pendente; troca manual parar/iniciar |
| Modelo ativo | PARCIAL | Nome reportado; caminho somente em processo próprio |
| Perfis por modelo, importação/exportação | IMPLEMENTADA | Validação Pydantic, SQLite; seleção manual do modelo |
| Samplers e saída acima de 2048 | IMPLEMENTADA | Mock HTTP comprova max_tokens=5000; sem limite visual 2048 |
| Inicialização avançada CPU/KV/FA/template | PARCIAL | Argumentos verificados contra código; execução real pendente |
| Thinking rápido/profundo/personalizado | PARCIAL | kwargs reais, exige Jinja; sem certificação por família |
| Chat e streaming | IMPLEMENTADA | SSE via backend e integração browser com fixture HTTP |
| Sistema, múltiplas conversas, pesquisa, edição | IMPLEMENTADA | SQLite e API; sistema salvo ao gerar |
| Regenerar, continuar, interromper | PARCIAL | Integração com fixtures; continuação depende do template |
| Exportar Markdown e JSON | IMPLEMENTADA | Exportação conversa própria; sem importação de histórias Lite |
| Código e cópia | IMPLEMENTADA | Blocos Markdown/code; sem syntax highlighting por linguagem |
| Uso de tokens/estatísticas por mensagem | PARCIAL | Campos retornados em usage, ausentes ficam indisponíveis |
| Limites solicitados/efetivos/alocado/ocupado | IMPLEMENTADA | Contagem pelo motor antes de gerar; sem medição contínua do KV |
| Truncamento e aviso de contexto | IMPLEMENTADA | finish_reason length, redução explícita, recusa sem espaço |
| Estimativa de duração | PARCIAL | Média de medições anteriores do mesmo nome de modelo; sem calibragem por hardware/perfil |
| Benchmark e histórico de avaliações | IMPLEMENTADA | Registro opt-in e respostas antigas de regeneração, CSV/JSON |
| Comparação lado a lado | IMPLEMENTADA | Dois resultados selecionáveis; sem avaliação automática |
| RAM/CPU/paginação/estado/logs | PARCIAL | Métricas reais do sistema; externo sem PID não tem RAM do motor; paginação pode faltar no Windows |
| Porta ocupada e recuperação de conexão | IMPLEMENTADA | Checagem de bind, polling reconecta; não reinicia geração silenciosamente |
| Assistente de configuração | PARCIAL | Formulário inicial com teste de conexão, não wizard em múltiplos passos |
| Instruct | PLANEJADA | Atualmente somente conversa por messages |
| Story | PLANEJADA | Sem editor de história |
| Adventure | PLANEJADA | Sem parser de ações |
| Personagens e cenários | PLANEJADA | Sem armazenamento/importação de cartões |
| Memória | PARCIAL | Sistema persistente; sem memória dinâmica/seleção automática |
| World Info | PLANEJADA | Sem acionamento por chaves |
| Author's Note | PLANEJADA | Sem inserção por profundidade |
| Editor de texto | PARCIAL | Edição individual de mensagens; sem documento narrativo |
| Importação de histórias Lite/cartões | PLANEJADA | Export próprio não equivale a compatibilidade Lite |
| Ferramentas, execução de código e MCP | PLANEJADA | Nenhum executor habilitado |
| Multimodalidade | PLANEJADA | Texto apenas |
| ZIP Windows autossuficiente | PLANEJADA | Script e CI preparados; runner não acionado |

Origem do inventário: KoboldCpp get_capabilities/rotas e Lite generate_savefile,
kai_json_load, kai_scenario_load, display_memory_tab e painel MCP. Referências
imutáveis constam em ENGENHARIA_REVERSA.md. Não se afirma paridade integral.

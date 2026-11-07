# Studio 0.5 — Plugins e Habilidades

## Navegação

Modelos, Parâmetros, Benchmarks e Monitoramento passam para o menu expansível do
rodapé, junto de Configurações e tema. O topo não duplica o botão claro/escuro.
Conversas, Agente e Plugins e Habilidades permanecem na navegação principal.

## Marketplace local

O catálogo inicial contém 8 plugins e 8 habilidades mantidos pelo Central IA.
Os 16 itens iniciais são incluídos no aplicativo; instalar os registra e ativa
localmente. Também é possível importar pacotes e cadastrar conexões MCP. A loja
não sincroniza automaticamente o diretório ou as contas do ChatGPT.
Há pesquisa, categorias, filtro de instalados, detalhes, instalação, ativação,
desativação e remoção reversível. O estado fica no SQLite e entra no backup. Alterações usam uma transação
serializada para preservar atualizações simultâneas de extensões diferentes.

Os quatro plugins correspondentes aos recursos existentes vêm instalados e ativos
para preservar o comportamento anterior: internet, documentos, arquivos do projeto
e terminal. Calculadora, JSON, CSV e relógio são opcionais, disponíveis para instalar.

| Plugin | Função e limites |
| --- | --- |
| Pesquisa na internet | Busca e leitura públicas; depende do botão Internet. |
| Leitura de documentos | Trechos/busca apenas em anexos desta conversa. |
| Arquivos do projeto | Leitura/listagem; escrita somente Build e conforme aprovação. |
| Terminal do projeto | Programas locais somente Build e conforme aprovação. |
| Calculadora | Aritmética sem eval, nomes, funções, arquivos ou rede; expressão de até 500 caracteres, 80 nós e expoente absoluto até 12; ponto flutuante. |
| Assistente JSON | Valida/formata JSON de até 20.000 caracteres; resultado até 40.000. |
| Análise de CSV | Coluna numérica explícita, separador e marca decimal; até 20.000 caracteres/1.000 linhas/64 colunas; filtro opcional de negativos, contagem de inválidos e soma/mínimo/máximo. Até 50 dígitos significativos e 20 casas decimais; sem separadores de milhares implícitos. |
| Data e hora | Data/hora real do computador em UTC. |

Ativar plugin não muda Internet, Plan/Build ou permissões. A lista é filtrada no
backend e cada chamada deve pertencer ao conjunto oferecido naquela tarefa; o modelo
não consegue executar um plugin ausente ou desativado pedindo seu nome. Mudanças de
instalação/ativação são bloqueadas enquanto uma geração está em andamento.

## Habilidades

Oito conjuntos de instruções: revisão de código, Python, planejamento, redação,
resumos, análise de dados, tradução e pesquisa com fontes. Não são modelos novos,
nem acrescentam ferramentas ou permissão para executar ações.

Depois de instalar e ativar, selecione até três no botão Habilidades do compositor,
na conversa ou no agente. Os nomes/instruções são exibidos nos detalhes. A seleção
é salva com a sessão e reaparece ao abrir a conversa. O backend valida instalação e
ativação e inclui as instruções na preparação real do pedido, antes de contar tokens.
Desativar/remover uma habilidade retira sua seleção do compositor.

A qualidade e o uso correto das ferramentas dependem do modelo carregado. O protocolo
nativo ou textual e os limites de etapas/tokens da versão anterior continuam válidos.

## Validação

Testes verificam estado persistido, controles de instalação/ativação/remoção,
filtragem por modo/Internet, bloqueio de execução de plugin não instalado, instruções
na requisição real e sessão, aritmética e rejeição de código, JSON, CSV e relógio.

O roteiro Chromium usa uma fixture HTTP identificada, ferramentas locais reais e
projeto temporário. Instala/desativa/ativa a calculadora, instala habilidade, seleciona
no compositor, comprova resultado real 30 e instruções no pedido, recarrega a sessão,
consulta catálogo/pesquisa e verifica navegação, rodapé, temas e telas menores.
Não é benchmark de qualidade de um modelo treinado, nem teste de loja externa.

Resultado local: 77 testes integrados e os três roteiros Chromium passaram,
incluindo regressões de chat/cópia, E2E de limites/benchmark e o catálogo novo.

## Formatos externos e funcionamento no estilo Codex

Além dos 16 itens iniciais, o catálogo importa SKILL.md e pacotes ZIP. A importação
mostra habilidades, instruções, arquivos, servidores e avisos antes de confirmar;
a confirmação fica vinculada ao SHA-256 dos bytes revisados. Importar não inicia
servidores nem executa scripts.

Formatos aceitos:

- Habilidade independente: SKILL.md com frontmatter YAML contendo name e description,
  corpo de instruções, referências, scripts e assets opcionais no ZIP.
- Layout portátil Agent Plugins: plugin.json na raiz, skills/ e mcp.json.
- Layout legado Codex: .codex-plugin/plugin.json, skills/ e .mcp.json.
- agents/openai.yaml: política allow_implicit_invocation e dependências MCP com URL.
  Dependências sem configuração utilizável precisam ser cadastradas pelo usuário.

A compatibilidade cobre esses componentes, não todas as extensões do catálogo
proprietário do ChatGPT/Codex. Hooks, apps exclusivos da conta, telas MCP Apps,
OAuth interativo e transferência de sessões da OpenAI não são implementados.
O app avisa sobre componentes reconhecidos que não executa.

ZIP: até 8 MiB no upload, 200 entradas, 20 MiB expandidos e 2 MiB por arquivo.
Até 20 habilidades e 8 servidores por pacote. Caminhos absolutos, travessia de
pastas, links simbólicos, nomes ambíguos e nomes reservados do Windows são recusados.
YAML usa carregador seguro sem aliases/objetos executáveis. Recursos originais ficam
no SQLite e no backup; cópias de trabalho são materializadas na pasta privada do app.

## Seleção automática e recursos

Com a seleção automática ligada no compositor, o modelo recebe nomes/descrições de
até 16 habilidades instaladas e pode usar load_skill quando uma for relevante. O
conteúdo é carregado sob demanda, sem executar código. A política de opt-out em
agents/openai.yaml é respeitada; habilidades com opt-out ainda podem ser escolhidas
manualmente. Há limite conjunto de três habilidades por tarefa.

A carga automática retorna até 4.000 caracteres de instruções, informa truncamento
e permite consultar o SKILL.md completo por trechos com read_skill_resource. Recursos
só podem ser lidos por IDs selecionados/carregados e dentro da pasta da habilidade.
O loop e o contexto continuam limitados: habilidades grandes podem exigir contexto
maior ou consultas adicionais. A seleção correta depende do modelo, não é garantida
por um teste de transporte.

Scripts usam run_skill_script somente no Agente Build com projeto escolhido e plugin
Terminal ativo. A confirmação mostra o comando real; Ask e Auto pedem aprovação,
Full segue a autorização escolhida. Python, JavaScript, PowerShell e shell usam
runtimes instalados no computador. Plan não executa scripts. Variáveis de raiz
PLUGIN_ROOT/CLAUDE_PLUGIN_ROOT e SKILL_ROOT são disponibilizadas. Não existe sandbox
para esses programas, como já ocorre com comandos normais do Build.

## Conexões MCP

O cliente usa o SDK MCP Python 1.30.0 e suporta STDIO e Streamable HTTP. Cada conexão
é cadastrada sem iniciar programa/requisição; o usuário confirma Conectar a cada
abertura do app. Uma tarefa dedicada mantém transporte e sessão no mesmo ciclo de
vida, inclusive encerramento e interrupção. Nenhuma conexão é restaurada em segundo
plano sem esse consentimento.

Depois de conectar, escolha até oito ferramentas por servidor; no máximo 16 entram
em uma tarefa. Descoberta suporta até oito páginas/256 ferramentas e catálogo de até
1 MiB. Esquemas de entrada são limitados e referências externas são recusadas.
Somente ferramentas conectadas, selecionadas e com plugin de origem ativo são
oferecidas. Texto e conteúdo estruturado são retornados na sequência da conversa;
resultados são limitados a 40.000 caracteres no histórico e 6.000 no contexto do
modelo. Imagens/áudio retornados por MCP não recebem análise multimodal nesta etapa.
MCP prompts/resources não são expostos como ferramentas nesta etapa.

Conversa e Agente Build podem usar MCP; Plan não oferece ferramentas MCP, pois o
cliente não pode garantir a ausência de efeitos apenas por uma anotação do servidor.
MCP HTTP requer o botão Internet ligado na conversa. STDIO inicia processos com
rede/permissões próprias. Chamadas MCP pedem aprovação em Ask e Auto; Full dispensa.
A autorização do botão Internet para busca/leitura nativa permanece inalterada.
Interromper encerra a conexão e o processo local; não desfaz ações já realizadas por
um serviço externo.

Autenticação: Bearer e env/headers com referências ${VAR}, ${env:VAR} ou $VAR. Os
valores digitados ao conectar ficam só em memória, não entram no SQLite/backup e não
são enviados ao modelo como configuração. Configurações e arquivos importados são
dados do usuário: não inclua credenciais literais em comandos, URLs ou arquivos.
Credenciais via ambiente são lidas do ambiente do computador. Serviços que exigem
OAuth interativo precisam de suporte adicional ou de autenticação alternativa
oficialmente aceita pelo próprio serviço.

O pacote de exemplo pode ser baixado no marketplace. Ele inclui um SKILL.md com
referência/script e um servidor MCP de soma usando apenas Python padrão. Seu código
está em examples/extensions/central-demo. Importação e chamada real do exemplo são
testadas; o Python para executar o servidor é um pré-requisito externo. O motor de
inferência continua incluído no EXE, sem exigir Python/Node para conversa local.

Referências de formato consultadas:
- https://developers.openai.com/codex/skills/
- https://developers.openai.com/plugins/build/plugins
- https://developers.openai.com/codex/mcp/

Resultado local após a compatibilidade externa: 99 testes integrados passaram,
além dos roteiros de navegador. STDIO e HTTP autenticado foram exercitados contra
servidores locais reais; o exemplo distribuído foi importado e retornou soma 42.

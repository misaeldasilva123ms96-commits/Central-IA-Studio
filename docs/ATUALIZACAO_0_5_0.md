# Studio 0.5 — Plugins e Habilidades

## Navegação

Modelos, Parâmetros, Benchmarks e Monitoramento passam para o menu expansível do
rodapé, junto de Configurações e tema. O topo não duplica o botão claro/escuro.
Conversas, Agente e Plugins e Habilidades permanecem na navegação principal.

## Marketplace local

O catálogo inicial contém 8 plugins e 8 habilidades mantidos pelo Central IA.
Os 16 itens iniciais vêm instalados e ativos, com opção de desativar ou remover
localmente. Escolhas anteriores de desativação e remoção são preservadas. Também é possível importar pacotes e cadastrar conexões MCP. A loja
não sincroniza automaticamente o diretório ou as contas do ChatGPT.
Há pesquisa, categorias, filtro de instalados, detalhes, instalação, ativação,
desativação e remoção reversível. O estado fica no SQLite e entra no backup. Alterações usam uma transação
serializada para preservar atualizações simultâneas de extensões diferentes.

Os oito plugins vêm instalados: internet, documentos, arquivos do projeto,
terminal, calculadora, JSON, CSV e relógio. O mesmo vale para as oito habilidades.

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
conteúdo é carregado sob demanda, sem executar código. O campo allow_implicit_invocation do pacote é preservado como recomendação.
Conforme a preferência do usuário, o automático começa ligado: o controle geral e o
controle individual no catálogo têm precedência, inclusive para pacotes que recomendam
uso manual. Ambos são salvos no banco e podem ser desativados; seleção manual continua
disponível. A conversa também tem um controle próprio de automático. Há limite conjunto de três habilidades por tarefa.

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

Resultado local final: 112 testes integrados passaram,
além dos roteiros de navegador. STDIO e HTTP autenticado foram exercitados contra
servidores locais reais; o exemplo distribuído foi importado e retornou soma 42.

O controle geral de automático fica em Plugins e Habilidades, e cada habilidade tem
seu próprio controle de Uso automático. Ambos ficam ligados por padrão para itens
instalados/ativos. A recomendação allow_implicit_invocation:false do pacote é
mostrada, mas não impede o usuário de autorizar o automático. Desligar o automático
não desinstala a habilidade nem impede a seleção manual.


### Catálogos online, básicos e horários

Os oito plugins e as oito habilidades básicas começam instalados e ativos. As
escolhas já salvas de remover ou desativar continuam valendo. O catálogo local
agora usa cartões compactos e o filtro Todos / Instalados / Não instalados.

A aba Catálogos online consulta explicitamente quatro fontes públicas: OpenAI
Skills (curated), Anthropic Skills, Claude Plugins Official e Vercel Agent Skills.
Também aceita um repositório público GitHub próprio, com pasta opcional no
formato `/tree/branch/pasta`. Branches com barras, repositórios privados, pacotes
npm exclusivos do OpenCode, hooks e interfaces proprietárias não são suportados.
O catálogo identifica SKILL.md e plugins Codex/Claude com habilidades ou MCP;
plugins apenas com comandos, hooks ou LSP são omitidos. Uma consulta real nesta
atualização encontrou 39 + 18 + 17 + 9 opções; essa quantidade varia nas fontes.

A consulta fixa um commit, mostra origem e instruções, baixa os arquivos de apoio
da pasta selecionada e exige confirmação da prévia. A instalação usa exatamente
o pacote revisado (hash e prévia com validade de dez minutos). Servidores MCP
continuam desconectados até confirmação própria. Limites: 100 itens por fonte,
oito fontes em cache por vinte minutos, 200 arquivos, 20 MiB expandidos e 8 MiB
comprimidos por pacote. O GitHub público pode impor limites de consulta. Catálogo
local e itens instalados continuam disponíveis sem internet. Licenças e requisitos
devem ser consultados na origem de cada pacote.

Perguntas e respostas novas mostram HH:mm abaixo da mensagem, no fuso horário
do navegador. A data completa aparece ao passar o mouse. O horário da pergunta
é salvo ao aceitar o envio e o da resposta no início da geração. Editar preserva
o horário original; uma nova geração recebe um novo registro. A migração é
aditiva e não inventa horários para mensagens antigas que não tinham esse dado.
Horários e botões ficam fora da cópia do conteúdo da mensagem.


Prévias desta revisão: [conversa com horários](previews/v0.5.0/conversa-com-horarios.png),
[tela pequena](previews/v0.5.0/horarios-mobile.png) e
[catálogo online em fixture de navegador](previews/v0.5.0/catalogo-online-fixture.png).
O teste da interface online usa uma fonte determinística; a consulta às quatro
fontes públicas e o download real foram verificados separadamente. A regressão
de chat também verifica que horários não entram na cópia do conteúdo e que o
protocolo textual mantém streaming e métricas de decodificação.


### Painel de trabalho e ajustes da sessão

O horário das mensagens do usuário agora ocupa uma linha no fluxo normal, fora
do balão. Isso evita sobreposição em mensagens curtas como “ola”, inclusive em
320 pixels de largura.

O painel de trabalho agrupa pensamento retornado pelo motor, comentários
intermediários e chamadas de ferramentas. Enquanto o modelo trabalha, ele abre e
mostra o tempo decorrido. Recolhe ao começar o texto da resposta e ao concluir;
pode ser expandido pelo usuário. Pedidos de aprovação mantêm o painel aberto.
A nova sequência salva também os trechos de pensamento, preservando sua posição
em relação às ferramentas após recarregar. Históricos anteriores sem essa
sequência continuam exibindo o pensamento agregado que havia sido salvo.
Somente o pensamento efetivamente retornado pelo motor é mostrado. O cronômetro
atualiza um componente próprio; não redesenha os trechos de pensamento a cada
segundo. O tempo final é o tempo total da geração registrado pelo backend.

O botão de interromper do topo foi removido. O botão no compositor continua
interrompendo geração e ferramentas. Ao navegar para outra área durante uma
tarefa, uma faixa permite voltar à conversa ou ao agente em execução.

Ajustes da sessão inclui modelo/contexto carregado, instruções e exportação do
histórico, modo de resposta, pensamento, saída, temperatura, amostragem avançada,
contexto/CPU, lote, cache, Flash Attention, visão e template. Campos que exigem
reinício estão marcados. O perfil é validado pelo backend ao salvar, com erro
local e opção de exportar JSON. Durante a geração, os campos ficam bloqueados.

O teste `tests/browser/check_work_panel.py` usa o Studio e uma fixture HTTP de
modelo pausada em cada etapa. Verifica cronômetro, ordem pensamento/ferramenta,
recolhimento antes do fim do streaming, histórico, aprovação nos demais roteiros,
horário em mensagem curta, salvamento e bloqueio do perfil, um único botão de
interromper e ausência de erros no navegador. As capturas dessa revisão ficam
no artefato de testes de interface do GitHub, fora das fontes do produto.


### Modos com parâmetros e memória automática

Antes desta revisão, Rápido e Profundo alteravam somente a solicitação de
pensamento; temperatura e saída continuavam com os valores anteriores. Agora o
seletor aplica presets reais, compartilhados pelo backend e pelas duas telas.

| Modo | Temperatura | Saída solicitada | Pensamento solicitado |
| --- | ---: | ---: | --- |
| Rápido | 0,40 | 512 | Desativado |
| Equilibrado | 0,70 | 1536 | Padrão do modelo |
| Preciso | 0,20 | 1024 | Padrão do modelo |
| Código | 0,25 | 2048 | Padrão do modelo |
| Criativo | 0,95 | 2048 | Padrão do modelo |
| Profundo | 0,60 | 3072 | Ativado |
| Personalizado | Definida pelo usuário | Definida pelo usuário | Definido pelo usuário |

Os presets também definem Top-P, Top-K, Min-P e penalidade de repetição. Os valores
completos estão em `MODE_PRESETS`, em `backend/domain.py`, e no campo
`mode_presets` do bootstrap. Clientes da API podem aplicar um preset explicitamente
com `POST /api/profiles/preset`, passando mode e profile. Importar/salvar um perfil
preserva seus valores explícitos; o nome do modo não sobrescreve silenciosamente
parâmetros enviados pela API. Rápido e Profundo mantêm prioridade sobre o campo thinking, como antes; Personalizado respeita esse campo. Na interface, alterar manualmente saída, pensamento
ou amostragem muda o seletor para Personalizado. Contexto, CPU, RAM, cache,
projetor, template e opções de compactação são preservados ao trocar o modo.
Preciso reduz a diversidade da amostragem; não garante exatidão factual. Pensamento
e velocidade continuam dependentes do modelo e do template.

Contexto é a janela total compartilhada entre instruções, histórico, anexos,
ferramentas e a resposta. Saída máxima é o teto por resposta, incluindo pensamento
emitido pelo motor. O limite efetivo é calculado com a contagem do próprio motor
e a janela realmente carregada. Um preset não aumenta contexto nem RAM.

A compactação automática começa ligada, com gatilho padrão de 80% da janela
ou menos espaço do que a reserva de saída desejada. Preserva dois turnos recentes
(contando o envio atual), e solicita uma memória de até 512 tokens, limitada
adicionalmente pela janela. Esses controles podem ser ajustados/desativados em
Memória da conversa. A compactação acontece entre envios, antes da resposta;
ferramentas de uma tarefa em andamento continuam sujeitas aos limites da janela.

O mesmo motor local resume o prefixo antigo em lotes medidos pelo tokenizer,
com no máximo oito etapas e cinco minutos por tentativa. Não usa ferramentas,
não acessa internet e permite interrupção pelo botão normal. A memória anterior
é incorporada ao resumir novos trechos. Conteúdo resumido é marcado como dado
não confiável dentro da primeira mensagem preservada do usuário, sem promover
esse conteúdo a instruções de sistema. Mensagem atual, instruções atuais e
turnos recentes não são cortados. Resultados extensos de ferramentas entram como
trechos marcados, com referências; estado de revisões/desfazer também é registrado.
Imagens antigas são referenciadas por nome/ID, sem inventar uma análise visual.

O checkpoint fica no SQLite e no backup, com hash das mensagens e do estado das
ferramentas cobertas. Editar mensagens antigas ou desfazer uma ação invalida o
resumo. O histórico original permanece disponível para leitura e exportação.
A interface permite ver e descartar a memória. Desativar a compactação impede
seu uso na próxima geração. Aumentar a quantidade de turnos preservados também
reconsidera o checkpoint. Somente um resumo concluído que reduz a entrada e
permite gerar substitui a memória anterior. Falha, resumo truncado ou cancelamento
não apagam mensagens nem alteram sua ordem. Se a mensagem atual/instruções não
couberem sozinhas, o app informa o limite; resumir não amplia a janela física.

Resumos podem omitir ou distorcer detalhes e a primeira compactação pode demorar
no CPU. Não é uma compressão sem perdas. O painel mostra progresso, mensagens
cobertas e contagem de entrada antes/depois. O tempo total de trabalho inclui a
preparação/compactação; velocidade de geração e tokens de saída continuam
medidos para a resposta principal.

Validação desta revisão: 124 testes de backend, incluindo envio efetivo dos valores
dos seis presets ao motor, orçamento de tokens, resumo em lotes, persistência,
backup, reutilização, invalidação, descarte e cancelamento. O roteiro
`tests/browser/check_presets_context.py` verifica os sete modos em ambas as telas,
valores visíveis, Personalizado ao editar, memória preservada após recarregar,
originais intactos, descarte e tela pequena. Modelos HTTP controlados verificam
o fluxo; a qualidade semântica no modelo treinado do usuário exige teste real.

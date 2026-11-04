# Central IA Studio 0.3.0 — atualização em desenvolvimento

## Contrato desta entrega

Chat com estrutura inspirada no ChatGPT, preservando identidade Central IA e
inferência local. Os controles existentes continuam acessíveis. A biblioteca deve
aceitar caminho digitado ou escolhido visualmente; navegação ocorre no computador
que executa o Studio, sem upload. Conversas e perfis anteriores continuam legíveis.
O motor recebe melhorias verificáveis de controle de memória/contexto e diagnóstico,
sem prometer qualidade ou velocidade de um modelo treinado que não foi medido.

## Interface

Tema escuro com fundos #212121, #171717 e #303030; texto #ececec, destaque verde
restrito à conexão e foco. Tema claro usa branco e cinzas neutros. Fonte de sistema,
controles de 11–14 px, conteúdo 15 px/1.8, coluna de conversa até 768 px (820 em
monitores grandes). Barra superior de 56 px (52 no celular). Sidebar de 248 px,
recolhível no desktop e sobreposta com fundo de fechamento no celular. Histórico
pesquisável com renomear/excluir; exclusão só ocorre após confirmação.

Mensagens de usuário alinhadas à direita, respostas sem contêiner decorativo,
Markdown/GFM idêntico durante e após streaming, cores de sintaxe locais em nove
linguagens. Copiar usa o texto original, inclusive indentação; seleções preservam
tabelas, e HTML do modelo não é executado. Parâmetros completos ficam no módulo
próprio; Ajustes abre um diálogo com foco contido e fechamento por Escape.

Compositor aumenta até 140 px, Enter envia e Shift+Enter insere linha. Durante
composição IME, Enter não envia. A rolagem acompanha o final enquanto o usuário
estiver próximo dele; ao subir para ler, permanece onde ele escolheu e oferece
um botão para voltar à última mensagem. Nova conversa também aceita Ctrl+Shift+O.

## Seletor de pasta

Selecionar pasta abre um diálogo com unidades do Windows / pasta pessoal / raiz
no Linux, navegação por subpastas e Pasta acima. Caminho pode ser editado dentro
do diálogo. Cancelar/Escape não adiciona pasta. Usar esta pasta preenche a entrada;
Adicionar pasta confirma o cadastro. Caminhos com espaços e acentos são mantidos.
Apenas diretórios são listados. Erros de permissão e caminhos inexistentes são
informados. Cadastrar/remover pastas não altera a conexão do motor ativo.

## Central Engine 0.2.0

A base llama.cpp permanece fixada no commit já validado; houve alteração real na
CLI nativa e nas políticas de execução. Cache adicional de prompts agora tem teto
padrão 256 MiB, configurável de 0 a 8192; anteriormente seguia o padrão upstream de
8192 MiB. Não é um teto da RAM total: modelo, KV e buffers são separados. Perfis
antigos recebem os campos novos ao carregar, preservando seus valores existentes.
O cache do slot já existia e agora pode ser desligado por requisição. A interface
exibe tokens reutilizados quando a API fornece esse dado. Context shift desativado
impede descarte silencioso de contexto. Estados de carregamento, pronto e falha
diferenciam inicialização de desconexão; parada solicitada não é exibida como falha.

## Verificação e limites

Testes de API/persistência, integração com binário nativo e navegador são executados
antes da entrega. A fixture GGUF possui pesos aleatórios, não treinados: ela permite
verificar inferência, reutilização, overflow e interrupção, sem avaliar qualidade ou
comparar velocidade com Ministral real. As capturas de interface usam uma fixture
HTTP identificada, sem conversas reais do usuário. A validação Windows fica no CI.

O conceito visual foi gerado antes da implementação. A comparação deve cobrir
hierarquia/coluna, cores, tipografia, componentes, controles e responsividade.
Conteúdo das capturas é dado de teste; nome do modelo, histórico e métricas vêm
desse teste, sem reproduzir valores inventados do mockup. A marca continua textual,
sem o logotipo ilustrativo do conceito. Instruções de sistema, exportação e conexão
continuam visíveis por serem funções reais do produto. Esses são desvios intencionais.

Esta entrega não adiciona GPU, multimodalidade, agentes, busca na web ou modelos
treinados próprios. A evolução competitiva começa por fluxo consistente, biblioteca
usável e diagnóstico verificável, mantendo esses recursos maiores como trabalho futuro.

## Evidência local e comparação visual

31 testes pytest passaram (um aviso de depreciação em dependência de testes).
Build Vite passou; Chromium verificou envio otimista, sistema personalizado,
seleção/carregamento de conversa, rolagem durante streaming, cópia de código
colorido e tabelas, troca de abas, restauração em erro, seletor de pastas e sua
confirmação/cancelamento, renomeação, exclusão confirmada/cancelada, pesquisa e
sete viewports: 1586×992, 1440×900, 1366×768, 1024×600, 390×844, 390×500 e 844×390.
O E2E anterior de 5000 tokens solicitados, benchmark e regeneração também passou.

No binário nativo compilado para Linux, o prompt repetido reutilizou 559 tokens;
com cache desligado, reutilizou zero. Entrada excedente foi rejeitada com HTTP 400.
O mesmo teste gerou 2050 tokens com pesos aleatórios, interrompeu e recuperou a
geração, e validou Studio → processo nativo → SSE → SQLite. Não é benchmark de
modelo treinado e não comprova ganho de velocidade no notebook do usuário.

As imagens do conceito e do navegador foram inspecionadas diretamente no mesmo
ciclo de QA, incluindo desktop na resolução nativa do conceito (1586×992):

| Ponto | Comparação e resultado |
| --- | --- |
| Estrutura | Sidebar, seletor de modelo, conversa centralizada e compositor inferior mantidos; inspector passou a diálogo. |
| Cores | Fundos neutros #212121/#171717/#303030; superfícies sem gradientes decorativos. |
| Tipografia | Fonte de sistema legível e hierarquia separada entre conteúdo, controles e detalhes; código em monoespaçada. |
| Componentes | Balão à direita, resposta aberta, toolbar fora do código, botão de envio circular e ícones outline. |
| Responsividade | Menu sobreposto no celular, campo acessível e sem overflow de documento nos sete tamanhos. |
| Conteúdo visível | Mensagem de sistema, exportação, status e módulo Conversas foram preservados como desvios funcionais registrados; modelo, histórico e texto vêm da fixture. |
| Marca | Marca textual preservada; ícone ilustrativo do conceito não foi incorporado. |

A estrutura visual foi verificada contra o conceito, com os desvios explícitos
acima. Prévia: [capturas e conceito](previews/v0.3.0/README.md). Os ZIPs Windows,
seus hashes e o smoke test do EXE são verificados pelo workflow da PR antes da
entrega do pacote. Nenhum merge ou lançamento automático faz parte desta atualização.

A revisão da PR também identificou um diálogo de histórico oculto ao renomear ou
excluir pela sidebar estando em outro módulo. Os diálogos agora são portados para
o body, fora do contêiner oculto do chat. O teste cobre renomear/excluir a partir
de Modelos e garante que Ctrl+Shift+O não troque a conversa com um diálogo aberto.
O build reutilizável do motor só é aceito após conclusão com sucesso, igualdade
da árvore engine e verificação dos SHA-256; o teste nativo é repetido mesmo ao
reutilizar o binário, seguido de novo empacotamento e smoke test do Studio EXE.

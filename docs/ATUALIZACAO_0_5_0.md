# Studio 0.5 — Plugins e Habilidades

## Navegação

Modelos, Parâmetros, Benchmarks e Monitoramento passam para o menu expansível do
rodapé, junto de Configurações e tema. O topo não duplica o botão claro/escuro.
Conversas, Agente e Plugins e Habilidades permanecem na navegação principal.

## Marketplace local

O catálogo inicial contém 8 plugins e 8 habilidades mantidos pelo Central IA.
Os pacotes são incluídos no aplicativo; instalar registra e ativa o item localmente,
sem baixar ou executar código de terceiros. Não é uma loja de extensões remotas.
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

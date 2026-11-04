# Changelog

## 0.4.0 — em validação

Anexos por botão +, arrastar/soltar e colar, com originais no banco e extração local
limitada de documentos. Consulta de trechos/busca em anexos para não colocar todo
o documento no contexto. Visão por modelo + mmproj, detectada pela capacidade real.
Interface ajustada à referência aprovada, marca e ações inline, menu de permissões
sem corte. Modo Agente com Plan/Build, projeto selecionado, aprovação por ação,
políticas Ask/Auto/Full e desfazer com proteção contra edições posteriores.
Ferramentas públicas de busca/leitura de internet, fontes e resultados persistidos.
Central Engine 0.3 com mmproj CPU explícito. Nenhum download automático de modelos.


## 0.3.0 — Chat, motor e distribuição organizados

Chat com histórico lateral pesquisável, balões, compositor expansível, código com
cores e ajustes em painel recolhível. Renomear/excluir conversas, confirmação de
exclusão e temas claro/escuro. Seletor de diretórios locais mantendo a entrada por
texto; pastas podem ser cadastradas sem parar um motor em uso.

Central Engine 0.2.0: teto de cache adicional de prompts configurável (256 MiB
por padrão), controle de reutilização por requisição e contagem de tokens
reutilizados. Context shift desativado, estados de carregamento/erro explícitos
e perfis antigos completados com novos campos sem alterar os valores salvos.


Distribuição separada em aplicativo Windows e fontes/documentação completas.
Pasta inicial com iniciador e guia curto; runtime, motor, licenças e acesso offline
às fontes preservados. ZIPs validados, sem modelos ou dados pessoais incluídos.

## 0.2.1 — lançado

Balão do usuário imediato, restauração do rascunho em erro, cabeçalho compacto
e layout preso ao viewport com rolagem interna. Conversa preservada ao trocar
de módulo, código/copiar com marcação sem SVG, sistema padrão pt-BR editável
e estatísticas de tempo mais explícitas. Controle de thinking baseado no template
carregado e estimativas separadas por motor/perfil.


## 0.2.0 — Central Engine incluído

Motor C++ CPU próprio sobre llama.cpp MIT, sem dependência de KoboldCpp.
CLI validada, diagnóstico, contagem real com template, streaming e cancelamento.
Integração e descoberta automática no Studio, fontes/licenças no pacote e build
Windows com teste nativo usando pesos aleatórios, sem baixar modelos treinados.


## 0.1.0 — 2026-11-03

Primeira implementação de Central IA Studio: frontend pt-BR compilado,
gerenciador Python/SQLite, descoberta GGUF, CLI KoboldCpp segura, chat SSE,
parâmetros/contexto/thinking, histórico, benchmark opt-in, métricas e logs.
Adicionados testes de integração com fixture HTTP e processos controlados,
roteiro Windows, empacotamento de fontes, workflow Windows manual e documentação
baseada em fontes oficiais. Sem inferência real ou executável Windows gerado.

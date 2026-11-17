# Dados compartilhados e migração segura

## Padrão

ONEFILE e ONEDIR usam **%LOCALAPPDATA%\CentralIAStudio**. Ao trocar apenas o
formato, não copie banco, GGUF ou perfis: ambos abrem a mesma base. O aplicativo
bloqueia uma segunda instância que tente usar essa base, mesmo em outra porta.
Versão do esquema é a mesma em ambos; uma base com esquema futuro é recusada,
sem remover tabelas. Atualizar o EXE não substitui o diretório persistente.

O SQLite mantém conversas, anexos, perfis, benchmarks, revisões, memória de
contexto, extensões e MCP. A pasta extensions e logs também são persistentes.
Modelos e projetos continuam nos caminhos externos configurados.

## Atualização de versões com data junto ao EXE

1. Feche a versão antiga e faça um backup em Configurações.
2. Ao executar a nova versão numa pasta com a base antiga data, se o destino
   compartilhado estiver vazio, ela é copiada automaticamente por snapshot SQLite.
3. É criado um backup antes de transformar configurações. A origem nunca é apagada.
4. Se a base antiga estiver em outra pasta, execute:

   CentralIAStudio.exe --migrate-from "C:\instalacao antiga\data"

5. Se já houver dados no destino, não há sobrescrita ou mesclagem. A base antiga
   é preservada e um aviso indica seu caminho. Use --data-dir para abri-la
   explicitamente, ou escolha um destino vazio para a cópia. Não copie bancos
   uns por cima dos outros. A migração pode recusar links ou banco inconsistente.

Os backups da cópia e migration.json ficam no novo diretório. O caminho conhecido
do antigo motor integrado é normalizado para detecção automática; caminhos de
motores externos, GGUFs e projetos não são alterados. Arquivos GGUF encontrados
na antiga pasta de dados não são copiados: ficam na origem, com a lista no relatório.
Não apague instalações antigas se você guardava modelos dentro delas.

A migração é para uma base nova, não sincronização contínua com um aplicativo
antigo. Não continue gravando na versão antiga após trocar. Se houver duas bases
com dados, não fazemos uma mesclagem destrutiva: solicite um plano de importação
com backups e revisão antes de qualquer substituição.

## Portátil ou pasta escolhida

- --portable: usa data junto ao EXE e verifica permissão de escrita.
- --data-dir "D:\Central dados": usa a pasta escolhida em ambos os formatos.
- CENTRAL_DATA_DIR: alternativa por variável de ambiente, com prioridade abaixo
  de --data-dir. Não combinar com --portable.

Portátil é explícito; não funciona num diretório sem permissão. Instalações
portáteis em pastas diferentes não são magicamente a mesma base: use --data-dir
comum para alternar. Para migrar a uma pasta escolhida ainda vazia:

CentralIAStudio.exe --data-dir "D:\Central dados" --migrate-from "C:\antiga\data"

Recursos _internal/_MEI são somente recursos; --data-dir dentro da extração é
recusado. O lock é liberado pelo sistema após falha do processo. Credenciais MCP
informadas na conexão continuam só em memória, como antes; não são migradas.

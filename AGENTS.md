# Central IA Studio

As distribuições oficiais Windows são ONEFILE (`CentralIAStudio.exe`) e ONEDIR
(`Central-IA-Studio-Windows-x64.zip`). Use sempre o mesmo código, versão, commit,
frontend, motor e esquema de dados. Diferenças só de empacotamento/inicialização.
O pipeline deve construir e testar ambas separadamente; nenhuma falha pode ser
ignorada para aprovar a atualização. Os modelos GGUF permanecem externos.

Não faça merge nem publique releases sem autorização explícita do usuário.
Não apague dados de origem ou versões anteriores. Migrações não podem sobrescrever
bases existentes; mantenha backup consistente do SQLite e a origem intacta.
Consulte docs/ONEFILE_WINDOWS.md e docs/MIGRACAO_DE_DADOS.md ao mudar empacotamento,
caminhos, inicialização ou persistência. Preserve os controles de Agente/MCP.

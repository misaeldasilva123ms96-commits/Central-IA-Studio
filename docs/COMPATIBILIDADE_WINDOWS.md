# Compatibilidade da distribuição 0.6

| Item | ONEFILE | ONEDIR |
| --- | --- | --- |
| Plataforma | Windows x64 | Windows x64 |
| Código, frontend e recursos | Mesmo commit/payload | Mesmo commit/payload |
| Motor | Central Engine CPU, mesmo SHA-256 | Central Engine CPU, mesmo SHA-256 |
| CPU do motor | AVX2/FMA/F16C/BMI2 | AVX2/FMA/F16C/BMI2 |
| Python/Node de sistema para o app | Não | Não |
| GGUFs | Externos | Externos |
| Dados padrão | LocalAppData/CentralIAStudio | LocalAppData/CentralIAStudio |
| Esquema e perfis | Mesmo esquema | Mesmo esquema |
| Recursos de Agente/MCP/anexos | Mesmo código e políticas | Mesmo código e políticas |
| Instalação sem escrita | Dados/extração em local gravável | Dados em local gravável |
| Extração temporária | Necessária a cada execução | Sem extração de instalação |

O runner usado é Windows Server 2022 x64. A execução real do EXE e do motor é
testada nele; Windows 11 no i5-7200U/8 GB continua exigindo validação no computador
alvo. Nenhum dos aproximadamente 17 GGUFs do usuário foi certificado por esses
ensaios: o modelo de CI é minúsculo, de pesos aleatórios e sem treinamento.

O resultado obrigatório de cada formato e de intercâmbio bidirecional fica em
TEST_RESULTS.json. BUILD_REPORT.json registra medidas e limitações, sem projetar
resultados do runner no computador do usuário. Uma falha bloqueia a aprovação
conjunta e o envio dos executáveis pelo workflow.

Durante revisão, downloads são artefatos do CI com o prazo de retenção do GitHub.
Após autorização para release, o workflow manual exige ambos os formatos do
commit exato aprovado e publica ambos, sem modificar lançamentos antigos.

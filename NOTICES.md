# Origens e avisos

Central IA Studio 0.1.0 — implementação nova distribuída sob AGPL-3.0-or-later.
O texto integral está em LICENSE. Não se reivindica autoria do KoboldCpp,
KoboldAI Lite, llama.cpp ou de suas dependências. Não foram copiados logotipos,
interfaces, código C/C++ ou Python desses projetos. A integração é por CLI/HTTP.
A licença escolhida para o Central não altera a licença dos componentes externos.

Referências estudadas: KoboldCpp (LostRuins e colaboradores), tag v1.124.2,
commit 6d2fedf8624e5f05926af3191f9efdcb13c4133c, AGPL-3.0;
KoboldAI Lite (KoboldAI e colaboradores), commit
42032c7acfc194d262de9d9ae86160555e0ab47f, AGPL-3.0.
Os repositórios não integram o pacote, exceto o texto padrão da licença AGPL.

O motor KoboldCpp é fornecido separadamente pelo usuário. Sua redistribuição
exigiria distribuir os avisos e fontes correspondentes de todos os componentes.
Não há motor, modelo GGUF ou binário de terceiros neste pacote de fontes.

Frontend compilado contém React/React DOM (Meta, MIT), Lucide (ISC),
react-markdown, remark-gfm e dependências transitivas (licenças por pacote em
THIRD_PARTY_FRONTEND.txt e frontend/package-lock.json).
Backend depende de FastAPI (MIT), Uvicorn (BSD-3-Clause), HTTPX (BSD-3-Clause),
psutil (BSD-3-Clause) e suas dependências. O build Windows coleta as respectivas
metainformações; confira também os avisos de PyInstaller (GPL com exceção de bootloader).

Para fornecer o código correspondente: mantenha o arquivo
central-ia-studio-source.zip ao lado da aplicação; o pacote Windows o inclui
no servidor em /api/source e na raiz do pacote. Modificações devem atualizar esse
arquivo e preservar LICENSE e avisos conforme a licença aplicável.

## Central Engine (novo componente)

A partir da integração do Central Engine, o pacote Windows inclui nosso executável
CPU construído sobre llama.cpp MIT, com avisos, fontes upstream e patches na pasta
CentralIAStudio/engine. As fontes do aplicativo continuam sem binários. A CLI e as
rotas do motor são código novo sob MIT (engine/NOTICE.md); o motor é separado do
aplicativo AGPL e usa HTTP local. O KoboldCpp continua sendo alternativa externa.
As descrições anteriores sobre ausência de motor referem-se à entrega 0.1.0.

# Licenças, origens e arquivos de distribuição

Studio: AGPL-3.0-or-later, com texto em LICENSE. O código-fonte correspondente fica
embutido em `_internal/central-ia-studio-source.zip` e é servido em `/api/source`,
acessível em Configurações. A reorganização dos downloads preserva esse acesso offline.

Central Engine: CLI e adaptações próprias sobre llama.cpp/ggml MIT, na revisão
fixada em engine/CMakeLists.txt. O motor é processo separado, com fontes da CLI,
patches, testes e build em `central-engine-source.zip`; a revisão upstream completa
está em `llama-cpp-source.zip`. Ambos acompanham o ZIP Fontes e Documentação.
Não é um núcleo matemático reescrito do zero. KoboldCpp continua como integração
externa opcional; seu EXE não é distribuído no pacote.

O ZIP Windows preserva LICENSE/NOTICE do motor e third-party-licenses.zip em
`CentralIAStudio/engine`. Licença do Studio e inventários completos ficam em
`CentralIAStudio/licencas`. `_internal` mantém os recursos originais do runtime.
Não remova esses diretórios para tentar distribuir apenas o EXE.

Dependências Python estão em requirements.txt; frontend e transitivas em
frontend/package-lock.json. THIRD_PARTY_FRONTEND.txt reúne os avisos npm, incluindo
highlight.js BSD-3-Clause. THIRD_PARTY_PYTHON.txt é regenerado no build Windows
com as versões observadas naquele ambiente. A licença do app não substitui as
licenças dessas dependências.

Central-IA-Studio-Fontes-e-Documentacao.zip reúne fontes, licenças e documentação
completas para consulta e recompilação. O SHA256SUMS.txt do lançamento cobre os dois
ZIPs. Ao modificar código/frontend/motor, reconstrua os arquivos correspondentes
antes de publicar. A publicação é uma operação separada dos testes de cada PR.

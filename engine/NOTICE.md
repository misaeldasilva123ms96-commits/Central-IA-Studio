# Central Engine — origens

A CLI, políticas de inicialização, diagnóstico e as rotas de compatibilidade do
Central Engine foram implementadas pelo projeto Central IA Studio (2026), sob MIT.
A inferência, GGUF, ggml, templates e servidor de geração são do **llama.cpp**, dos
autores ggml, sob MIT. Não são uma implementação de inferência criada do zero.

Revisão upstream fixada: d1044bc82712fbf08996080bef6298b24a27e9c7.
https://github.com/ggml-org/llama.cpp/tree/d1044bc82712fbf08996080bef6298b24a27e9c7

O texto MIT original está em LICENSE. As dependências do snapshot (incluindo
cpp-httplib, nlohmann/json e minja) têm seus avisos preservados em
third-party-licenses.zip. As fontes upstream estão em llama-cpp-source.zip e as
modificações/CLI em central-engine-source.zip. O patch adiciona rotas e desativa
configurações implícitas do llama.cpp; não apaga avisos de autoria.

Não contém código ou binários do KoboldCpp. Não inclui modelos treinados.
O aplicativo Central IA Studio permanece AGPL-3.0-or-later; o motor é um programa
separado, com licença MIT, comunicado por HTTP local.

# Licenças e origens

Fontes verificadas: [KoboldCpp LICENSE.md](https://github.com/LostRuins/koboldcpp/blob/6d2fedf8624e5f05926af3191f9efdcb13c4133c/LICENSE.md) e
[Lite LICENSE.md](https://github.com/LostRuins/lite.koboldai.net/blob/42032c7acfc194d262de9d9ae86160555e0ab47f/LICENSE.md), ambos texto AGPL-3.0. Há componentes com outras
licenças: [llama.cpp](https://github.com/LostRuins/koboldcpp/blob/6d2fedf8624e5f05926af3191f9efdcb13c4133c/src/LLAMACPP_LICENSE), [ggml](https://github.com/LostRuins/koboldcpp/blob/6d2fedf8624e5f05926af3191f9efdcb13c4133c/ggml/src/GGML_LICENSE)
e arquivos LICENSE próprios em vendor/otherarch. Não os redistribuímos.

O Central é implementação nova de gerenciador e cliente de API; não inclui o código
nem o EXE desses motores. O texto padrão AGPL foi copiado para LICENSE sem alteração.
Escolheu-se AGPL-3.0-or-later para o código novo e entrega de fontes completas.
NOTICES.md identifica autores externos, fontes e dependências. Não é parecer jurídico
sobre a classificação de uma futura obra derivada; futuras cópias exigem revisão
por arquivo. Não foram usados nome, logotipo ou identidade visual dos produtos originais.

Dependências de runtime Python são fixadas em requirements.txt; dependências do
frontend e transitivas estão em frontend/package-lock.json. Os avisos/licenças
presentes nos pacotes npm foram reunidos em THIRD_PARTY_FRONTEND.txt, inclusive
os transitivos de build. Não se apresenta apenas a licença do pacote principal
como se cobrisse toda a distribuição.

O pacote Windows deve manter o ZIP de fontes correspondente à versão compilada,
LICENSE, NOTICES e avisos de dependências. O script inclui o ZIP no bundle e o servidor
o oferece em /api/source. Se o frontend/motor for modificado, regenere o arquivo.
Não há publicação, release ou envio a terceiros nesta sessão.

# Central Engine — primeira implementação

## Entrega

Executável C++ `central-engine-nocuda.exe`, com CLI/políticas/rotas próprias,
construído estaticamente sobre llama.cpp MIT no commit
`d1044bc82712fbf08996080bef6298b24a27e9c7`. O compilador, Python e CMake são apenas
ferramentas de desenvolvimento; o motor não precisa deles no Windows de uso.
O motor não chama KoboldCpp nem depende de um EXE de terceiros em runtime.
Não se afirma que toda a inferência foi inventada pelo projeto Central.

`engine/src/main.cpp` valida CLI, arquivos, porta, CPU e cache e chama o servidor
linkado no mesmo processo. `engine/src/central_routes.h` implementa diagnóstico e
ponte de contagem/identidade/contexto. `engine/scripts/prepare_upstream.py` aplica
patch mínimo, reconstituído de `git show` sobre commit validado. O patch também
desativa configurações implícitas de ambiente/sistema do llama.cpp.

As rotas de geração OpenAI, Jinja, amostragem, leitura GGUF e kernels de cálculo
continuam sendo o código upstream. Origem explícita: engine/NOTICE.md, licença MIT,
fontes upstream e scripts/patches distribuídos no pacote.

## Integração do Studio

- Detecta `result=CentralEngine` nas capacidades do servidor.
- Descobre engine/central-engine-nocuda.exe ao lado do EXE do Studio quando não há
  caminho salvo. Preferências explícitas antigas são preservadas.
- Envia `repeat_penalty`, mantém samplers reais e usa a contagem nativa com template.
- Não aplica a reserva de 20/35% específica do KoboldCpp ao Central Engine.
- Cancelamento fecha a conexão HTTP/SSE e cancela a requisição no servidor; não
  apresenta uma chamada fictícia a /api/extra/abort. KoboldCpp mantém seu genkey.
- Contexto alocado continua vindo do servidor. Não se promete janela ilimitada.

## Escopo e limites

CPU x64 AVX2/FMA/F16C/BMI2, sem CUDA; compatível em instruções com i5-7200U.
Não é uma certificação de desempenho nesse notebook. Memória depende do modelo,
quantização e contexto. Uma geração simultânea; contexto fixado, autofit desligado.
KV quantizado exige Flash Attention; com FA desligada use f16/bf16. GPU layers >0,
backends remotos, ferramentas/MCP, downloads e multimodalidade não são expostos
pela CLI. Não há GUI separada do motor; a interface é o Studio.

GGUF do usuário não é empacotado nem baixado. O teste estrutural gera um arquivo
aleatório de ~300 KB (não treinado): carregar, contar mensagens, gerar 2050 tokens,
separar SSE, cancelar/recuperar e encerrar. Qualidade, famílias comerciais,
compatibilidade de thinking e velocidade real requerem modelos treinados e teste
no hardware de destino. Não rotulamos pesos aleatórios como modelo funcional de chat.

## Compilação e pacote Windows

O workflow Windows compila o motor por CMake/MSVC, executa teste sobre o binário
real e depois o inclui no pacote do Studio. Fontes, avisos e hashes acompanham
o motor. O smoke test do Studio extraído verifica a descoberta automática.
O pacote do motor também é disponibilizado como artefato separado.

O CI fica vinculado à PR desta implementação; a release v0.1.0 já publicada
permanece a versão anterior. Nenhuma nova release é publicada automaticamente.

## Evidência local executada nesta implementação

- CMake/Ninja/GCC Linux: compilação estática do núcleo, binário ~17 MiB.
- `engine/tests/test_engine_http.py`: binário nativo real, contexto 4096,
  2050 tokens gerados pela fixture aleatória, SSE, aplicação de kwargs Jinja na
  contagem, interrupção por desconexão, nova geração após interrupção e encerramento.
- Caminho com espaço/acento e extensão .GGUF; variável LLAMA_ARG_HOST indevida
  ignorada; opções remotas/ferramentas/GPU rejeitadas pela CLI.
- API completa Studio → processo próprio → SSE → SQLite: passou.
- 23 testes pytest passaram; frontend compilou e os dois testes de navegador
  passaram, incluindo o caminho anterior de compatibilidade KoboldCpp.

Esses resultados não equivalem ao teste Windows nem aos modelos treinados.
O resultado Windows é registrado no check da PR e nos artefatos do workflow.

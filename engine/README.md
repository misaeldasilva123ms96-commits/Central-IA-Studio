# Central Engine 0.2.0 — CPU / sem CUDA

Motor de inferência do Central IA Studio, implementado em C++ sobre llama.cpp MIT,
com CLI própria, políticas locais e compatibilidade com o gerenciador Central.
Não depende de KoboldCpp, Python ou Node.js para executar. Não é um motor neural
reescrito do zero: a base matemática, carregamento GGUF e servidor são llama.cpp.

## Executar

Requer CPU x64 com AVX2/FMA/F16C/BMI2 (o i5-7200U possui essas instruções).
Não use em CPUs antigas sem essas instruções. Builds não usam detecção nativa da
máquina de compilação nem AVX-512, CUDA, Vulkan, SYCL ou OpenMP.

No Windows, selecione `central-engine-nocuda.exe` nas Configurações do Studio.
No pacote com motor incluído, ele é detectado automaticamente na pasta `engine`
ao lado do EXE do Studio. Adicione sua pasta de modelos e inicie um GGUF.

Uso direto pelo terminal:

```
central-engine-nocuda.exe --model "D:\MODELO LOCAL\modelo.gguf" --contextsize 4096 --threads 2
central-engine-nocuda.exe --help
central-engine-nocuda.exe --diagnostico
```

Sem argumento de modelo, o motor mostra erro explicativo. Não há outro launcher
GUI: a interface é o Central IA Studio. Ctrl+C encerra o servidor em execução.
Por padrão: porta 5001, contexto 4096, 2 threads, lote 128, KV q8_0, Flash Attention.
Sem FA, use KV f16 ou bf16. Cache KV e arquitetura ainda dependem do modelo.
O Studio pode usar o arquivo `.jinja` indicado por perfil. Geração e contagem usam
o mesmo template do servidor. Thinking depende do template, nunca só do nome do modelo.

## Cache e limites de memória (0.2.0)

O cache de prefixos no slot já existia no llama.cpp e permanece habilitado. O Studio
agora permite desligá-lo por requisição (`prompt_cache`, apenas Central Engine),
e mostra os tokens efetivamente reutilizados em Detalhes da geração quando a API
os informa. Não se promete uma taxa de tokens/s: o benefício depende do prefixo
compartilhado e do modelo.

O teto padrão para snapshots **adicionais** de prompts em RAM foi reduzido de
8192 MiB (padrão upstream) para 256 MiB. Ajuste com `--prompt-cache-mib N`, de 0 a
8192, ou com Cache adicional em RAM no perfil do Studio, seguido de reinício.
Zero desativa snapshots extras, sem desligar a memória KV do contexto ou remover
o reaproveitamento do prefixo do slot. Esse teto não limita a RAM total do motor:
pesos do modelo, contexto KV e buffers continuam consumindo memória separadamente.

O motor agora inicia com `--no-context-shift`: solicitações maiores que a janela
são rejeitadas, em vez de descartar silenciosamente partes do contexto por shifting.
O Studio já conta o prompt e calcula o espaço de saída antes de gerar.

## Diferenças intencionais em relação ao KoboldCpp

Apenas texto/CPU nesta versão. Uma geração simultânea (`--parallel 1`), sem router,
sem downloads, sem interface web upstream, sem ferramentas/MCP e sem configuração
implícita herdada de arquivos/variáveis LLAMA_ARG_* do llama.cpp. Camadas GPU precisam
ser zero; lote -1 não é aceito. O contexto não é reduzido automaticamente por autofit.
Há métricas nativas em /props e API OpenAI em /v1/chat/completions.

As rotas /api/extra/version, /api/v1/model, /api/extra/true_max_context_length e
/api/extra/tokencount são compatibilidade implementada por nós, não KoboldCpp.
A contagem usa o parser real de mensagens/template do llama.cpp. O Studio detecta
`result=CentralEngine`, usa repeat_penalty e interrompe fechando a conexão HTTP,
que cancela o trabalho no servidor. Não se anuncia /api/extra/abort inexistente.

## Compilar

CMake >=3.19, compilador C++17, Git e Python 3 só no desenvolvimento. Em Windows:
Visual Studio 2022 com ferramentas C++. O CRT é estático para não exigir instalação
separada de Visual C++ Runtime. A fonte upstream é baixada por commit fixo (shallow).

```
cmake -S engine -B work/engine-build -DCMAKE_BUILD_TYPE=Release
cmake --build work/engine-build --config Release --target central-engine-nocuda --parallel 2
```

O binário fica em work/engine-build/bin (em MSVC, subpasta Release).
Para fonte existente, use `-DCENTRAL_LLAMA_SOURCE=C:/caminho/llama.cpp`;
a revisão deve ser a fixada, e o patch é reconstruído de `git show` em cada configure.
A construção padrão é CPU AVX2 estática, não uma compilação CUDA apenas renomeada.

## Testes sem baixar modelos

Instale engine/tests/requirements.txt no ambiente de teste. O gerador cria um
GGUF de ~300 KB com pesos aleatórios, não treinados. O teste real carrega esse
arquivo, conta tokens com template, gera via SSE, interrompe e verifica recuperação.
Isso prova o caminho de execução, não qualidade, compatibilidade de famílias nem
velocidade de modelos treinados. Não se apresentam esses números como benchmark.

```
python engine/tests/make_tiny_gguf.py CAMINHO_LLAMA work/tiny.gguf
python engine/tests/test_engine_http.py CAMINHO_BINARIO work/tiny.gguf
```

Os binários de entrega não incluem esse GGUF. Consulte NOTICE.md e as licenças.

# APIs e parâmetros

## Contrato oficial verificado

Base: `http://127.0.0.1:5001`. Rotas no handler de [koboldcpp.py:7461](https://github.com/LostRuins/koboldcpp/blob/6d2fedf8624e5f05926af3191f9efdcb13c4133c/koboldcpp.py#L7461)
e [koboldcpp.py:7878](https://github.com/LostRuins/koboldcpp/blob/6d2fedf8624e5f05926af3191f9efdcb13c4133c/koboldcpp.py#L7878). Respostas opcionais variam conforme o modelo carregado.

| Rota KoboldCpp | Uso no Central | Observação |
|---|---|---|
| GET /api/extra/version | Capacidades/Jinja/conexão | Não confundir com versão do protocolo Kobold /api/v1/info/version. |
| GET /api/v1/model | Identidade reportada | Caminho de arquivo só é conhecido para processo gerenciado. |
| GET /api/extra/true_max_context_length | Contexto alocado | Não usa o teto anunciado para Horde. |
| POST /api/extra/tokencount | Contar mensagens já formatadas | Envia messages e os mesmos kwargs de thinking. Falha impede geração. |
| POST /v1/chat/completions | Chat SSE | messages, max_tokens, samplers, genkey, stream e include_usage. |
| POST /api/extra/abort | Interromper geração própria | Só envia genkey ativo do Central. |
| GET /api/extra/perf | Mapeado, não usado para atribuir tokens | Evita atribuir a um chat a métrica global de outro cliente. |
| POST /api/v1/generate | Mapeado; geração nativa ainda planejada | max_length / prompt; não é a rota usada pelo chat v0.1. |
| POST /api/extra/generate/stream | Mapeado; geração nativa planejada | O adaptador v0.1 usa stream de OpenAI. |

## Efeito dos controles

| Campo | Parâmetro enviado | Exige reinício? |
|---|---|---|
| Contexto | --contextsize na inicialização e max_context_length na requisição | Para aumentar alocação: sim |
| Saída máxima | max_tokens | Não; inteiro 1–524288 sujeito a contexto |
| Temperatura, Top-P, Top-K, Min-P | temperature, top_p, top_k, min_p | Não |
| Penalidade de repetição | rep_pen | Não; intervalo conservador 1–3 |
| Threads, Threads BLAS | --threads, --blasthreads | Sim |
| Lote | --blasbatchsize | Sim; -1,16,32,64,128,256,512,1024,2048,4096 |
| Camadas GPU | --gpulayers | Sim; padrão 0 |
| Cache KV | --quantkv | Sim; f16/bf16/q8_0/q5_1/q4_0 |
| Flash Attention | ativa por padrão; --noflashattention desativa | Sim |
| Template | --jinja e --jinjatemplate arquivo local opcional | Sim |
| Thinking | chat_template_kwargs.enable_thinking e reasoning_effort | Não, mas Jinja precisa estar ativo |

Limites CLI foram lidos em [koboldcpp.py:14503](https://github.com/LostRuins/koboldcpp/blob/6d2fedf8624e5f05926af3191f9efdcb13c4133c/koboldcpp.py#L14503), linhas 14508,14521,14524,
14545–14548,14565 e14582. O aplicativo valida limites numéricos finitos e nunca
aceita argumentos extras livres. O intervalo 524288 é limite de validação da CLI,
não uma recomendação para máquina com 8 GB.

## Contabilidade de contexto

1. Consulta contexto real do motor e toma o mínimo entre alocado e perfil.
2. Conta mensagens com a API nativa, incluindo sistema e kwargs do template.
3. Aplica `min(solicitado, contexto - entrada - 8, contexto - reserva_backend)`.
4. A reserva segue o limite de `calculate_min_remain_hardlimit` (20% se entrada
   menor que 25% do contexto, caso contrário 35%, com mínimo do backend).
5. Sem espaço, recusa antes de salvar a mensagem e iniciar inferência.

**Efetivo enviado** é o limite da requisição após nossa política. O backend ainda
pode terminar antes por EOS, interrupção, erro ou regras próprias. O Central
registra tokens e motivo retornados, sem inventar a quantidade quando `usage`
não vier. O contexto ocupado é a entrada contada antes da geração, não um medidor
contínuo do cache KV. Tokens/s significa tokens de saída / tempo total, incluindo
processamento de prompt; não se apresenta como velocidade pura de decodificação.

Rápido solicita `enable_thinking=false`, esforço none; Profundo true, esforço high;
Personalizado respeita on/off/default. Nenhum modo confirma automaticamente que o
modelo obedeceu. O campo `thinking_confirmed` permanece false até existir validação
que esta versão ainda não fornece. O template GGUF pode ser detectado, mas um template
customizado ou adaptador externo pode mudar o comportamento. A contagem e a geração
precisam usar o mesmo motor sem alterações concorrentes de outros clientes.

## API do gerenciador

Prefixo `/api`: bootstrap, settings, models, profiles, engine, engine/start,
engine/stop, abort, conversations, conversations/id/export, messages/id,
generate, benchmarks, metrics, logs, backup e source. Métodos e contratos estão
nos modelos Pydantic e rotas de `backend/app.py`. Requisições mutáveis exigem
`X-Central-Token` obtido em bootstrap na mesma origem. Bind fixo em loopback;
sem CORS e sem autenticação para uso remoto (uso remoto não é suportado).

# Resultado de testes — 2026-11-03

## Ambiente e escopo

Linux x86-64, Python 3.12.14, Node 24.19.0. Runtime de teste isolado em work/venv:
FastAPI 0.115.12, Uvicorn 0.34.2, HTTPX 0.28.1, psutil 7.0.0, pytest 8.3.5.
Frontend: React 19.1.0, Vite 6.3.5; lock npm incluído. Browser final:
Playwright 1.58.0 com Chromium instalado em /usr/bin/chromium, headless.

## Evidência executada

| Comando / verificação | Resultado |
|---|---|
| `npm ci --prefix frontend` (verificação final) | Código 0; instalação limpa a partir do lock |
| `npm run build --prefix frontend` | Código 0; frontend compilado, ~403 kB sem compressão; JS ~121 kB gzip |
| `work/venv/bin/python -m pytest -q` | **19 passaram**, código 0; um aviso de depreciação anyio/Starlette |
| `python -m compileall -q backend run.py` | Código 0 |
| `python tests/browser/check_interface.py` | Passou: navegação, persistência de saída 10000, tema claro/escuro, desktop/mobile e ausência de overflow horizontal |
| `work/venv/bin/python tests/browser/check_chat.py` | Passou: chat SSE contra fixture HTTP, envio de 5000 tokens de limite, reasoning, histórico, benchmark, regeneração |
| `git diff --check` (licenças de terceiros preservadas via atributos) | Código 0; sem erros nos arquivos autorais |
| ZIP extraído em diretório limpo | Bootstrap e asset JS servidos em HTTP, código 0; Linux com dependências fixadas |
| `python scripts/package_source.py` | ZIP verificado com testzip, frontend/API presentes, sem EXE/GGUF; hash no arquivo de integridade da entrega |

Os testes HTTP usam um servidor local controlado que imita o contrato das rotas
KoboldCpp verificadas na fonte. O retorno “Olá, mundo!” e os 3 tokens dessa fixture
são **dados artificiais para teste**, não inferência nem benchmark de modelo.
O teste de processo cria um script inofensivo que aguarda e é encerrado; não executa
o anexo. No Windows esse teste POSIX é pulado e o workflow acrescenta smoke test do
EXE empacotado. Nenhum workflow Windows foi acionado nesta sessão.

### Cobertura por comportamento

- GGUF recursivo, duplicação de pasta, arquivo inválido/truncado, limites do parser.
- Perfis acima de 2048, persistência entre instâncias do Store, backup e recuperação
  não destrutiva de configuração inválida.
- Streaming SSE, mensagens/sistema, kwargs de thinking on/off, modos Rápido/Profundo,
  capacidade Jinja ausente, template customizado e flags CLI efetivas.
- Contagem/contexto: limite ajustado para 384 com entrada 7800 e janela 8192;
  entrada 8190 rejeitada antes de persistir; lock liberado em erro.
- Erro HTTP 503 preservado, regeneração arquiva resposta anterior, continuação,
  edição, exportação MD/JSON, pesquisa, logs e benchmark CSV/JSON.
- CSRF, Host/Origin, URL não local, parâmetros extras, tipo/intervalo inválido,
  modelo fora de pasta cadastrada, geração concorrente e integridade SQLite/FK.
- Início/parada do processo próprio, argv sem shell, espaço no caminho, porta ocupada,
  abort vinculado ao genkey do Central, métricas indisponíveis indicadas sem fabricação.

## Verificação visual

O controle de navegador conectado exigido pela skill Browser não estava disponível
(nenhuma ferramenta js associada); o navegador remoto disponível não compartilha o
loopback deste workspace. Usou-se Playwright/Chromium no ambiente como fallback.
Primeira tentativa usou binário headless padrão ausente; corrigido para o Chromium
já instalado, sem baixar navegador.

Inspecionamos via `view_image` o conceito `docs/design/conceito.png`, a captura desktop
e a captura mobile, no mesmo passe de QA. Verificamos desktop 1440×900 e mobile
390×844. A imagem conceitual é uma prancha com duas janelas e proporção diferente;
não há dimensão nativa única de browser equivalente. A implementação usa o navegador
real e não reproduz as molduras falsas de janela da prancha.

| Comparação | Evidência / decisão |
|---|---|
| Layout | Sidebar 220 px e inspector 280 px, chat central/compositor inferior mantidos; sem recorte de controles |
| Paleta | Graphite #111318, painel #191c23 e violeta #9c8cff aplicados; sem imagens/gradientes decorativos |
| Tipografia | Título central, hierarquia e textos de formulário legíveis; fontes de sistema para reduzir peso |
| Ícones | Lucide outline consistente em navegação, envio, conexão, salvar e ações |
| Texto principal | “Sua IA, no seu computador.”, ajuda, “Configurar conexão”, “Enviar” e navegação preservados |
| Componentes | Campos numéricos reais, bordas discretas, compositor e formulário de sessão correspondem ao conceito |
| Mobile | Menu em gaveta; inspector acessível pelo módulo Parâmetros; nenhum overflow horizontal |

Desvios intencionais necessários ao funcionamento pedido: barra de histórico/pesquisa,
mensagem de sistema, indicador de reinício, opção de benchmark e métricas reais foram
acrescentados ao conceito resumido. Modelo é campo somente leitura, pois a troca exige
seleção/início na biblioteca. Enviar fica desativado enquanto desconectado. O botão
de tema usa ação única em vez do toggle ilustrativo. Não usamos moldura de aplicativo
Windows falsa. A cópia acima da dobra difere somente por essas adições funcionais
registradas e pelo número de versão. Não se afirma equivalência pixel a pixel;
foi verificada a fidelidade da estrutura, hierarquia, paleta e componentes, com esses
desvios explícitos. Sem recortes, imagens faltantes ou erros JavaScript observados.

## Falhas encontradas durante verificação

1. Primeiro pytest coletou testes dos repositórios de referência em work e falhou
   por dependências desses projetos; pytest.ini agora limita a descoberta a tests.
2. Dependências globais eram diferentes das fixadas: criamos venv e repetimos a suíte.
3. Playwright não encontrou seu binário padrão: usamos Chromium instalado.
4. Captura da biblioteca revelou scroll da página retido após navegação: o auto-scroll
   do chat agora afeta somente o histórico e a navegação volta ao topo. Placeholders
   Windows também foram corrigidos para uma única barra invertida.
5. A primeira correção de scroll colocou um hook após o retorno condicional de
   carregamento; o teste de navegador detectou a tela sem abrir. O hook foi movido
   antes do retorno e os testes foram repetidos após a correção.
6. Repetição imediata do smoke test de pacote encontrou falso positivo de porta
   ocupada em TIME_WAIT. A sonda usa SO_REUSEADDR em POSIX e exclusividade em
   Windows; repetimos a suíte e a inicialização do ZIP duas vezes após a correção.
7. Locator de contexto não encontrou texto exato por causa do marcador ↻:
   teste usa o campo numérico acessível; sem alteração artificial do produto.

Essas falhas não foram omitidas nem tratadas como testes aprovados.

## Não validado

Execução do anexo, PE/hash, build Windows, duplo clique em Windows, carregamento de
GGUF real, obediência do thinking por família, velocidade, RAM do i5-7200U, qualidade
de resposta, consumo contínuo de KV e todos os modos de Lite. A aprovação definitiva
dos dez critérios do pedido permanece condicionada aos testes no notebook.

# Central IA Studio

Central IA Studio 0.6.0 em validação: aplicativo de IA local em português brasileiro.
Interface React compilada, API Python, SQLite, Central Engine CPU incluído e
compatibilidade com KoboldCpp externo.
Sem Electron, Docker, Node.js em produção, telemetria ou downloads automáticos.

## Duas distribuições Windows sincronizadas

| Formato | Download | Uso |
| --- | --- | --- |
| ONEFILE | **CentralIAStudio.exe** | Um arquivo necessário. Extrai recursos em TEMP ao iniciar. |
| ONEDIR | **Central-IA-Studio-Windows-x64.zip** | Extrair todo o ZIP; manter executável e pastas juntos. |
| Fontes | **Central-IA-Studio-Fontes-e-Documentacao.zip** | Fontes completas, licenças e guias; opcional para executar. |

Ambos vêm do mesmo commit/versão e pipeline, com os mesmos recursos e motor.
Não exigem Python, Node, Docker, WSL nem KoboldCpp externo. Modelos GGUF ficam
externos e compartilháveis. Plugins externos podem exigir runtimes próprios.

Dados padrão em **%LOCALAPPDATA%\CentralIAStudio**, compartilhados entre os dois.
Portátil só com **--portable**, em pasta gravável; **--data-dir** permite um local
escolhido. Consulte [migração segura](docs/MIGRACAO_DE_DADOS.md) ao atualizar uma
versão antiga com pasta data. A origem não é apagada nem bases são sobrescritas.

Versão, commit, formato e pasta dos dados ficam em Configurações. Para encerrar,
use “Encerrar aplicativo” ou Ctrl+C no console. Apenas processos iniciados pelo
app são encerrados. Navegador abre quando o serviço 127.0.0.1 estiver pronto.

Em cada PR/execução manual, o CI constrói e testa cada formato e gera hashes,
DISTRIBUTIONS.json, TEST_RESULTS.json e BUILD_REPORT.json. Se um falhar, não há
aprovação parcial nem publicação de executáveis. Releases e merges continuam
exigindo autorização; o build não publica automaticamente.

Leia [ONEFILE](docs/ONEFILE_WINDOWS.md), [desempenho](docs/OTIMIZACAO_DESEMPENHO.md)
e [comparação e limites](docs/COMPARACAO_ONEDIR_ONEFILE.md). O ONEFILE não é execução
em memória e pode ser mais lento na inicialização por extrair a cada uso.

## Executar a entrega de fontes no Windows

1. No ZIP técnico, extraia também `Fontes/central-ia-studio-source.zip` em uma pasta gravável. Instale Python **3.12 x64** se necessário.
2. Execute `PREPARAR_WINDOWS.cmd` uma vez e autorize nele o download de dependências.
3. Abra `INICIAR_CENTRAL_IA_STUDIO.cmd`. O navegador abrirá em `http://127.0.0.1:8765`.
4. Em **Configurações**, confira o Central Engine detectado no pacote, ou indique um KoboldCpp externo.
5. Em **Modelos**, adicione sua pasta (sugestão: `D:\MODELO LOCAL`), selecione um GGUF,
   ajuste o perfil e clique **Iniciar**. Se outro modelo estiver ativo, pare o motor gerenciado primeiro.
6. Converse. Para interromper, use o botão do chat. Para sair, feche o gerenciador com Ctrl+C na janela do console.

O frontend já vem compilado. Não é necessário npm no computador de uso.
O ZIP de fontes **não é um executável Windows autossuficiente**. O workflow manual
`.github/workflows/windows.yml` prepara esse pacote em runner Windows, sem publicar release.
O CI valida o pacote Windows em cada PR, sem publicar automaticamente. Consulte [instalação](docs/INSTALACAO_WINDOWS.md).

## Funcionalidades entregues

- Descoberta recursiva e leitura limitada de metadados GGUF, sem copiar modelos.
- Início/parada do motor próprio, porta ocupada, logs, perfis por caminho do modelo.
- Chat streaming, sistema, histórico pesquisável, edição, regeneração, continuação, Markdown/código e cópia.
- Saída numérica acima de 2048, contagem pelo template do backend, limites explícitos, aviso de truncamento.
- Pedidos de thinking por modo/template; raciocínio separado quando retornado pelo motor.
- Benchmarks opt-in, resultado integral, comparação, CSV/JSON, métricas reais do sistema.
- SQLite com integridade referencial, backup, importação/exportação de perfis, tema claro/escuro.

## Desenvolver na nuvem/Linux

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt pytest==8.3.5
npm ci --prefix frontend
npm run build --prefix frontend
.venv/bin/python -m pytest -q
.venv/bin/python run.py --no-browser
```

No Windows, use `.venv\Scripts\python.exe`. Não execute o EXE Windows em Linux.
`python scripts/package_source.py` gera o ZIP de fontes. Para preparar o pacote
Windows, consulte o script PowerShell e a documentação de instalação.

## Limites desta entrega

O CI testa inferência com um GGUF minúsculo de pesos aleatórios, sem treinamento. Não é um benchmark dos GGUFs reais do usuário. Compatibilidade das famílias
Qwen, DeepSeek, MiniCPM, Granite, Ministral e LFM não foi certificada por nome.
O parser informa o que consta no arquivo; o carregamento real decide a compatibilidade.
O desempenho no i5-7200U/8 GB e o duplo clique Windows **aguardam validação no hardware**.
Nenhuma promessa de contexto ilimitado. Comece com 1,5–3B quantizado, contexto 4096,
2 threads e GPU layers 0; estas são sugestões, não resultados medidos.

Personagens, cenários, World Info, ferramentas, MCP e multimodalidade constam no
[mapa de paridade](docs/MAPA_FUNCIONALIDADES.md), sem telas falsas.
Veja [resultados de testes](docs/RESULTADO_TESTES.md), [pendências](docs/PENDENCIAS.md)
e [engenharia reversa](docs/ENGENHARIA_REVERSA.md).

Licença AGPL-3.0-or-later. Consulte LICENSE, NOTICES.md e docs/LICENCAS_E_ORIGENS.md.

## Central Engine — motor próprio sobre llama.cpp

O desenvolvimento atual inclui `engine/`, nosso motor C++ de inferência CPU,
sem dependência de KoboldCpp. A inferência usa llama.cpp MIT com revisão fixada,
créditos preservados e fontes correspondentes incluídas. Não reivindicamos a criação
dos kernels de inferência. Consulte [motor](engine/README.md) e
[integração](docs/CENTRAL_ENGINE.md). O pacote validado no CI inclui o motor;
a release v0.1.0 antiga não é alterada retroativamente.

## Atualização 0.3.0

A interface passa a priorizar a conversa, com histórico lateral pesquisável,
renomeação e exclusão com confirmação. Os ajustes da sessão ficam no botão
**Ajustes**, e o seletor no cabeçalho leva à biblioteca para trocar de modelo.
**Modelos → Selecionar pasta** abre um navegador de diretórios locais: entre na
pasta e clique em **Usar esta pasta**, depois **Adicionar pasta**. Você também
pode continuar digitando o caminho completo. Não há upload nem cópia dos GGUF.

Os parâmetros completos incluem controles do cache do Central Engine 0.2.0.
Consulte [a documentação do motor](engine/README.md) e
[o relatório da atualização](docs/ATUALIZACAO_0_3_0.md). As releases anteriores
continuam disponíveis. A publicação só ocorre após validar os pacotes da versão.

## Atualização 0.4.0 em validação

A interface segue a referência escolhida, com marca, textos maiores, conversa mais
larga e ações junto às respostas. O botão **+** aceita documentos e imagens; também
funcionam arrastar/soltar e colar imagens. Originais, vínculos e revisões ficam no
SQLite e entram no backup. Tipos: texto/código, CSV, PDF com texto, DOCX, XLSX,
PNG/JPEG/WebP/GIF/BMP. Até seis arquivos de 8 MiB por envio. PDFs sem texto precisam
de OCR externo ou de páginas como imagens enviadas a um modelo de visão.

**Agente**, abaixo de Conversas, tem histórico independente. Escolha o projeto e
use **Plan** para leitura/planejamento ou **Build** para propor edições e comandos.
As permissões ficam visíveis no compositor: **Solicitar aprovação**, **Aprovar por
mim** e **Acesso completo**. Plan não recebe ferramentas de escrita/comandos em
nenhuma opção. Alterações guardam a versão anterior e podem ser desfeitas pela
interface, se o arquivo não tiver sido modificado depois.

**Internet** oferece busca pública e leitura de páginas, com resultados no histórico
de ferramentas e links para fontes. Buscas/URLs são enviadas a Bing, DuckDuckGo ou
Jina Reader quando necessário. Arquivos anexados não são enviados automaticamente
como arquivos a esses serviços; consultas propostas pelo modelo podem conter texto
da conversa. Ativar Internet autoriza buscas e leituras sem confirmação adicional,
inclusive em Solicitar aprovação. Desativar remove essas ferramentas. O botão controla as
ferramentas web, não uma firewall: comandos são programas reais com suas permissões
e podem ter rede própria. A pasta do projeto não é uma sandbox.

Imagens exigem um modelo de visão e seu **mmproj compatível**, configurado nos
parâmetros e carregado pelo motor. Não basta selecionar um modelo apenas textual.
O Studio informa a capacidade carregada e não simula reconhecimento visual.
[Guia e limites da 0.4](docs/ATUALIZACAO_0_4_0.md). A release publicada permanece
separada desta versão de teste até sua aprovação.


## Plugins e Habilidades — atualização 0.5

A navegação principal reúne Conversas, Agente e **Plugins e Habilidades**. Modelos,
Parâmetros, Benchmarks, Monitoramento, Configurações e tema ficam no menu do rodapé.

O marketplace local inicial traz **8 plugins e 8 habilidades**. Os itens vêm no app;
instalar registra e ativa a extensão no computador, sem baixar código de terceiros.
Use pesquisa/categorias e o filtro de instalados para gerenciar o conjunto. Depois de
instalar uma habilidade, escolha até três no compositor da conversa ou do agente.
Plugins ativos continuam sujeitos a Internet, Plan/Build e às permissões escolhidas.

[Catálogo, comportamento e limites](docs/ATUALIZACAO_0_5_0.md).


A atualização também importa **SKILL.md** e ZIPs nos layouts **plugin.json** portátil
ou **.codex-plugin/plugin.json** legado. Habilidades podem ser carregadas pelo modelo
sob demanda, com controles geral e individual em Plugins e Habilidades. Referências
são lidas por trechos; scripts exigem Agente Build e a aprovação correspondente.

Em **Conexões MCP**, cadastre STDIO ou Streamable HTTP, autorize a conexão e escolha
as ferramentas. Bearer/variáveis de sessão são próprios de cada serviço; não há
transferência automática de conta ou OAuth do ChatGPT. Servidores e scripts externos
podem precisar de Python, Node ou outro programa instalado; a inferência local segue
incluída no EXE. Veja os limites e componentes suportados no guia da atualização.

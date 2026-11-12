# ONEFILE e ONEDIR sincronizados — Windows x64

As duas distribuições oficiais são geradas pelo mesmo workflow e mesmo checkout:

| Formato | Arquivo necessário | Característica |
| --- | --- | --- |
| ONEFILE | CentralIAStudio.exe | Um arquivo distribuído; extrai internamente em TEMP a cada execução. |
| ONEDIR | Central-IA-Studio-Windows-x64.zip | Extrair todo o ZIP; manter _internal, engine e licencas junto do EXE. |

Mesmos frontend, backend, modelo de dados, perfis, plugins, habilidades, MCP,
anexos, agente, modos e memória de contexto. O motor é o mesmo binário validado
por SHA-256. Nenhum GGUF é incluído ou duplicado. Python/Node/Git/Docker/WSL não
são exigidos para usar o app e o motor integrado. Plugins externos podem declarar
seus próprios runtimes/serviços; importar um plugin não instala nem executa isso.
O exemplo de MCP em Python continua sendo um exemplo que exige Python; o CI testa
o SDK também com um servidor de fixture EXE independente, sem Python no PATH.

A versão, commit, formato e diretório de dados aparecem em Configurações e no
menu do rodapé. build-info.json é embutido; DISTRIBUTIONS.json e SHA256SUMS.txt
identificam os downloads. Ambos usam o mesmo payload_digest; só o campo de formato
e a disposição dos recursos são distintos. Código único; nenhuma cópia paralela.

O ONEFILE não roda inteiramente em memória. O bootloader PyInstaller extrai
bibliotecas, frontend, fontes e motor em uma pasta _MEI no TEMP antes de iniciar
Python. Precisa de espaço e permissão nesse TEMP, mesmo que o EXE esteja num
local somente leitura. Antivírus e cache do sistema afetam a primeira execução.
Os builds não têm assinatura de um editor certificado; SmartScreen pode pedir uma verificação. Confira os hashes e não desative o antivírus para contornar falhas.
Uma falha nessa extração ocorre antes do nosso código: o bootloader em console
mostra seu erro (que pode ser em inglês) e não abre o banco do usuário.

## Uso e encerramento

Execute CentralIAStudio.exe. O navegador só abre quando o servidor local está
pronto. Dados ficam em LocalAppData, nunca no TEMP. Em Configurações, “Encerrar
aplicativo” encerra o gerenciador, motor gerenciado e seus descendentes. Ctrl+C
no console também encerra. Motores externos não são mortos.

A árvore iniciada pelo gerenciador pertence a um Windows Job Object com
KILL_ON_JOB_CLOSE. No ONEFILE há também acompanhamento do pai bootloader: matar
só esse pai não deve deixar o gerenciador e o motor órfãos. Na saída normal o
bootloader limpa sua extração. Se o próprio bootloader for morto à força, a pasta
_MEI pode permanecer. Não prometemos limpeza nesse caso e não apagamos pastas
TEMP arbitrárias na próxima execução; a limpeza do Windows pode removê-las.

Consulte [compatibilidade](COMPATIBILIDADE_WINDOWS.md) e [migração](MIGRACAO_DE_DADOS.md) antes de atualizar.

## Build de desenvolvimento

Windows, Python 3.12 x64, Node 22, Git e ferramentas C++ para compilar o motor:

1. npm ci --prefix frontend e npm run build --prefix frontend.
2. Preparar o motor aprovado em work/engine-package, com licenças/fontes.
3. python scripts/python_notices.py; python scripts/package_source.py.
4. ./scripts/build_windows.ps1 (sempre ambos os formatos).

scripts/build_onefile.ps1 é um atalho para o mesmo build dual, sem criar outra
base de código. Há análises PyInstaller separadas, mas argumentos, dependências,
recursos e metadados vêm da mesma preparação. O CI testa ambos separadamente e
só envia downloads após o teste conjunto e intercâmbio de dados aprovados.

## Fontes e licenças

Fontes do Studio e licenças acompanham ambos e são acessíveis offline no app.
O ZIP Central-IA-Studio-Fontes-e-Documentacao.zip contém as fontes completas do
motor e da revisão llama.cpp, avisos e documentação. É opcional para executar;
baixe-o para consultar/recompilar o motor offline. Nenhum download é automático.
A publicação manual exige aprovação prévia, os dois formatos aprovados do mesmo
commit e hashes íntegros. O workflow de build não cria release nem faz merge.

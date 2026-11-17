# Otimizações e medição

Sem alterar kernels, quantização, limites de RAM, contexto ou parâmetros de
inferência para criar uma aparência de ganho. Central Engine mantém a revisão
llama.cpp e os mesmos flags; o cache do build continua validado por hash.

Mudanças mensuráveis isoladas:

- HTTPX compartilhado no ciclo de vida do app, no máximo quatro URLs locais,
  fechado no encerramento. Consultas não recriam o contexto HTTP a cada poll.
- Metadados GGUF em LRU de 128 entradas, por caminho/tamanho/mtime/ctime/identidade e hash dos primeiros 4 KiB (protege
  contra timestamps de escrita com baixa resolução no Windows). Cada
  retorno é copiado e mudanças do arquivo invalidam a entrada. Diretórios ainda
  são varridos, então novos modelos continuam aparecendo ao atualizar a biblioteca.
- Pillow/pypdf carregados apenas no processamento que os utiliza. Workers de texto
  não importam parsers PDF/imagem. O launcher chama freeze_support antes de carregar
  backend/uvicorn, evitando inicializar o app de novo nos workers congelados.
- Navegador abre após prontidão real, sem espera fixa; sem processos Electron.
- Parada fecha o processo gerenciado; Job Object cobre descendentes na saída abrupta.

scripts/measure_optimizations.py mede três imports por estratégia, dez consultas
HTTP por estratégia e dez varreduras de 17 cabeçalhos sintéticos por estratégia.
O baseline é a operação equivalente sem a otimização, não uma alegação de benchmark
de toda a versão anterior. Cabeçalhos sintéticos não validam 17 GGUFs treinados.
Valores reais vão em BUILD_REPORT.json; não há números inventados neste documento.

scripts/test_windows_distribution.py mede dois inícios por formato, RSS/USS do
manager, launcher e motor separadamente, JS heap do Chromium, tempo de carregar
um GGUF minúsculo, parada, extração e limpeza normal. O navegador de teste é uma
ferramenta do CI, não dependência instalada pelo aplicativo. JS heap não é RAM
completa do navegador; somar RSS pode contar páginas compartilhadas mais de uma vez.

Resultados do runner não certificam o i5-7200U/8 GB, nem modelos de vários GB.
Não há promessa de que ONEFILE use menos RAM ou inicialize mais rápido. O formato
serve à conveniência de distribuição; ONEDIR normalmente evita extração repetida.

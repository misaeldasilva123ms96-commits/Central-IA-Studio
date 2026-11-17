# Comparação das distribuições

A fonte dos valores é BUILD_REPORT.json, emitido pelo CI no mesmo commit dos
executáveis, acompanhado de TEST_RESULTS.json e DISTRIBUTIONS.json.

| Medida | Definição |
| --- | --- |
| distributed_bytes | ZIP ONEDIR versus EXE ONEFILE, bytes efetivamente baixados. |
| installed_bytes | Conteúdo instalado, sem GGUFs nem dados pessoais. |
| startup_seconds | Popen até bootstrap HTTP válido, dois inícios por formato. |
| manager_idle / launcher_idle | RSS e USS privados observados; ONEFILE tem bootloader pai. |
| manager_with_engine / engine | Consumos separados com o mesmo GGUF minúsculo. |
| frontend.js_heap_used | Heap JS após abrir a interface no Chromium de teste. |
| temporary_extraction_bytes | Recursos extraídos observados; zero no ONEDIR. |
| shutdown_seconds | Pedido local de saída até término do processo inicializador. |
| temporary_cleaned | Limpeza normal da pasta _MEI; não aplicável ao ONEDIR. |
| forced_exit_temp_remains | Diagnóstico após matar o bootloader; sobras são uma limitação conhecida. |

Os caches do sistema/antivírus não são apagados entre inícios; “primeiro” não
significa disco garantidamente frio. Migração é testada separadamente antes dos
inícios medidos. Cada formato recebe estado de teste equivalente. Não são medidas
de latência/qualidade de modelos reais do usuário.

Os testes rodam com ACL real sem escrita na instalação, PATH sem Python/Node,
Internet bloqueada por regra de firewall do executável e GGUF fora da instalação.
Incluem motor real, SSE, interrupção, SQLite após reiniciar, parser isolado,
plugin/skill, SDK MCP com servidor EXE, licenças/fontes e processo externo preservado.
Um terceiro teste abre em ONEDIR os dados escritos por ONEFILE e vice-versa.
Qualquer falha impede disponibilizar os dois arquivos como atualização aprovada.

# Pendências e próximos incrementos

## Validação necessária antes de uso estável

1. Gerar o ZIP Windows em runner autorizado e testar a partir de extração limpa.
2. Executar com KoboldCpp confiável v1.124.2 e GGUF reais, inclusive modelos citados
   pelo usuário; registrar arquitetura/quantização/template/hash e erros por arquivo.
3. Medir desempenho no i5-7200U/8 GB; não há benchmark real nesta entrega.
4. Verificar Jinja e thinking on/off por template. A variável detectada não prova
   comportamento; esforço none pode encerrar orçamento sem alterar template incompatível.
5. Validar cancelamento, continuação e encerramento Windows. O fixture de processo
   é POSIX; o workflow pula esse teste e acrescenta smoke test do EXE empacotado.

## Funcionalidades ainda ausentes / parciais

Paridade Story/Adventure/Instruct, cartões de personagem, cenários, World Info,
Author's Note, importação Lite, ferramentas/MCP, anexos multimodais, highlighting
sintático, editor narrativo, validação automática de famílias, seleção de arquivos
por diálogo nativo, restauração de backup pela UI e wizard guiado.

A troca de modelo é parar/selecionar/iniciar, sem hot-swap. Backend externo tem nome
reportado mas não PID/RAM reconhecido. Threads/KV/template de processo externo
precisam ser alterados fora do Central. Contexto ocupado é medido antes da geração.
Uso de tokens só aparece se retornado pelo backend. Estimativa de tempo é baseada
em taxa end-to-end anterior do mesmo nome de modelo; ainda não agrupa por perfil.

## Robustez futura

Rotação do log do motor; limite de retenção de históricos e avaliações; lock de
instância por diretório de dados; otimizar descoberta em bibliotecas muito grandes;
controle de tamanho do corpo HTTP; encerramento por Windows Job Object; verificação
de versão/capacidades detalhadas e teste de contrato contra processo KoboldCpp real;
lock/aviso contra clientes concorrentes no motor; empacotamento offline validado.

Não iniciar inferência automaticamente após uma falha de conexão; o usuário
precisa reenviar para evitar duplicar respostas. Sem telemetria ou downloads de
modelos/motor. Não publicar release nem fazer merge sem revisão.

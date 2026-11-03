# Central IA Studio: primeira versão local com adaptador KoboldCpp

Adiciona gerenciador Python/SQLite e frontend compilado em português para descobrir
GGUF, iniciar/parar um motor fornecido pelo usuário e conversar por streaming.
Saída acima de 2048 é enviada quando há espaço no contexto, com limites visíveis,
perfis por modelo, thinking solicitado por template, histórico e métricas.

Validação: suíte de 19 testes com fixtures HTTP/processo, build Vite e testes de
navegador desktop/mobile. Fonte KoboldCpp v1.124.2 examinada com referências
imutáveis. Sem inferência real, execução do anexo ou build Windows nesta sessão;
workflow Windows manual e roteiro de validação incluídos. Paridade faltante está
em docs/MAPA_FUNCIONALIDADES.md e docs/PENDENCIAS.md. Não foi aberto PR remoto.

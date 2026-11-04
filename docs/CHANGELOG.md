# Changelog

## 0.2.1 — em validação

Balão do usuário imediato, restauração do rascunho em erro, cabeçalho compacto
e layout preso ao viewport com rolagem interna. Conversa preservada ao trocar
de módulo, código/copiar com marcação sem SVG, sistema padrão pt-BR editável
e estatísticas de tempo mais explícitas. Controle de thinking baseado no template
carregado e estimativas separadas por motor/perfil.


## 0.2.0 — Central Engine incluído

Motor C++ CPU próprio sobre llama.cpp MIT, sem dependência de KoboldCpp.
CLI validada, diagnóstico, contagem real com template, streaming e cancelamento.
Integração e descoberta automática no Studio, fontes/licenças no pacote e build
Windows com teste nativo usando pesos aleatórios, sem baixar modelos treinados.


## 0.1.0 — 2026-11-03

Primeira implementação de Central IA Studio: frontend pt-BR compilado,
gerenciador Python/SQLite, descoberta GGUF, CLI KoboldCpp segura, chat SSE,
parâmetros/contexto/thinking, histórico, benchmark opt-in, métricas e logs.
Adicionados testes de integração com fixture HTTP e processos controlados,
roteiro Windows, empacotamento de fontes, workflow Windows manual e documentação
baseada em fontes oficiais. Sem inferência real ou executável Windows gerado.

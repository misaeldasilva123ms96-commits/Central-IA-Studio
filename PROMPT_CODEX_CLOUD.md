# Prompt pronto para o Codex na nuvem

Use este texto após colocar os arquivos deste ZIP em um repositório GitHub e conectar o repositório no Codex Cloud.

---

Você é o engenheiro principal do projeto **Central IA Studio**, um aplicativo de IA local em português que pretende oferecer mais controle e melhor experiência que interfaces simples de execução de modelos GGUF.

**Contexto:** o repositório já inclui um MVP FastAPI + frontend HTML/CSS/JS; chat em streaming compatível com API OpenAI local, ligação ao KoboldCpp existente, integração com llama.cpp e gerenciamento básico do llama-server. O alvo inicial é Windows com notebook Intel Core i5-7200U, 8 GB RAM, sem GPU dedicada, além de compatibilidade WSL Ubuntu. O desenvolvimento no Codex Cloud deve evitar exigir inferência pesada durante os testes de CI.

**Objetivo:** continuar o desenvolvimento da base existente, não reescrever do zero sem motivo. Revise arquitetura, experiência do usuário, robustez, segurança e testes e implemente as correções prioritárias de forma incremental.

**Regras obrigatórias:**
1. Crie uma branch `feat/studio-v0.2` a partir da base atual; **não faça merge automático na main**.
2. Faça auditoria estática da implementação, incluindo SSE/parsing, fallback de modelos, persistência, concorrência de chats, limite de contexto, caminho GGUF, validação de URL, gestão de subprocessos, encerramento e exposição da API local.
3. Preserve a interface em português, visual escuro moderno, responsivo, sem frameworks grandes se não forem necessários.
4. Implemente perfis de desempenho `Econômico (8 GB RAM)`, `Equilibrado` e `Avançado`, sem suposições falsas sobre VRAM ou disponibilidade de memória.
5. Mostre claramente a diferença entre `max_tokens` (limite pedido), contexto (`ctx_size`) e limite real do modelo. Permita números acima de 2048 sem prometer geração ilimitada.
6. Adicione testes unitários, de integração com provedores HTTP simulados e teste E2E leve da UI. Não exija baixar modelos GGUF para rodar a CI.
7. Não exponha portas externas, não envie arquivos pessoais à internet, não execute comandos produzidos pela IA e não incorpore binários de terceiros ao repositório.
8. Quando houver divergência entre motores, faça detecção de capacidades, e só envie parâmetros suportados.
9. Documente o setup Windows/PowerShell e WSL, migração entre PCs, logs e solução de falhas.
10. Gere relatório de mudanças, testes executados, riscos restantes e instruções de validação local.

**Critérios de aceite:**
- Projeto inicia com `python run.py` após instalar dependências.
- Site apresenta conversa nova, histórico, configuração e painel de modelos.
- Mocks KoboldCpp/llama-server transmitem streaming e erro via API sem travar.
- Ajustes persistem e os testes passam.
- PR separado aberto para revisão; sem merge automático.

Se encontrar bugs no MVP, priorize correções antes de adicionar recursos. Não anuncie como implementado nada que não tenha sido efetivamente testado.

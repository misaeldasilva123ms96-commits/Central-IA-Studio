# Central IA Studio — plano de evolução

## Versão 0.1.0: Base funcional (entregue)
- Backend FastAPI e SPA responsiva em pt-BR.
- Chat streaming com histórico no navegador.
- Compatibilidade HTTP local com KoboldCpp e llama-server.
- Configuração de amostragem e tamanho de geração, com campo até 65536 tokens.
- Catálogo de modelos locais e start/stop do llama-server.
- Testes de API básicos e CI.

## Versão 0.2.0: Qualidade e controle
- End-to-end real para KoboldCpp e llama-server, validação de compatibilidade.
- Ler metadados do GGUF (tamanho de contexto, arquitetura, quantização) sem carregá-lo.
- Opção de ajuste seguro ao limite real do modelo/contexto; aviso claro sobre RAM.
- Histórico em SQLite local com migração do localStorage e backup/exportação.
- Log rotativo e gerenciamento de erros de carregamento de motor.
- Otimização de tokens de raciocínio com modo configurável onde compatível.
- Testes de abort real, concorrência, SSE e encerramento de processo.

## Versão 0.3.0: Experiência integrada
- Instalador Windows e executável distribuível.
- Detectar instalação existente do KoboldCpp e do llama.cpp sem cópia de binário.
- Perfis de CPU e de memória de acordo com benchmark local; modo baixo consumo.
- Biblioteca GGUF com comparação dos modelos e requisitos estimados.
- Conversas, perfis e presets de prompt separados por projeto.
- Acessibilidade e mais testes de interface.

## Versão 0.4.0: Studio de programação
- Workspace local para anexar arquivos com permissões explícitas.
- Chat contextual com trechos de código e diffs de revisão antes de aplicar.
- Ferramentas externas/agentes opt-in, com sandbox e logs completos.
- Modo servidor WSL integrado com diagnóstico de rede e consumo.
- Editor de prompts com presets, versão, testes e avaliação de resultados.

## Política de segurança
- Sem telemetria por padrão, sem abrir porta pública por padrão.
- Nunca executar automaticamente arquivos sugeridos por um modelo.
- Não baixar ou incorporar código proprietário do KoboldCpp, nem contornar licenças.
- Nunca realizar merge na main sem autorização explícita.
- Branches e PRs separados; validação antes de releases.

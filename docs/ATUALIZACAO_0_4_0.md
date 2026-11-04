# Studio 0.4 — anexos, agente, internet e fidelidade visual

## Contrato e compatibilidade

Conversas antigas recebem `kind=chat` por migração aditiva; mensagens, perfis,
histórico e exportação continuam disponíveis. A execução do chat permanece local;
Internet fica desligada por padrão e é uma escolha por conversa/tarefa. O pacote
Windows conserva a organização da 0.3: aplicativo, fontes/documentação e hashes.
Nenhuma release anterior é substituída por este código de teste.

## Anexos

Botão + com opções de documentos/imagens, drag/drop no chat/agente e paste de
imagens. Até 6 arquivos de 8 MiB por mensagem; a conversa tem limite de 8 imagens.
Originais e hashes ficam como BLOBs no SQLite e entram no backup existente. A
miniatura permite baixar o original. Cópias de rascunhos não enviados podem ser
limpas após 24 horas; o arquivo original no disco nunca é removido.

Texto/código/CSV/JSON/YAML/XML, PDF não protegido com até 40 páginas, DOCX e XLSX
são extraídos localmente em processo isolado com limite de 20 segundos. Office:
até 20 MiB descompactados; XLSX: até 10 planilhas e 2.000 linhas. O texto extraído
é limitado a 60.000 caracteres, com aviso ao atingir o teto. PDF sem texto produz
aviso de OCR indisponível; não inventamos reconhecimento ou transcrição.

O prompt recebe uma prévia curta e o ID do documento. Ferramentas de leitura por
trecho e busca literal consultam o restante do texto extraído dentro da conversa,
sem expor anexos de outras conversas. Isso não é busca semântica/embeddings. Os
resultados enviados ao modelo são limitados e informam o corte. O contexto do
modelo ainda pode se esgotar; o motor não descarta histórico silenciosamente.

Imagens preservam os bytes originais e recebem uma cópia JPEG para inferência,
com até 1600 px, sem metadados e apenas o primeiro quadro de animações. A capacidade
é lida de `/props.modalities.vision`. Ela exige GGUF de visão e projetor mmproj
compatível carregados. O caminho de upload/transporte é testado com fixture;
qualidade e compatibilidade com o par treinado do usuário exigem validação real.

## Agente e permissões

Agente aparece imediatamente abaixo de Conversas e tem histórico independente.
Plan disponibiliza leitura/listagem de projeto, anexos e internet se habilitada.
Build acrescenta escrever arquivo e executar comandos. A política é aplicada pelo
backend à lista de ferramentas e a cada chamada, não apenas por instrução ao modelo.

| Opção | Comportamento |
| --- | --- |
| Solicitar aprovação (padrão) | Confirma escrita, comandos, arquivos fora do projeto/sensíveis e cada busca/leitura web. Anexos fornecidos e leitura comum no projeto dispensam nova confirmação. |
| Aprovar por mim | Autoriza leitura, internet e escrita comum no projeto. Comandos, caminhos externos, pastas de sistema e arquivos sensíveis detectados por regras ainda pedem aprovação. |
| Acesso completo | Autoriza as ferramentas disponíveis sem confirmação, inclusive arquivos fora do projeto e comandos no Build, com as permissões do usuário do Windows. |

Plan continua sem escrita/comandos em todos os níveis. Auto usa regras determinísticas,
não um classificador capaz de avaliar toda a segurança de um programa. Acesso completo
não concede privilégios de administrador nem significa que todos os formatos/modelos
são suportados. O nível escolhido é visível e persiste na tarefa; nova tarefa começa
em Solicitar aprovação e com ferramentas Internet desligadas.

A confirmação mostra o caminho absoluto, diff completo ou argv e pasta de trabalho.
Ações negadas/expiradas não executam; 180 segundos sem resposta equivalem a negar.
Há até 8 etapas/12 ferramentas por geração e orçamento de saída compartilhado.
Comandos têm até 60 segundos e 64 KiB de saída e podem ser interrompidos. Usam
programas instalados no computador; não instalamos Python/npm de desenvolvimento.
A pasta de trabalho NÃO é isolamento: comandos podem acessar arquivos e rede com
as permissões do usuário. O botão Internet controla ferramentas web, não o sistema.

Escritas UTF-8 de até 128 KiB guardam os bytes anteriores no banco e verificam o hash
antes de substituir. Desfazer pede confirmação e verifica o hash novamente; não
sobrescreve um arquivo que mudou desde a ação. A interface esconde Desfazer no Plan
e durante tarefas. O backup do banco inclui anexos/revisões, não a pasta do projeto.

Modelos com `supports_tools` usam chamadas nativas OpenAI; os demais podem usar um
protocolo JSON textual estrito, cujas mensagens de controle não são exibidas como
resposta final. A confiabilidade depende do modelo; um 3B pode não decidir/formatar
as ferramentas corretamente. Não há execução de texto livre ou inferência de permissão.

## Internet e privacidade

`web_search` usa Bing RSS e fallback DuckDuckGo, sem chave paga. `web_fetch` lê
HTML/texto público, sem executar scripts, sem cookies/sessão do navegador do usuário.
A conexão direta valida todos os IPs DNS, conecta ao IP verificado e preserva
verificação TLS por hostname. Redirecionamentos são revalidados. Endereços locais,
privados/reservados e portas diferentes de 80/443 são recusados.

Em rede com proxy que não permite CONNECT ao IP validado, pode ser usado Jina Reader,
um leitor público remoto, após validar o destino público. O domínio pode ser resolvido
por DNS-over-HTTPS do Google quando o resolvedor local não está disponível. Esses
serviços recebem a consulta/domínio/URL solicitada; não recebem automaticamente os
BLOBs dos anexos. Resultados informam a origem/provedor e são tratados como dados
não confiáveis. O modelo pode incluir texto da conversa nas consultas: o modo Ask
permite revisar esse envio; Auto/Full concedem a autorização definida acima.

Resposta web limitada a 1 MiB; trecho enviado ao modelo limitado a 14.000 caracteres.
Provedores gratuitos podem bloquear, exigir CAPTCHA ou ficar indisponíveis. A falha
é registrada como erro de ferramenta; não se fabricam resultados, fontes ou acesso
a sites autenticados. Links externos da resposta abrem em outra aba.

## Visual escolhido e verificação

Referência principal: [conceito escolhido pelo usuário](previews/v0.3.0/conceito.png).
Estado Agente: [conceito](previews/v0.4.0/conceito-agente.png), estendido pelo pedido
posterior do seletor de permissões. O logotipo PNG foi gerado a partir da marca do
conceito e usado no produto, sem imitar o logotipo de terceiros.

Em 1586×992: sidebar 292 px, cabeçalho 72 px, conteúdo 22 px, código 17 px,
marca 48 px, coluna de conversa até 1120 px. Fundos #212121/#171717/#303030;
balões à direita, respostas abertas, logo junto da resposta, ações inline abaixo,
compositor inferior largo. Controles avançados e exportação ficam em Ajustes,
preservando o espaço do chat. Telas menores usam tipografia reduzida e menu lateral
sobreposto/rolável, com campo de envio dentro do viewport.

A checagem visual compara hierarquia/colunas, cores, tipografia, marca, posição das
ações, compositor, seletores e estados responsivos. Desvios intencionais: Agente,
permissões, Internet e anexos são acréscimos solicitados; Continuar e detalhes reais
foram preservados; não incluímos microfone inativo. As imagens de teste identificam
fixtures e não representam respostas/velocidade de modelos treinados.

## Evidências

Testes reais de SQLite/migração, originais/backup, formatos de documentos, políticas
Plan/Build, aguardar/negar aprovação, gravação/undo, execução/cancelamento de comando,
DNS privado/redirecionamento, transporte multimodal e protocolo textual. Navegador
Chromium automatizado é usado porque a conexão do navegador local não está disponível.
Ele verifica upload, drag/drop, cópia, menus, permissão e seis/sete tamanhos de janela.
O CI Windows repete inferência nativa com pesos aleatórios e extrai texto/PNG/PDF
pelo EXE congelado para validar subprocessos e dependências empacotadas.

A busca/leitura pública teve teste manual real (Example Domain e consulta pública),
separado dos testes determinísticos sem rede externa. Inferência nativa de texto é
verificada com pesos aleatórios, inclusive cancelamento e 2050 tokens, sem benchmark
ou promessa de qualidade/velocidade de Ministral treinado. O suporte de visão a um
par modelo/mmproj treinado permanece dependente de validação com esse par.

### Resultado local e comparação

52 testes da suíte integrada passaram, incluindo interrupção em ambos os motores,
preservação da chave entre etapas e identificação de projetores. O roteiro novo
também verifica que a conversa não pode ser trocada durante upload. Os três roteiros de
navegador passaram: funcionalidades novas, regressões de chat/cópia e E2E anterior de
5000 tokens solicitados, benchmark e regeneração. A espera de conexão do roteiro
antigo foi ajustada de 12 para 20 segundos para acomodar o polling assíncrono; não
é uma medição de latência de inferência. O binário nativo 0.3 passou novamente nos
2050 tokens, reutilização de 559 tokens, overflow, interrupção e recuperação.

| Comparação com referência | Ajuste/resultado |
| --- | --- |
| Marca | Asset real no topo e junto do assistente; anteriormente a marca era apenas textual. |
| Coluna e tipografia | Sidebar 292 px e corpo 22 px em 1586×992, com conversa e código mais largos. |
| Ações | Copiar/Editar/Regenerar/Continuar e Detalhes junto da resposta, em vez de próximos ao compositor. |
| Cabeçalho e controles | Ajustes contém sistema/exportação; o chat principal fica livre da barra técnica. |
| Compositor | Botão + funcional, anexos, permissões, Internet e, no agente, Build/Plan e projeto. |
| Menus | Permissões renderiza no body, com posicionamento limitado ao viewport; corrigido corte lateral observado na QA. |
| Responsividade | Chat em sete tamanhos e agente em seis, incluindo 390×500 e 844×390; documento não transborda e compositor fica dentro da janela. |
| Cores e componentes | Charcoal neutro, marca teal, balão arredondado e resposta aberta; sem novos cards decorativos. |

Conceito e capturas mais recentes foram inspecionados diretamente com view_image.
A cópia acima da dobra foi conferida: novos controles são os pedidos pelo usuário;
nome do modelo/conversa e tempo vêm do teste, sem reproduzir métricas inventadas do
conceito. Desvios intencionais são os registrados acima. Capturas:
[prévias 0.4](previews/v0.4.0/README.md). Os checks da PR registram a validação Windows.

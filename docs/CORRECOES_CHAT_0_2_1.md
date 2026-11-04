# Correções de chat 0.2.1 — pacote de teste

## Problemas e comportamento corrigido

- A mensagem do usuário aparecia somente após a resposta terminar. O balão agora
  aparece antes da primeira chamada HTTP e o compositor é limpo. Se a requisição
  for rejeitada, o rascunho volta ao campo; o histórico do servidor é reconciliado
  sem duplicar mensagens ou apresentá-las como persistidas antes da confirmação.
- Chat com altura mínima fixa e cabeçalho de 83/70 px podia exceder a janela.
  Cabeçalho agora tem 56 px no desktop e 52 px no celular. O shell usa 100dvh,
  com rolagem interna de histórico, formulários e inspector. O compositor fica
  dentro do viewport, incluindo 390×500 e 844×390. Controles superiores compactos.
- A conversa/geração era perdida na interface ao mudar de módulo. O chat permanece
  montado, escondido nas outras abas; o usuário pode voltar e interromper a geração.
- Botões e SVGs ficavam dentro do pre de código. A marcação agora é pre > code,
  com toolbar fora do código; blocos sem linguagem também têm cópia. Cópia de
  seleção no chat remove SVG/ações e preserva recuos, linhas vazias e cercas.
  Não apaga a palavra literal “svg” se ela fizer parte da mensagem.
- O renderizador de Markdown/GFM é o mesmo durante streaming e após persistência.
  Os componentes de código mantêm identidade durante o polling de métricas,
  preservando seleção e rolagem dos blocos.
- Novas conversas recebem instrução padrão pt-BR e uso de blocos Markdown, visível
  e editável em Mensagem de sistema. O sistema personalizado não é apagado quando
  a primeira conversa ganha ID. Strings vazias e sistemas de conversas antigas
  são respeitados; não reescrevemos respostas nem histórico existente.
- Taxa total e tempo até primeiro trecho ficam explícitos. A taxa de decodificação
  aparece somente se o backend fornecer timings válidos. Estimativa usa histórico
  do mesmo motor/modelo/perfil e se refere a gerar todo o limite, não a prever a
  duração de qualquer resposta. Dados antigos sem perfil não entram na estimativa.
- Thinking usa declarações do template carregado no Central Engine, sem inferir
  suporte pelo nome do modelo. Ativar em template sem controle é rejeitado com
  orientação; desativar nesse caso mantém o padrão e informa a limitação. A
  presença de uma variável não comprova que um modelo treinado a obedece.

## Evidência local

26 testes pytest passaram. O teste de navegador usa uma API de fixture explícita:
retarda a criação da conversa, verifica o balão antes da resposta, preservação do
sistema, troca de aba em geração, recuperação em erro, GFM durante streaming,
cópia de código/seleção sem SVG, identidade do DOM após polling e cinco viewports:
1366×768, 1024×600, 390×844, 390×500 e 844×390. Build Vite passou.
O adaptador antigo também passou no teste E2E existente. O binário real Central
Engine com pesos aleatórios passou em 2050 tokens, interrupção/recuperação e API
Studio → processo → SQLite. Esses testes não validam qualidade de um LLM treinado.

O CI da PR repete o teste de UI em Chromium e o pacote nativo Windows. Resultados
Windows permanecem nos checks da PR. A release v0.2.0 não é substituída por este
pacote de teste. Não houve download do modelo treinado do usuário, acesso ao seu
notebook ou promessa de ganho de velocidade de inferência.

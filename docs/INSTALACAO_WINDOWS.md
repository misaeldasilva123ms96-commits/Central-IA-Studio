# Instalação Windows 11 x64

## Pacote entregue agora: fontes com frontend compilado

Extraia em pasta gravável (sugestão: `D:\Dev\Projetos\Central_IA_Studio`).
Requer Python 3.12 x64. Execute PREPARAR_WINDOWS.cmd, confirme o download de
dependências e aguarde. Esse passo é explícito, não ocorre durante o uso normal.
Depois abra INICIAR_CENTRAL_IA_STUDIO.cmd por duplo clique. Não precisa Node.js,
WSL, Docker ou GPU. O navegador abrirá em http://127.0.0.1:8765.

Se a porta estiver ocupada, feche a instância antiga ou execute
`.venv\Scripts\python.exe run.py --port 8766`.

Configurações: informe `http://127.0.0.1:5001`. Para um motor já aberto, teste a
conexão e use o chat. Parâmetros ↻ não mudam um processo externo. Para gerenciar o
motor, selecione o executável confiável local, adicione a pasta dos modelos,
selecione um modelo, ajuste o perfil e inicie. O Central nunca baixa o motor ou GGUF.
Se a porta do motor estiver ocupada, conecte ao existente ou troque a porta.

Recomendação inicial não medida: modelos pequenos quantizados (1,5–3B), contexto
4096, saída solicitada 4096 (efetiva pode ser menor), 2 threads, lote 128,
GPU layers 0. Um 7B pode pressionar 8 GB de RAM. Não há bloqueio por estimativa.
Não há garantia para famílias apenas pelo nome; veja metadados e erros do motor.

## Pacote portátil autossuficiente: build preparado, não executado aqui

No GitHub, após revisar e enviar os arquivos, execute manualmente o workflow
“Validar e empacotar Windows x64”. Ele usa Windows 2022, Python 3.12 x64 e Node 22,
instala versões fixadas, compila frontend, testa, empacota com PyInstaller onedir,
valida inicialização HTTP do EXE e anexa o ZIP à execução. Não publica releases.
É pipeline repetível com versões fixadas de pacotes diretos e lock npm; ainda não
é build binário determinístico bit a bit, pois runner/Python patch/transitivos pip
podem variar. Nenhum runner foi acionado nesta sessão.

Para build local em máquina de desenvolvimento Windows:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
npm ci --prefix frontend
npm run build --prefix frontend
python -m pytest -q
python scripts/package_source.py
./scripts/build_windows.ps1
```

No pacote compilado, basta extrair e abrir INICIAR_CENTRAL_IA_STUDIO.cmd.
O runtime Python e as bibliotecas estarão na pasta CentralIAStudio; preserve sua
estrutura. Modelo e motor permanecem externos. Este caminho precisa ser validado
em Windows antes de declarar o critério de duplo clique aprovado.

## Dados e encerramento

Fontes: data ao lado de run.py. Executável: data ao lado do EXE.
Não extraia em Program Files nem em diretório somente leitura. Banco:
central.sqlite3; logs: central.log e engine.log. Crie backup em Configurações.
Para restaurar, feche o gerenciador, preserve toda a pasta data, substitua o banco
por uma cópia consistente do backup e remova/arquive os antigos arquivos -wal/-shm
apenas após encerramento completo. Não há restauração automática destrutiva.
Configuração inválida gera aviso; salve uma configuração válida para recuperar.
Banco corrompido é preservado e a inicialização falha, em vez de apagar dados.

Feche com Ctrl+C na janela do console. O shutdown encerra o processo próprio.
Fechar apenas a aba não encerra o gerenciador. Encerramento abrupto da janela ou
queda do sistema pode deixar motor órfão; confira o Gerenciador de Tarefas.

## Checklist definitivo no notebook

- Duplo clique inicia o gerenciador e navegador; nenhum serviço é exposto na rede.
- GGUF real aparece com metadados; motor confiável carrega sem erro.
- Chat transmite texto; interromper para a geração; troca de modelo libera recursos.
- Solicitar >2048 com contexto suficiente, conferir efetivo, usage e motivo.
- Comparar thinking on/off usando template específico do modelo e examinar retorno.
- Reabrir aplicativo e confirmar histórico/perfis, exportações e backup.
- Medir RAM, paginação, tempo de primeiro token e tokens/s com prompt registrado.

Nenhum desses testes de notebook foi executado na nuvem.

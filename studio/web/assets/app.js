(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];
  const STORE = 'central-ia-studio-sessions-v1';
  const CURRENT = 'central-ia-studio-current-v1';
  const names = { chat: 'CONVERSAS', models: 'MODELOS E MOTOR', settings: 'CONFIGURAÇÕES' };
  let config = null;
  let runtime = null;
  let pending = null;
  let toastTimer = null;
  let sessions = readSessions();
  let currentId = localStorage.getItem(CURRENT);

  function readSessions() {
    try {
      const data = JSON.parse(localStorage.getItem(STORE) || '[]');
      return Array.isArray(data) ? data.filter(s => s && typeof s.id === 'string' && Array.isArray(s.messages)) : [];
    } catch { return []; }
  }
  function session() { return sessions.find(s => s.id === currentId); }
  function persist() {
    try { localStorage.setItem(STORE, JSON.stringify(sessions)); localStorage.setItem(CURRENT, currentId || ''); }
    catch { toast('O armazenamento do navegador está cheio. Exporte sua conversa.', true); }
  }
  function newSession() {
    if (pending) pending.abort();
    const item = { id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, title: 'Nova conversa', created: Date.now(), messages: [] };
    sessions.unshift(item);
    currentId = item.id;
    persist();
    showView('chat');
    render();
    $('#promptInput').focus();
  }
  function ensureSession() { if (!session()) newSession(); }
  function toast(text, isError = false) {
    const node = $('#toast'); node.textContent = text; node.classList.toggle('error', isError); node.classList.add('visible');
    clearTimeout(toastTimer); toastTimer = setTimeout(() => node.classList.remove('visible'), 4700);
  }
  async function api(url, options = {}) {
    const response = await fetch(url, { ...options, headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } });
    const json = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof json.detail === 'string' ? json.detail : `Erro HTTP ${response.status}`);
    return json;
  }
  function showView(view) {
    $$('.view').forEach(node => node.classList.toggle('active', node.id === `view-${view}`));
    $$('.nav-link').forEach(node => node.classList.toggle('active', node.dataset.view === view));
    $('#sectionTitle').textContent = names[view];
    $('#sidebar').classList.remove('mobile-open');
    if (view === 'models') { refreshModels(); refreshStatus(); }
    if (view === 'settings' && config) populateSettings();
  }
  function renderSessionList() {
    const root = $('#sessionList'); root.replaceChildren();
    $('#chatCount').textContent = String(sessions.length);
    sessions.forEach(item => {
      const button = document.createElement('button');
      button.className = `session${item.id === currentId ? ' selected' : ''}`;
      button.textContent = item.title || 'Conversa'; button.title = item.title;
      button.onclick = () => { if (pending) pending.abort(); currentId = item.id; persist(); showView('chat'); render(); };
      root.append(button);
    });
  }
  function renderMessage(root, role, text, isError = false) {
    const row = document.createElement('div'); row.className = `message ${role}${isError ? ' error' : ''}`;
    const avatar = document.createElement('div'); avatar.className = 'avatar'; avatar.textContent = '✳';
    const bubble = document.createElement('div'); bubble.className = 'bubble'; bubble.textContent = text;
    row.append(avatar, bubble); root.append(row); return bubble;
  }
  function render() {
    ensureSession(); renderSessionList();
    const chat = session();
    $('#conversationTitle').textContent = chat.messages.length ? chat.title : 'Sua IA. Suas regras.';
    const root = $('#chatMessages'); root.replaceChildren();
    $('#welcome').classList.toggle('hidden', chat.messages.length > 0);
    chat.messages.forEach(msg => renderMessage(root, msg.role, msg.content, !!msg.error));
    root.scrollTop = root.scrollHeight;
  }
  function updateGenerating(on) {
    $('#sendButton').classList.toggle('hidden', on);
    $('#stopButton').classList.toggle('hidden', !on);
    $('#promptInput').disabled = on;
  }
  async function send(messageText) {
    const text = (messageText ?? $('#promptInput').value).trim();
    if (!text || pending) return;
    ensureSession();
    const target = session();
    $('#promptInput').value = '';
    target.messages.push({ role: 'user', content: text });
    if (target.messages.length === 1) target.title = text.length > 48 ? `${text.slice(0, 48)}…` : text;
    const output = { role: 'assistant', content: '' };
    target.messages.push(output);
    persist(); render();
    const root = $('#chatMessages');
    const bubble = root.querySelector('.message:last-child .bubble');
    bubble.textContent = 'Gerando resposta…';
    updateGenerating(true);
    pending = new AbortController();
    const controller = pending;
    try {
      const response = await fetch('/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ messages: target.messages.filter(m => m.content && !m.error).map(m => ({role: m.role, content: m.content})) })
      });
      if (!response.ok || !response.body) throw new Error(`Falha ao iniciar geração (HTTP ${response.status}).`);
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '', ended = false;
      while (!ended) {
        const {value, done} = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, {stream: true});
        let split;
        while ((split = buffer.search(/\r?\n\r?\n/)) >= 0) {
          const packet = buffer.slice(0, split); buffer = buffer.slice(split).replace(/^\r?\n\r?\n/, '');
          const event = packet.match(/^event:\s*(.+)$/m)?.[1]?.trim() || 'message';
          const data = packet.match(/^data:\s*(.+)$/m)?.[1];
          if (!data) continue;
          let parsed; try { parsed = JSON.parse(data); } catch { continue; }
          if (event === 'token') {
            output.content += parsed.text || '';
            if (session()?.id === target.id) bubble.textContent = output.content;
            root.scrollTop = root.scrollHeight;
          } else if (event === 'error') { throw new Error(parsed.message || 'Erro desconhecido no motor.'); }
          else if (event === 'finish' && parsed.reason === 'length') { /* Resposta atingiu o limite de tokens. */ }
          else if (event === 'done') { ended = true; break; }
        }
      }
      if (!output.content) output.content = 'O motor não retornou texto. Verifique as configurações e os logs.';
    } catch (error) {
      if (controller.signal.aborted) {
        output.content ||= 'Geração interrompida.';
      } else {
        output.content = output.content ? `${output.content}\n\n[Erro: ${error.message}]` : `Erro: ${error.message}`;
        output.error = true; toast(error.message, true);
      }
    } finally {
      if (pending === controller) pending = null;
      persist(); render(); updateGenerating(false);
      $('#promptInput').focus();
    }
  }
  async function refreshStatus() {
    try {
      runtime = await api('/api/status');
      $('#connectionDot').classList.toggle('online', !!runtime.online);
      $('#connectionLabel').textContent = runtime.online ? 'Motor conectado' : 'Motor desconectado';
      $('#dashboardStatus').textContent = runtime.online ? 'Conectado' : 'Desconectado';
      $('#dashboardEndpoint').textContent = runtime.endpoint;
      $('#dashboardMode').textContent = runtime.provider === 'koboldcpp' ? 'KoboldCpp' : runtime.provider === 'llama-managed' ? 'llama.cpp gerenciado' : 'llama.cpp externo';
      $('#dashboardModel').textContent = runtime.models[0] || '—';
      $('#composerModel').textContent = runtime.online ? (runtime.models[0] || 'Motor local') : 'Nenhum modelo conectado';
    } catch (error) {
      $('#connectionDot').classList.remove('online');
      $('#connectionLabel').textContent = 'API indisponível';
    }
  }
  async function refreshModels() {
    try {
      const result = await api('/api/models');
      const root = $('#modelList'); root.replaceChildren();
      $('#modelCount').textContent = `${result.items.length} modelo(s)`;
      if (!result.items.length) { const item = document.createElement('p'); item.className = 'muted'; item.textContent = 'Nenhum GGUF encontrado. Configure a pasta em Configurações.'; root.append(item); }
      for (const item of result.items) {
        const row = document.createElement('div'); row.className = 'model-row';
        const name = document.createElement('span'); name.textContent = `◈  ${item.name}`; name.title = item.path;
        const size = document.createElement('small'); size.textContent = `${item.size_gb} GB`;
        const choose = document.createElement('button'); choose.className = 'secondary-button'; choose.textContent = 'Selecionar';
        choose.onclick = () => { showView('settings'); $('[name="model_file"]').value = item.path; toast('Modelo selecionado. Salve as configurações para aplicar.'); };
        row.append(name, size, choose); root.append(row);
      }
    } catch (error) { toast(error.message, true); }
  }
  function populateSettings() {
    const form = $('#settingsForm');
    Object.entries(config).forEach(([name, value]) => {
      const field = form.elements.namedItem(name);
      if (field) field.value = value;
    });
  }
  async function loadConfig() {
    config = await api('/api/config'); populateSettings();
  }
  async function saveConfig(event) {
    event.preventDefault();
    const form = $('#settingsForm');
    const next = { ...config };
    Object.keys(next).forEach(key => {
      const field = form.elements.namedItem(key);
      if (!field) return;
      next[key] = field.type === 'number' ? Number(field.value) : field.value;
    });
    try {
      config = await api('/api/config', { method: 'PUT', body: JSON.stringify(next) });
      populateSettings();
      $('#saveStatus').textContent = '✓ Configurações salvas localmente.';
      toast('Configurações salvas!'); refreshStatus(); refreshModels();
    } catch (error) { toast(error.message, true); $('#saveStatus').textContent = error.message; }
  }
  async function manageEngine(action) {
    try {
      const result = await api(`/api/engine/${action}`, {method:'POST'});
      toast(action === 'start' ? 'Motor iniciado. Aguarde o modelo ficar pronto.' : 'Motor gerenciado encerrado.');
      setTimeout(refreshStatus, action === 'start' ? 2000 : 300);
      if (!result.running && action === 'start') toast('O processo encerrou. Consulte os logs do motor.', true);
    } catch (error) { toast(error.message, true); }
  }
  function exportSession() {
    const chat = session(); if (!chat) return;
    const json = JSON.stringify({studio:'Central IA Studio', version:'0.1.0', ...chat}, null, 2);
    const blob = new Blob([json], {type:'application/json'});
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `central-ia-conversa-${chat.id}.json`;
    a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    toast('Conversa exportada em JSON.');
  }

  $('#newChat').onclick = newSession;
  $('#refreshStatus').onclick = refreshStatus;
  $('#menuBtn').onclick = () => $('#sidebar').classList.toggle('mobile-open');
  $$('.nav-link').forEach(btn => btn.onclick = () => showView(btn.dataset.view));
  $$('.prompt-grid button').forEach(btn => btn.onclick = () => { $('#promptInput').value = btn.dataset.prompt; $('#promptInput').focus(); });
  $('#sendButton').onclick = () => send();
  $('#stopButton').onclick = () => pending?.abort();
  $('#promptInput').addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); send(); }
  });
  $('#settingsForm').addEventListener('submit', saveConfig);
  $('[name="provider"]').addEventListener('change', event => {
    const base = $('[name="api_base_url"]');
    base.value = event.target.value === 'koboldcpp' ? 'http://127.0.0.1:5001/v1' : 'http://127.0.0.1:8081/v1';
  });
  $('#startEngine').onclick = () => manageEngine('start');
  $('#stopEngine').onclick = () => manageEngine('stop');
  $('#reloadModels').onclick = () => { refreshModels(); refreshStatus(); };
  $('#openSettings').onclick = () => showView('settings');
  $('#readLogs').onclick = async () => { try { $('#engineLogs').textContent = (await api('/api/engine/logs')).text || 'Nenhum log disponível.'; } catch(e) { toast(e.message, true); } };
  $('#exportChat').onclick = exportSession;
  $('#clearHistory').onclick = () => {
    if (!confirm('Excluir todas as conversas salvas neste navegador? Esta ação não pode ser desfeita.')) return;
    if (pending) pending.abort(); sessions = []; currentId = null; persist(); newSession(); toast('Histórico removido do navegador.');
  };
  document.addEventListener('keydown', event => {
    if (event.key.toLowerCase() === 'n' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); newSession(); }
  });
  ensureSession(); render();
  loadConfig().catch(error => toast(`Não foi possível carregar configurações: ${error.message}`, true));
  refreshStatus();
  setInterval(refreshStatus, 15000);
})();

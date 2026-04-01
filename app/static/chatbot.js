/**
 * ConstructTwin v3 — SiteAI Chatbot Widget
 * Floating panel · Multi-turn · Typing indicator · Markdown · Chips
 */
(function () {
  'use strict';

  var SESSION_ID  = 'session_' + Date.now();
  var MAX_HISTORY = 10;
  var history     = [];

  var CHIPS = [
    'Site overview',
    'High risk activities',
    'TBM advance status',
    'Progress summary',
    'Equipment issues',
    'Delay forecast',
  ];

  /* ── Inject widget CSS ───────────────────────────────────── */
  var style = document.createElement('style');
  style.textContent = '\
#cb-btn{\
  position:fixed;bottom:24px;right:24px;z-index:9000;\
  width:56px;height:56px;border-radius:50%;\
  background:var(--accent,#F5A623);border:none;cursor:pointer;\
  font-size:22px;display:flex;align-items:center;justify-content:center;\
  box-shadow:0 4px 20px rgba(245,166,35,.45);\
  transition:transform .2s;\
}\
#cb-btn:hover{transform:scale(1.1);box-shadow:0 6px 28px rgba(245,166,35,.6);}\
.cb-pulse{\
  position:absolute;width:100%;height:100%;border-radius:50%;\
  background:var(--accent,#F5A623);opacity:.28;\
  animation:cbPulse 2.4s infinite;pointer-events:none;\
}\
@keyframes cbPulse{0%{transform:scale(1);opacity:.28}100%{transform:scale(1.9);opacity:0}}\
#cb-panel{\
  position:fixed;bottom:90px;right:24px;z-index:8999;\
  width:360px;max-height:540px;\
  background:var(--surface,#0E0E12);\
  border:1px solid var(--border2,#36363F);\
  border-radius:18px;\
  display:none;flex-direction:column;\
  box-shadow:0 16px 52px rgba(0,0,0,.65);\
  overflow:hidden;\
}\
#cb-panel.cb-open{display:flex;animation:cbSlideUp .2s ease;}\
@keyframes cbSlideUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}\
#cb-head{\
  padding:14px 16px;\
  background:linear-gradient(135deg,rgba(245,166,35,.08),rgba(59,130,246,.05));\
  border-bottom:1px solid var(--border,#232329);\
  display:flex;align-items:center;gap:10px;flex-shrink:0;\
}\
.cb-bot-icon{\
  width:36px;height:36px;border-radius:10px;\
  background:linear-gradient(135deg,#F5A623,#e09520);\
  display:flex;align-items:center;justify-content:center;\
  font-size:18px;flex-shrink:0;\
}\
.cb-bot-name{font-family:var(--font-d,"Syne",sans-serif);font-size:13px;font-weight:700;color:var(--text,#F4F4F5);}\
.cb-bot-status{\
  font-size:10px;color:var(--green,#10B981);\
  font-family:var(--font-m,"IBM Plex Mono",monospace);\
  display:flex;align-items:center;gap:4px;\
}\
.cb-bot-status::before{\
  content:"";width:5px;height:5px;border-radius:50%;\
  background:var(--green,#10B981);animation:cbBlink 1.4s infinite;\
}\
@keyframes cbBlink{0%,100%{opacity:1}50%{opacity:.15}}\
#cb-close{\
  background:none;border:none;color:var(--text3,#71717A);\
  cursor:pointer;font-size:18px;padding:4px;line-height:1;\
  border-radius:6px;transition:all .12s;margin-left:auto;\
}\
#cb-close:hover{color:var(--text,#F4F4F5);background:var(--surface3,#1C1C22);}\
#cb-msgs{\
  flex:1;overflow-y:auto;padding:14px 12px;\
  display:flex;flex-direction:column;gap:9px;\
  scrollbar-width:thin;scrollbar-color:var(--border2,#36363F) transparent;\
}\
#cb-msgs::-webkit-scrollbar{width:3px;}\
#cb-msgs::-webkit-scrollbar-thumb{background:var(--border2,#36363F);border-radius:4px;}\
.cb-msg{\
  max-width:88%;padding:10px 13px;\
  border-radius:12px;font-size:12.5px;line-height:1.65;\
}\
.cb-msg.cb-bot{\
  background:var(--surface2,#151519);\
  border:1px solid var(--border,#232329);\
  align-self:flex-start;border-bottom-left-radius:3px;\
  color:var(--text,#F4F4F5);\
}\
.cb-msg.cb-user{\
  background:linear-gradient(135deg,#F5A623,#e09520);\
  color:#000;font-weight:500;\
  align-self:flex-end;border-bottom-right-radius:3px;\
}\
.cb-msg strong{font-weight:700;}\
.cb-msg ul{padding-left:16px;margin:4px 0;}\
.cb-msg li{margin-bottom:2px;}\
.cb-msg code{\
  background:rgba(255,255,255,.08);padding:1px 5px;\
  border-radius:4px;font-family:monospace;font-size:11px;\
}\
.cb-typing{display:flex;gap:3px;padding:4px 2px;align-items:center;}\
.cb-typing span{\
  display:inline-block;width:5px;height:5px;\
  background:var(--text3,#71717A);border-radius:50%;\
  animation:cbTyp 1.1s infinite;\
}\
.cb-typing span:nth-child(2){animation-delay:.15s;}\
.cb-typing span:nth-child(3){animation-delay:.30s;}\
@keyframes cbTyp{0%,80%,100%{transform:scale(.55);opacity:.35}40%{transform:scale(1);opacity:1}}\
.cb-welcome{\
  text-align:center;padding:18px 14px 8px;\
  font-size:11px;\
  font-family:var(--font-m,"IBM Plex Mono",monospace);\
  color:var(--text3,#71717A);line-height:1.7;\
}\
.cb-welcome strong{\
  display:block;\
  font-family:var(--font-d,"Syne",sans-serif);\
  font-size:14px;font-weight:800;\
  color:var(--text,#F4F4F5);margin-bottom:4px;\
}\
#cb-chips{\
  display:flex;flex-wrap:wrap;gap:5px;\
  padding:4px 12px 10px;\
}\
.cb-chip{\
  padding:4px 10px;\
  background:var(--surface2,#151519);\
  border:1px solid var(--border,#232329);\
  border-radius:20px;font-size:11px;\
  color:var(--text3,#71717A);cursor:pointer;\
  transition:all .15s;\
  font-family:var(--font-m,"IBM Plex Mono",monospace);\
}\
.cb-chip:hover{\
  border-color:var(--accent,#F5A623);\
  color:var(--accent,#F5A623);\
  background:rgba(245,166,35,.05);\
}\
#cb-input-row{\
  display:flex;gap:7px;padding:10px 12px;\
  border-top:1px solid var(--border,#232329);flex-shrink:0;\
}\
#cb-input{\
  flex:1;background:var(--surface2,#151519);\
  border:1px solid var(--border,#232329);border-radius:9px;\
  padding:8px 12px;color:var(--text,#F4F4F5);\
  font-size:12.5px;\
  font-family:var(--font-b,"Inter",sans-serif);\
  outline:none;transition:border-color .15s;\
  resize:none;min-height:36px;max-height:80px;\
  line-height:1.5;\
}\
#cb-input:focus{border-color:var(--accent,#F5A623);}\
#cb-input::placeholder{color:var(--text4,#52525B);}\
#cb-send{\
  width:36px;height:36px;border-radius:9px;flex-shrink:0;\
  background:var(--accent,#F5A623);border:none;cursor:pointer;\
  display:flex;align-items:center;justify-content:center;\
  font-size:15px;color:#000;transition:background .15s;\
  align-self:flex-end;\
}\
#cb-send:hover{background:#e09520;}\
#cb-send:disabled{opacity:.45;cursor:not-allowed;}\
@media(max-width:480px){\
  #cb-panel{width:calc(100vw - 24px);right:12px;bottom:82px;}\
}\
';
  document.head.appendChild(style);

  /* ── Build DOM ───────────────────────────────────────────── */
  var btn = document.createElement('button');
  btn.id = 'cb-btn';
  btn.setAttribute('aria-label', 'Open SiteAI chat');
  btn.innerHTML = '<div class="cb-pulse"></div><span>🤖</span>';
  document.body.appendChild(btn);

  var panel = document.createElement('div');
  panel.id = 'cb-panel';
  panel.setAttribute('role', 'dialog');
  panel.innerHTML =
    '<div id="cb-head">' +
      '<div class="cb-bot-icon">🤖</div>' +
      '<div>' +
        '<div class="cb-bot-name">SiteAI</div>' +
        '<div class="cb-bot-status">Online · Groq llama-3.3-70b</div>' +
      '</div>' +
      '<button id="cb-close" aria-label="Close">✕</button>' +
    '</div>' +
    '<div id="cb-msgs">' +
      '<div class="cb-welcome">' +
        '<strong>👋 SiteAI Assistant</strong>' +
        'Ask me anything — risks, progress, delays, TBM status, workers.' +
      '</div>' +
    '</div>' +
    '<div id="cb-chips"></div>' +
    '<div id="cb-input-row">' +
      '<textarea id="cb-input" rows="1" placeholder="Ask about your site…"></textarea>' +
      '<button id="cb-send" aria-label="Send">➤</button>' +
    '</div>';
  document.body.appendChild(panel);

  /* ── Refs ────────────────────────────────────────────────── */
  var msgsEl  = document.getElementById('cb-msgs');
  var inputEl = document.getElementById('cb-input');
  var sendEl  = document.getElementById('cb-send');
  var chipsEl = document.getElementById('cb-chips');

  /* ── Chips ───────────────────────────────────────────────── */
  CHIPS.forEach(function (text) {
    var c = document.createElement('button');
    c.className   = 'cb-chip';
    c.textContent = text;
    c.onclick     = function () { sendMessage(text); };
    chipsEl.appendChild(c);
  });

  /* ── Toggle ──────────────────────────────────────────────── */
  btn.onclick = function () {
    var open = panel.classList.toggle('cb-open');
    if (open) inputEl.focus();
  };
  document.getElementById('cb-close').onclick = function () {
    panel.classList.remove('cb-open');
  };
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') panel.classList.remove('cb-open');
  });

  /* ── Auto-resize textarea ────────────────────────────────── */
  inputEl.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 80) + 'px';
  });

  /* ── Send on Enter ───────────────────────────────────────── */
  inputEl.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      doSend();
    }
  });
  sendEl.onclick = doSend;

  function doSend() {
    var text = inputEl.value.trim();
    if (!text) return;
    inputEl.value = '';
    inputEl.style.height = 'auto';
    sendMessage(text);
  }

  /* ── Append bubble ───────────────────────────────────────── */
  function appendMsg(role, text) {
    var div = document.createElement('div');
    div.className = 'cb-msg ' + (role === 'user' ? 'cb-user' : 'cb-bot');
    if (role === 'assistant') {
      div.innerHTML = renderMarkdown(text);
    } else {
      div.textContent = text;
    }
    msgsEl.appendChild(div);
    scrollBottom();
    return div;
  }

  /* ── Typing indicator ────────────────────────────────────── */
  function showTyping() {
    var d = document.createElement('div');
    d.className = 'cb-msg cb-bot';
    d.id = 'cb-typing';
    d.innerHTML = '<div class="cb-typing"><span></span><span></span><span></span></div>';
    msgsEl.appendChild(d);
    scrollBottom();
  }
  function hideTyping() {
    var el = document.getElementById('cb-typing');
    if (el) el.remove();
  }

  /* ── API call ────────────────────────────────────────────── */
  async function sendMessage(text) {
    chipsEl.style.display = 'none';
    appendMsg('user', text);

    history.push({ role: 'user', content: text });
    if (history.length > MAX_HISTORY * 2) {
      history = history.slice(-MAX_HISTORY * 2);
    }

    sendEl.disabled = true;
    showTyping();

    try {
      var res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message:    text,
          user_id:    window.CTWIN_USER_ID || 1,
          session_id: SESSION_ID,
          history:    history.slice(-MAX_HISTORY),
        }),
      });

      if (!res.ok) throw new Error('HTTP ' + res.status);

      var data  = await res.json();
      var reply = data.reply || '⚠️ Empty response from server.';

      hideTyping();
      appendMsg('assistant', reply);
      history.push({ role: 'assistant', content: reply });

    } catch (err) {
      hideTyping();
      appendMsg('assistant', '⚠️ SiteAI unavailable. Make sure your server is running.\n\n`' + err.message + '`');
    }

    sendEl.disabled = false;
    inputEl.focus();
  }

  /* ── Scroll ──────────────────────────────────────────────── */
  function scrollBottom() {
    msgsEl.scrollTop = msgsEl.scrollHeight;
  }

  /* ── Markdown renderer ───────────────────────────────────── */
  function renderMarkdown(text) {
    if (!text) return '';

    var s = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    // Bold
    s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    // Italic
    s = s.replace(/(?:^|(?<=\s))_([^_]+)_(?=\s|$)/g, '<em>$1</em>');
    // Inline code
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bullet lists
    var lines  = s.split('\n');
    var out    = [];
    var inList = false;
    lines.forEach(function (line) {
      if (/^[•\-\*]\s+/.test(line.trim())) {
        if (!inList) { out.push('<ul>'); inList = true; }
        out.push('<li>' + line.trim().replace(/^[•\-\*]\s+/, '') + '</li>');
      } else {
        if (inList) { out.push('</ul>'); inList = false; }
        out.push(line);
      }
    });
    if (inList) out.push('</ul>');

    return out.join('\n')
      .replace(/\n{2,}/g, '<br><br>')
      .replace(/\n/g, '<br>');
  }

})();
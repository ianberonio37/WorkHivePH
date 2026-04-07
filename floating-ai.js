/**
 * WorkHive Floating AI Assistant
 * ------------------------------------------------------------
 * Principles: Usable · Functional · Adaptable · Internal Control
 *
 * Drop one <script src="floating-ai.js"></script> tag before </body>
 * on any page and the widget self-initialises.
 *
 * Internal Control:
 *   - All API calls go through WHAssistant.sendMessage()
 *   - Toggle WHAssistant.config.enabled = false to kill the widget site-wide
 *   - Toggle WHAssistant.config.apiEnabled = false to run in demo/mock mode
 *   - Context is always injected so the AI knows which page it's on
 */

(function () {
  'use strict';

  // ─── Config (Internal Control) ───────────────────────────────────────────────
  const config = {
    enabled:    true,          // master switch — set false to hide widget everywhere
    apiEnabled: true,          // false = mock mode (no real API calls yet)
    apiKey:     '',            // not needed — key is secured inside the Cloudflare Worker
    workerUrl:  'https://workhive-assistant.ian-beronio37.workers.dev',
    model:      'llama-3.3-70b-versatile', // Groq model — fast & free tier available
    maxHistory: 20,            // max messages kept in session memory
    position:   'bottom-right' // future: 'bottom-left'
  };

  if (!config.enabled) return;

  // ─── Page Context Detection (Adaptable) ──────────────────────────────────────
  function detectPageContext() {
    const path = window.location.pathname.toLowerCase();

    if (path.includes('logbook'))       return { page: 'logbook',      label: 'Digital Logbook',      hint: 'Help me fill in maintenance records, suggest failure modes, or explain fields.' };
    if (path.includes('checklist'))     return { page: 'checklist',    label: 'Checklist',             hint: 'Guide me through inspection steps or explain checklist items.' };
    if (path.includes('parts-tracker')) return { page: 'parts-tracker',label: 'Parts Tracker',         hint: 'Help me find parts, check stock levels, or suggest reorder points.' };
    if (path.includes('assistant'))     return { page: 'assistant',    label: 'My Work Assistant',     hint: 'I can help you plan your shift, prioritise tasks, or answer technical questions.' };
    return                              { page: 'home',                label: 'WorkHive Home',         hint: 'Ask me anything about the platform or industrial maintenance.' };
  }

  // ─── Mock Responses (Demo Mode) ──────────────────────────────────────────────
  const mockResponses = {
    logbook: [
      "For **Failure Mode**, common options include: Vibration, Overheating, Leakage, Electrical Fault, Mechanical Wear, or Corrosion. What equipment are you logging?",
      "For a good maintenance entry, make sure to include: the exact time it started, what you observed first, and any action taken. Want me to suggest a format?",
      "A **Root Cause** entry should answer *why* the failure happened, not just what broke. Example: 'Bearing failure due to insufficient lubrication' is better than just 'Bearing failed'.",
    ],
    checklist: [
      "Before signing off a checklist, double-check the safety lockout/tagout steps are confirmed. That's the most commonly missed item.",
      "If an item is 'N/A', always add a short reason — it helps during audits and shows the check was deliberately skipped, not forgotten.",
    ],
    'parts-tracker': [
      "A good reorder point = (Average Daily Usage × Lead Time in Days) + Safety Stock. Want me to help calculate it for a specific part?",
      "For critical spares, consider keeping at least one unit on-hand regardless of usage frequency — downtime cost usually outweighs holding cost.",
    ],
    default: [
      "I'm your WorkHive AI Assistant. I can help you with maintenance logs, checklists, parts management, and shift planning. What do you need?",
      "Great question. While I'm in demo mode right now, once connected to the AI backend I can give you real-time answers based on your specific equipment and history.",
    ]
  };

  function getMockResponse(page) {
    const pool = mockResponses[page] || mockResponses.default;
    return pool[Math.floor(Math.random() * pool.length)];
  }

  // ─── State ────────────────────────────────────────────────────────────────────
  let isOpen    = false;
  let isTyping  = false;
  let history   = []; // { role: 'user'|'assistant', content: string }
  const ctx     = detectPageContext();

  // ─── Render HTML ─────────────────────────────────────────────────────────────
  function buildWidget() {
    const wrapper = document.createElement('div');
    wrapper.id = 'wh-ai-widget';
    wrapper.innerHTML = `
      <style>
        /* ── Widget Shell ── */
        #wh-ai-widget {
          position: fixed;
          bottom: 24px;
          right: 24px;
          z-index: 9999;
          font-family: 'Poppins', sans-serif;
        }

        /* ── Trigger Button ── */
        #wh-ai-trigger {
          width: 56px;
          height: 56px;
          border-radius: 50%;
          background: linear-gradient(135deg, #F7A21B, #e8920a);
          border: none;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 4px 20px rgba(247,162,27,0.45), 0 0 0 0 rgba(247,162,27,0.3);
          transition: transform 0.2s, box-shadow 0.2s;
          animation: wh-pulse 3s ease-in-out infinite;
          position: relative;
        }
        #wh-ai-trigger:hover {
          transform: scale(1.08);
          box-shadow: 0 6px 28px rgba(247,162,27,0.6);
        }
        @keyframes wh-pulse {
          0%, 100% { box-shadow: 0 4px 20px rgba(247,162,27,0.45), 0 0 0 0 rgba(247,162,27,0.25); }
          50%       { box-shadow: 0 4px 20px rgba(247,162,27,0.45), 0 0 0 10px rgba(247,162,27,0); }
        }
        #wh-ai-trigger svg { pointer-events: none; }

        /* ── Tooltip ── */
        #wh-ai-tooltip {
          position: absolute;
          right: 64px;
          top: 50%;
          transform: translateY(-50%);
          background: rgba(22,32,50,0.95);
          border: 1px solid rgba(247,162,27,0.3);
          color: #fff;
          font-size: 12px;
          padding: 6px 12px;
          border-radius: 8px;
          white-space: nowrap;
          pointer-events: none;
          opacity: 0;
          transition: opacity 0.2s;
        }
        #wh-ai-trigger:hover #wh-ai-tooltip { opacity: 1; }

        /* ── Chat Panel ── */
        #wh-ai-panel {
          position: absolute;
          bottom: 68px;
          right: 0;
          width: 340px;
          max-height: 480px;
          background: linear-gradient(160deg, #1F2E45 0%, #162032 100%);
          border: 1px solid rgba(247,162,27,0.2);
          border-radius: 16px;
          box-shadow: 0 20px 60px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.04);
          display: flex;
          flex-direction: column;
          overflow: hidden;
          opacity: 0;
          transform: translateY(12px) scale(0.97);
          pointer-events: none;
          transition: opacity 0.22s ease, transform 0.22s ease;
        }
        #wh-ai-panel.open {
          opacity: 1;
          transform: translateY(0) scale(1);
          pointer-events: all;
        }

        /* ── Panel Header ── */
        #wh-ai-header {
          padding: 14px 16px;
          background: linear-gradient(90deg, rgba(247,162,27,0.12) 0%, transparent 100%);
          border-bottom: 1px solid rgba(255,255,255,0.07);
          display: flex;
          align-items: center;
          gap: 10px;
          flex-shrink: 0;
        }
        .wh-ai-avatar {
          width: 32px; height: 32px;
          background: linear-gradient(135deg,#F7A21B,#29B6D9);
          border-radius: 50%;
          display: flex; align-items: center; justify-content: center;
          flex-shrink: 0;
        }
        .wh-ai-header-text { flex: 1; }
        .wh-ai-header-text strong { display: block; color: #fff; font-size: 13px; font-weight: 600; }
        .wh-ai-header-text span   { color: #F7A21B; font-size: 10px; font-weight: 500; letter-spacing: 0.04em; text-transform: uppercase; }
        #wh-ai-close {
          background: none; border: none; color: rgba(255,255,255,0.4);
          cursor: pointer; font-size: 18px; line-height: 1; padding: 2px 4px;
          border-radius: 4px; transition: color 0.15s, background 0.15s;
        }
        #wh-ai-close:hover { color: #fff; background: rgba(255,255,255,0.08); }

        /* ── Page Context Tag ── */
        #wh-ai-context-tag {
          margin: 10px 12px 0;
          padding: 6px 10px;
          background: rgba(41,182,217,0.1);
          border: 1px solid rgba(41,182,217,0.2);
          border-radius: 8px;
          font-size: 10px;
          color: #29B6D9;
          display: flex;
          align-items: center;
          gap: 6px;
          flex-shrink: 0;
        }

        /* ── Messages ── */
        #wh-ai-messages {
          flex: 1;
          overflow-y: auto;
          padding: 12px;
          display: flex;
          flex-direction: column;
          gap: 10px;
          scrollbar-width: thin;
          scrollbar-color: rgba(247,162,27,0.2) transparent;
        }
        #wh-ai-messages::-webkit-scrollbar { width: 4px; }
        #wh-ai-messages::-webkit-scrollbar-thumb { background: rgba(247,162,27,0.2); border-radius: 2px; }

        .wh-msg {
          max-width: 88%;
          padding: 9px 12px;
          border-radius: 12px;
          font-size: 12.5px;
          line-height: 1.5;
          animation: wh-msg-in 0.18s ease;
        }
        @keyframes wh-msg-in {
          from { opacity: 0; transform: translateY(4px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .wh-msg.user {
          align-self: flex-end;
          background: linear-gradient(135deg, rgba(247,162,27,0.2), rgba(247,162,27,0.12));
          border: 1px solid rgba(247,162,27,0.25);
          color: #fff;
          border-bottom-right-radius: 4px;
        }
        .wh-msg.assistant {
          align-self: flex-start;
          background: rgba(42,61,88,0.7);
          border: 1px solid rgba(255,255,255,0.07);
          color: rgba(255,255,255,0.9);
          border-bottom-left-radius: 4px;
        }
        .wh-msg.assistant strong { color: #F7A21B; }

        /* ── Typing Indicator ── */
        .wh-typing {
          align-self: flex-start;
          display: flex; align-items: center; gap: 4px;
          padding: 10px 14px;
          background: rgba(42,61,88,0.7);
          border: 1px solid rgba(255,255,255,0.07);
          border-radius: 12px;
          border-bottom-left-radius: 4px;
        }
        .wh-typing span {
          width: 6px; height: 6px;
          background: #F7A21B;
          border-radius: 50%;
          animation: wh-dot 1.2s ease-in-out infinite;
        }
        .wh-typing span:nth-child(2) { animation-delay: 0.2s; }
        .wh-typing span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes wh-dot {
          0%, 80%, 100% { opacity: 0.2; transform: scale(0.8); }
          40%           { opacity: 1;   transform: scale(1.1); }
        }

        /* ── Input Row ── */
        #wh-ai-input-row {
          padding: 10px 12px;
          border-top: 1px solid rgba(255,255,255,0.07);
          display: flex;
          gap: 8px;
          flex-shrink: 0;
          background: rgba(22,32,50,0.4);
        }
        #wh-ai-input {
          flex: 1;
          background: rgba(22,32,50,0.8);
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: 10px;
          color: #fff;
          font-family: 'Poppins', sans-serif;
          font-size: 12px;
          padding: 8px 12px;
          outline: none;
          resize: none;
          max-height: 80px;
          transition: border-color 0.2s;
        }
        #wh-ai-input:focus { border-color: rgba(247,162,27,0.4); box-shadow: 0 0 0 3px rgba(247,162,27,0.07); }
        #wh-ai-input::placeholder { color: rgba(255,255,255,0.25); }
        #wh-ai-send {
          width: 36px; height: 36px;
          background: linear-gradient(135deg, #F7A21B, #e8920a);
          border: none;
          border-radius: 10px;
          cursor: pointer;
          display: flex; align-items: center; justify-content: center;
          flex-shrink: 0;
          align-self: flex-end;
          transition: transform 0.15s, opacity 0.15s;
        }
        #wh-ai-send:hover   { transform: scale(1.06); }
        #wh-ai-send:active  { transform: scale(0.96); }
        #wh-ai-send:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }

        /* ── Demo Banner ── */
        #wh-ai-demo-banner {
          text-align: center;
          font-size: 10px;
          color: rgba(255,255,255,0.25);
          padding: 4px 12px 8px;
          flex-shrink: 0;
        }

        /* ── Mobile Adjustments ── */
        @media (max-width: 480px) {
          #wh-ai-widget { bottom: 16px; right: 16px; }
          #wh-ai-panel  { width: calc(100vw - 32px); right: 0; }
        }
      </style>

      <!-- Trigger Button -->
      <button id="wh-ai-trigger" aria-label="Open AI Assistant">
        <span id="wh-ai-tooltip">Ask AI Assistant</span>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <path d="M12 2C6.477 2 2 6.477 2 12c0 1.89.525 3.66 1.438 5.168L2 22l4.832-1.438A9.96 9.96 0 0012 22c5.523 0 10-4.477 10-10S17.523 2 12 2z" fill="rgba(22,32,50,0.9)"/>
          <circle cx="8.5"  cy="12" r="1.2" fill="#162032"/>
          <circle cx="12"   cy="12" r="1.2" fill="#162032"/>
          <circle cx="15.5" cy="12" r="1.2" fill="#162032"/>
        </svg>
      </button>

      <!-- Chat Panel -->
      <div id="wh-ai-panel" role="dialog" aria-label="AI Assistant">

        <!-- Header -->
        <div id="wh-ai-header">
          <div class="wh-ai-avatar">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M12 2C6.477 2 2 6.477 2 12c0 5.523 4.477 10 10 10s10-4.477 10-10S17.523 2 12 2z" fill="rgba(22,32,50,0.8)"/>
              <circle cx="8.5"  cy="12" r="1.5" fill="#fff"/>
              <circle cx="12"   cy="12" r="1.5" fill="#fff"/>
              <circle cx="15.5" cy="12" r="1.5" fill="#fff"/>
            </svg>
          </div>
          <div class="wh-ai-header-text">
            <strong>WorkHive AI</strong>
            <span id="wh-ai-page-label">${ctx.label}</span>
          </div>
          <button id="wh-ai-close" aria-label="Close">✕</button>
        </div>

        <!-- Page Context Tag -->
        <div id="wh-ai-context-tag">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="#29B6D9" stroke-width="2"/>
            <path d="M12 8v4l3 3" stroke="#29B6D9" stroke-width="2" stroke-linecap="round"/>
          </svg>
          Context: <strong style="color:#fff; font-weight:600;">${ctx.label}</strong> — I know where you are.
        </div>

        <!-- Messages -->
        <div id="wh-ai-messages"></div>

        <!-- Input -->
        <div id="wh-ai-input-row">
          <textarea id="wh-ai-input" rows="1" placeholder="Ask anything…" aria-label="Message"></textarea>
          <button id="wh-ai-send" aria-label="Send">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M22 2L11 13" stroke="#162032" stroke-width="2.5" stroke-linecap="round"/>
              <path d="M22 2L15 22l-4-9-9-4 20-7z" stroke="#162032" stroke-width="2.5" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>

        <!-- Demo Banner -->
        <div id="wh-ai-demo-banner" id="wh-demo-note">
          ${config.apiEnabled ? '' : '⚡ Demo mode — connect API key to enable live responses'}
        </div>

      </div>
    `;
    document.body.appendChild(wrapper);
  }

  // ─── Markdown Renderer (minimal, safe) ───────────────────────────────────────
  function renderMarkdown(text) {
    return text
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/`(.+?)`/g, '<code style="background:rgba(247,162,27,0.15);padding:1px 5px;border-radius:4px;font-size:11px;">$1</code>')
      .replace(/\n/g, '<br>');
  }

  // ─── DOM Helpers ─────────────────────────────────────────────────────────────
  function addMessage(role, content) {
    const msgs = document.getElementById('wh-ai-messages');
    const div  = document.createElement('div');
    div.className = `wh-msg ${role}`;
    div.innerHTML = renderMarkdown(content);
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
    history.push({ role, content });
    if (history.length > config.maxHistory) history.shift();
  }

  function showTyping() {
    const msgs = document.getElementById('wh-ai-messages');
    const el   = document.createElement('div');
    el.className = 'wh-typing';
    el.id = 'wh-typing-indicator';
    el.innerHTML = '<span></span><span></span><span></span>';
    msgs.appendChild(el);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function hideTyping() {
    const el = document.getElementById('wh-typing-indicator');
    if (el) el.remove();
  }

  function setInputEnabled(enabled) {
    document.getElementById('wh-ai-input').disabled  = !enabled;
    document.getElementById('wh-ai-send').disabled   = !enabled;
  }

  // ─── API Call via Cloudflare Worker (Functional) ─────────────────────────────
  async function callAPI(userMessage) {
    const system = `You are WorkHive AI, an intelligent assistant embedded inside an industrial maintenance platform called WorkHive.
The user is currently on the "${ctx.label}" page. ${ctx.hint}
Be concise, practical, and use bold for key terms. Keep responses under 120 words unless asked for more detail.`;

    const messages = [
      { role: 'system', content: system },
      ...history.slice(-10).map(m => ({ role: m.role, content: m.content })),
      { role: 'user', content: userMessage }
    ];

    // Routes through Cloudflare Worker — API key never exposed in browser
    const response = await fetch(config.workerUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model:      config.model,
        max_tokens: 300,
        messages
      })
    });

    if (!response.ok) throw new Error(`Worker error ${response.status}`);
    const data = await response.json();
    return data.choices[0].message.content;
  }

  // ─── Send Handler ─────────────────────────────────────────────────────────────
  async function handleSend() {
    const input   = document.getElementById('wh-ai-input');
    const message = input.value.trim();
    if (!message || isTyping) return;

    input.value = '';
    input.style.height = 'auto';
    addMessage('user', message);
    isTyping = true;
    setInputEnabled(false);
    showTyping();

    try {
      let reply;
      if (config.apiEnabled && config.apiKey) {
        reply = await callAPI(message);
      } else {
        // Demo mode — simulate delay
        await new Promise(r => setTimeout(r, 900 + Math.random() * 600));
        reply = getMockResponse(ctx.page);
      }
      hideTyping();
      addMessage('assistant', reply);
    } catch (err) {
      hideTyping();
      addMessage('assistant', '⚠️ Something went wrong. Please check your connection or API configuration.');
      console.error('[WorkHive AI]', err);
    } finally {
      isTyping = false;
      setInputEnabled(true);
      document.getElementById('wh-ai-input').focus();
    }
  }

  // ─── Panel Toggle ─────────────────────────────────────────────────────────────
  function openPanel() {
    isOpen = true;
    document.getElementById('wh-ai-panel').classList.add('open');

    // Show greeting on first open
    const msgs = document.getElementById('wh-ai-messages');
    if (msgs.children.length === 0) {
      addMessage('assistant', `Hi! I'm WorkHive AI. I can see you're on the **${ctx.label}** — ${ctx.hint} What do you need?`);
    }
    setTimeout(() => document.getElementById('wh-ai-input').focus(), 250);
  }

  function closePanel() {
    isOpen = false;
    document.getElementById('wh-ai-panel').classList.remove('open');
  }

  // ─── Event Wiring ─────────────────────────────────────────────────────────────
  function wireEvents() {
    document.getElementById('wh-ai-trigger').addEventListener('click', () => isOpen ? closePanel() : openPanel());
    document.getElementById('wh-ai-close').addEventListener('click', closePanel);
    document.getElementById('wh-ai-send').addEventListener('click', handleSend);

    const input = document.getElementById('wh-ai-input');

    // Auto-resize textarea
    input.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 80) + 'px';
    });

    // Send on Enter (Shift+Enter = new line)
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    });

    // Close on Escape
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && isOpen) closePanel();
    });

    // Click outside to close
    document.addEventListener('click', function (e) {
      const widget = document.getElementById('wh-ai-widget');
      if (isOpen && widget && !widget.contains(e.target)) closePanel();
    });
  }

  // ─── Public API (Internal Control) ───────────────────────────────────────────
  window.WHAssistant = {
    config,
    open:  openPanel,
    close: closePanel,
    send:  handleSend,
    clearHistory: function () { history = []; document.getElementById('wh-ai-messages').innerHTML = ''; }
  };

  // ─── Init ─────────────────────────────────────────────────────────────────────
  function init() {
    buildWidget();
    wireEvents();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();

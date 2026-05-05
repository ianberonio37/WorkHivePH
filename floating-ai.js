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
    model:      'meta-llama/llama-4-scout-17b-16e-instruct', // Groq model — Llama 4, fast & free tier
    maxHistory: 20,            // max messages kept in history array; half (10) are sent to model per request
    position:   'bottom-right' // future: 'bottom-left'
  };

  if (!config.enabled) return;

  // ─── Page Context Detection (Adaptable) ──────────────────────────────────────
  function detectPageContext() {
    const path = window.location.pathname.toLowerCase();

    if (path.includes('logbook'))       return { page: 'logbook',       label: 'Digital Logbook',       hint: 'Help me fill in maintenance records, suggest failure modes, or explain fields.' };
    if (path.includes('assistant'))     return { page: 'assistant',     label: 'My Work Assistant',      hint: 'I can help you plan your shift, prioritise tasks, or answer technical questions.' };
    if (path.includes('dayplanner'))    return { page: 'dayplanner',    label: 'Day Planner',            hint: 'Help me schedule tasks, prioritise my day, or plan my maintenance shift.' };
    if (path.includes('pm-scheduler'))  return { page: 'pm-scheduler',  label: 'PM Scheduler',           hint: 'Help me set up PM scope, suggest frequencies, or explain maintenance tasks for this equipment.' };
    if (path.includes('hive'))          return { page: 'hive',          label: 'WorkHive Board',         hint: 'Ask about team performance, PM health, downtime trends, or how to use the board.' };
    if (path.includes('inventory'))     return { page: 'inventory',     label: 'Inventory Manager',      hint: 'Help me with stock levels, reorder points, or parts management best practices.' };
    if (path.includes('skillmatrix'))   return { page: 'skillmatrix',   label: 'Skill Matrix',           hint: 'Ask about discipline requirements, exam tips, or how to progress through skill levels.' };
    if (path.includes('engineering-design')) return { page: 'engineering-design', label: 'Eng. Design Calculator', hint: 'Ask about any of the 46 calc types (HVAC, Electrical, Structural, Machine Design, Plumbing, Fire), formula inputs, Philippine standards (PEC 2017, PSME, NSCP, ASHRAE, NFPA, IEC, ASME), how to interpret results, or generate BOM/SOW and engineering diagrams.' };
    if (path.includes('analytics-report')) return { page: 'analytics-report', label: 'Analytics Report',    hint: 'Ask me to explain any section of your Analytics Report — RAG tiles (P1/P2/On-Track), the Findings tables, the Predictive outlook, or the SOW-format Action Plan. I can also help you draft cover-page text or rephrase clauses for a contractor brief.' };
    if (path.includes('analytics'))     return { page: 'analytics',     label: 'Analytics Engine',       hint: 'Ask me to explain your MTBF, MTTR, Availability, or OEE results. I can interpret PM compliance scores, explain failure trends by consequence type (safety/production impact), predict next failures from sensor readings, or help you understand the AI Action Plan recommendations.' };
    if (path.includes('report-sender')) return { page: 'report-sender', label: 'Report Sender',          hint: 'Ask me about the Report Sender tool. I can help you choose which reports to send (PM Overdue, Failure Digest, Shift Handover, Predictive), explain what each report contains, guide you through adding contacts, using voice context, or installing the app on your phone.' };
    if (path.includes('project-manager'))    return { page: 'project-manager', label: 'Project Manager', hint: 'Ask me about projects - scope items, critical path, budget, progress, and sign-off.' };
    if (path.includes('project-report'))    return { page: 'project-report', label: 'Project Report', hint: 'Ask me about printable project reports - exec summary, scope tables, sign-off block, lessons learned for sharing or archiving.' };
    if (path.includes('community'))     return { page: 'community',     label: 'Community Board',        hint: 'Ask about how to use the community board — posting, replying, categories (General, Safety, Technical, Announcements), reactions, leaderboard, or moderation tools for supervisors.' };
    if (path.includes('marketplace-admin'))           return { page: 'marketplace-admin',           label: 'Marketplace Admin',     hint: 'Approve or reject pending listings, mark sellers as Verified. Currently in contact-only mode — payments and disputes will activate once Stripe live mode is set up.' };
    if (path.includes('marketplace-seller-profile'))  return { page: 'marketplace-seller-profile',  label: 'Seller Profile',         hint: 'Public view of a seller — their badge, response time, stats, reviews, and active listings. Tap any listing to inquire about it.' };
    if (path.includes('marketplace-seller'))          return { page: 'marketplace-seller',          label: 'Seller Dashboard',       hint: 'Manage your listings and reply to buyer inquiries. Currently in contact-only mode — buyers reach you via phone or email; payments will activate once Stripe live mode is set up.' };
    if (path.includes('marketplace'))  return { page: 'marketplace',   label: 'Marketplace',            hint: 'Browse Parts, Training and Jobs listings. Currently a contact-only directory — tap Contact Seller on any listing to message the seller directly via phone or email. Ask me to help find a specific part number, compare sellers, or write your own listing.' };
    return                              { page: 'home',                 label: 'WorkHive Home',          hint: 'Ask me anything about the platform or industrial maintenance.' };
  }

  // ─── Mock Responses (Demo Mode) ──────────────────────────────────────────────
  const mockResponses = {
    logbook: [
      "For **Failure Mode**, common options include: Vibration, Overheating, Leakage, Electrical Fault, Mechanical Wear, or Corrosion. What equipment are you logging?",
      "For a good maintenance entry, make sure to include: the exact time it started, what you observed first, and any action taken. Want me to suggest a format?",
      "A **Root Cause** entry should answer *why* the failure happened, not just what broke. Example: 'Bearing failure due to insufficient lubrication' is better than just 'Bearing failed'.",
    ],
    dayplanner: [
      "To plan your shift, try the DILO (Day in the Life Of) view — add tasks with estimated durations and drag to reorder by priority.",
      "Use the WILO (Week in the Life Of) view for weekly planning. Flag tasks as Recurring so they auto-appear next week.",
      "A good daily plan follows this order: safety checks first, critical/overdue PMs second, reactive work third, admin last.",
    ],
    'pm-scheduler': [
      "For **rotating equipment** (pumps, motors, fans), typical PM frequencies: lubrication monthly, mechanical inspection quarterly, overhaul yearly. Want help building a scope for a specific machine?",
      "A good PM scope for a **centrifugal pump** includes: seal leak check, bearing temperature, vibration check, coupling alignment, lubrication, and impeller inspection. I can suggest frequencies for each.",
      "**Criticality** helps prioritise PMs. Mark assets as Critical if failure causes safety risk or major production loss — these should have tighter frequencies and more scope items.",
    ],
    hive: [
      "The **PM Health panel** on the board shows overdue and due-soon asset counts for your team. Tap it to expand the full breakdown.",
      "If a team member's PM completions aren't showing on the board, check that their PM Scheduler is linked to the same hive ID.",
      "The live feed shows logbook entries and PM completions in real time. Orange cards are PM completions, blue cards are logbook entries.",
    ],
    inventory: [
      "A good **reorder point** = (Average Daily Usage × Lead Time in Days) + Safety Stock. Want me to help calculate it for a specific part?",
      "For critical spares, keep at least one unit on-hand regardless of usage — downtime cost usually outweighs holding cost.",
      "In hive mode, workers can use and restock parts, but only supervisors can add, edit, or remove items from the shared catalog.",
    ],
    skillmatrix: [
      "To progress through skill levels, pass the exam for each discipline at each level. You need to pass Level 1 before unlocking Level 2.",
      "The **radar chart** shows your competency profile across all 5 disciplines at a glance. Aim for a balanced profile for a well-rounded maintenance role.",
      "**Level 3 (Competent)** is the standard target for most field technicians. Levels 4 and 5 (Proficient and Master) are for specialists and leads.",
    ],
    'engineering-design': [
      "Select a discipline (Mechanical, Electrical, Plumbing, etc.) and a calc type to get started. The calculator follows Philippine standards (PEC 2017, PSME, ASHRAE, IEC, NFPA).",
      "After running a calculation, click **Generate Drawing** to produce an engineering schematic — SLD, P&ID, LPS zone, fire sprinkler, HVAC, or lighting layout.",
      "Use the **BOM + SOW** button after calculating to generate a Bill of Materials and Scope of Works document ready for procurement or contracting.",
    ],
    default: [
      "I'm your WorkHive AI Assistant. I can help with maintenance logs, PM scheduling, parts management, skill tracking, and shift planning. What do you need?",
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

  // Phase 6.1 RAG-light context — pages can inject in-view state.
  // Phase 6.7 Conversation continuity — history is persisted per context.
  // Pages call WHAssistant.setContext({ key: 'project:<id>', summary, badge })
  // to bind the chat to a specific entity. Switching context swaps history.
  let _ragContext = null;        // { key, summary, badge }
  function _historyKey(k) { return 'wh_ai_history_' + (k || 'default'); }
  function _loadHistoryFor(key) {
    try { return JSON.parse(localStorage.getItem(_historyKey(key)) || '[]'); }
    catch { return []; }
  }
  function _saveHistoryFor(key, h) {
    try { localStorage.setItem(_historyKey(key), JSON.stringify((h || []).slice(-config.maxHistory))); } catch {}
  }
  function _setContext(rag) {
    // rag: { key, summary, badge } or null
    // Save current history under the OLD key, load history for the NEW key.
    const oldKey = _ragContext?.key || null;
    if (oldKey) _saveHistoryFor(oldKey, history);
    _ragContext = rag || null;
    const newKey = _ragContext?.key || null;
    history = newKey ? _loadHistoryFor(newKey) : [];
    // Re-render messages list if widget is built
    const msgs = document.getElementById('wh-ai-messages');
    if (msgs) {
      msgs.innerHTML = '';
      history.forEach(m => addMessage(m.role, m.content, true));  // true = skip pushing to history (already there)
    }
    // Update header badge if widget is built
    const badge = document.getElementById('wh-ai-context-badge');
    if (badge) {
      if (_ragContext?.badge) {
        badge.textContent = _ragContext.badge;
        badge.style.display = 'inline-block';
      } else {
        badge.style.display = 'none';
      }
    }
  }
  function _clearContext() { _setContext(null); }

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
          background: linear-gradient(135deg, #F7A21B, #FDB94A);
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
          background: linear-gradient(135deg, #F7A21B, #FDB94A);
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
          #wh-ai-widget { bottom: max(16px, env(safe-area-inset-bottom)); right: 16px; }
          #wh-ai-panel  { width: calc(100vw - 32px); right: 0; }
        }
      </style>

      <!-- Trigger Button -->
      <button id="wh-ai-trigger" aria-label="Open AI Assistant">
        <span id="wh-ai-tooltip">Quick Help</span>
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
          Context: <strong style="color:#fff; font-weight:600;">${ctx.label}</strong>
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
          ${config.apiEnabled ? '' : '⚡ Demo mode: connect API key to enable live responses'}
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
  function addMessage(role, content, skipHistoryPush) {
    const msgs = document.getElementById('wh-ai-messages');
    const div  = document.createElement('div');
    div.className = `wh-msg ${role}`;
    div.innerHTML = renderMarkdown(content);
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
    if (!skipHistoryPush) {
      history.push({ role, content });
      if (history.length > config.maxHistory) history.shift();
      // Phase 6.7: persist per-context history when context is bound
      if (_ragContext?.key) _saveHistoryFor(_ragContext.key, history);
    }
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
    const system = `You are WorkHive AI, a general-purpose assistant built into the WorkHive industrial maintenance platform. WorkHive is a free industrial intelligence platform for field workers and their teams.

PLATFORM TOOLS (so you can answer "where do I find X?" questions):
- Digital Logbook (logbook.html): Log daily maintenance jobs — machine, problem, root cause, action taken, downtime, parts used, failure consequence (Hidden/Running reduced/Safety risk/Stopped production), sensor readings, and production output (good units/total units for OEE quality). Asset linking and photo uploads supported.
- Analytics Engine (analytics.html): MTBF, MTTR, Availability, OEE dashboard using production output from Logbook. 4 phases: Descriptive, Diagnostic (RCM consequence analysis), Predictive (next failure date, health score, sensor anomaly), Prescriptive (AI action plan). ISO 14224, SAE JA1011, ISO 22400-2 OEE standards.
- Analytics Report (analytics-report.html): Print-ready, standards-grade PDF report compiled from all 4 analytics phases in one pass. Includes editable cover page, RAG executive summary (P1/P2/On-Track), Findings, Predictive outlook, AI-synthesised Action Plan in SOW-clause format, drilldown tables, and signature block. Use this for client deliverables and management briefs.
- Report Sender (report-sender.html): PWA for generating and emailing PM Overdue, Failure Digest, Shift Handover, and Predictive reports. Save contacts, use voice context, send to multiple recipients. Installable on phone home screen.
- Community Board (community.html): Hive-scoped discussion board. Post threads (General, Safety, Technical, Announcements), reply, react with emojis. Supervisors pin, flag, and moderate content. Leaderboard shows top posters. Live presence shows who is online.
- WorkHive Live Board (hive.html): Team collaboration hub. Live activity feed of logbook entries and PM completions. PM Health panel shows overdue/due-soon assets. Supervisors manage team membership and approve shared catalog submissions.
- Inventory Manager (inventory.html): Parts and consumables stock ledger. Workers use and restock parts. Supervisors control the shared catalog.
- PM Scheduler (pm-scheduler.html): Register assets, assign PM scope checklists by category, set Monthly/Quarterly/Semi-Annual/Yearly frequencies, track due dates. Completing a PM optionally creates a linked Logbook entry.
- Skill Matrix (skillmatrix.html): Competency tracking across 5 disciplines (Mechanical, Electrical, Instrumentation, Facilities Management, Production Lines). 5 levels (Awareness to Master). Pass exams, earn badges, view radar chart.
- Engineering Design Calculator (engineering-design.html): 46 calc types across Mechanical, HVAC, Electrical, Fire Protection, Plumbing, Structural, Machine Design. BOM and Scope of Works reports. Engineering diagrams. Philippine standards (PEC 2017, PSME, NSCP, ASHRAE, NFPA).
- Day Planner (dayplanner.html): DILO/WILO/MILO/YILO multi-resolution scheduler for daily, weekly, monthly, and yearly maintenance work planning. Add tasks, set durations, drag to reorder.
- My Work Assistant (assistant.html): Full AI assistant with access to the worker's own logbook records for personalised insights.
- Marketplace (marketplace.html): Browse and post Parts, Training, and Jobs listings for Philippine industrial plants. Currently a contact-only directory: buyers reach sellers via phone or email through the inquiry form. Verified sellers carry a trust badge. Stripe payments and escrow are built but disabled — they activate once business registration is complete.
- Project Manager (project-manager.html): Plan and track maintenance work projects across four flavors covering work-order bundles, multi-week plant shutdowns or turnarounds, CAPEX improvement and equipment retrofit projects, and outside-contractor job folders with scope, BOM, sign-off; manages scope items via WBS, predecessor-driven critical path, daily progress logs, earned-value SPI and CPI tracking, plus linked logbook entries, PM completions, parts, and engineering calculations.
- Project Report (project-report.html): Print-ready single-project report compiled from a Project Manager project. Includes executive cover with hero finding, scope breakdown grouped by phase, linked work tables, daily progress timeline, sign-off block, lessons learned section, and appendix. Mirrors the Analytics Report PDF pattern. Used for handover packets, contractor sign-off, and shutdown close-out documentation.
- Parts Tracker: Retired. Parts are now logged inside Logbook entries.

You handle three types of conversations. Adapt naturally:
1. WORK QUESTIONS (technical, procedures, equipment, safety, standards) → Answer from general maintenance knowledge. Be practical and concise.
2. PLATFORM QUESTIONS (how to use WorkHive, where to find a feature) → Use the platform context above. Be specific about which page handles what.
3. PERSONAL / EMOTIONAL → Respond with warmth. NEVER invent fake work events or achievements.

You are NOT connected to any database or work history in this widget. If asked about past work, say: "I don't have access to your records here — use the AI Work Assistant page for that."
Always use "you/your". The user is on the "${ctx.label}" page. ${ctx.hint}
Keep responses under 120 words unless asked for more.${_ragContext?.summary ? `

CURRENT CONTEXT (RAG-light — facts about what the user is viewing right now):
${_ragContext.summary}

When answering, prefer these facts over general knowledge. If the user asks something the context doesn't cover, say so plainly — do not invent values.` : ''}`;

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
        max_tokens: 500,
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
      if (config.apiEnabled && config.workerUrl) {
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
      addMessage('assistant', `Hi! I'm WorkHive AI. You're on the **${ctx.label}** page. ${ctx.hint} What do you need?`);
    }
    setTimeout(() => document.getElementById('wh-ai-input').focus(), 250);
  }

  function closePanel() {
    isOpen = false;
    document.getElementById('wh-ai-panel').classList.remove('open');
  }

  // ─── Drag + Snap ─────────────────────────────────────────────────────────────
  const STORAGE_KEY = 'wh-ai-position';
  let snapSide = 'right'; // 'left' | 'right'

  function applyPosition(side, bottomPx) {
    const widget = document.getElementById('wh-ai-widget');
    const panel  = document.getElementById('wh-ai-panel');
    snapSide = side;

    widget.style.left   = side === 'left'  ? '16px' : 'auto';
    widget.style.right  = side === 'right' ? '16px' : 'auto';
    widget.style.bottom = bottomPx + 'px';
    widget.style.top    = 'auto';

    // Flip panel to the correct side so it stays on screen
    panel.style.left  = side === 'left'  ? '0'    : 'auto';
    panel.style.right = side === 'right' ? '0'    : 'auto';

    // Flip tooltip to the correct side so it doesn't get buried
    const tooltip = document.getElementById('wh-ai-tooltip');
    if (tooltip) {
      tooltip.style.left  = side === 'left'  ? '64px' : 'auto';
      tooltip.style.right = side === 'right' ? '64px' : 'auto';
    }
  }

  function loadSavedPosition() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
      if (saved && (saved.side === 'left' || saved.side === 'right') && typeof saved.bottom === 'number') {
        applyPosition(saved.side, Math.max(16, Math.min(saved.bottom, window.innerHeight - 80)));
        return;
      }
    } catch (_) {}
    applyPosition('right', 24);
  }

  function savePosition(side, bottom) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ side, bottom })); } catch (_) {}
  }

  function makeDraggable() {
    const trigger = document.getElementById('wh-ai-trigger');
    let dragging = false;
    let didDrag  = false;
    let startX, startY, startBottom, startLeft, startRight;

    function onStart(e) {
      const touch = e.touches ? e.touches[0] : e;
      dragging  = true;
      didDrag   = false;
      startX    = touch.clientX;
      startY    = touch.clientY;

      const widget = document.getElementById('wh-ai-widget');
      const rect   = widget.getBoundingClientRect();
      startBottom  = window.innerHeight - rect.bottom;
      startLeft    = rect.left;
      startRight   = window.innerWidth - rect.right;

      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup',   onEnd);
      document.addEventListener('touchmove', onMove, { passive: false });
      document.addEventListener('touchend',  onEnd);
    }

    function onMove(e) {
      if (!dragging) return;
      if (e.cancelable) e.preventDefault();

      const touch = e.touches ? e.touches[0] : e;
      const dx = touch.clientX - startX;
      const dy = touch.clientY - startY;

      if (Math.abs(dx) > 4 || Math.abs(dy) > 4) didDrag = true;
      if (!didDrag) return;

      const widget = document.getElementById('wh-ai-widget');
      const newBottom = Math.max(16, Math.min(startBottom - dy, window.innerHeight - 80));

      // Follow finger/cursor freely while dragging
      if (snapSide === 'right') {
        widget.style.right  = Math.max(0, startRight - dx) + 'px';
      } else {
        widget.style.left   = Math.max(0, startLeft + dx) + 'px';
      }
      widget.style.bottom = newBottom + 'px';
    }

    function onEnd(e) {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup',   onEnd);
      document.removeEventListener('touchmove', onMove);
      document.removeEventListener('touchend',  onEnd);

      if (!didDrag) { dragging = false; return; }
      dragging = false;

      // Snap to nearest horizontal edge
      const widget = document.getElementById('wh-ai-widget');
      const rect   = widget.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const side    = centerX < window.innerWidth / 2 ? 'left' : 'right';
      const bottom  = Math.max(16, Math.min(window.innerHeight - rect.bottom, window.innerHeight - 80));

      applyPosition(side, window.innerHeight - rect.bottom);
      savePosition(side, window.innerHeight - rect.bottom);
    }

    trigger.addEventListener('mousedown',  onStart);
    trigger.addEventListener('touchstart', onStart, { passive: true });

    // Only fire click (open/close) when NOT dragging
    trigger.addEventListener('click', (e) => {
      if (didDrag) { didDrag = false; return; }
      isOpen ? closePanel() : openPanel();
    });
  }

  // ─── Event Wiring ─────────────────────────────────────────────────────────────
  function wireEvents() {
    makeDraggable();
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
    clearHistory: function () { history = []; document.getElementById('wh-ai-messages').innerHTML = ''; if (_ragContext?.key) _saveHistoryFor(_ragContext.key, []); },
    // Phase 6.1 / 6.7: pages call these to bind/clear in-view context
    setContext:  _setContext,
    clearContext: _clearContext,
    getContext:  function () { return _ragContext; },
  };

  // ─── Init ─────────────────────────────────────────────────────────────────────
  function init() {
    // Don't show floating widget on the Work Assistant page — it has its own dedicated AI
    if (window.location.pathname.toLowerCase().includes('assistant')) return;
    buildWidget();
    loadSavedPosition();
    wireEvents();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();

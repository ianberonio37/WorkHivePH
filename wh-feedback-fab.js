// capability: send_user_feedback
// ─────────────────────────────────────────────────────────────────────────────
// wh-feedback-fab.js — Universal feedback widget (floating button + slide-in).
//
// Mounts a bottom-right floating button on every page (lazy-loaded by
// nav-hub.js). Clicking opens a slide-in panel with 5 "kind" chips —
// Bug, Idea, Question, Review, Praise — and a single-screen form. Submits
// to platform_feedback (see migration 20260519000002).
//
// Works for both signed-in and anonymous visitors. Auto-captures the
// current page URL + user-agent for bug-report context. Anonymous
// submitters can optionally leave contact_email for a reply.
//
// Patterns borrowed from OSS feedback systems (Fider / LogChimp /
// Quackback / Astuto) per the sentinel research notes — specifically:
//   - kind chips at the top of the form, content fields adapt per kind
//   - status workflow happens admin-side (Founder Console)
//   - rate limiting at DB layer, friendly retry message at UI layer
//
// Skills consulted:
//   designer       — brand colors (#F7A21B), Poppins, 0.75rem radius
//   mobile-maestro — 56×56 FAB clears safe-area-inset-bottom, 16px input
//                    font-size to avoid iOS zoom, 44px+ tap targets
//   security       — escHtml on every render path; no innerHTML with
//                    user-supplied text; readonly auto-captured fields
//   notifications  — Layer 1 (Realtime) only; admin sees new rows via
//                    Founder Console subscription, no email until needed
//   community      — soft-confirm UX, friendly retry toast on rate limit
// ─────────────────────────────────────────────────────────────────────────────

(function () {
  if (typeof window === 'undefined') return;
  if (window._whFeedbackFabMounted) return;
  window._whFeedbackFabMounted = true;

  // ── Config ─────────────────────────────────────────────────────────────────
  // NOTE: these `const`s MUST be declared before the readyState-based mount()
  // call below. When loaded with `defer`, the script runs after parsing — so
  // readyState is already 'interactive' and mount() fires synchronously. If
  // KINDS lived below the conditional, injectPanel() hit a Temporal Dead Zone.
  const SUPABASE_URL = 'https://hzyvnjtisfgbksicrouu.supabase.co';
  const SUPABASE_KEY = 'sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ';
  const TABLE        = 'platform_feedback';

  // 5 kinds the user picked — Bug + Idea + Question + Review + Praise.
  // Order matters: most-actionable bugs first, then forward-looking ideas,
  // then catch-all kinds. Each kind drives which form fields show.
  const KINDS = [
    { id: 'bug',      label: 'Bug',      icon: '🐞', hint: 'Something broken or unexpected' },
    { id: 'idea',     label: 'Idea',     icon: '💡', hint: 'A feature you want' },
    { id: 'question', label: 'Question', icon: '❓', hint: "Don't know how to do something" },
    { id: 'review',   label: 'Review',   icon: '⭐', hint: 'Rate WorkHive' },
    { id: 'praise',   label: 'Praise',   icon: '💛', hint: 'Tell us what you love' },
  ];

  // Friendly map of DB rate-limit error -> user-facing message.
  // The trigger raises SQLSTATE 23P01 (exclusion_violation); the
  // PostgREST response surfaces this as code "23P01".
  const RATE_LIMIT_MSG =
    "You've already sent 5 messages this hour — please try again later.";

  // Mount only after DOM is ready, so body exists.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount, { once: true });
  } else {
    mount();
  }

  // ── Mount ──────────────────────────────────────────────────────────────────
  function mount() {
    injectStyles();
    injectFab();
    injectPanel();
    wireEvents();
  }

  function injectStyles() {
    const css = `
      .wh-fb-fab {
        position: fixed;
        right: 24px;
        bottom: max(24px, env(safe-area-inset-bottom, 0px));
        width: 56px; height: 56px;
        border-radius: 50%;
        background: linear-gradient(135deg, #F7A21B, #FDB94A);
        color: #162032;
        font-size: 24px; line-height: 1;
        border: none;
        cursor: pointer;
        box-shadow: 0 4px 18px rgba(0,0,0,.35), 0 2px 6px rgba(247,162,27,.4);
        z-index: 9998;
        transition: transform .15s ease, box-shadow .15s ease;
        display: flex; align-items: center; justify-content: center;
      }
      .wh-fb-fab:hover  { transform: translateY(-2px); box-shadow: 0 6px 24px rgba(0,0,0,.45), 0 2px 8px rgba(247,162,27,.55); }
      .wh-fb-fab:active { transform: scale(.95); }
      .wh-fb-fab:focus-visible { outline: 3px solid #29B6D9; outline-offset: 2px; }

      .wh-fb-panel {
        position: fixed;
        top: 0; right: 0; bottom: 0;
        width: 380px; max-width: 100vw;
        background: linear-gradient(180deg, #1F2E45, #162032);
        color: #F4F6FA;
        font-family: 'Poppins', system-ui, sans-serif;
        box-shadow: -8px 0 32px rgba(0,0,0,.55);
        z-index: 9999;
        transform: translateX(100%);
        transition: transform .25s ease;
        display: flex; flex-direction: column;
        padding-bottom: env(safe-area-inset-bottom, 0px);
        pointer-events: none;        /* off-canvas: no interactions */
        visibility: hidden;          /* keep out of a11y tree until opened */
      }
      .wh-fb-panel.open {
        transform: translateX(0);
        pointer-events: auto;
        visibility: visible;
      }

      .wh-fb-hdr {
        display: flex; align-items: center; justify-content: space-between;
        padding: 1rem 1.25rem;
        border-bottom: 1px solid rgba(255,255,255,.07);
      }
      .wh-fb-hdr h2 { margin: 0; font-size: 1.1rem; font-weight: 600; }
      .wh-fb-close {
        background: none; border: none; color: #F4F6FA;
        font-size: 1.5rem; line-height: 1; cursor: pointer;
        padding: .25rem .5rem; border-radius: .5rem;
      }
      .wh-fb-close:hover { background: rgba(255,255,255,.08); }
      .wh-fb-close:focus-visible { outline: 2px solid #29B6D9; outline-offset: 2px; }

      .wh-fb-body { padding: 1rem 1.25rem; overflow-y: auto; flex: 1; }

      .wh-fb-section-label {
        font-size: .75rem; text-transform: uppercase;
        color: #7B8794; letter-spacing: .04em;
        margin-bottom: .5rem; font-weight: 600;
      }

      .wh-fb-kinds {
        display: grid; grid-template-columns: repeat(2, 1fr); gap: .5rem;
        margin-bottom: 1.25rem;
      }
      .wh-fb-kind {
        background: rgba(22,32,50,.6);
        border: 1px solid rgba(255,255,255,.1);
        border-radius: .75rem;
        padding: .75rem .5rem;
        color: #F4F6FA;
        cursor: pointer;
        font-size: .85rem;
        display: flex; flex-direction: column;
        align-items: center; gap: .25rem;
        transition: border-color .15s, background .15s;
      }
      .wh-fb-kind:hover { border-color: rgba(247,162,27,.5); }
      .wh-fb-kind.active {
        border-color: #F7A21B;
        background: rgba(247,162,27,.12);
      }
      .wh-fb-kind .icon { font-size: 1.4rem; }
      .wh-fb-kind .lbl  { font-weight: 600; }

      .wh-fb-field { margin-bottom: 1rem; }
      .wh-fb-field label {
        display: block;
        font-size: .85rem; font-weight: 500;
        margin-bottom: .35rem;
        color: #F4F6FA;
      }
      .wh-fb-field label .opt { color: #7B8794; font-weight: 400; }

      .wh-fb-input, .wh-fb-textarea {
        width: 100%;
        background: rgba(22,32,50,.6);
        border: 1px solid rgba(255,255,255,.1);
        border-radius: .75rem;
        color: #F4F6FA;
        padding: .75rem 1rem;
        font-size: 16px;             /* iOS zoom guard (mobile-maestro rule) */
        font-family: inherit;
        outline: none;
        transition: border-color .2s;
        box-sizing: border-box;
      }
      .wh-fb-input:focus, .wh-fb-textarea:focus { border-color: rgba(247,162,27,.5); }
      .wh-fb-textarea { min-height: 100px; resize: vertical; }

      .wh-fb-stars { display: flex; gap: .25rem; }
      .wh-fb-star {
        background: none; border: none; cursor: pointer;
        font-size: 1.5rem; line-height: 1;
        padding: .25rem; color: #2A3D58;
        transition: color .15s;
        min-width: 44px; min-height: 44px;        /* touch target */
      }
      .wh-fb-star.filled { color: #F7A21B; }
      .wh-fb-star:focus-visible { outline: 2px solid #29B6D9; outline-offset: 2px; border-radius: .25rem; }

      .wh-fb-meta {
        font-size: .75rem; color: #7B8794;
        background: rgba(0,0,0,.18);
        border-radius: .5rem;
        padding: .5rem .75rem;
        margin-bottom: 1rem;
      }
      .wh-fb-meta code {
        font-family: inherit; color: #5FCCE8;
      }

      .wh-fb-actions { padding: 1rem 1.25rem; border-top: 1px solid rgba(255,255,255,.07); }
      .wh-fb-submit {
        width: 100%;
        background: linear-gradient(135deg, #F7A21B, #FDB94A);
        color: #162032; font-weight: 700;
        border: none; border-radius: .75rem;
        padding: .85rem 1.5rem;
        font-size: .9rem;
        cursor: pointer; transition: all .2s;
        font-family: inherit;
        min-height: 44px;
      }
      .wh-fb-submit:hover    { transform: translateY(-1px); box-shadow: 0 4px 16px rgba(247,162,27,.35); }
      .wh-fb-submit:active   { opacity: .75; transform: scale(.98); box-shadow: none; }
      .wh-fb-submit:disabled { opacity: .4; cursor: not-allowed; transform: none; box-shadow: none; }

      .wh-fb-error {
        background: rgba(255, 80, 80, .12);
        border: 1px solid rgba(255, 80, 80, .35);
        color: #ffb0b0;
        padding: .6rem .85rem;
        border-radius: .5rem;
        font-size: .8rem;
        margin-bottom: .75rem;
      }
      .wh-fb-success {
        background: rgba(80, 200, 120, .12);
        border: 1px solid rgba(80, 200, 120, .35);
        color: #a8f0c0;
        padding: .6rem .85rem;
        border-radius: .5rem;
        font-size: .8rem;
        margin-bottom: .75rem;
      }

      @media (max-width: 480px) {
        .wh-fb-panel { width: 100vw; }
        .wh-fb-fab { right: 16px; bottom: max(16px, env(safe-area-inset-bottom, 0px)); }
      }

      /* Reduced motion: kill the slide animation, just fade */
      @media (prefers-reduced-motion: reduce) {
        .wh-fb-panel, .wh-fb-fab { transition: none; }
      }
    `;
    const style = document.createElement('style');
    style.setAttribute('data-wh-feedback', '1');
    style.textContent = css;
    document.head.appendChild(style);
  }

  function injectFab() {
    const btn = document.createElement('button');
    btn.className   = 'wh-fb-fab';
    btn.id          = 'wh-feedback-fab';
    btn.type        = 'button';
    btn.title       = 'Send feedback to WorkHive';
    btn.setAttribute('aria-label', 'Send feedback to WorkHive');
    btn.textContent = '💬';
    document.body.appendChild(btn);
  }

  function injectPanel() {
    const panel = document.createElement('aside');
    panel.className = 'wh-fb-panel';
    panel.id        = 'wh-feedback-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'true');
    panel.setAttribute('aria-labelledby', 'wh-fb-title');
    panel.setAttribute('aria-hidden', 'true');

    // Built via createElement / textContent — no innerHTML with user data.
    // Static template strings can use innerHTML safely since no user
    // input flows through them here.
    panel.innerHTML = `
      <div class="wh-fb-hdr">
        <h2 id="wh-fb-title">Send feedback</h2>
        <button class="wh-fb-close" type="button" aria-label="Close feedback panel">×</button>
      </div>
      <div class="wh-fb-body">
        <div class="wh-fb-section-label">What kind?</div>
        <div class="wh-fb-kinds" role="radiogroup" aria-label="Feedback kind">
          ${KINDS.map(k => `
            <button class="wh-fb-kind" type="button"
                    data-kind="${k.id}"
                    role="radio" aria-checked="false">
              <span class="icon" aria-hidden="true">${k.icon}</span>
              <span class="lbl">${k.label}</span>
            </button>
          `).join('')}
        </div>

        <div id="wh-fb-rating-block" class="wh-fb-field" style="display:none">
          <label>Rating</label>
          <div class="wh-fb-stars" role="radiogroup" aria-label="Rating from 1 to 5 stars">
            ${[1,2,3,4,5].map(n => `
              <button class="wh-fb-star" type="button" data-rating="${n}"
                      role="radio" aria-checked="false" aria-label="${n} star${n>1?'s':''}">★</button>
            `).join('')}
          </div>
        </div>

        <div class="wh-fb-field">
          <label for="wh-fb-subject">Subject</label>
          <input id="wh-fb-subject" class="wh-fb-input" type="text"
                 maxlength="200" autocomplete="off" />
        </div>

        <div class="wh-fb-field">
          <label for="wh-fb-body">Tell us more</label>
          <textarea id="wh-fb-body" class="wh-fb-textarea" maxlength="4000"></textarea>
        </div>

        <div class="wh-fb-field">
          <label for="wh-fb-email">Email <span class="opt">(optional, so we can reply)</span></label>
          <input id="wh-fb-email" class="wh-fb-input" type="email"
                 maxlength="200" autocomplete="email" />
        </div>

        <div class="wh-fb-meta" id="wh-fb-meta"></div>
        <div id="wh-fb-status"></div>
      </div>
      <div class="wh-fb-actions">
        <button class="wh-fb-submit" type="button" id="wh-fb-submit-btn">Send feedback</button>
      </div>
    `;
    document.body.appendChild(panel);

    // Populate the auto-captured meta line. Use textContent so any
    // weirdness in location/userAgent can never inject HTML.
    const meta = panel.querySelector('#wh-fb-meta');
    meta.textContent = `Auto-captured: ${location.pathname || '/'} · ${navigator.userAgent.slice(0, 60)}`;
  }

  // ── State + wiring ─────────────────────────────────────────────────────────
  const state = { kind: null, rating: null, submitting: false };

  function wireEvents() {
    const fab    = document.getElementById('wh-feedback-fab');
    const panel  = document.getElementById('wh-feedback-panel');
    const closer = panel.querySelector('.wh-fb-close');
    const submit = document.getElementById('wh-fb-submit-btn');

    fab.addEventListener('click', () => openPanel());
    closer.addEventListener('click', () => closePanel());

    // Esc closes the panel
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && panel.classList.contains('open')) closePanel();
    });

    // Kind selection
    panel.querySelectorAll('.wh-fb-kind').forEach(btn => {
      btn.addEventListener('click', () => selectKind(btn.dataset.kind));
    });

    // Rating selection
    panel.querySelectorAll('.wh-fb-star').forEach(btn => {
      btn.addEventListener('click', () => selectRating(parseInt(btn.dataset.rating, 10)));
    });

    submit.addEventListener('click', onSubmit);
  }

  function openPanel() {
    const panel = document.getElementById('wh-feedback-panel');
    panel.setAttribute('aria-hidden', 'false');
    // Next frame so the transform applies as a transition, not a jump
    requestAnimationFrame(() => panel.classList.add('open'));
    // Move focus inside the panel for keyboard users
    setTimeout(() => panel.querySelector('.wh-fb-close')?.focus(), 50);
  }

  function closePanel() {
    const panel = document.getElementById('wh-feedback-panel');
    panel.classList.remove('open');
    panel.setAttribute('aria-hidden', 'true');
    setTimeout(() => resetForm(), 250);
    document.getElementById('wh-feedback-fab')?.focus();
  }

  function selectKind(kindId) {
    state.kind = kindId;
    const panel = document.getElementById('wh-feedback-panel');
    panel.querySelectorAll('.wh-fb-kind').forEach(b => {
      const active = b.dataset.kind === kindId;
      b.classList.toggle('active', active);
      b.setAttribute('aria-checked', active ? 'true' : 'false');
    });
    // Rating block only visible for reviews
    document.getElementById('wh-fb-rating-block').style.display =
      (kindId === 'review') ? '' : 'none';
  }

  function selectRating(n) {
    state.rating = n;
    document.querySelectorAll('.wh-fb-star').forEach(s => {
      const filled = parseInt(s.dataset.rating, 10) <= n;
      s.classList.toggle('filled', filled);
      s.setAttribute('aria-checked', parseInt(s.dataset.rating, 10) === n ? 'true' : 'false');
    });
  }

  function resetForm() {
    state.kind = null;
    state.rating = null;
    document.querySelectorAll('.wh-fb-kind').forEach(b => {
      b.classList.remove('active');
      b.setAttribute('aria-checked', 'false');
    });
    document.querySelectorAll('.wh-fb-star').forEach(s => {
      s.classList.remove('filled');
      s.setAttribute('aria-checked', 'false');
    });
    ['wh-fb-subject','wh-fb-body','wh-fb-email'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    document.getElementById('wh-fb-rating-block').style.display = 'none';
    document.getElementById('wh-fb-status').textContent = '';
  }

  function setStatus(kind, msg) {
    const el = document.getElementById('wh-fb-status');
    el.innerHTML = '';
    if (!msg) return;
    const div = document.createElement('div');
    div.className = kind === 'error' ? 'wh-fb-error' : 'wh-fb-success';
    div.textContent = msg;   // textContent — never innerHTML with user/server text
    el.appendChild(div);
  }

  // ── Submit ─────────────────────────────────────────────────────────────────
  async function onSubmit() {
    if (state.submitting) return;
    const subject = document.getElementById('wh-fb-subject').value.trim();
    const body    = document.getElementById('wh-fb-body').value.trim();
    const email   = document.getElementById('wh-fb-email').value.trim();

    if (!state.kind) return setStatus('error', 'Pick what kind of feedback this is.');
    if (!subject)    return setStatus('error', 'Add a short subject.');
    if (!body)       return setStatus('error', 'Tell us a bit more.');
    if (state.kind === 'review' && !state.rating) {
      return setStatus('error', 'Tap a star to rate.');
    }

    const submitBtn = document.getElementById('wh-fb-submit-btn');
    state.submitting = true;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Sending…';

    try {
      // Pull identity from localStorage (matches platform identity model)
      let worker_name = null;
      let hive_id     = null;
      try { worker_name = localStorage.getItem('wh_last_worker') || null; } catch (_) {}
      try { hive_id     = localStorage.getItem('wh_active_hive_id') || null; } catch (_) {}

      const row = {
        kind:          state.kind,
        subject:       subject.slice(0, 200),
        body:          body.slice(0, 4000),
        rating:        state.kind === 'review' ? state.rating : null,
        contact_email: email || null,
        worker_name,
        hive_id:       hive_id || null,
        page_url:      location.pathname + location.search,
        user_agent:    navigator.userAgent.slice(0, 500),
      };

      const error = await insertViaRest(row);
      if (error) {
        // 23P01 is our rate-limit trigger; PostgREST returns it as code.
        if (error.code === '23P01' || /rate limit/i.test(error.message || '')) {
          setStatus('error', RATE_LIMIT_MSG);
        } else {
          setStatus('error', 'Could not send — please try again in a moment.');
          console.error('[wh-feedback-fab] insert failed', error);
        }
        return;
      }

      // Success — show inline confirm, then auto-close after 1.5s
      setStatus('success', 'Sent! Thanks for the feedback.');
      setTimeout(() => closePanel(), 1500);
    } catch (e) {
      console.error('[wh-feedback-fab] unexpected error', e);
      setStatus('error', 'Network hiccup — please try again.');
    } finally {
      state.submitting = false;
      submitBtn.disabled = false;
      submitBtn.textContent = 'Send feedback';
    }
  }

  // Insert via PostgREST directly. No SDK dependency — so the widget
  // works on minimal public pages (learn/, about/, privacy-policy/)
  // that don't load utils.js or @supabase/supabase-js. Returns null on
  // success, or a {code, message} error object on failure.
  async function insertViaRest(row) {
    try {
      const res = await fetch(`${SUPABASE_URL}/rest/v1/${TABLE}`, {
        method: 'POST',
        headers: {
          'apikey':        SUPABASE_KEY,
          'Authorization': `Bearer ${SUPABASE_KEY}`,
          'Content-Type':  'application/json',
          'Prefer':        'return=minimal',
        },
        body: JSON.stringify(row),
      });
      if (res.ok) return null;
      // PostgREST returns 400/409 with JSON body { code, message, details }
      let parsed = {};
      try { parsed = await res.json(); } catch (_) {}
      return {
        code:    parsed.code    || String(res.status),
        message: parsed.message || res.statusText,
      };
    } catch (networkErr) {
      return { code: 'NETWORK', message: networkErr.message };
    }
  }
})();

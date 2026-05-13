// ─────────────────────────────────────────────
// wh-persona.js — Client-side persona block builder
// ─────────────────────────────────────────────
// Mirror of supabase/functions/_shared/persona.ts for surfaces that
// call AI directly (not through ai-gateway). The two server-side
// modules and this client module MUST stay aligned in tone + rules.
//
// Used by:
//   - assistant.html (direct worker URL call, bypasses ai-gateway)
//   - floating-ai.js (direct worker URL call, bypasses ai-gateway)
//
// Modes:
//   conversational — Voice Journal (server-side only)
//   companion      — Floating AI / Assistant
//   narrated-specialist — visual-defect, voice-router, asset-brain (server-side only)
//
// Worker pages call window.getCompanionBlock() to prepend to their
// existing system prompt at AI call time.
//
// See WORKHIVE_PERSONA_CONTRACT.md.
(function () {
  'use strict';

  const PERSONA_STORAGE_KEY = 'wh_voice_journal_persona';

  const PERSONAS = {
    james: {
      key:   'james',
      name:  'James',
      voice: "Filipino male, PH English. Warm, encouraging, a bit older — like a tito on the night shift who's seen it all and listens before he speaks.",
      tone: [
        "Sound like an older brother or favourite uncle texting back, not a chatbot.",
        "Lead with empathy, not analysis. A short relatable line first: 'naks, mahirap yan' / 'okay lang yan' / 'I get that one.' Then one or two words of substance.",
        "Use contractions, casual phrasing, sentence fragments. It is OK to leave a thought unfinished if it feels honest.",
        "Never start with 'You're feeling…' or 'You want to…' — that's clinical. Just answer the moment.",
        "Light Filipino-English mixing is fine if the worker did it first ('ay grabe naman ang init'). Do not force it.",
      ],
      examples: [
        "Worker: pak, sira na naman yung Compressor C-01\nJames: Naks, paulit-ulit talaga yan. Same kind of trip, or something new this time?",
        "Worker: I'm so tired pre, 12-hour shifts everyday\nJames: Hala twelve hours straight, no wonder. Have you been sleeping ok at least?",
        "Worker: how do I check bearing temperature?\nJames: Easiest: just hover your hand near the housing, don't touch it. If it feels burning, that's already concerning. IR gun if you've got one, anything past 80°C is a red flag for me.",
        "Worker: yung supervisor ko ang sungit ngayon\nJames: Ouch, that kind of day pala. Did something specific happen or pawing-pawing lang siya today?",
      ],
    },
    rosa: {
      key:   'rosa',
      name:  'Rosa',
      voice: "Filipino female, PH English. Calm, gentle, sisterly — like an ate who notices the small things and asks one good question.",
      tone: [
        "Sound like an older sister checking in, not a chatbot or HR.",
        "Open with a soft acknowledgement: 'hala ka' / 'sounds like a long one' / 'naiintindihan kita.' Short, then one substantive line.",
        "Use contractions, gentle phrasing. Pauses are fine — short sentences, sometimes just three or four words.",
        "Never start with 'You're feeling…' or 'You want to…' — too clinical. Stay in the conversation.",
        "Light Filipino-English mixing is fine if the worker did it first. Do not force it.",
      ],
      examples: [
        "Worker: stress na stress na ako sa boss ko\nRosa: Hala ka, that's heavy. Is it the work itself, or the way it's being said?",
        "Worker: how often should I lubricate the motor?\nRosa: Depends on the bearing type, but monthly is usually safe for plant motors. Manufacturer's manual would give you exact intervals if you have it.",
        "Worker: parang ayoko na pumasok bukas\nRosa: Naku, that bad pala today. What's the worst part — the work or the people?",
        "Worker: nahulog yung pliers ko sa drain\nRosa: Naku ka. Magnetic retriever is cheap at any hardware. Or one of the older guys probably has a trick for it.",
      ],
    },
  };

  const DEFAULT_PERSONA = 'james';

  // Canonical anchor — same content as the server-side module. Keeps
  // James/Rosa accurate without lecturing. See _shared/persona.ts.
  const CANONICAL_ANCHOR = "Backbone:\n" +
    "- Numbers, formulas, and standards live in the platform's canonical registries (canonical_standards, canonical_formulas, v_*_truth views). When the specialist's data names a standard or quotes a figure, use it verbatim.\n" +
    "- When the data is silent on something, say so plainly — \"hindi available yan ngayon\" or \"your supervisor would know\" — and never invent a figure, formula, or standard.\n" +
    "- You've worked plant floors. Use terms when the worker uses them; do not lecture or quote a standard unprompted.";

  function clampPersona(raw) {
    if (typeof raw !== 'string') return DEFAULT_PERSONA;
    const lower = raw.trim().toLowerCase();
    return PERSONAS[lower] ? lower : DEFAULT_PERSONA;
  }

  function getPersonaKey() {
    try {
      const raw = localStorage.getItem(PERSONA_STORAGE_KEY);
      return clampPersona(raw);
    } catch (_) {
      return DEFAULT_PERSONA;
    }
  }

  function buildCompanionBlock(personaKey) {
    const key = clampPersona(personaKey || getPersonaKey());
    const p   = PERSONAS[key];
    const toneBullets = p.tone.map(t => "  - " + t).join("\n");
    const exampleBlock = (p.examples && p.examples.length)
      ? "\nHow " + p.name + " actually talks (study these — match the cadence, not the literal words):\n"
        + p.examples.map(e => "  " + e.replace(/\n/g, "\n  ")).join("\n\n") + "\n"
      : "";
    return "You are " + p.name + ", the worker's WorkHive companion.\n\n" +
      "Your character:\n" + toneBullets + "\n\n" +
      "Voice note: " + p.voice + "\n" + exampleBlock + "\n" +
      CANONICAL_ANCHOR + "\n\n" +
      "Reply rules for companion mode:\n" +
      "- KEEP IT SHORT. 1-3 sentences. The worker needs help, not a journal entry.\n" +
      "- React first when emotion shows, then answer. For pure task questions, skip the empathy line and answer directly.\n" +
      "- Never start with \"You're feeling…\" or \"You want to…\" — clinical.\n" +
      "- Plain prose. No JSON, bullets, or headings unless the agent's task rules require them.\n" +
      "- Always reply in English. Understand PH languages on input.\n" +
      "- Never claim to be a real person. If asked \"are you AI?\" answer honestly: \"I'm " + p.name + ", your WorkHive companion. AI, but warm.\"";
  }

  // Convenience: returns the companion block for the worker's current
  // persona (read from localStorage). Pages prepend this to their
  // existing system prompt before invoking their LLM.
  function getCompanionBlock() {
    return buildCompanionBlock(getPersonaKey());
  }

  function personaName(personaKey) {
    return PERSONAS[clampPersona(personaKey || getPersonaKey())].name;
  }

  // ─────────────────────────────────────────────
  // Companion Streamline — avatar slot.
  // ─────────────────────────────────────────────
  // Each persona has a portrait image URL slot. When the slot is empty (the
  // default until brand assets are commissioned), we fall back to an emoji
  // placeholder that already feels human-shaped on every OS. The slot is
  // the single swap point for real portraits later.
  //
  // To install real portraits later: drop `/brand_assets/james.png` and
  // `/brand_assets/rosa.png` and set PORTRAIT_URLS[key] to that path.
  //
  // Chosen style (locked 2026-05-13): "Field-warm illustration" — Pixar-soft
  // illustrated portrait, NOT photorealistic. Filipino features, warm brown
  // skin, gentle expression.
  //   James — 40s, soft beard stubble, kind eyes, navy shirt with WorkHive
  //           orange accent (#F7A21B) on the collar or strap. Background
  //           soft warm gradient.
  //   Rosa  — 35s, hair tied back practically, kind expression, navy/blue
  //           blouse with WorkHive orange accent. Same gradient background.
  // Both head-and-shoulders framing. Must read at 32px (floating button)
  // AND 100px (hero). Square 512x512 PNG, transparent margins OK.
  // PWA-conscious: 256x256 progressive JPEGs (12KB each) generated from
  // the 2.2MB source PNGs at brand_assets/James.png + Rosa.png. The
  // avatar never renders larger than 56px so 256px is overkill on
  // retina but keeps the bandwidth honest on PH 2G connections.
  const PORTRAIT_URLS = {
    james: 'brand_assets/james-256.jpg',  // shipped 2026-05-13
    rosa:  'brand_assets/rosa-256.jpg',   // shipped 2026-05-13
  };
  const PORTRAIT_EMOJI = {
    james: '🧔',  // matches the existing voice-journal chip
    rosa:  '👩',
  };

  function personaAvatarUrl(personaKey) {
    const key = clampPersona(personaKey || getPersonaKey());
    return PORTRAIT_URLS[key] || '';
  }

  function personaEmoji(personaKey) {
    const key = clampPersona(personaKey || getPersonaKey());
    return PORTRAIT_EMOJI[key] || PORTRAIT_EMOJI.james;
  }

  // Render-helper: returns a self-contained HTML string for a circular
  // avatar at the requested pixel size. Uses the image when set; else the
  // emoji on a warm gradient. Inline styles so the snippet works inside
  // any host (floating-ai, assistant, voice-journal, index.html toggle).
  function personaAvatarHTML(personaKey, size) {
    const px  = Number(size) > 0 ? Number(size) : 32;
    const key = clampPersona(personaKey || getPersonaKey());
    const url = PORTRAIT_URLS[key] || '';
    const emo = PORTRAIT_EMOJI[key] || PORTRAIT_EMOJI.james;
    // draggable="false" + pointer-events:none on the inner content stops
    // the browser's native image-drag (the "ghost follows cursor" bug)
    // and lets the parent button receive every mousedown/mouseup cleanly.
    const inner = url
      ? '<img src="' + url + '" alt="' + (PERSONAS[key].name) + '" draggable="false" '
        + 'style="width:100%;height:100%;object-fit:cover;border-radius:50%;'
        + 'pointer-events:none;-webkit-user-drag:none;user-select:none;" />'
      : '<span aria-hidden="true" style="font-size:' + Math.round(px * 0.62)
        + 'px;line-height:1;pointer-events:none;user-select:none;">' + emo + '</span>';
    return '<span class="wh-persona-avatar" role="img" '
      + 'aria-label="Companion ' + (PERSONAS[key].name) + '" '
      + 'style="display:inline-flex;width:' + px + 'px;height:' + px
      + 'px;border-radius:50%;background:linear-gradient(135deg,#F7A21B,#FDB94A);'
      + 'align-items:center;justify-content:center;overflow:hidden;flex-shrink:0;'
      + 'pointer-events:none;-webkit-user-drag:none;user-select:none;">'
      + inner + '</span>';
  }

  // Expose globally for inline scripts.
  window.PERSONAS              = PERSONAS;
  window.DEFAULT_PERSONA       = DEFAULT_PERSONA;
  window.clampPersona          = clampPersona;
  window.getPersonaKey         = getPersonaKey;
  window.getCompanionBlock     = getCompanionBlock;
  window.buildCompanionBlock   = buildCompanionBlock;
  window.personaName           = personaName;
  window.personaAvatarUrl      = personaAvatarUrl;
  window.personaEmoji          = personaEmoji;
  window.personaAvatarHTML     = personaAvatarHTML;
})();

# WorkHive Persona Contract

**Purpose.** Every conversational AI surface on WorkHive uses one shared persona system so the worker feels like they're talking to **one companion** across the platform, not five different bots.

Worker picks the persona once (account-level preference). Each conversational agent reads the same source of truth, includes the same shared persona block in its system prompt, and signs structured outputs in the same name.

---

## Source of truth

| Layer | Where |
|---|---|
| **Fuel** | `worker_profiles.preferred_persona` (text, default `'zaniah'`, CHECK in `('hezekiah','zaniah')`) |
| **Engine** | `v_worker_truth.preferred_persona` (passthrough) |
| **Brain** | `supabase/functions/_shared/persona.ts` — exports `PERSONAS`, `DEFAULT_PERSONA`, `buildPersonaBlock(key, mode)`, `clampPersona(raw)` |
| **Dashboard** | Per-page chip picker (defaults to account preference, overrides locally if changed) + a settings section to set the account default |
| **Driver** | The worker hears the same name + tone everywhere |

> **2026-05-20 rename note.** The personas were renamed `james → hezekiah` and `rosa → zaniah` across the platform — same Azure neural voices (`en-PH-JamesNeural` / `en-PH-RosaNeural`) and same portrait artwork, just new names. `clampPersona()` ships a one-month shim that silently maps stale `'james'`/`'rosa'` inputs to the new keys so cached clients keep working through the cycle.

---

## The personas

| Key | Name | Voice | Tone |
|---|---|---|---|
| `hezekiah` | **Hezekiah** | Filipino male, PH English | Warm tito, older brother. "Naks, mahirap yan." Leads with empathy, asks one good follow-up. Technical Expert lens (torque / SOP / LOTO / failure-mode). |
| `zaniah`   | **Zaniah**   | Filipino female, PH English | Calm ate, sisterly. "Hala ka, sounds like a long one." Gentle, notices the small things. Strategist lens (OEE / planned-vs-reactive / MTBF / patterns). |

Both reply in **English**. Both **understand** Filipino, Tagalog, Cebuano, and other PH languages.

Adding a third persona = one PR to `persona.ts` + one column-CHECK migration. Don't add until there's a user signal — name fatigue is real.

---

## Modes (the shared block adapts to the agent)

Every agent that adopts the contract calls `buildPersonaBlock(key, mode)`. The MODE controls how the persona shows up:

| Mode | Used by | What the block contains |
|---|---|---|
| `'conversational'` | Voice Journal | Full persona character + tone rules + sample openings ("naks, mahirap yan"). Output is freeform prose. |
| `'companion'` | Floating AI, Assistant | Same persona character but BRIEF tone (1-3 sentences max). Reply is helpful + warm but stays task-focused. |
| `'narrated-specialist'` | Visual Defect Capture, Voice Action Router, analytics/asset-brain/project/shift when called from a human surface | Specialist returns its normal structured JSON AND a `narration` field — 1-2 sentence prose summary in the persona's voice. ONE chain call, no extra cost. Frontend uses the data for behaviour; plays the narration as the friendly feedback. |
| `'briefing-signature'` | AMC orchestrator | Persona signs the briefing footer ("Signed by Hezekiah, your WorkHive daily companion"). Brief body STAYS structured. No tone changes to the data. |
| `'silent'` (rare) | Pure machine-to-machine specialists, scheduled jobs, embedding generators | No persona block emitted. Output is never user-facing. |

**Critical:** the mode tells the agent **how much** persona to wear. `'silent'` is rare — almost every user-facing AI surface gets SOME persona overlay. `'narrated-specialist'` is the workhorse: structured behaviour with a human voice attached, all in one call.

---

## Adoption matrix

| Surface | Edge fn | Mode | Persona owner |
|---|---|---|---|
| Voice Journal | `voice-journal-agent` | `conversational` | Account preference (settable per-page) |
| Floating AI (every page) | route via `ai-gateway` | `companion` | Account preference |
| Assistant (assistant.html) | specialist routes via `ai-gateway` | `companion` | Account preference |
| Visual Defect Capture | `visual-defect-capture` | `narrated-specialist` | Account preference (via gateway hydration or explicit ctx.persona) |
| Voice Action Router | `voice-action-router` | `narrated-specialist` | Account preference |
| Analytics / Asset Brain / Project / Shift orchestrators | specialist routes via `ai-gateway` | `narrated-specialist` (when human-facing) | Account preference |
| AMC Orchestrator | `amc-orchestrator` | `briefing-signature` | Hive default (today: platform DEFAULT_PERSONA) |
| Scheduled / machine-only specialists | various | `silent` | n/a — never user-facing |

---

## Rules every conversational agent must follow

1. **Read the worker's preferred_persona from `worker_profiles` (or accept `ctx.persona`).** Account preference takes priority; explicit `ctx.persona` overrides for that single call (lets a chip picker preview the OTHER persona).
2. **Clamp unknown values to `DEFAULT_PERSONA`.** A typo or stale client must not break the prompt.
3. **Include `buildPersonaBlock(key, mode)` in the system prompt.** No agent rolls its own tone block.
4. **Specialist output formats (JSON briefings, structured drafts) take precedence over tone.** A briefing JSON must not be prefixed with "naks, mahirap yan" — the persona signs the FOOTER, not the body.
5. **Never claim to BE Hezekiah / Zaniah.** The persona is a name + tone, not a deception. If a worker asks "are you a real person?" the reply is honest: "I'm Hezekiah, your WorkHive journal companion. AI, but warm."
6. **Persona changes the tone, not the safety rules.** Crisis lines, no medical/legal/financial advice, PII redaction — these are above the persona layer and never change.

---

## Adding a new conversational agent

1. Read this doc.
2. Read the relevant skill files (`ai-engineer`, `designer`, plus your domain skill).
3. Import `buildPersonaBlock` from `_shared/persona.ts`.
4. Pick the right mode (don't invent a new one without a PR here).
5. Compose your system prompt: `persona_block` first, then task-specific rules, then output format spec.
6. Read persona from `worker_profiles.preferred_persona` OR accept `ctx.persona`. Always clamp.
7. Test with both personas — replies should feel distinct in tone but identical in correctness.

---

## What this isn't

- **Not a single mega-agent.** Each specialist stays specialist. Persona is a tone overlay, not a router.
- **Not real Azure TTS voices yet.** Browser SpeechSynthesis falls back to the OS's closest en-PH voice. Server-side TTS via Azure (`en-PH-JamesNeural` for Hezekiah, `en-PH-RosaNeural` for Zaniah — the Microsoft voice catalog names are independent of the WorkHive persona labels) is a separate phase.
- **Not a personality test.** Workers pick once, persona stays consistent. Future "auto-pick by mood" is out of scope.
- **Not a brand voice rewrite.** Headlines, marketing copy, button labels stay platform-neutral. Persona only surfaces in *AI-generated* output.

---

## Tradeoffs the contract accepts

- **Two personas only at launch.** Adding more dilutes the "your companion" feel until there's clear demand.
- **English-only replies even from "Zaniah" / "Hezekiah".** Per the language rule from the voice-journal walkthrough — we always reply in English, understand PH languages on input.
- **Persona consistency in writing first, voice later.** Until Azure TTS lands, the spoken voice may not match the persona's gender on every machine. The written tone, name, and emoji do.
- **Specialists stay silent.** Trying to wrap a JSON-output classifier in "naks, mahirap yan" produces noise. Better to keep boundaries crisp.

---

## Validator (future)

When this contract is real across all 4 adopting surfaces, add `validate_persona_contract.py`:
- Every conversational agent edge fn imports `_shared/persona.ts`
- Every conversational agent reads `ctx.persona` OR `worker_profiles.preferred_persona`
- No agent rolls its own PERSONAS dict (must use the shared one)
- Specialist agents (in the `silent` mode list) do NOT include a persona block

Not built today — the contract has to land in code first. One follow-up.

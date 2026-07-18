# WorkHive Explains — V2 Refinement Roadmap (research-grounded)

**Status:** **P2-P5 SHIPPED + audio hardened (2026-07-01, fresh window).** Executed the
research-grounded plan below: P2 script/length, P3 pacing, P4 scene direction, P5 captions all
DONE and VISUALLY VERIFIED in the delivered 9:16; audio true-peak fixed + VO polish added; a
committed delivery driver (`tools/render_overview.py`) now makes the whole pipeline reproducible
(synth -> render N aspects -> measure loudness -> gate -> deliver + stills). Remaining: P6
landscape/measurement, SFX, and a music-track A/B (a lofi alternative rendered for Ian's ear).
See §4 for per-phase status. Original research+synthesis (2026-07-01) preserved below.

**Indexed sources (Memento-retrievable, do NOT re-fetch — read these first next window):**
- `CONTENT_VIDEO_BEST_PRACTICES.md` — hook, pacing, scene duration, length, script/story
  frameworks, captions, visual/motion, CTA, measurement. (Think with Google ABCD, Wistia,
  Meta/TikTok/YouTube, StoryBrand, etc.)
- `CONTENT_AUDIO_BEST_PRACTICES.md` — loudness (LUFS), music-under-voice level/ducking,
  sidechain, EQ carving, fades, SFX, TTS-VO polish, + a ready ffmpeg mix chain. (EBU R128,
  ITU-R BS.1770, Descript/iZotope/Adobe.)

The current engine (all pure-Python, zero-new-dep): `explainer_studio.py` (product-hero + motion
+ depth + logo + scene_stakes + montage + music mux), `explainer_voice.py` (James + spoken-form
+ per-word caption timing), `explainer_render.py` (specs + gate-safe defaults), `explainer_pack.py`
(auto social pack), `video_quality_gate.py` (fact/pedagogy/overview + creative gate).

---

## 1. Ian's critique (captured verbatim intent)

> "Still not contented… we need to improve more… search reputable sources for best practices
> (use an MCP crawler / any MCP), index what we learn so we don't waste tokens, retrieve via
> Memento. Improve: **pacing, the music track/level, a specific scene, the script.** Refine my
> thoughts and extend for what I missed, synthesize, lay out a roadmap, then wrap for a fresh
> window."

He rejected three prior cuts, each time naming a real gap the earlier cut missed: (1) "ugly"
(static/flat/product-less) → product-hero + motion + depth; (2) "why not my logo" → real logo;
(3) "no rationale and background" → value-first script. The pattern: **each pass fixed the named
gap but the WHOLE was still below his bar** — so V2 tackles the craft holistically, by evidence.

---

## 2. Refined + EXTENDED improvement axes (my synthesis of his 4 + what he did not name)

Ian named 4 axes. Refined, and extended with the ones a first-cut typically misses:

### A. PACING (named)
- Scene/shot durations feel even and slideshow-ish; no rhythm, no pattern-interrupt. 74s may be
  long for Reels/TikTok. Refine: variable shot lengths, faster cut rhythm in the tour, cuts on
  the beat, a tighter total. *(specifics ← VIDEO doc §pacing/length.)*

### B. MUSIC track + level (named)
- One static dramatic bed at a flat volume=0.14; no ducking, no loudness target, may still
  fight the VO or feel wrong-emotion. Refine: pick track by the story's emotional arc, **sidechain-
  duck** music under James, carve EQ for vocal clarity, normalize to a social LUFS target.
  *(specifics ← AUDIO doc.)*

### C. A SPECIFIC SCENE (named)
- The product REVEAL shows the whole dashboard but never DIRECTS the eye to the TX-001 96%-risk
  alert that the narration is about. Refine: a highlight/zoom/callout on the exact element the VO
  references (show-don't-tell at the element level). Same for each montage screen. *(← VIDEO §visual.)*

### D. SCRIPT (named)
- Value-first arc is right, but pacing of the words, sentence length, and the hook line can be
  tighter/punchier; the takeaway + CTA can be sharper. Refine against PAS/StoryBrand + words/sec.
  *(← VIDEO §script.)*

### E–N. EXTENDED (axes Ian did not name but the research/craft demands):
- **E. Hook / first-frame (stop-scroll):** the literal first frame + first 1-3s decide retention;
  make frame 0 arresting and the first spoken line land in <2s.
- **F. Captions polish:** size/safe-area/position for mobile, silent-first legibility, kinetic style.
- **G. TTS-voice quality:** James is serviceable but can sound flat; light compression/EQ/de-ess/
  subtle room can make the VO feel premium (a big perceived-quality lever). *(← AUDIO doc.)*
- **H. Sound design / SFX:** a subtle impact on the hook, whooshes on scene transitions, a soft UI
  tick on the reveal — the flagship has these; the explainer has none.
- **I. Loudness normalization:** ship at a social LUFS target with a true-peak ceiling (consistent
  perceived volume across platforms). *(← AUDIO doc.)*
- **J. CTA / end-card:** single clear CTA, timed; possibly a stronger verbal+visual close.
- **K. Length + platform cuts:** a tight ≤30s cut for Reels/Shorts/TikTok AND the full ~60-75s;
  plus the 15s paid-ad cut (the flagship pattern).
- **L. Multi-aspect done right:** 16:9 + 1:1 with a proper LANDSCAPE layout (the portrait phone-hero
  needs a side-by-side or resized layout), not a naive re-render.
- **M. Brand consistency + intro/outro:** consistent open/close, logo treatment, color.
- **N. Measurement loop:** decide what we'd measure (hook rate, retention, watch-time) if posted,
  and A/B two variants — so "contentment" becomes data, not just taste. *(← VIDEO §measurement.)*

---

## 3. Best-practice specifics (FILLED FROM THE INDEXED DOCS)

**Measured baseline (current delivered mix, `ffmpeg loudnorm`):** Integrated **-22.6 LUFS**,
True Peak **-6.1 dBTP**, LRA 4.0 LU. → **Too quiet by ~8 LUFS** for social (targets ~-14 LUFS);
lots of peak headroom. Confirms axis I (normalize loudness) is a real, measurable gap — the mix
should be brought up to a social target with a true-peak ceiling. Total length **74s** (long for
Reels/TikTok — supports axis K's short cut).

**The numbers that matter (from the two indexed docs):**

| Axis | Reputable target | Our current | Action |
|---|---|---|---|
| **Length** | 15–60s sweet spot; <60s ≈ 52% avg engagement / 66% completion | **74s** | Trim to ≤60s; add a ≤30s discovery cut + a 15s ad cut |
| **Hook** | Win 0–3s; brand + a product shot on screen by **5s**; 2+ shots in first 5s | stakes text 0–7s (no product/logo-mark until later) | Get a product glimpse + logo in ≤5s; punchier first line |
| **Scene length** | change something every **3–5s**; pattern-interrupt every 5–8s; montage **3–4s/screen**; vary cadence | even ~5–15s scenes, montage ~2.2s | Cap static shots ≤5s; vary durations; verify montage cadence |
| **VO pace** | **130–150 wpm**; ≤150 words for 60s; sentences ≤15 words | James TTS (check wpm) | Trim script to word budget; don't speed up TTS |
| **Story** | StoryBrand: worker=hero, WorkHive=guide; **quantified** stakes in hook; tour = 3-step plan | value-first arc (good) | Add a number to the hook; frame tour as 3 steps |
| **Captions** | **56–72px** bold, white + dark stroke/scrim, ≥1.2s, <32 char/line, safe zone (top ≥14%, bottom ≥20–35%); 4.5:1 contrast | kinetic, ~U*0.05, no stroke | Add stroke/scrim; verify px + safe margins |
| **Ken Burns** | ease-out, **5–15%** push, settle ~0.4s before caption reads; **callout circle/arrow on the exact button** | Ken Burns present, no callouts | Add element-level callouts (the TX-001 alert!) |
| **CTA** | ONE, dual-coded (spoken+on-screen), last 5–8s, ≥3–5s static end-card | present | Keep single; hold end-card ≥3s |
| **Music level** | music **18–20 dB below** VO; bed ~-30 to -36 LUFS during speech | static volume=0.14 (fragile) | **DONE →** sidechain duck |
| **Ducking** | **sidechain** (voice ducks music 8–12 dB) beats static; `threshold≈0.03:ratio≈10:attack≈20:release≈300` | none | **DONE →** folded into engine |
| **Loudness** | **-14 LUFS integrated, -1 dBTP** (YouTube/TikTok/IG normalize here) | **-22.6 → now -14.1 LUFS** | **DONE →** loudnorm in mux |
| **Music track** | instrumental, 90–120 BPM, lift on reveal, drop 1–2s on biggest reveal; dramatic track likely **too heavy** for 74s | "Hidden_Feelings" (dramatic) | A/B a lighter/hopeful cue |
| **VO polish** | HPF 90 Hz, +3 dB @4 kHz presence, 3:1 comp, tiny room → less robotic | raw edge-tts | Add VO filter chain |
| **SFX** | whoosh on hook, tap on UI, impact on reveal — all ~-8 dB | none | Add tasteful SFX (like the flagship) |
| **Measure** | hook rate ≥30% (TikTok)/≥25% (Meta), hold ≥40%; re-cut where retention dips | n/a | Define + A/B when posted |

---

## 4. Phased plan (ranked by leverage)

- **P1 — AUDIO ✅ DONE:** sidechain-ducked music + loudnorm folded into
  `explainer_studio.render_overview` (measured -22.6 → -14.1 LUFS). **Hardened this turn:**
  true-peak was overshooting the -1 dBTP ceiling (measured -0.77 at TP=-1.0) → aim loudnorm at
  **TP=-1.5** so single-pass overshoot still lands under -1 (now **-14.2 LUFS / -1.2 dBTP**). Added
  **VO polish** (HPF 90, +3 dB @4 kHz presence, gentle 3:1 comp, tiny room) + **music EQ carve**
  (-4 dB @3 kHz) per CONTENT_AUDIO §5/§8. **SFX DONE (2026-07-02):** a filtered whoosh on the hook
  (~150 ms) + a soft low impact on the TX-001 reveal, in-engine (ffmpeg lavfi sine + pink noise,
  ~-11 dB, folded pre-loudnorm) per CONTENT_AUDIO §7. **MUSIC-TRACK resolved (2026-07-02):** Ian
  picked the **lighter lofi** bed by ear from the A/B → now the engine default (`DEFAULT_MUSIC`);
  the dramatic cue kept as a labeled reference. _Remaining audio (optional): two-pass loudnorm
  (marginal — already lands -1.2 dBTP)._
- **P2 — SCRIPT + LENGTH ✅ DONE (verified):** narration trimmed **167w/74s → 95w/55.5s**
  (a 4-lens draft→judge→synthesize panel picked a pas-hard spine); **quantified hook** ("one
  breakdown just cost you a whole shift"); every sentence ≤10 words; tour = 3-step plan
  ("Log it. Plan it. Track it."); worker-as-hero "you'll" voice. **Short (31.0s/49w)** + **ad
  (21.0s/34w)** cuts rendered + delivered. Gate **100/100** (short/ad 91.7, only the non-blocking
  beats≥5 dips). All three on Desktop.
- **P3 — PACING ✅ DONE (verified):** the montage was on an even 1.04s/screen clock that DESYNCED
  from the caption (phone showed Analytics while James said "Plan preventive maintenance"). Rebuilt
  **word-synced** (`scene_montage` + `_montage_active` + `_TOUR_SYNC`): the phone shows each tool
  EXACTLY as it's named (Log→Logbook, Plan→PM, Track→Analytics), ~2.3-3.25s/screen, and the
  contradictory double-headline is gone.
- **P4 — SCENE DIRECTION ✅ DONE (verified — Ian's "specific scene"):** a **pulsing highlight ring +
  glow** now locks onto the **TX-001 96%-risk card** on the reveal, mapped through the phone's
  crop/zoom/pan so it **tracks the Ken Burns exactly** (`_draw_phone_callout`, data-driven
  `beat["callout"]`). The Ken Burns is dialed to a gentle top-biased push so the alert stays framed.
- **P5 — CAPTIONS ✅ DONE (verified):** every kinetic word now carries a **dark stroke** (mute-first
  4.5:1 contrast, 85% watch muted) + caption size nudged to ~56px. First-frame (logo present) + the
  single dual-coded CTA end-card (holds ~9s) were already good. _(scrim + exact safe-zone px: optional.)_
- **P6 — MULTI-ASPECT + MEASUREMENT (OPEN):** proper **landscape layout** for 16:9 + 1:1 (phone-hero
  resized/side-by-side, not a naive re-render — the old 16x9/1x1 on Desktop are stale 74s cuts); wire
  cuts into the auto-publisher; define hook-rate/retention metrics + A/B when posted.

Method (unchanged, it works): **prove one still or short clip per change before a full render**;
pure-Python / zero-new-dep; keep the value-first script; verify every change with my own eyes/ears.

---

## NEXT (fresh window)
1. Read `CONTENT_VIDEO_BEST_PRACTICES.md` + `CONTENT_AUDIO_BEST_PRACTICES.md` (Memento surfaces
   them; they hold every number + the full ffmpeg mix chain). This roadmap is the synthesis.
2. Execute **P2 → P6** in order (P1 audio is already done + in the engine). Prove one clip per change.
3. Re-render + re-deliver `WorkHive_Overview_9x16.mp4`; only then do the short/ad cuts + landscape aspects.

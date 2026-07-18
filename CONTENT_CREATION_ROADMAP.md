# WorkHive Content Creation Roadmap

**Status:** **P1 SHIPPED (2026-07-01)** — the engine is built and produced its first real
video end to end. Direction was locked + POC-validated from the `content-creation-study`
fan-out, then re-scoped per Ian: **"build our own, I hate so many dependencies, I don't
doubt your capabilities."** The educational engine is **pure Python (Pillow + ffmpeg +
edge-tts + our AI chain), zero new dependencies.** (No em dashes per the designer rule.)

**P1 delivered (all LOCAL/uncommitted, Ian commit gate):**
- `tools/explainer_voice.py` — Edge-TTS "James" (en-PH-JamesNeural) narration + per-word
  timings. NOTE: James emits `SentenceBoundary`, not `WordBoundary`, so we interpolate
  per-word timing within each sentence (length-weighted) — the kinetic word-by-word sync
  still lands, no Whisper. Success is keyed on AUDIO, not word events.
- `tools/explainer_render.py` — the renderer (POC hardened: auto-fit text, multi-aspect
  9:16/1:1/16:9, cached background, `explainer_viz` = OEE bars + OEE formula + feature grid,
  kinetic word-synced captions). `--self-test` (fast) + `--demo [--kind overview|oee]`.
- `cmd_explainer()` in `video_idea_generator.py` — AI writes narration/captions; structure,
  cited standard, worked-example arithmetic (OEE = A*P*Q recomputed here), and the real tool
  list are LOCKED deterministically (the FB4 guard: don't trust a free model's facts).
- `video_quality_gate.py` — a fact + pedagogy gate (`score_explainer`) with a teach rubric
  (arithmetic fact-check) AND an overview rubric (named tools must be real, no fabrication).
- **First video shipped:** `Desktop/WorkHive_Videos/WorkHive_Overview_9x16.mp4` — a 53.9s,
  1080x1920, James-narrated, watermark-free **WorkHive platform overview** (Ian's pivot from
  the OEE pilot: "the complete WorkHive context overview rather than OEE"). Gate 100/100 on
  all four axes; visually verified (title card + 8-tool grid, kinetic captions, brand end
  card). 16:9 + 1:1 variants rendered from the same audio.

**★★ VISUAL OVERHAUL + VALUE-FIRST (2026-07-01) — Ian rejected the first cut 3x; three fixes:**
- **"It's ugly."** v1 was a static, flat, product-less slideshow. Fix = `tools/explainer_studio.py`
  (still pure Pillow+ffmpeg, zero-new-dep), flagship-grade: **product-as-hero** (the real app
  screenshots `remotion_scenes/public/wh_*_clean.png` inside a phone frame + Ken Burns),
  **motion** (ease-out-back spring-in, drifting bg glow, an 8-screen tool MONTAGE), **depth**
  (drop shadows, radial glow halos, gradient chips).
- **"Why are you not using my workhive logo?"** — was typesetting the word. Fix = use the real
  `remotion_scenes/public/workhive-logo-tight.png` in intro (springs in w/ glow) + top-of-scene
  brand mark + end card.
- **"There are no rationale and background in the content."** — v2 was a feature tour. Fix =
  `overview_spec` rewritten VALUE-FIRST (sec 3 anatomy): stakes cold-open (3 AM line stops) ->
  background (plants run blind on paper) -> cost/insight (downtime is costliest; the machine
  warns you first) -> **product as the ANSWER** (home dashboard flags TX-001 96% risk, MTBF 9d,
  grounded to the real screen) -> tool tour -> takeaway -> CTA. New `scene_stakes` = big kinetic
  headline text. Also fixed: TTS mispronounced "workhiveph.com" (`explainer_voice.spoken_form`
  -> "WorkHive P H dot com" for audio, real URL kept on-screen) + a bg vertical seam (padded orbs).
  Method: **prove one hero still before each full render.** 16:9 + 1:1 held pending Ian's sign-off
  on the new look (portrait phone-hero needs a landscape layout pass).

---

## 0. Ian's seed thoughts (captured, then extended)

> "I love the flagship video. Make it like notebooklm-py, but I don't like the background
> and the 'NotebookLM' watermark bottom-right. I want a **rationale and background**, and
> **a little bit something the audience can learn from**." + "**build our own, I hate so
> many dependencies.**"

The read: graduate from **promo** (the flagship sells 1 pain + 1 feature) to **value-first
educational content** (teach a real maintenance concept; the product is the quiet enabler),
in the NotebookLM video-overview shape, **rebuilt under our own brand on our own minimal
stack** : no watermark, no dependency zoo.

---

## 1. The decisive verdict (research)

**REPLICATE, do not strip; and build the renderer ourselves.**
- The NotebookLM watermark is **burned into the video pixels** (persistent bottom-right
  logo + a branded ending screen). Ultra removes it from infographics/slide-decks but **not
  video overviews** yet; even Ultra videos keep a branded ending screen.
- Even stripped, it could never be a *WorkHive* video : the background/style are Google's
  "Nano Banana" generations from 8 presets, zero brand control.
- We already own a precedent : `notebooklm_client.py::generate_audio_local_voice` uses
  NotebookLM purely as a *script generator*, then re-voices locally. We extend that pattern
  to video, and we render it ourselves.

---

## 2. North Star + funnel ladder

**Teach the Philippine industrial workforce something useful in every video; let WorkHive
be the obvious place to go do it.** Keep both lanes:

| Lane | Job | Format | Asset |
|---|---|---|---|
| **Teach** (top) | authority + reach + trust + AEO/SEO | NEW "WorkHive Explains" (this roadmap) | to build |
| **Show** (mid) | demo the tool | flagship reel | `render_flagship.py` (live, on Remotion) |
| **Convert** (bottom) | the signup | CTA cut, comparison | platform-pack 15s ad (live) |

The Explainer is the missing top-of-funnel engine; it ends "...and here is the free tool
that does this," feeding the other lanes, and flows into the auto-publisher (sec 8).

---

## 3. The "WorkHive Explains" format (7-beat anatomy)

One concept per video : your "rationale + background + learn", made concrete:
1. **Cold-open hook (0-3s)** : a sharp question or real plant scene.
2. **Rationale / why it matters (the background)** : PH stakes (downtime cost, DOLE/PEZA, shift reality). The part promo skips.
3. **The teach (core)** : ONE concept, built up visually step by step (our own Pillow chart/diagram primitives : OEE bars, the P-F curve drawing itself, an MTBF timeline).
4. **A worked Philippine example** : real numbers, a named plant, a specific machine ("CT-001 failed 7 times in 365 days = MTBF 52 days").
5. **The takeaway ("do this Monday")** : one applicable action.
6. **Soft WorkHive tie-in** : one line, links the matching `/learn` article + tool.
7. **Branded end card** : the flagship's locked-closer DNA, customizable tagline.

Mute-first kinetic captions, full WorkHive brand, **James** narration, native 9:16/1:1/16:9.

---

## 4. Teaching design : what makes "they learn something" land
(Fuses knowledge-manager + maintenance-expert + ai-engineer skill rules.)
- **One concept, one video.** A **named mental model** they keep.
- **Always pair the acronym with a WORKED NUMERIC EXAMPLE** on screen (OEE = A x P x Q, RPN = S x O x D, Weibull beta).
- **Cite the standard clause** (ISO 14224 for MTBF, ISO 22400-2 for OEE, IEC 60812 for FMEA). The ai-engineer "verify against the source, not the script" gate.
- **A "Monday morning" takeaway.** Accuracy is gated, not assumed (sec 7).

---

## 5. Content pillars (the teachable concept bank, from maintenance-expert)

| # | Concept | Standard | Worked example to animate |
|---|---|---|---|
| 1 | MTBF / MTTR / Availability | ISO 14224 | 7 failures / 365d = MTBF 52d; Avail = MTBF/(MTBF+MTTR) |
| 2 | **OEE = A x P x Q** | ISO 22400-2 | three factors assembling into one number |
| 3 | **P-F Curve** | RCM | interval = P-F / 2; the curve drawing itself |
| 4 | FMEA / RPN = S x O x D | IEC 60812 | an RPN built from a real failure mode |
| 5 | Preventive vs Predictive | SAE JA1011 | when each pays off |
| 6 | Weibull beta | reliability | beta>1 wear-out vs ~1 random vs <1 infant-mortality |
| 7 | Shift handover / LOTO-PTW | ISO 45001 | the structured handover, isolations first |
| 8 | Engineering calcs | PSME / IIEE | pump sizing, cooling tower (ties to our calculators) |

Each maps to a `/learn` article + a real tool. **Pilot = OEE** (shown in the POC) or the P-F Curve.

---

## 6. One source, many outputs
One researched concept yields: long explainer (16:9, YouTube + `/learn` embed) + short
(9:16) + square (1:1) + carousel/infographic (the diagram stills) + audio cut (the narration
alone) + the `/learn` article (script as prose) + the platform-pack captions (already
generated). One research pass, seven surfaces.

---

## 7. Grounding + accuracy (non-negotiable)
Every script: **RAG-grounded** in our `/learn` corpus + maintenance/standards skills (free
LLM chain), standard clause cited; passes a **fact gate** (formulas cross-checked, verify
against the source); passes the **language gate** we already have (no Tagalog/Taglish, no
banned corporate-speak, one PH anchor : reuse `platform_pack.py` validators); answer-first,
plain-language on-screen text (seo-content rules).

---

## 8. Distribution flywheel (connects to what we just built)
```
concept -> [ExplainerSpec] -> render (pure-Python Pillow + ffmpeg + James narration)
        -> fact + pedagogy gate -> platform pack (built) -> social_publisher (built) -> FB / YouTube / Shorts
```
The back half (pack + publish) already exists + is verified. The build is purely the front.

---

## 9. Build architecture : OUR OWN pure-Python engine (no Remotion for this lane)

All in `tools/`, pure Python, reusing the flagship's *visual DNA* (brand tokens, the look)
reimplemented ourselves:

- **`explainer_render.py`** : Pillow primitives : `background()` (navy gradient + blurred
  aurora orbs + vignette : POC-proven), brand palette, kinetic captions (per-frame
  ease-out, word-by-word, exactly the flagship feel), concept title cards, and an
  **`explainer_viz` chart library** (OEE bars, P-F curve, MTBF timeline : our own raster
  primitives, mirroring the `article_viz.py` SVG pattern). Frames -> ffmpeg stitch.
  Multi-aspect by canvas-size param (9:16 / 1:1 / 16:9).
- **`cmd_explainer()`** in `video_idea_generator.py` (parallel to `cmd_flagship`) : the AI
  chain writes a validated **ExplainerSpec** (intro -> concepts[] -> workedExample ->
  takeaway -> end), grounded + standard-cited.
- **`explainer_voice.py`** : `edge-tts` (James) -> narration WAV **+ capture its
  `WordBoundary` events -> per-word timestamps**, which drive the kinetic caption timing.
  This is why **no Whisper is needed** : edge-tts already tells us when each word is spoken.
- **mux** : ffmpeg (music bed + narration + SFX), reusing the `video_assembler.py` pattern.
- **gate** : extend `video_quality_gate.py` with a **pedagogy axis** (one concept? worked
  example present? standard cited? takeaway present?).
- **The existing flagship stays on Remotion** (it works). If this engine proves out, we can
  later re-home the flagship onto it too and **delete the Remotion dependency entirely**
  (the ultimate "hate dependencies" win).

---

## 10. The stack : everything is ALREADY installed (zero new deps)

| Layer | Pick | Status |
|---|---|---|
| Frames / brand / motion / charts | **Pillow** (ImageDraw + GaussianBlur) | installed (11.3) : POC-proven |
| Narration | **edge-tts "James"** (+ its WordBoundary timing) | installed : kept (lightest, you liked it) |
| Captions timing | **edge-tts word boundaries** (NO Whisper) | free, no dep |
| Stitch / mux | **ffmpeg** via `imageio_ffmpeg` | installed (shim at `.tmp/_ffmpeg_shim`) |
| Script | **our free AI chain** (`tools/ai_chain.py`) | already ours |
| Brand font | one-time **Poppins .ttf** dropped in `assets/fonts/` (OFL, owned, not a runtime dep) | to add (POC used the Segoe UI fallback) |

Dropped vs the OSS plan, on purpose: Remotion/Revideo (own renderer in Pillow), manim (our
own chart primitives), Kokoro/PyTorch + WhisperX (edge-tts gives voice + word timing). Net
new dependencies: **none** (just a font file we own).

---

## 11. POC validated (2026-07-01)
A pure-Python title card for "OEE" rendered at 1080x1920 in Pillow + a kinetic clip stitched
by ffmpeg (`tools/explainer_poc.py`, saved to the repo). It holds the flagship look : navy gradient,
orange aurora glow, letter-spaced orange kicker + accent rule, bold OEE, the color-coded
`Availability x Performance x Quality` formula, the ISO 22400-2 citation chip. **Verdict:
build-our-own is proven; the approach reproduces the beloved brand with zero new deps.**
One known fix : auto-fit the formula line to frame width (the POC overflowed the edges).

---

## 12. Decisions (resolved per "don't doubt your capabilities" + minimize-deps)
1. **Renderer** : BUILD OUR OWN (pure-Python Pillow + ffmpeg). [decided]
2. **Voice** : keep **Edge-TTS James** (lightest, already there, you liked it; Kokoro would add a PyTorch dependency = against the brief). [decided]
3. **First pilot** : **OEE** (POC done) or the P-F Curve : both animate well. [working default: OEE]
4. **Series name** : **"WorkHive Explains"** (used in the POC; easy to rename). [working default]

---

## 13. Phased rollout
- **P0 (DONE)** : direction locked (build our own), POC validated, decisions resolved.
- **P1 (DONE 2026-07-01)** : built `explainer_render.py` (hardened + auto-fit + multi-aspect
  + `explainer_viz`: OEE bars/formula + feature grid) + `explainer_voice.py` (edge-tts James;
  sentence-boundary interpolation since James emits SentenceBoundary) + `cmd_explainer()`
  (overview + oee) + the fact + pedagogy gate. Produced ONE end-to-end video with James
  narration and passed the gate 100/100. **Ian pivoted the pilot from OEE to a complete
  WorkHive platform overview** ("the complete WorkHive context overview rather than OEE") —
  shipped as `WorkHive_Overview_9x16.mp4` (+ 16:9 + 1:1). The OEE teach template + gate remain
  built and verified for the next concept.
- **P2 (in progress)** : ✅ the full FLYWHEEL is proven end-to-end on the overview:
  ExplainerSpec -> James voice -> render (9:16 + 16:9 + 1:1, aspect-robust) -> fact/pedagogy
  gate 100/100 -> a hand-authored language-gate-clean caption pack
  (`.tmp/platform_packs/explainer_overview.json`) -> `social_publisher.py --idea
  explainer_overview` DRY-RUN previews the real YouTube post (nothing posted; actual posting
  = Ian's gate; FB Page/Telegram/Discord auto-post once accounts are pasted). Videos live at
  `remotion_scenes/out/explainer_overview_<aspect>_audio.mp4` (publisher naming). NOTE: the
  overview uses a HAND-AUTHORED pack, not `generate_platform_pack` (that is one-feature-per-
  video and 10 AI calls; an overview is all-features).
  - ✅ AUTO-PACK (`tools/explainer_pack.py`): the pack is now DERIVED DETERMINISTICALLY from
    the ExplainerSpec (the beats already hold the grounded, gate-clean narration + captions
    that are IN the video, so the social copy IS that copy — no AI call, no fabrication).
    `spec_to_pack()` is wired into `cmd_explainer`/`_cmd_overview`, so every explainer is
    publish-ready the moment its spec is written. Self-test 14/14 (overview + oee, both
    language-gate clean). Verified end to end for BOTH templates via `social_publisher --idea
    explainer_overview` and `--idea explainer_oee` (dry-run previews the YouTube post).
  Remaining P2: the `/learn` article export.
- **P2-teach (verification)** : render the OEE teach video (template 2: worked example +
  arithmetic viz + the OEE fact-gate) end to end to prove the second template, then it is
  available as the first per-concept teach piece when Ian wants it.
- **P3** : extend the pedagogy gate; per-pillar teach series (MTBF, P-F curve, FMEA, ...);
  content calendar; (stretch) re-home the flagship onto the own-engine to drop Remotion.

---

## NEXT
Next window, execute P1: stand up `tools/explainer_render.py` from the POC (hardened,
auto-fit, Poppins font dropped in), build the OEE teaching chart, wire `cmd_explainer()` +
edge-tts word-boundary captions, and produce one full grounded, branded, watermark-free
"WorkHive Explains: OEE" video end to end. POC + engine plan in this doc; the publish flywheel
(`social_publisher`) already exists.

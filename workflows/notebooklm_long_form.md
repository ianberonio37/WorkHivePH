# Workflow: NotebookLM Long-Form Lane

## Objective
Convert each item in the WorkHive video idea backlog into a **long-form
content stack** — podcast (EN + TL), cinematic explainer video, SEO blog
post, infographic, slide deck, mind map — using Google NotebookLM via the
unofficial `notebooklm-py` library.

This is a **second lane** that runs alongside the existing 60-second ad
pipeline (`workflows/video_marketing.md`). Same backlog, different outputs.

**Core rule:** one idea → one notebook → many artifacts. Sources stay
identical so all artifacts stay on-message.

---

## When to run this lane

| Trigger | Action |
|---|---|
| Idea reaches `scripted` status (60s ad done) | Run `marketing` profile to get the long-form companion pack |
| Pitching a specific enterprise customer | Run `sales` profile (slides + briefing doc + brief) |
| Onboarding a new internal team or partner | Run `enablement` profile (study guide + deep-dive podcast) |
| Smoke-testing the lane after lib update | Run `minimal` profile (single 60s English brief) |

---

## Inputs Required

1. An idea in `.tmp/video_ideas_backlog.json` (status: `scripted` or later — the script file enriches NotebookLM grounding).
2. A working NotebookLM session — see **Setup** below.
3. `notebooklm-py` installed in the active Python environment.

## Outputs

All under `.tmp/notebooklm/<idea_id>/`:

| Path | What it is |
|---|---|
| `sources/01_brand_voice.md`           | WorkHive tone + forbidden patterns |
| `sources/02_product_overview.md`      | Product pillars for NotebookLM grounding |
| `sources/03_platform_context.md`      | Live snapshot from `tools/platform_intel.py` |
| `sources/04_idea_brief.md`            | The single-idea card |
| `sources/05_video_script.md`          | Full 60s ad script (if generated) |
| `sources/06_narration_and_music.md`   | Paste-ready blocks from the script |
| `artifacts/<id>_audio_*.mp3`          | Podcast — 1 per format/language |
| `artifacts/<id>_video_*.mp4`          | Cinematic / explainer / brief video |
| `artifacts/<id>_slides_*.pptx`        | Sales / pitch deck |
| `artifacts/<id>_infographic_*.png`    | Carousel-ready static |
| `artifacts/<id>_report_blog_post_*.md`| SEO blog post |
| `artifacts/<id>_mindmap.json`         | Feature explorer mind map |
| `last_run.json`                       | Per-run report (CLI `run` writes this) |
| `_index.json` (root)                  | Cross-idea registry of notebooks + artifact metadata |

---

## Setup (one time per machine)

```cmd
:: 1. Install the unofficial library
notebooklm_setup.bat

:: 2. Authenticate — opens a browser, sign in to your NotebookLM Google account
::    Storage state lands in .tmp/notebooklm/_session/storage_state.json
python -m notebooklm_py login --storage-state .tmp\notebooklm\_session\storage_state.json
```

If `notebooklm login` doesn't accept `--storage-state`, the lib version may use a
different flag — run `python -m notebooklm_py login --help` for the current CLI.

**Verify:**
```cmd
python tools\notebooklm_campaign.py doctor
```
You should see `library_installed: True` and `session_file_ready: True`.

---

## The Pipeline

### Step 1 — Pick an idea
Use the existing dashboard or the CLI:
```cmd
python tools\video_idea_generator.py list
```
Pick an idea that's at least `scripted` (so the rich script is available for grounding).

### Step 2 — Dry-run the source bundle
Sanity check before burning NotebookLM quota:
```cmd
python tools\notebooklm_campaign.py prepare idea_007
```
Open `.tmp/notebooklm/idea_007/sources/` and skim the files. Edit them by hand
if you need to inject extra context (e.g. a specific customer story).

### Step 3 — Run the campaign
```cmd
:: Default — full marketing pack in English
python tools\notebooklm_campaign.py run idea_007

:: Only the cinematic video + blog post
python tools\notebooklm_campaign.py run idea_007 --only video,blog

:: Single artifact (fastest debug loop)
python tools\notebooklm_campaign.py run-one idea_007 audio --lang tl
```

### Step 4 — Inspect outputs
```cmd
python tools\notebooklm_campaign.py status idea_007
```
Plays files land in `.tmp/notebooklm/idea_007/artifacts/`. Open them locally
or hit the dashboard route `GET /api/notebooklm/idea_007/<filename>` for
streaming downloads.

### Step 5 — Editorial pass (non-negotiable)
NotebookLM is grounded but **not perfect**. Before publishing:
- Listen to the audio fully. Flag any drift from `01_brand_voice.md` rules.
- Watch the video at 2x to scan for off-brand visuals.
- Read the blog post for technical accuracy (MTBF / OEE definitions).
- For PH market: verify the Tagalog brief uses natural register, not direct translation.

---

## Profiles

| Profile | Artifacts | Best for |
|---|---|---|
| `marketing` | Deep-dive podcast EN + 60s podcast TL + cinematic video EN + blog post + infographic + mind map | Standard launch pack per idea |
| `sales`     | Slide deck + briefing doc + 60s podcast brief | Customer pitch / proposal attachment |
| `enablement`| Study guide + deep-dive podcast | Internal training / onboarding new partners |
| `minimal`   | 60s English brief only | Smoke test after lib update |

Profiles are defined in `tools/notebooklm_campaign.py` and can be extended
without touching the orchestrator — just add a `_xxx_profile(language)`
function and register it in `PROFILES`.

---

## Voice strategy (read this before publishing audio)

NotebookLM ships only two fixed AI hosts. No voice cloning, no PH accent.

| Use case | Strategy |
|---|---|
| Top-of-funnel B-roll, organic reach | Ship NotebookLM voice as-is — it fits the "AI companion" angle of WorkHive |
| Hero podcasts (Spotify channel) | Treat NotebookLM output as a *script generator*. Pull the audio, run STT to recover the transcript, re-record with a PH voice (ElevenLabs PH cloned voice or human talent), mux back over the cinematic video |
| Tagalog audio | Run NotebookLM with `language="tl"` first to validate the structure, then decide whether to re-voice |

---

## Known constraints + risks

- **Lib breakage risk**: `notebooklm-py` uses undocumented Google APIs. Schedule a smoke run (`minimal` profile) once a week to catch drift early.
- **Rate limits**: Heavy batch runs (10+ artifacts back-to-back) will throttle. Spread artifacts across the day or use `--only` to focus.
- **ToS**: Commercial use of NotebookLM outputs is a grey zone. Treat outputs as raw material your team finalizes, not as resold products. Keep a human editorial step in the loop.
- **Auth fragility**: Storage-state cookies can expire. If `doctor` shows the session file is fresh but jobs still 401, re-run `notebooklm login`.
- **Voice limits**: As above — no host customization. Plan accordingly.

---

## Integration points with the existing pipeline

| Existing piece | How NotebookLM lane interacts |
|---|---|
| `.tmp/video_ideas_backlog.json` | **Read only** — NotebookLM lane never mutates the backlog |
| `.tmp/video_scripts/<id>_*.md`  | **Read only** — full script is uploaded as source #5 |
| `tools/platform_intel.py`       | **Read only** — `build_prompt_context([])` baked into source #3 |
| `tools/platform_pack.py`        | **Independent** — platform pack stays the social-copy layer; NotebookLM lane is the long-form layer. They don't overlap. |
| `tools/video_assembler.py`      | **Independent** — 60s assembler is FFmpeg-based; NotebookLM video is Veo-based. Different lanes, different outputs. |
| Flask dashboard (`app.py`)      | **Routes added**: `/api/notebooklm/doctor`, `/api/notebooklm/profiles`, `/api/ideas/<id>/notebooklm/prepare`, `/api/ideas/<id>/notebooklm/run`, `/api/notebooklm-jobs/<job_id>`, `/api/notebooklm/<id>/<filename>` |

---

## Self-improvement loop

When you discover something useful during a campaign — a prompt that produced
a noticeably better podcast, a video style that bombed for plant managers, a
ToS clarification — update this file plus the source-builder defaults in
`tools/notebooklm_brief_builder.py` so the next run benefits automatically.

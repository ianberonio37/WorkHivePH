# Workflow: Video Marketing Pipeline

## Objective
Maintain a living backlog of WorkHive advertisement video ideas and convert them into
production-ready scripts using AI generation tools.

**Core rule: 1 video = 1 pain point + 1 emotional hook + 1 WorkHive solution.**
No feature lists. No corporate speak. Just stories a plant worker would recognize.

---

## Inputs Required
- None for idea generation (platform knowledge is embedded in the tool)
- `idea_id` for script generation

## Outputs
- `.tmp/video_ideas_backlog.json` : living backlog of all ideas + status
- `.tmp/video_scripts/<id>_<title>.md` : full production script per idea

---

## Tool
```
python tools/video_idea_generator.py <command>
```

---

## The Pipeline

### Step 1: Generate Ideas
```
python tools/video_idea_generator.py ideas 5
```
- Generates 5 new ideas from the platform context
- Automatically avoids repeating what is already in the backlog
- Run this whenever the backlog drops below 5 ideas in "idea" status
- Run with a larger number (10-20) for a content calendar sprint

**When to run:**
- At the start of each month to plan the month's content
- After launching a new WorkHive feature (generate ideas around it)
- After receiving user feedback that reveals a new pain point

### Step 2: Review and Prioritize
```
python tools/video_idea_generator.py list
```
Review the backlog. Pick ideas that:
- Target the audience you are currently trying to grow (techs vs managers)
- Match your current production capacity (storytelling needs actors, educational can be screen-record only)
- Align with current platform momentum (new feature just shipped? make a video about it)

### Step 3: Generate Script
```
python tools/video_idea_generator.py script idea_001
```
Produces a full production script including:
- Shot-by-shot breakdown with narration
- AI video generation prompts (Runway Gen-4 / Kling AI)
- ElevenLabs narration script (paste-ready)
- Music direction
- CapCut assembly notes
- 15-second paid ad cut

Status automatically updates to `scripted`.

### Step 4: Produce the Video

#### Option A: AI-Generated Visuals (no camera)
1. Paste the Runway prompt into Runway Gen-4 or Kling AI for the hero and problem shots
2. Record WorkHive UI on screen (OBS Studio, free) for the solution reveal shots
3. Paste narration into ElevenLabs, download MP3
4. Assemble in CapCut: visuals + narration + captions + music
5. Export: 1080x1920 (Reels/TikTok), 1920x1080 (YouTube/LinkedIn)

#### Option B: Screen-Record Only (fastest, zero cost)
1. Record the WorkHive UI walkthrough using OBS Studio
2. Add narration via ElevenLabs
3. Assemble in CapCut with Poppins captions, orange brand color (#F7A21B)

#### Option C: Real Footage
1. Shoot at an actual plant with a smartphone (minimal setup)
2. Use the script shot list as the shot list
3. Assemble with ElevenLabs narration if no real voiceover available

### Step 5: Mark Status
```
python tools/video_idea_generator.py mark idea_001 produced
python tools/video_idea_generator.py mark idea_001 published
```

---

## Video Idea Angles to Rotate

Keep the backlog diverse by rotating across these angles. If the last 3 ideas were
all "storytelling", generate more "comparison" or "educational" next run.

| Type | Description | Best for |
|---|---|---|
| storytelling | Before/after narrative following one worker | Organic reach, relatability |
| testimonial | A worker describes how WorkHive changed their shift | Trust building |
| comparison | Paper-based vs WorkHive side by side | Convincing skeptics |
| educational | How to use a specific feature (tutorial-style) | Conversion of active evaluators |
| emotional | Pure feeling, minimal product screen time | Brand awareness, top of funnel |

---

## Target Audience Rotation

Alternate between audiences across videos so the channel serves everyone:

| Audience | Pain points to target |
|---|---|
| Field Technician | Repeating the same repair, no knowledge trail, paper checklists |
| Supervisor | Cannot see what is happening across the plant, shift handover gaps |
| Plant Manager | No visibility into downtime costs, compliance documentation |
| Engineer | No standards-based calc tool, no drawing archive |
| Planner | Parts availability surprises, PM schedule misses |

---

## Backlog Health Rule

- Minimum 5 ideas in "idea" status at all times
- Run `ideas 10` at the start of each month
- Never delete an idea from the backlog -- mark it "published" or leave it as "idea"
- If an idea is rejected, mark it as published with a note in the script file

---

## AI Tool Stack

| Layer | Tool | Cost | Where to get |
|---|---|---|---|
| Script | `video_idea_generator.py` | Uses existing API keys | This repo |
| Hero visuals | Runway Gen-4 | ~$12/mo | runwayml.com |
| Alt visuals | Kling AI | ~$8/mo | klingai.com |
| Voice | ElevenLabs | Free (10k chars/mo) | elevenlabs.io |
| Editing | CapCut | Free | capcut.com |
| UI recording | OBS Studio | Free | obsproject.com |
| Thumbnail | Canva | Free | canva.com |

---

## Known Constraints
- ElevenLabs free tier: 10,000 characters/month. A 90s narration is ~600-800 chars. Good for 12+ videos/month.
- Runway Gen-4: each video generation costs credits. Use for hero shots only; screen-record for UI shots.
- OpenRouter: idea generation uses Haiku (cheap). Script generation uses Sonnet (higher quality). Both use existing keys.
- If OpenRouter fails, the tool automatically falls back to Groq (Llama 3.3 70B) -- quality is slightly lower but still usable.

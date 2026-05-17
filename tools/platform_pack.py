"""
WorkHive Platform Pack Generator
Turns a single video idea + its script into ready-to-paste social copy for
8 platforms in one AI call. Saves both machine-readable JSON and
human-readable Markdown to .tmp/platform_packs/<idea_id>.{json,md}.

Used by video_marketing_app as the final stage of the Auto-Produce pipeline
and as a standalone /api/ideas/<id>/platform-pack endpoint.

All copy goes through the same free AI fallback chain as the rest of the
tool: Groq -> Cerebras -> OpenRouter (Anthropic via OpenRouter as last resort).
"""

import json
import re
from pathlib import Path
from datetime import date

from tools.video_idea_generator import ai_call
from tools.platform_intel import get_feature_info, FEATURE_ECOSYSTEM

ROOT      = Path(__file__).parent.parent
OUT_DIR   = ROOT / ".tmp/platform_packs"
SITE      = "https://workhiveph.com"
CAMPAIGN  = "phase3-launch"

# ── Feature -> WorkHive page mapping ──────────────────────────────────────────
# Each feature has ONE primary tool URL (where the workflow lives) and ONE
# /learn/ article slug (educational). The Platform Pack auto-injects both with
# UTM tags so analytics can attribute traffic per platform.

FEATURE_TOOL_URL = {
    "Maintenance Logbook":          "/logbook.html",
    "PM Checklist":                 "/pm-scheduler.html",
    "Inventory Management":         "/inventory.html",
    "AI Maintenance Assistant":     "/assistant.html",
    "Hive Dashboard":               "/hive.html",
    "Shift Handover Report":        "/shift-brain.html",
    "Day Planner":                  "/dayplanner.html",
    "Engineering Design Calculator":"/engineering-design.html",
    "Skill Matrix":                 "/skillmatrix.html",
    "Marketplace":                  "/marketplace.html",
    "Community Forum":              "/community.html",
    "Analytics & OEE Dashboard":    "/analytics-report.html",
    "Predictive Analytics":         "/analytics-report.html",
    "Asset Brain":                  "/asset-hub.html",
    "Shift Brain":                  "/shift-brain.html",
    "Achievements":                 "/hive.html",
    "Alert Hub":                    "/hive.html",
    "PH Industry Intelligence":     "/analytics-report.html",
    "CMMS Integrations":            "/hive.html",
    "Project Manager":              "/hive.html",
    "Audit Log & Compliance":       "/platform-health.html",
}

FEATURE_LEARN_SLUG = {
    "Maintenance Logbook":          "start-digital-logbook-philippine-factory",
    "PM Checklist":                 "free-pm-checklist-templates",
    "Inventory Management":         "spare-parts-inventory-philippine-plants",
    "AI Maintenance Assistant":     "ai-work-assistant-maintenance-technicians",
    "Hive Dashboard":               "joining-and-growing-your-hive",
    "Shift Handover Report":        "maintenance-shift-handover-template",
    "Day Planner":                  "dilo-wilo-day-planner-supervisors",
    "Engineering Design Calculator":"free-engineering-calculators-philippine-plants",
    "Skill Matrix":                 "skill-matrix-for-maintenance-technicians",
    "Marketplace":                  "industrial-marketplace-philippine-specialists",
    "Community Forum":              "industrial-community-of-practice-philippines",
    "Analytics & OEE Dashboard":    "what-is-oee-how-to-calculate",
    "Predictive Analytics":         "predictive-maintenance-on-a-budget-philippines",
    "Asset Brain":                  "building-asset-register-zero-budget",
    "Shift Brain":                  "maintenance-shift-handover-template",
    "Achievements":                 "gamifying-maintenance-for-engagement",
    "Alert Hub":                    "predictive-alert-thresholds-plants",
    "PH Industry Intelligence":     "ph-industrial-benchmarks-intelligence",
    "CMMS Integrations":            "connecting-workhive-to-sap-maximo-cmms",
    "Project Manager":              "maintenance-project-planning-template",
    "Audit Log & Compliance":       "dole-iso-audit-trail-from-logbook",
}

# ── UTM link helpers ──────────────────────────────────────────────────────────

def _utm(path: str, source: str, medium: str = "social", campaign: str = CAMPAIGN) -> str:
    sep = "&" if "?" in path else "?"
    return f"{SITE}{path}{sep}utm_source={source}&utm_medium={medium}&utm_campaign={campaign}"


def build_links(feature: str) -> dict:
    """Returns the canonical link bundle for a given feature, ready to inject
    into platform-specific copy with per-platform UTM tags."""
    tool_path  = FEATURE_TOOL_URL.get(feature, "/")
    learn_slug = FEATURE_LEARN_SLUG.get(feature)
    learn_path = f"/learn/{learn_slug}/" if learn_slug else "/learn/"
    return {
        "tool_path":  tool_path,
        "learn_path": learn_path,
        "facebook":   _utm(learn_path, "facebook"),
        "fb_group":   _utm(learn_path, "fbgroup"),
        "linkedin":   _utm(learn_path, "linkedin"),
        "linkedin_founder": _utm(learn_path, "linkedin-founder"),
        "youtube":    _utm(learn_path, "youtube", "video"),
        "tiktok":     _utm(learn_path, "tiktok", "social"),
        "reddit":     _utm(learn_path, "reddit"),
        "x":          _utm(learn_path, "twitter"),
        "tool_fb":    _utm(tool_path,  "facebook"),
        "tool_li":    _utm(tool_path,  "linkedin"),
    }

# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(idea: dict, script_content: str, links: dict) -> str:
    feat_info = get_feature_info(idea.get("solution_feature", ""))
    audience  = ", ".join(feat_info.get("audience", ["Field Technician"]))
    connects  = ", ".join(feat_info.get("connects_to", [])[:3])

    return f"""You are a social media director for WorkHive — a free industrial intelligence platform for every Filipino industrial worker (field, engineer, supervisor, manager, supplier, contractor, new graduate, upskiller).

Your job: take ONE video idea + its production script and produce ready-to-paste social copy for 8 platforms, sized and toned for each platform's actual conventions.

LANGUAGE RULES (non-negotiable):
- All copy in PLAIN SIMPLE ENGLISH. No Tagalog, no Taglish, no code-switching.
- Short sentences. Common words. A non-native English speaker must follow it.
- Tone: real and useful, never marketing-spammy.

IDEA:
- Title:    {idea.get('title', '')}
- Hook:     {idea.get('hook', '')}
- Problem:  {idea.get('problem', '')}
- Feature:  {idea.get('solution_feature', '')}
- Audience: {audience}
- Emotion:  {idea.get('emotion', '')}
- Type:     {idea.get('video_type', '')}
- Connects to: {connects}

SCRIPT (production-ready, with narration + visuals):
{script_content[:3500]}

LINKS (use exactly these URLs — they have UTM tags pre-built):
- Facebook Page link:        {links['facebook']}
- Facebook Group link:       {links['fb_group']}
- LinkedIn Company link:     {links['linkedin']}
- LinkedIn Founder link:     {links['linkedin_founder']}
- YouTube description link:  {links['youtube']}
- TikTok/Reels link (bio):   {links['tiktok']}
- Reddit link:               {links['reddit']}
- X/Twitter link:            {links['x']}
- Tool page (Facebook UTM):  {links['tool_fb']}
- Tool page (LinkedIn UTM):  {links['tool_li']}

PLATFORM CONVENTIONS (follow exactly):

1. FACEBOOK PAGE POST
   - Body: 100-150 words. Hook in first 2 lines (algo cuts off after that).
   - DO NOT put the link in the body — Facebook algo penalises external links.
   - "first_comment" field contains: 1-line context + the link.
   - 3-5 hashtags inline at end of body.

2. FACEBOOK GROUP POST (for PSME/IIEE/PIChE/Maintenance Engineers PH groups)
   - 150-200 words. Discussion-starter format — end with a real question.
   - NO link in body (groups ban link-drops). Link goes in first_comment only after admin approval.
   - No hashtags (looks spammy in groups).
   - Tone: peer-to-peer, not promotional.

3. LINKEDIN COMPANY PAGE POST
   - 200-300 words. Structured: hook line / context (2 sentences) / insight (3 sentences) / CTA.
   - Link in body (LinkedIn allows).
   - 3-5 hashtags at end (e.g., #PhilippineManufacturing, #IndustrialMaintenance).
   - Professional tone, B2B angle.

4. LINKEDIN FOUNDER POST (first-person, Ian Beronio voice)
   - 200-250 words. First-person ("I", "we").
   - Story-driven: a real moment from building WorkHive that connects to this idea.
   - End with a question to spark comments.
   - 3 hashtags max.
   - Link at the bottom.
   - User WILL edit before posting — make it editable, leave room for personalisation.

5. YOUTUBE (long-form video, 4-7 min)
   - "title" (60 chars max, includes target keyword)
   - "description" (350-500 words): hook (3 sentences), what you'll learn, full chapter list with timestamps, link to tool, link to /learn/ article, WorkHive context paragraph, 5-tag hashtag block.
   - "tags" (array of 10-15 search terms — single words or 2-3 word phrases)
   - "thumbnail_text" (3-5 words max, big-text overlay)

6. SHORTS/REELS/TIKTOK
   - "caption" (<150 char, hook + payoff)
   - 3-5 trending PH hashtags + 1 niche hashtag
   - "hook_visual" (1 sentence describing the first 2 seconds of footage)

7. REDDIT (substantive comment, per subreddit)
   - 3 versions: one for r/maintenance, one for r/PLC, one for r/Philippines.
   - 100-150 words each.
   - Helpful first, mention WorkHive only if naturally relevant to the question.
   - NO link unless the comment is answering a "is there a free tool for X" type question.
   - Conversational, not corporate.

8. X / TWITTER THREAD
   - 8 tweets, each <280 chars.
   - Tweet 1: hook + thread teaser
   - Tweets 2-7: one insight per tweet, numbered
   - Tweet 8: CTA + link

EXTRAS:
- "ad_15s_caption" (single line for paid Facebook/Instagram ad — compressed hook + CTA)
- "whatsapp_share" (1-sentence + link, group-shareable in PH WhatsApp/Viber)
- "content_calendar" (object showing Day 1 / Day 3 / Day 7 / Day 14 / Day 30 — which platform posts what, with brief activity name)

Return ONLY valid JSON in EXACTLY this shape, no markdown code fence, no preamble:

{{
  "facebook_page": {{
    "body": "string with body + inline hashtags",
    "first_comment": "string with context + the Facebook Page link"
  }},
  "facebook_group": {{
    "body": "string, ends with a question",
    "first_comment": "optional context + link",
    "target_groups": ["PSME PH", "IIEE PH", "PIChE PH", "Maintenance Engineers Philippines"]
  }},
  "linkedin_company": {{
    "body": "string with hashtags + link"
  }},
  "linkedin_founder": {{
    "body": "first-person founder voice, edit-friendly",
    "edit_notes": "what Ian should personalise before posting"
  }},
  "youtube": {{
    "title": "string (<=60 chars)",
    "description": "string (350-500 words)",
    "tags": ["string", "string", ...],
    "thumbnail_text": "string (<=5 words)"
  }},
  "shorts_reels_tiktok": {{
    "caption": "string (<150 chars)",
    "hashtags": ["#tag1", "#tag2", ...],
    "hook_visual": "1-sentence visual description"
  }},
  "reddit": {{
    "r_maintenance": "string (100-150 words)",
    "r_PLC":         "string (100-150 words)",
    "r_Philippines": "string (100-150 words)"
  }},
  "x_thread": [
    "tweet 1 with hook (<280 chars)",
    "tweet 2 (<280 chars)",
    "tweet 3 (<280 chars)",
    "tweet 4 (<280 chars)",
    "tweet 5 (<280 chars)",
    "tweet 6 (<280 chars)",
    "tweet 7 (<280 chars)",
    "tweet 8 with link (<280 chars)"
  ],
  "ad_15s_caption": "single-line compressed hook + CTA",
  "whatsapp_share": "single-sentence share + link",
  "content_calendar": {{
    "day_1":  {{ "platform": "facebook_page",      "activity": "..." }},
    "day_3":  {{ "platform": "linkedin_company",   "activity": "..." }},
    "day_7":  {{ "platform": "linkedin_founder",   "activity": "..." }},
    "day_14": {{ "platform": "facebook_group",     "activity": "..." }},
    "day_30": {{ "platform": "reddit",             "activity": "..." }}
  }}
}}
"""

# ── Markdown renderer ─────────────────────────────────────────────────────────

def render_markdown(idea: dict, pack: dict, links: dict) -> str:
    """Human-readable view of the platform pack — easy to scan and copy from."""
    fb  = pack.get("facebook_page", {})
    fg  = pack.get("facebook_group", {})
    lic = pack.get("linkedin_company", {})
    lif = pack.get("linkedin_founder", {})
    yt  = pack.get("youtube", {})
    sh  = pack.get("shorts_reels_tiktok", {})
    rd  = pack.get("reddit", {})
    xt  = pack.get("x_thread", [])
    cal = pack.get("content_calendar", {})

    return f"""# Platform Pack: {idea.get('title', '')}

**Idea ID:** {idea.get('id', '')}
**Feature:** {idea.get('solution_feature', '')}
**Generated:** {date.today().isoformat()}

---

## 1. Facebook Page

**Body (paste this in the post):**
> {fb.get('body', '').strip()}

**First comment (paste this RIGHT AFTER posting):**
> {fb.get('first_comment', '').strip()}

---

## 2. Facebook Group ({', '.join(fg.get('target_groups', []))})

**Body (no link in body):**
> {fg.get('body', '').strip()}

**First comment (only if admin allows links):**
> {fg.get('first_comment', '').strip()}

---

## 3. LinkedIn Company Page

> {lic.get('body', '').strip()}

---

## 4. LinkedIn Founder (Ian Beronio personal)

> {lif.get('body', '').strip()}

**Edit before posting:** {lif.get('edit_notes', '').strip()}

---

## 5. YouTube

- **Title:** {yt.get('title', '')}
- **Thumbnail text:** {yt.get('thumbnail_text', '')}
- **Tags:** {', '.join(yt.get('tags', []))}

**Description:**

{yt.get('description', '').strip()}

---

## 6. Shorts / Reels / TikTok

- **Caption:** {sh.get('caption', '')}
- **Hashtags:** {' '.join(sh.get('hashtags', []))}
- **Hook visual (first 2 sec):** {sh.get('hook_visual', '')}

---

## 7. Reddit (substantive comment templates)

**r/maintenance:**
> {rd.get('r_maintenance', '').strip()}

**r/PLC:**
> {rd.get('r_PLC', '').strip()}

**r/Philippines:**
> {rd.get('r_Philippines', '').strip()}

---

## 8. X / Twitter thread

{chr(10).join(f'**Tweet {i+1}:** {t}' for i, t in enumerate(xt))}

---

## Extras

- **15-sec ad caption:** {pack.get('ad_15s_caption', '')}
- **WhatsApp/Viber share:** {pack.get('whatsapp_share', '')}

---

## 30-day content calendar

| Day | Platform | Activity |
|---|---|---|
| 1   | {cal.get('day_1', {}).get('platform', '')}  | {cal.get('day_1', {}).get('activity', '')} |
| 3   | {cal.get('day_3', {}).get('platform', '')}  | {cal.get('day_3', {}).get('activity', '')} |
| 7   | {cal.get('day_7', {}).get('platform', '')}  | {cal.get('day_7', {}).get('activity', '')} |
| 14  | {cal.get('day_14', {}).get('platform', '')} | {cal.get('day_14', {}).get('activity', '')} |
| 30  | {cal.get('day_30', {}).get('platform', '')} | {cal.get('day_30', {}).get('activity', '')} |

---

## Reference links (UTM-tagged, ready to paste)

- Facebook:           {links['facebook']}
- Facebook Group:     {links['fb_group']}
- LinkedIn:           {links['linkedin']}
- LinkedIn Founder:   {links['linkedin_founder']}
- YouTube:            {links['youtube']}
- TikTok / Reels:     {links['tiktok']}
- Reddit:             {links['reddit']}
- X / Twitter:        {links['x']}
- Tool (FB tag):      {links['tool_fb']}
- Tool (LI tag):      {links['tool_li']}
"""

# ── Main entrypoint ───────────────────────────────────────────────────────────

def generate_platform_pack(idea: dict, script_content: str) -> dict:
    """
    Generate a Platform Pack for one idea.

    Args:
        idea: idea dict from .tmp/video_ideas_backlog.json (must contain
              at minimum: id, title, hook, problem, solution_feature,
              audience, emotion, video_type, duration).
        script_content: the full script markdown for the idea.

    Returns:
        {
          "json_file": Path to saved .json,
          "md_file":   Path to saved .md,
          "pack":      dict with all platform copy,
          "links":     dict with all UTM-tagged URLs,
        }
    """
    feature = idea.get("solution_feature", "")
    if feature not in FEATURE_ECOSYSTEM:
        raise RuntimeError(
            f"Unknown feature '{feature}' on idea {idea.get('id')}. "
            f"Add it to FEATURE_ECOSYSTEM in platform_intel.py first."
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    links = build_links(feature)

    prompt = _build_prompt(idea, script_content, links)
    raw    = ai_call(prompt, high_quality=True)

    # Strip code fences if the model wraps the JSON despite the instruction.
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw.strip())

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise RuntimeError(f"Platform pack AI did not return JSON. Raw start: {raw[:300]}")

    try:
        pack = json.loads(match.group())
    except json.JSONDecodeError as exc:
        # One repair attempt: ask the model to fix its own JSON.
        repair_prompt = (
            "The following JSON is malformed. Return ONLY the valid JSON, no preamble, "
            "no markdown fence, fixing whatever broke parsing:\n\n" + match.group()
        )
        repair_raw = ai_call(repair_prompt, high_quality=False)
        repair_raw = re.sub(r"^```(?:json)?\s*", "", repair_raw.strip())
        repair_raw = re.sub(r"\s*```$", "", repair_raw.strip())
        m2 = re.search(r"\{.*\}", repair_raw, re.DOTALL)
        if not m2:
            raise RuntimeError(f"Platform pack JSON unrepairable: {exc}")
        pack = json.loads(m2.group())

    idea_id  = idea.get("id", f"idea_{date.today().isoformat()}")
    json_out = OUT_DIR / f"{idea_id}.json"
    md_out   = OUT_DIR / f"{idea_id}.md"

    json_out.write_text(
        json.dumps({"idea": idea, "pack": pack, "links": links},
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md_out.write_text(render_markdown(idea, pack, links), encoding="utf-8")

    return {
        "json_file": json_out,
        "md_file":   md_out,
        "pack":      pack,
        "links":     links,
    }


def load_existing_pack(idea_id: str) -> dict | None:
    """Return cached pack if one exists, else None."""
    json_out = OUT_DIR / f"{idea_id}.json"
    if not json_out.exists():
        return None
    try:
        return json.loads(json_out.read_text(encoding="utf-8"))
    except Exception:
        return None

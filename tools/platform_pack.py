"""
WorkHive Platform Pack Generator v3 - Multi-call architecture.

Each of 10 platform sections (FB Page, FB Group, LinkedIn Company, LinkedIn
Founder, YouTube, Shorts/Reels/TikTok, Reddit set, X thread, Extras, Calendar)
gets its OWN focused AI call with its OWN validator and ONE retry round.

Why multi-call: in v2 we tried to produce all 10 sections in a single prompt.
The Groq llama-3.3-70b model truncates output when the JSON gets large -
several long-form bodies came back at 50% of the asked word count. With
multi-call each AI round-trip only has to produce ONE focused section, so
it never has to choose what to truncate.

Stays on the same free fallback chain (Groq -> Cerebras -> OpenRouter) via
tools.video_idea_generator.ai_call. 8-12 AI calls per pack, ~30-90 sec total.

Same public API as v2: generate_platform_pack() returns a dict including
'warnings', 'pack', 'links', 'json_file', 'md_file'.
"""

import json
import re
import time
from pathlib import Path
from datetime import date

from tools.video_idea_generator import ai_call
from tools.platform_intel import get_feature_info, FEATURE_ECOSYSTEM

# ── Rate-limit pacing (Groq free tier = 30 req/min = 1 every 2 sec) ───────────
# We add a small sleep between per-platform calls to stay comfortably under the
# Groq quota. If a call still 429s (or "All providers failed"), we backoff and
# retry once before giving up on that platform.

INTER_CALL_SLEEP_SEC = 2.5      # paced gap between per-platform attempts
BACKOFF_SLEEP_SEC    = 30       # waited after a suspected rate-limit failure

# ── Paths + campaign constants ────────────────────────────────────────────────

ROOT     = Path(__file__).parent.parent
OUT_DIR  = ROOT / ".tmp/platform_packs"
SITE     = "https://workhiveph.com"
CAMPAIGN = "phase3-launch"

# ── Feature -> WorkHive page mapping ──────────────────────────────────────────

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

# ── Quality rules (shared across platforms) ───────────────────────────────────

BANNED_PHRASES = [
    "are you tired of", "discover how", "unlock real insights",
    "unlock insights", "sign up now", "learn more about",
    "our tool helps you", "introducing", "data-driven decisions",
    "game-changer", "game changer", "revolutionize", "leverage",
    "in today's", "in this video, we'll explore", "in this video we'll explore",
    "make informed decisions", "optimize your plant's performance",
    "have you ever struggled", "has anyone used",
    "don't miss out", "don't just take our word",
    "but how does it work", "why not try",
]

# Tagalog/Taglish markers. ANY of these in a long-form output = language violation.
TAGALOG_MARKERS = [
    r"\bkumusta\b", r"\bmga\b", r"\bka-\w+", r"\bpwede\b", r"\bnaman\b",
    r"\btalaga\b", r"\bsila\b", r"\bnila\b", r"\bsya\b", r"\bnya\b",
    r"\bdin\b", r"\brin\b", r"\bpara\s+sa\b", r"\bpara\s+kay\b",
    r"\btayo\b", r"\bnatin\b", r"\bkayo\b", r"\bninyo\b",
    r"\bito\b", r"\biyan\b", r"\bganito\b", r"\bganyan\b",
    r"\bgrabe\b", r"\bsobra\b", r"\bsaglit\b", r"\bsandali\b",
    r"\bhindi\b", r"\bsige\b", r"\bbaka\b",
]
TAGALOG_RE = re.compile("|".join(TAGALOG_MARKERS), re.IGNORECASE)

PH_ANCHOR_TERMS = [
    "cabuyao", "calabarzon", "peza", "mindanao", "batangas", "bulacan",
    "subic", "davao", "manila", "quezon", "laguna", "cavite", "luzon",
    "visayas", "pampanga", "ilocos", "pangasinan", "filipino", "philippine",
    "philippines", "psme", "iiee", "piche", "dole", "tesda", "php",
    " p-", " ahu-", " conveyor #", " boiler b-", " pump p-", " compressor ",
]

MIN_WORDS = {
    "fb_page":           90,
    "fb_group":          120,
    "linkedin_company":  170,
    "linkedin_founder":  170,
    "youtube_desc":      280,
    "reddit_each":       70,
}

# ── UTM helpers ───────────────────────────────────────────────────────────────

def _utm(path: str, source: str, medium: str = "social",
         campaign: str = CAMPAIGN) -> str:
    sep = "&" if "?" in path else "?"
    return f"{SITE}{path}{sep}utm_source={source}&utm_medium={medium}&utm_campaign={campaign}"


def build_links(feature: str) -> dict:
    tool_path  = FEATURE_TOOL_URL.get(feature, "/")
    learn_slug = FEATURE_LEARN_SLUG.get(feature)
    learn_path = f"/learn/{learn_slug}/" if learn_slug else "/learn/"
    return {
        "tool_path":         tool_path,
        "learn_path":        learn_path,
        "facebook":          _utm(learn_path, "facebook"),
        "fb_group":          _utm(learn_path, "fbgroup"),
        "linkedin":          _utm(learn_path, "linkedin"),
        "linkedin_founder":  _utm(learn_path, "linkedin-founder"),
        "youtube":           _utm(learn_path, "youtube", "video"),
        "tiktok":            _utm(learn_path, "tiktok", "social"),
        "reddit":            _utm(learn_path, "reddit"),
        "x":                 _utm(learn_path, "twitter"),
        "tool_fb":           _utm(tool_path,  "facebook"),
        "tool_li":           _utm(tool_path,  "linkedin"),
    }

# ── Validator primitives ──────────────────────────────────────────────────────

def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def _has_ph_anchor(text: str) -> bool:
    low = (text or "").lower()
    return any(a in low for a in PH_ANCHOR_TERMS)


def _has_banned_phrase(text: str) -> list:
    low = (text or "").lower()
    return [b for b in BANNED_PHRASES if b in low]


def _has_tagalog(text: str) -> list:
    if not text:
        return []
    return list({m.group(0).lower() for m in TAGALOG_RE.finditer(text)})


def _check(label, text, min_words=None, require_ph=False,
           forbid_tagalog=True, forbid_workhive=False,
           must_start_with=None) -> list:
    """Generic per-text validator. Returns list of issue strings."""
    issues = []
    text = (text or "").strip()
    if not text:
        return [f"{label}: empty."]
    wc = _word_count(text)
    if min_words and wc < min_words:
        issues.append(f"{label}: {wc} words, must be {min_words}+.")
    banned = _has_banned_phrase(text)
    if banned:
        issues.append(f"{label}: uses banned phrase(s) {banned}. Rewrite.")
    if require_ph and not _has_ph_anchor(text):
        issues.append(f"{label}: missing Philippine-specificity anchor "
                      f"(name a PH plant location / Filipino role / PHP amount / "
                      f"24h time / specific equipment ID).")
    if forbid_tagalog:
        tag = _has_tagalog(text)
        if tag:
            issues.append(f"{label}: contains Tagalog word(s) {tag}. "
                          f"Rule: PLAIN SIMPLE ENGLISH ONLY.")
    if forbid_workhive and "workhive" in text.lower():
        issues.append(f"{label}: must NOT mention WorkHive. Rule R6: this "
                      f"comment is karma-building. Pretend WorkHive does not exist.")
    if must_start_with:
        head = text[:240].lower()
        anchor = must_start_with[:50].lower().rstrip(".!?")
        if anchor and anchor not in head:
            issues.append(f'{label}: must open with the original hook verbatim. '
                          f'Expected leading text containing: "{anchor}"')
    return issues

# ── Shared prompt context ─────────────────────────────────────────────────────

def _context_block(idea: dict, script_content: str, links: dict) -> str:
    feat_info = get_feature_info(idea.get("solution_feature", ""))
    audience  = ", ".join(feat_info.get("audience", ["Field Technician"]))
    connects  = ", ".join(feat_info.get("connects_to", [])[:3])
    return f"""WORKHIVE: Free industrial intelligence platform for every Filipino industrial worker. Free forever at worker tier. Audience spans field workers, engineers, supervisors, managers, suppliers, contractors, new graduates, upskilling workers.

IDEA:
- Title:        {idea.get('title','')}
- Original hook (verbatim): "{idea.get('hook','').strip()}"
- Problem:      {idea.get('problem','').strip()}
- Feature:      {idea.get('solution_feature','')}
- Audience:     {audience}
- Emotion:      {idea.get('emotion','')}
- Connects to:  {connects}

PRODUCTION SCRIPT (source of truth; do not invent new facts):
{script_content[:2800]}

LINKS (paste verbatim where the platform instructs):
- Facebook Page:       {links['facebook']}
- Facebook Group:      {links['fb_group']}
- LinkedIn Company:    {links['linkedin']}
- LinkedIn Founder:    {links['linkedin_founder']}
- YouTube:             {links['youtube']}
- TikTok:              {links['tiktok']}
- Reddit:              {links['reddit']}
- X/Twitter:           {links['x']}
- Tool (FB tag):       {links['tool_fb']}
- Tool (LI tag):       {links['tool_li']}

HARD RULES (always):
- Plain simple English only. NO Tagalog, NO Taglish, NO code-switching.
  (Banned: kumusta, mga, ka-, naman, talaga, pwede, sige, etc.)
- NO banned phrases: {", ".join(BANNED_PHRASES[:12])}, etc.
- One concrete Philippine anchor required (PH plant location, Filipino role,
  PHP amount, 24h time like 14:30, or specific equipment like Pump P-204B).
"""

# ── Per-platform prompts (each requests ONE focused JSON object) ──────────────

def _prompt_facebook_page(idea, script, links, feedback=""):
    ctx = _context_block(idea, script, links)
    hook = idea.get('hook','').strip()
    return f"""{ctx}

TASK: Write ONE Facebook Page post for WorkHive.

PLATFORM RULES (mandatory):
- "body" MUST open with the original hook verbatim: "{hook}"
- "body" must be {MIN_WORDS['fb_page']}+ words (count carefully)
- "body" tells one specific Philippine plant scene (real place, real time, real cost)
- 3-5 hashtags inline at the END of body (e.g., #PhilippineManufacturing #IndustrialMaintenance)
- NO link in body (Facebook algorithm penalises external links)
- "first_comment" = one plain context line + the Facebook link verbatim

GOOD EXAMPLE (study tone + structure; DO NOT copy facts):
{{
  "body": "[ORIGINAL HOOK VERBATIM HERE]. The Pampanga food line went dark again at 14:45 last Wednesday. Three hours. Nobody could pinpoint why from the paper logbook entries: 4 different operators, 3 different shifts, 12 conflicting notes.\\n\\nThis is where the WorkHive Maintenance Logbook closes the gap. Type or voice your entries in 30 seconds, and the same data feeds shift handover, the AI assistant, and the failure-signature scan automatically.\\n\\nFree for every plant team in the Philippines. No contract, no sales call.\\n\\n#IndustrialMaintenance #PhilippineManufacturing #PlantOperations",
  "first_comment": "Read the full guide: https://workhiveph.com/learn/start-digital-logbook-philippine-factory/?utm_source=facebook&utm_medium=social&utm_campaign=phase3-launch"
}}

{feedback}

Return ONLY this JSON, no markdown fence, no preamble:
{{
  "body": "...",
  "first_comment": "..."
}}"""


def _prompt_facebook_group(idea, script, links, feedback=""):
    ctx = _context_block(idea, script, links)
    return f"""{ctx}

TASK: Write ONE Facebook Group post for Philippine industry groups (PSME PH, IIEE PH, PIChE PH, Maintenance Engineers Philippines).

PLATFORM RULES (mandatory):
- "body" must be {MIN_WORDS['fb_group']}+ words
- Discussion-starter format: tells a real plant-floor situation, ends with an OPEN-ENDED question
- NO link in body (groups ban link-dropping; admin removes posts with links)
- NO hashtags (looks spammy in PH groups)
- Tone: peer-to-peer between Filipino plant engineers. Not promotional.
- WorkHive may be mentioned ONCE near the end as "a free tool we built for this" if it fits naturally.
- "first_comment" = optional 1-line + link (only used if admin approves)

GOOD EXAMPLE (tone reference; do NOT copy):
{{
  "body": "Question for the group, especially supervisors who run mixed-shift plants.\\n\\nWe just wrapped a downtime root-cause review on a Calabarzon bottling line. 38 hours unplanned in October. Four paper logbooks, two Excel sheets, three different shift teams writing the same failure mode with three different names ('jammed conveyor' vs 'belt slip' vs 'mechanical fault on C2').\\n\\nIt took us a full Sunday to reconcile, and we still missed 6 of the entries entirely until a tech walked us through what he meant.\\n\\nHonest question: how do your teams keep the SAME failure-mode language across shifts and across operators? Toolbox briefings? A printed cheat sheet? A digital tool that forces a dropdown?\\n\\nI ask because we built a free Filipino-made tool for this (WorkHive) but I want to know what works for you before I assume our approach is the right one.",
  "first_comment": "If you want to see the tool: https://workhiveph.com/learn/start-digital-logbook-philippine-factory/?utm_source=fbgroup&utm_medium=social&utm_campaign=phase3-launch",
  "target_groups": ["PSME PH", "IIEE PH", "PIChE PH", "Maintenance Engineers Philippines"]
}}

{feedback}

Return ONLY this JSON, no markdown fence, no preamble:
{{
  "body": "...",
  "first_comment": "...",
  "target_groups": ["PSME PH", "IIEE PH", "PIChE PH", "Maintenance Engineers Philippines"]
}}"""


def _prompt_linkedin_company(idea, script, links, feedback=""):
    ctx = _context_block(idea, script, links)
    return f"""{ctx}

TASK: Write ONE LinkedIn Company Page post for WorkHive.

PLATFORM RULES (mandatory):
- "body" must be {MIN_WORDS['linkedin_company']}+ words. AIM FOR 220-260.
  If your draft hits 180 words you are NOT done — add one more concrete
  example or one more sentence of insight before the CTA.
- Structure: 1-line hook / 2-3 sentence context / 4-5 sentence insight
  (use SPECIFIC numbers, equipment names, or PH plant scenarios) /
  1-sentence CTA + link / 3-5 hashtags
- Link inline is OK on LinkedIn
- B2B tone, professional but not corporate
- Must include at least TWO specific PH anchors (e.g., one PH plant
  location + one PHP cost figure, or one Filipino role title + one
  specific equipment ID)

GOOD EXAMPLE (study structure; do NOT copy):
{{
  "body": "Most Philippine plant teams already have the data they need for OEE. They just do not have a tool that respects how busy a shift actually is.\\n\\nWhen we sat with a Calabarzon food plant team last month, the supervisor pulled out 6 paper logbooks and 4 Excel sheets to assemble a root-cause review for one bottling line. The information was there. The reconciliation took him 14 hours across one weekend.\\n\\nWorkHive's Maintenance Logbook is built for exactly this gap. Operators and technicians log entries in 30 seconds (typed or voice). The AI assistant + shift handover + failure-signature scan pull from the same single source. The 14-hour reconciliation drops to 30 minutes because the data is already structured.\\n\\nFree for every Philippine plant. https://workhiveph.com/learn/start-digital-logbook-philippine-factory/?utm_source=linkedin&utm_medium=social&utm_campaign=phase3-launch\\n\\n#PhilippineManufacturing #IndustrialReliability #PlantOperations #Maintenance"
}}

{feedback}

Return ONLY this JSON, no markdown fence, no preamble:
{{
  "body": "..."
}}"""


def _prompt_linkedin_founder(idea, script, links, feedback=""):
    ctx = _context_block(idea, script, links)
    return f"""{ctx}

TASK: Write ONE first-person LinkedIn post in the voice of Ian Beronio (WorkHive founder).

PLATFORM RULES (mandatory):
- "body" must be {MIN_WORDS['linkedin_founder']}+ words
- First-person ("I", "we"). Real story moment from building WorkHive or from a real Philippine plant.
- Must include specific PH anchor (real plant location + specific number + specific equipment).
- End with a real, open-ended question to spark comments.
- Link at the very bottom.
- 3 hashtags max.
- "edit_notes" = 1-sentence instruction telling Ian what to personalise before posting.

GOOD EXAMPLE (study tone + story structure; do NOT copy):
{{
  "body": "Three weeks ago a plant supervisor in Calabarzon messaged me. His bottling line had 38 hours of unplanned downtime in October and his boss wanted a root-cause review by Monday. He had 4 paper logbooks, 2 Excel sheets, and a one-day window.\\n\\nHe used WorkHive's Maintenance Logbook + Analytics over one Saturday. Sunday morning he had the answer: 71 percent of his downtime traced to 3 sensor faults on Conveyor C-2 and Pump P-301. He brought a 1-page report to his Monday meeting and ordered the replacement parts the same day.\\n\\nTotal cost to him: PHP 0. Total cost to his plant from those 38 hours of downtime before this: PHP 1.2M (his estimate, not ours).\\n\\nThis is why we built WorkHive free at the worker tier forever. Most Filipino plants do not have the budget for SAP or Maximo. They DO have the data; they need a tool that respects how busy a plant team actually is.\\n\\nWhat pattern have you seen in your plant that the official KPI reports miss?\\n\\nhttps://workhiveph.com/learn/start-digital-logbook-philippine-factory/?utm_source=linkedin-founder&utm_medium=social&utm_campaign=phase3-launch\\n\\n#PhilippineManufacturing #IndustrialIntelligence #Reliability",
  "edit_notes": "Replace the Calabarzon example with a real conversation Ian has actually had, or keep this one and clearly mark it as a composite story."
}}

{feedback}

Return ONLY this JSON, no markdown fence, no preamble:
{{
  "body": "...",
  "edit_notes": "..."
}}"""


def _prompt_youtube(idea, script, links, feedback=""):
    ctx = _context_block(idea, script, links)
    return f"""{ctx}

TASK: Write the YouTube package for ONE long-form video (4-7 min) based on this idea.

PLATFORM RULES (mandatory):
- "title": <=60 chars, includes the feature keyword AND a benefit word
- "thumbnail_text": <=5 words, big-text overlay (e.g., "3 Patterns. 80% Downtime.")
- "tags": exactly 12 strings, mix of single words and 2-3 word phrases
- "description": {MIN_WORDS['youtube_desc']}+ words. AIM FOR 340-400.
  If your draft hits 250 words you are NOT done — flesh out the "About
  WorkHive" paragraph and the "What you will learn" bullets with one more
  sentence each. STRUCTURE must include ALL of:
    (a) 4-sentence hook (with PH anchor + specific number)
    (b) "What you will learn:" - 3 bullet points, EACH 1-2 sentences (not
        single phrases)
    (c) "Chapters:" - 5-7 timestamped entries like "0:00 The October 38-hour
        story", "1:30 Pattern 1: ..." (full descriptive titles, not just "Intro")
    (d) "About WorkHive" paragraph (4-5 sentences, includes the founder +
        DTI 8080496 line + Philippine free-tier mission)
    (e) "Tool used in this video:" - paste the Tool (FB tag) link
    (f) "Article version:" - paste the YouTube link
    (g) "Follow:" - "https://workhiveph.com" + "Page on Facebook" + "Page on LinkedIn"
    (h) 5 hashtags at the bottom

GOOD EXAMPLE (structure reference; do NOT copy):
{{
  "title": "How to Cut Downtime 25% with a PM Checklist",
  "thumbnail_text": "PM Checklist. 25% Win.",
  "tags": ["preventive maintenance", "PM checklist", "philippine manufacturing", "industrial maintenance", "OEE", "downtime reduction", "plant operations", "MTBF", "reliability engineering", "PSME", "iiee", "maintenance supervisor"],
  "description": "A plant supervisor in Calabarzon shaved 25 percent off his bottling-line downtime in 90 days with one tool: a digital PM checklist. He did not buy SAP. He did not hire a consultant. He used a free WorkHive tool and one disciplined weekly review.\\n\\nWhat you will learn:\\n- The 5 mistakes that kill most PM programs in the first 90 days\\n- How to build a 1-page PM checklist your shift teams will actually complete\\n- The weekly 30-minute review ritual that pushes PM compliance from 50 to 90 percent\\n\\nChapters:\\n0:00 The 38-hour October downtime story\\n1:30 Why most PM programs fail in the first 90 days\\n3:00 The 5 mandatory fields on a PM checklist\\n4:30 The weekly 30-minute review ritual\\n6:00 Free template + how to roll it out\\n\\nAbout WorkHive:\\nWe are a free industrial intelligence platform built specifically for the Philippine industrial workforce. Operated by WorkHive Engineering Services (DTI Business Name 8080496), founded by Ian Lumayno Beronio. Free at the worker tier forever.\\n\\nTool used in this video: https://workhiveph.com/pm-scheduler.html?utm_source=facebook&utm_medium=social&utm_campaign=phase3-launch\\n\\nArticle version: https://workhiveph.com/learn/free-pm-checklist-templates/?utm_source=youtube&utm_medium=video&utm_campaign=phase3-launch\\n\\nFollow:\\nWebsite: https://workhiveph.com\\nFacebook Page: WorkHive PH\\nLinkedIn Page: WorkHive PH\\n\\n#PhilippineManufacturing #IndustrialMaintenance #PMChecklist #PlantOperations #Reliability"
}}

{feedback}

Return ONLY this JSON, no markdown fence, no preamble:
{{
  "title": "...",
  "thumbnail_text": "...",
  "tags": ["...", "...", "...", "...", "...", "...", "...", "...", "...", "...", "...", "..."],
  "description": "..."
}}"""


def _prompt_shorts(idea, script, links, feedback=""):
    ctx = _context_block(idea, script, links)
    return f"""{ctx}

TASK: Write ONE short-form video package (YouTube Shorts / Instagram Reels / TikTok).

PLATFORM RULES (mandatory):
- "caption": <150 chars. Hook + payoff. Specific NOT generic.
- "hashtags": exactly 4 hashtags. 3 PH-trending + 1 niche. Mix #PhilippineTikTok or #fyp with industrial.
- "hook_visual": 1 sentence describing the FIRST 2 SECONDS of the video.
   MUST be FRESH - describe something not yet shown in examples.
   MUST be specific: equipment name, time of day, lighting, where the camera is.
   Generic answers ("plant manager looking at tablet") = REJECTED.

GOOD EXAMPLE FOR HASHTAGS ONLY (do NOT reuse the caption or hook):
{{
  "hashtags": ["#PhilippineManufacturing", "#IndustrialTikTok", "#PlantLife", "#PMChecklist"]
}}

{feedback}

Return ONLY this JSON, no markdown fence, no preamble:
{{
  "caption": "...",
  "hashtags": ["#...", "#...", "#...", "#..."],
  "hook_visual": "..."
}}"""


def _prompt_reddit(idea, script, links, feedback=""):
    ctx = _context_block(idea, script, links)
    return f"""{ctx}

TASK: Write THREE substantive Reddit comments — one for each subreddit. Reddit instantly downvotes marketing copy. Each comment must read like a real Philippine plant engineer who has seen this problem in production.

PLATFORM RULES (mandatory):
- Each comment {MIN_WORDS['reddit_each']}+ words.
- NO marketing phrases.
- NO Tagalog/Taglish (plain English only - "kumusta", "mga", "ka-", etc. are FORBIDDEN).

PER-SUBREDDIT RULES:

r/maintenance:
  - Helpful answer to a hypothetical practical question about maintenance.
  - MAY mention WorkHive ONCE near the end as "we use a free tool called WorkHive for this if you want to look" - but only if naturally relevant.
  - Include PH anchor.

r/PLC:
  - IMPORTANT: Pretend WorkHive does NOT exist for this comment.
  - Write a pure, helpful comment about PLC programming, ladder logic, sensor faults, or PM strategy.
  - NO mention of WorkHive. NO mention of any tool. Just engineering wisdom from experience.
  - PH anchor optional (PLC is universal); MUST sound like an experienced engineer.

r/Philippines:
  - Filipino-context comment about industrial work, career growth, or the AI/upskilling angle.
  - Plain English only (the audience knows English; Tagalog markers tip off the spam filter).
  - MAY mention WorkHive ONCE as "a free Filipino-built tool" with link.
  - Tone: helpful peer, not promotional.

GOOD EXAMPLE — r/maintenance (study tone, do NOT copy):
"For OEE tracking in a small plant, the unsexy answer is: get the logbook discipline right first. Most teams I have seen jump straight to a dashboard and end up with garbage in, garbage out. We tracked OEE on a Calabarzon bottling line for 18 months. Until everyone (operators, techs, supervisors) was writing the SAME failure mode names, the dashboard told us nothing useful. Practical steps: agree on 12-15 failure mode names for your line, make a 1-page cheat sheet, do a 10-minute toolbox briefing every Monday, and review the dashboard as a TEAM (not just the manager) once a week. If you want a free tool that handles this discipline for you, WorkHive is Philippine-built and works offline — but honestly, any tool works once the input discipline is there."

GOOD EXAMPLE — r/PLC (study tone, do NOT copy):
"For preventive maintenance triggers in a PLC, the cleanest pattern I have used is a separate retentive timer per asset, reset by a maintenance-complete bit from the SCADA HMI. Avoid embedding PM logic in the production sequence rung - it makes debugging painful when production timing changes. If your platform supports it, dump the PM-complete events to a CSV or to an MQTT topic so your reliability team can run their own analysis without touching the PLC code. Most plant-side resistance to PM I have seen comes from PMs interrupting production unpredictably; if you can publish a 'next-PM-due' tag the operator sees, they tend to accept the planned interrupt much better. What PLC family are you running and how strict is your change-management process? That changes the recommendation."

{feedback}

Return ONLY this JSON, no markdown fence, no preamble:
{{
  "r_maintenance": "...",
  "r_PLC":         "...",
  "r_Philippines": "..."
}}"""


def _prompt_x_thread(idea, script, links, feedback=""):
    ctx = _context_block(idea, script, links)
    return f"""{ctx}

TASK: Write ONE 8-tweet X / Twitter thread.

PLATFORM RULES (mandatory):
- Exactly 8 tweets in array order.
- Each tweet 180-275 characters (NOT shorter; aim for ~220).
- Tweet 1: hook + tease the payoff + "1/8" prefix.
- Tweets 2-7: ONE concrete insight per tweet. Numbered "X/8".
- Tweet 8: payoff + link verbatim. Prefix "8/8".
- NO marketing pitches. NO "But how does it work?" NO "Don't miss out!" NO "Why not try?"
- Each tweet has a specific number, name, time, or example.

GOOD EXAMPLE (study tone — concrete + numbered. Do NOT copy):
[
  "1/8 A Calabarzon plant supervisor cut his line downtime 25% in 90 days with one cheap change: a free PM checklist tool + a 30-min Monday review ritual. No SAP. No consultant. Here is exactly what he did.",
  "2/8 First he stopped tracking 47 different failure modes. He cut the list to 12 names everyone on every shift could spell the same way. 'Jammed conveyor' beat 'belt slip' + 'mechanical fault C2' as separate entries.",
  "3/8 Second he made a 1-page printed cheat sheet pinned at every workstation. Operators stopped guessing at categories. Logbook agreement jumped from 41% to 88% in week 4 (he tracked it).",
  "4/8 Third he introduced a Monday morning toolbox briefing. 10 minutes. The shift supervisor read out the top 3 failure modes from the previous week. No PowerPoint. No agenda. Just numbers.",
  "5/8 Fourth: weekly 30-min review. Team (not just manager). Look at the dashboard together. Pick ONE pattern to attack the next week. Track the result by next Monday.",
  "6/8 Fifth: PMs stopped being a checklist that gets faked. The team saw the connection between PM compliance and the failures THEY had to fix. PM compliance went from 50% to 88% in 90 days.",
  "7/8 Result: 38 hours of October unplanned downtime became 28 hours in November and 19 hours in December. He estimated PHP 1.2M avoided cost over the quarter. Total tool cost: zero.",
  "8/8 Free template + full playbook: https://workhiveph.com/learn/free-pm-checklist-templates/?utm_source=twitter&utm_medium=social&utm_campaign=phase3-launch"
]

{feedback}

Return ONLY this JSON array (8 strings), no markdown fence, no preamble:
[
  "1/8 ...",
  "2/8 ...",
  "3/8 ...",
  "4/8 ...",
  "5/8 ...",
  "6/8 ...",
  "7/8 ...",
  "8/8 ... {links['x']}"
]"""


def _prompt_extras(idea, script, links, feedback=""):
    ctx = _context_block(idea, script, links)
    return f"""{ctx}

TASK: Write 2 short pieces of copy.

1. "ad_15s_caption": ONE line for a paid Facebook/Instagram 15-second ad.
   - Specific. Earned. NO "Sign up now!" NO "Don't miss out!"
   - Format: result + tool + free. Example tone:
     "Cut downtime 25 percent in 90 days. Free PM checklist tool, Philippine-built."

2. "whatsapp_share": ONE sentence + the WhatsApp UTM link, the way a real
   Filipino supervisor would share with a ka-shift in Viber/WhatsApp chat.
   - Plain English only. Casual but professional.
   - Example tone:
     "Stumbled on a free PM checklist tool that actually fits how we run shifts here, sharing in case useful — [link]"

WhatsApp link to use: {_utm(links['learn_path'], 'whatsapp', 'social')}

{feedback}

Return ONLY this JSON, no markdown fence, no preamble:
{{
  "ad_15s_caption": "...",
  "whatsapp_share": "..."
}}"""


def _prompt_calendar(idea, script, links, feedback=""):
    ctx = _context_block(idea, script, links)
    return f"""{ctx}

TASK: Write a 30-day distribution calendar for THIS video idea.

PLATFORM RULES (mandatory):
- 5 entries: day_1, day_3, day_7, day_14, day_30
- Each "activity" must be a CONCRETE action, not generic.
- BAD: "Post about WorkHive's PM Checklist"
- GOOD: "Post the FB Page version with a screenshot of your team's actual OEE chart from week 1 of the rollout"

Suggested platform mix:
- day_1:  facebook_page
- day_3:  linkedin_company
- day_7:  linkedin_founder
- day_14: facebook_group (cross-post to PSME PH)
- day_30: reddit (r/maintenance or r/Philippines)

{feedback}

Return ONLY this JSON, no markdown fence, no preamble:
{{
  "day_1":  {{ "platform": "facebook_page",    "activity": "..." }},
  "day_3":  {{ "platform": "linkedin_company", "activity": "..." }},
  "day_7":  {{ "platform": "linkedin_founder", "activity": "..." }},
  "day_14": {{ "platform": "facebook_group",   "activity": "..." }},
  "day_30": {{ "platform": "reddit",           "activity": "..." }}
}}"""

# ── Generic AI round-trip with JSON parsing + repair ──────────────────────────

def _is_rate_limit_error(exc: Exception) -> bool:
    """Heuristic: detect rate-limit / quota failures from the ai_call chain."""
    msg = str(exc).lower()
    return (
        "all providers failed" in msg
        or "rate" in msg
        or "429" in msg
        or "quota" in msg
        or "too many requests" in msg
    )


def _ai_json(prompt: str, expected_root: str = "object",
             allow_backoff: bool = True):
    """Call AI, strip fences, parse JSON. Returns parsed object or raises.
    On suspected rate-limit failures, sleeps BACKOFF_SLEEP_SEC and retries once."""
    def _call_and_parse():
        raw = ai_call(prompt, high_quality=True)
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        raw = re.sub(r"\s*```$", "", raw.strip())
        pattern = r"\[.*\]" if expected_root == "array" else r"\{.*\}"
        m = re.search(pattern, raw, re.DOTALL)
        if not m:
            raise RuntimeError(f"AI did not return JSON {expected_root}. Raw start: {raw[:240]}")
        try:
            return json.loads(m.group())
        except json.JSONDecodeError as exc:
            repair = ai_call(
                "Fix this malformed JSON. Return ONLY valid JSON, no fence, "
                "no preamble:\n\n" + m.group(),
                high_quality=False,
            )
            repair = re.sub(r"^```(?:json)?\s*", "", repair.strip())
            repair = re.sub(r"\s*```$", "", repair.strip())
            m2 = re.search(pattern, repair, re.DOTALL)
            if not m2:
                raise RuntimeError(f"JSON unrepairable: {exc}")
            return json.loads(m2.group())

    try:
        return _call_and_parse()
    except Exception as exc:
        if allow_backoff and _is_rate_limit_error(exc):
            print(f"  [ai_json] rate-limit hit ({exc}); sleeping {BACKOFF_SLEEP_SEC}s then retrying once...")
            time.sleep(BACKOFF_SLEEP_SEC)
            return _call_and_parse()
        raise

# ── Per-platform generators (each: prompt -> AI -> validate -> retry once) ────

def _retry_block(issues: list) -> str:
    return ("\n\n=== PREVIOUS ATTEMPT FAILED VALIDATION ===\n"
            + "\n".join(f"  - {i}" for i in issues)
            + "\n\nFix every issue above. Do not return short copy. "
              "Do not use banned phrases. Plain simple English only.\n")


def _generate_one(label: str, prompt_fn, validate_fn, idea, script, links,
                  expected_root: str = "object") -> tuple:
    """Run a per-platform generator with one retry round.
    Returns (result, warnings). Result is the parsed JSON object (dict or list).
    Warnings is a list of remaining validation issues."""
    print(f"  [pack:{label}] attempt 1...")
    prompt = prompt_fn(idea, script, links)
    try:
        result = _ai_json(prompt, expected_root=expected_root)
    except Exception as exc:
        print(f"  [pack:{label}] attempt 1 FAILED to parse: {exc}")
        return ({}, [f"{label}: AI did not return parseable JSON ({exc})."])

    issues = validate_fn(result, idea)
    if not issues:
        return (result, [])

    print(f"  [pack:{label}] {len(issues)} validation issues; retrying with feedback...")
    feedback = _retry_block(issues)
    try:
        prompt_v2 = prompt_fn(idea, script, links, feedback=feedback)
        result_v2 = _ai_json(prompt_v2, expected_root=expected_root)
        issues_v2 = validate_fn(result_v2, idea)
        # Keep whichever is better. Ties go to v2.
        if len(issues_v2) <= len(issues):
            return (result_v2, issues_v2)
        return (result, issues)
    except Exception as exc:
        print(f"  [pack:{label}] retry crashed: {exc}; keeping v1.")
        return (result, issues)

# ── Per-platform validators ───────────────────────────────────────────────────

def _val_fb_page(r, idea):
    issues = []
    issues += _check("FB Page body", r.get("body"),
                     min_words=MIN_WORDS["fb_page"], require_ph=True,
                     must_start_with=idea.get("hook", ""))
    issues += _check("FB Page first_comment", r.get("first_comment"),
                     min_words=8)
    return issues


def _val_fb_group(r, idea):
    issues = []
    issues += _check("FB Group body", r.get("body"),
                     min_words=MIN_WORDS["fb_group"], require_ph=True)
    return issues


def _val_linkedin_company(r, idea):
    return _check("LinkedIn Company", r.get("body"),
                  min_words=MIN_WORDS["linkedin_company"], require_ph=True)


def _val_linkedin_founder(r, idea):
    issues = []
    issues += _check("LinkedIn Founder", r.get("body"),
                     min_words=MIN_WORDS["linkedin_founder"], require_ph=True)
    if not (r.get("edit_notes") or "").strip():
        issues.append("LinkedIn Founder: edit_notes is empty.")
    return issues


def _val_youtube(r, idea):
    issues = []
    issues += _check("YouTube title", r.get("title"))
    if r.get("title") and len(r["title"]) > 60:
        issues.append(f"YouTube title: {len(r['title'])} chars, must be <=60.")
    issues += _check("YouTube description", r.get("description"),
                     min_words=MIN_WORDS["youtube_desc"], require_ph=True)
    tags = r.get("tags", [])
    if not isinstance(tags, list) or len(tags) < 10:
        issues.append(f"YouTube tags: {len(tags) if isinstance(tags, list) else 0}, "
                      f"must be 10-12.")
    return issues


def _val_shorts(r, idea):
    issues = []
    cap = (r.get("caption") or "").strip()
    if not cap:
        issues.append("Shorts caption: empty.")
    elif len(cap) > 150:
        issues.append(f"Shorts caption: {len(cap)} chars, must be <=150.")
    elif _has_banned_phrase(cap):
        issues.append(f"Shorts caption: uses banned phrase(s).")
    hv = (r.get("hook_visual") or "").strip()
    if not hv:
        issues.append("Shorts hook_visual: empty.")
    elif "plant manager" in hv.lower() and "tablet" in hv.lower():
        issues.append("Shorts hook_visual: generic 'plant manager + tablet' — be specific.")
    if "worn bearing" in hv.lower() and "14:30" in hv:
        issues.append("Shorts hook_visual: lifted from example. Invent a fresh one.")
    tags = r.get("hashtags", [])
    if not isinstance(tags, list) or len(tags) < 3 or len(tags) > 5:
        issues.append(f"Shorts hashtags: must be 3-5 items.")
    return issues


def _val_reddit(r, idea):
    issues = []
    issues += _check("Reddit r_maintenance", r.get("r_maintenance"),
                     min_words=MIN_WORDS["reddit_each"], require_ph=True)
    issues += _check("Reddit r_PLC", r.get("r_PLC"),
                     min_words=MIN_WORDS["reddit_each"], forbid_workhive=True)
    issues += _check("Reddit r_Philippines", r.get("r_Philippines"),
                     min_words=MIN_WORDS["reddit_each"])
    return issues


def _val_x_thread(r, idea):
    issues = []
    if not isinstance(r, list):
        return [f"X thread: expected JSON array, got {type(r).__name__}."]
    if len(r) != 8:
        issues.append(f"X thread: {len(r)} tweets, must be exactly 8.")
    for i, t in enumerate(r):
        text = (t or "").strip()
        if len(text) < 100:
            issues.append(f"X thread tweet {i+1}: {len(text)} chars, "
                          f"must be 180+ (aim ~220).")
        elif len(text) > 280:
            issues.append(f"X thread tweet {i+1}: {len(text)} chars, "
                          f"must be <=280.")
        banned = _has_banned_phrase(text)
        if banned:
            issues.append(f"X thread tweet {i+1}: banned phrase {banned}.")
        if _has_tagalog(text):
            issues.append(f"X thread tweet {i+1}: contains Tagalog. "
                          f"Plain English only.")
    return issues


def _val_extras(r, idea):
    issues = []
    issues += _check("15-sec ad caption", r.get("ad_15s_caption"))
    issues += _check("WhatsApp share", r.get("whatsapp_share"))
    return issues


def _val_calendar(r, idea):
    issues = []
    for day in ["day_1", "day_3", "day_7", "day_14", "day_30"]:
        e = r.get(day, {})
        if not (e.get("activity") or "").strip():
            issues.append(f"Calendar {day}: activity empty.")
        elif len((e.get("activity") or "")) < 25:
            issues.append(f"Calendar {day}: activity too short, "
                          f"be concrete (>=25 chars).")
    return issues

# ── Post-process safety net ───────────────────────────────────────────────────

def _force_hook_opening(pack: dict, idea: dict):
    """If FB Page body doesn't lead with the hook, prepend it. Cheap insurance."""
    hook = (idea.get("hook") or "").strip()
    if not hook:
        return
    fb   = pack.get("facebook_page", {})
    body = (fb.get("body") or "").strip()
    head = body[:240].lower()
    anchor = hook[:50].lower().rstrip(".!?")
    if anchor and anchor not in head:
        fb["body"] = hook.rstrip(".") + ".\n\n" + body
        pack["facebook_page"] = fb

# ── Markdown renderer (unchanged from v2) ─────────────────────────────────────

def render_markdown(idea: dict, pack: dict, links: dict) -> str:
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

# ── Main orchestrator ─────────────────────────────────────────────────────────

def generate_platform_pack(idea: dict, script_content: str) -> dict:
    """Multi-call architecture: each platform section gets its own AI round-trip
    with focused prompt + per-section validator + one retry round."""
    feature = idea.get("solution_feature", "")
    if feature not in FEATURE_ECOSYSTEM:
        raise RuntimeError(
            f"Unknown feature '{feature}' on idea {idea.get('id')}. "
            f"Add it to FEATURE_ECOSYSTEM in platform_intel.py first."
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    links = build_links(feature)
    pack  = {}
    all_warnings = []

    # Each: (label, prompt_fn, validator_fn, target_key, expected_root)
    PLAN = [
        ("facebook_page",       _prompt_facebook_page,    _val_fb_page,         "facebook_page",       "object"),
        ("facebook_group",      _prompt_facebook_group,   _val_fb_group,        "facebook_group",      "object"),
        ("linkedin_company",    _prompt_linkedin_company, _val_linkedin_company,"linkedin_company",    "object"),
        ("linkedin_founder",    _prompt_linkedin_founder, _val_linkedin_founder,"linkedin_founder",    "object"),
        ("youtube",             _prompt_youtube,          _val_youtube,         "youtube",             "object"),
        ("shorts_reels_tiktok", _prompt_shorts,           _val_shorts,          "shorts_reels_tiktok", "object"),
        ("reddit",              _prompt_reddit,           _val_reddit,          "reddit",              "object"),
        ("x_thread",            _prompt_x_thread,         _val_x_thread,        "x_thread",            "array"),
        ("extras",              _prompt_extras,           _val_extras,          "_extras_temp",        "object"),
        ("calendar",            _prompt_calendar,         _val_calendar,        "content_calendar",    "object"),
    ]

    print(f"  [platform_pack v3] starting multi-call generation for {idea.get('id')} "
          f"(feature: {feature})")

    for i, (label, prompt_fn, val_fn, target_key, expected) in enumerate(PLAN):
        if i > 0:
            # Pace calls to stay under Groq free-tier (30/min).
            time.sleep(INTER_CALL_SLEEP_SEC)
        result, warnings = _generate_one(
            label, prompt_fn, val_fn, idea, script_content, links,
            expected_root=expected,
        )
        pack[target_key] = result
        all_warnings.extend(warnings)

    # FB Group target_groups: always-correct list (don't depend on AI returning it).
    if isinstance(pack.get("facebook_group"), dict):
        pack["facebook_group"]["target_groups"] = [
            "PSME PH", "IIEE PH", "PIChE PH", "Maintenance Engineers Philippines"
        ]

    # Flatten extras into top-level keys (UI expects them there)
    extras = pack.pop("_extras_temp", {}) or {}
    pack["ad_15s_caption"] = extras.get("ad_15s_caption", "")
    pack["whatsapp_share"] = extras.get("whatsapp_share", "")

    # Post-process safety net
    _force_hook_opening(pack, idea)

    # Save outputs
    idea_id  = idea.get("id", f"idea_{date.today().isoformat()}")
    json_out = OUT_DIR / f"{idea_id}.json"
    md_out   = OUT_DIR / f"{idea_id}.md"

    json_out.write_text(
        json.dumps({
            "idea":           idea,
            "pack":           pack,
            "links":          links,
            "warnings":       all_warnings,
            "prompt_version": "v3-multicall",
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md_out.write_text(render_markdown(idea, pack, links), encoding="utf-8")

    print(f"  [platform_pack v3] DONE for {idea.get('id')} "
          f"({len(all_warnings)} remaining warnings)")
    return {
        "json_file": json_out,
        "md_file":   md_out,
        "pack":      pack,
        "links":     links,
        "warnings":  all_warnings,
    }


def load_existing_pack(idea_id: str):
    """Return cached pack if one exists, else None."""
    json_out = OUT_DIR / f"{idea_id}.json"
    if not json_out.exists():
        return None
    try:
        return json.loads(json_out.read_text(encoding="utf-8"))
    except Exception:
        return None

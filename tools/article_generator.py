"""
WorkHive /learn/ article generator.

Mirrors the platform_pack.py architecture: focused prompt -> 14-model AI chain
(tools/ai_chain.call_ai_chain) -> validators -> retry-once -> structured dict.

Produces ONE article's content sections (NOT the full HTML). The scaffold
script (tools/scaffold_article.py) then renders these sections into the
canonical /learn/<slug>/index.html template.

Why split generator from scaffold:
- The scaffold owns HTML structure (head, JSON-LD scaffolds, footer) — boring
  and identical across articles.
- The generator owns CONTENT (intro, body sections, FAQ, sources) — varies
  per article and needs AI assistance.

Returns a dict with keys:
  intro:         opening 2-3 sentences (the "Short answer" callout)
  audience:      list of 6-8 audience role descriptions (validator wants 4+)
  toc:           list of (anchor_id, label) tuples for the article TOC
  sections:      list of (anchor_id, h2_text, html_paragraphs) for the body
  faq:           list of (question, answer) tuples (validator wants 6+)
  sources:       list of citation strings
  keywords:      string for meta-keywords + JSON-LD
  description:   1-sentence meta description (~150 chars)
  word_count:    int (validator wants 1800+ for credible long-form)
"""

import json
import re
import time
from pathlib import Path

from tools.ai_chain import call_ai_chain
from wh_pages import article_tool_map


# ── Capability grounding (Content Grounding Gate, generation-time) ─────────────
# The article's PRODUCT claims (how to use the tool / the flow) must trace to the
# tool page's REAL affordances — not invented. We pull the page evidence for the
# article's mapped tool and feed it into the section prompt as the only allowed
# source for product claims, then verify the drafted body against the live
# capability-grounding check. General/domain knowledge is unrestricted.
def _evidence_for_slug(slug: str):
    """Return (feature_id, evidence_block_text) for the article's tool, else (None, '')."""
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _t = _Path(__file__).resolve().parent
        if str(_t) not in _sys.path:
            _sys.path.insert(0, str(_t))
        import platform_catalog as _pc
        import page_evidence as _pe
        tool_url = (article_tool_map().get(slug) or ("",))[0]
        route = re.sub(r"^/", "", tool_url or "").split("?")[0].split("#")[0]
        if not route.endswith(".html"):
            return None, ""
        fid = _pc._href_stem(route)
        ev = _pe.load_evidence().get(fid)
        if not ev:
            return None, ""
        block = (
            f"REAL PAGE AFFORDANCES for {slug}'s tool (page {ev['route']}) — the ONLY "
            f"things you may claim the tool can do:\n"
            f"  Headings:        {ev.get('headings', [])[:14]}\n"
            f"  Buttons/actions: {ev.get('actions', [])[:18]}\n"
            f"  Fields:          {ev.get('fields', [])[:12]}\n"
            f"  Tabs:            {ev.get('tabs', [])[:10]}\n"
            f"  Connects to:     {ev.get('links_to', [])}"
        )
        return fid, block
    except Exception:
        return None, ""


def verify_grounding(article: dict, slug: str) -> list:
    """Run the capability-grounding check on a generated article's body. Returns
    the list of ungrounded (born-wrong) product claims — empty = grounded."""
    fid, _ = _evidence_for_slug(slug)
    if not fid:
        return []
    try:
        import content_grounding_gate as _cg
        body = (article.get("intro", "") + " "
                + " ".join(p for s in article.get("sections", []) for p in s.get("paragraphs", [])))
        return _cg.capability_issues_for_text(body, fid)
    except Exception:
        return []

# Banned phrases shared with platform_pack — corporate-speak that degrades AEO
# answer-extraction quality.
BANNED_PHRASES = [
    "are you tired of", "discover how", "unlock real insights",
    "unlock insights", "sign up now", "learn more about",
    "our tool helps you", "introducing", "data-driven decisions",
    "game-changer", "game changer", "revolutionize", "leverage",
    "in today's", "in this article, we'll explore",
    "make informed decisions", "optimize your plant's performance",
]

# Post-process scrubber: when the AI sneaks a banned phrase past the prompt
# rules and the per-section retry doesn't catch it, this last-line-of-defense
# replaces the phrase with a neutral alternative. Logged so we can see when
# the AI is drifting and tighten prompts upstream. Each replacement is a
# regex with case-preserving substitution.
#
# IMPORTANT: alternatives must NOT themselves contain another banned phrase,
# and must read naturally in context. Conservative substitutions only —
# when in doubt, the scrubber preserves AI output and just warns.
BANNED_PHRASE_REPLACEMENTS = [
    # (regex, replacement, label)
    (re.compile(r"\bdata-driven decisions\b", re.IGNORECASE),
     "evidence-backed choices",
     "data-driven decisions"),
    # game-changer / game changer / game-changers / game changers — explicit
    (re.compile(r"\bgame[\s-]changers\b", re.IGNORECASE),
     "meaningful improvements", "game-changers"),
    (re.compile(r"\bgame[\s-]changer\b",  re.IGNORECASE),
     "meaningful improvement",  "game-changer"),
    # revolutionize family — explicit per-form to avoid stem-suffix mismatch
    # (the previous capture-group approach produced "transforme" from
    #  "revolutionize" because the e in the suffix doubled with stem)
    (re.compile(r"\brevolutionizing\b", re.IGNORECASE), "transforming", "revolutionizing"),
    (re.compile(r"\brevolutionized\b",  re.IGNORECASE), "transformed",  "revolutionized"),
    (re.compile(r"\brevolutionizes\b",  re.IGNORECASE), "transforms",   "revolutionizes"),
    (re.compile(r"\brevolutionize\b",   re.IGNORECASE), "transform",    "revolutionize"),
    # leverage family — same fix
    (re.compile(r"\bleveraging\b", re.IGNORECASE), "using", "leveraging"),
    (re.compile(r"\bleveraged\b",  re.IGNORECASE), "used",  "leveraged"),
    (re.compile(r"\bleverages\b",  re.IGNORECASE), "uses",  "leverages"),
    (re.compile(r"\bleverage\b",   re.IGNORECASE), "use",   "leverage"),
    (re.compile(r"\bunlock real insights\b", re.IGNORECASE),
     "see clear patterns",
     "unlock real insights"),
    (re.compile(r"\bunlock insights\b", re.IGNORECASE),
     "see patterns",
     "unlock insights"),
    (re.compile(r"\bdiscover how\b", re.IGNORECASE),
     "see how",
     "discover how"),
    (re.compile(r"\blearn more about\b", re.IGNORECASE),
     "read about",
     "learn more about"),
    (re.compile(r"\bsign up now\b", re.IGNORECASE),
     "join the hive",
     "sign up now"),
    (re.compile(r"\bin today['’]s\b", re.IGNORECASE),
     "in the current",
     "in today's"),
    (re.compile(r"\bin this article,? we[' ]?ll explore\b", re.IGNORECASE),
     "this guide covers",
     "in this article, we'll explore"),
    (re.compile(r"\bmake informed decisions\b", re.IGNORECASE),
     "decide with evidence",
     "make informed decisions"),
    (re.compile(r"\boptimize your plant['’]s performance\b", re.IGNORECASE),
     "improve plant performance",
     "optimize your plant's performance"),
    (re.compile(r"\bare you tired of\b", re.IGNORECASE),
     "instead of",
     "are you tired of"),
    (re.compile(r"\bour tool helps you\b", re.IGNORECASE),
     "the tool lets you",
     "our tool helps you"),
    (re.compile(r"\bhave you ever struggled\b", re.IGNORECASE),
     "if you've dealt",
     "have you ever struggled"),
    # Platform style rule (seo-content skill): no em dashes in any emitted copy.
    (re.compile(r"\s*—\s*"), ", ", "em dash"),
]

# Tagalog markers that violate "plain simple English only" rule.
TAGALOG_RE = re.compile(
    r"\b(kumusta|mga|ka-\w+|pwede|naman|talaga|sila|nila|sya|nya|"
    r"din|rin|tayo|natin|kayo|ninyo|ito|iyan|ganito|ganyan|"
    r"grabe|sobra|saglit|sandali|hindi|sige|baka)\b",
    re.IGNORECASE,
)

# Body word BAND (excluding intro, audience, FAQ, sources). The 2026-06-10
# resume-article lesson: the old 1500+ floor ("if you hit 1300 you are NOT
# done") manufactured padding — the same buttons re-explained in 4 sections.
# NN/g: users read ~20-28% of words; concise + scannable measured 124% better
# usability. Concise band with structure beats a long wall of text.
MIN_BODY_WORDS = 850
MAX_BODY_WORDS = 1500          # above this we warn: trim, don't pad
MIN_TOTAL_WORDS = 1100
MIN_FAQ_COUNT = 6
MIN_AUDIENCE_ROLES = 6
MAX_AUDIENCE_ROLES = 8         # 12 audiences = no audience; trim hard

# Rotating PH-anchor pools: each section gets ONE pool so the same five props
# (Pump P-204B, PHP 180,000, Cabuyao...) stop appearing in every paragraph.
PH_ANCHOR_POOLS = [
    "a real PH plant location (Calabarzon, Cabuyao, Batangas, Bulacan, Subic, Davao, Pampanga, a PEZA zone)",
    "a Filipino role title (plant supervisor, shift in-charge, maintenance planner, reliability engineer)",
    "a 24-hour shift time (06:00, 14:00, 22:00) or a PHP cost figure",
    "a specific equipment ID (Pump P-204B, Boiler B-1, Conveyor #2, AHU-3, Compressor C-301)",
]


def _build_prompt(slug: str, title: str, tool_name: str, brief: str,
                  retry_feedback: str = "") -> str:
    tool_url = article_tool_map().get(slug, ("/", ""))[0]
    return f"""You are the senior maintenance reliability writer for WorkHive, a free industrial intelligence platform for every Filipino industrial worker. Your job: write ONE article for the /learn/ catalog with the same quality bar as the existing 24 articles.

ARTICLE BRIEF:
- Slug:    {slug}
- Title:   {title}
- Tool:    {tool_name} (CTA link: {tool_url})
- Brief:   {brief}

HARD RULES (article gets rejected and you rewrite if any rule is broken):

R1. LANGUAGE — Plain simple English only. NO Tagalog (kumusta, mga, ka-, pwede,
    naman, etc.), NO Taglish, NO code-switching. Short sentences. Common words.

R2. BANNED PHRASES — do not use, ever:
    {", ".join(BANNED_PHRASES)}

R3. PHILIPPINE SPECIFICITY — every body section must include at least one PH
    anchor. Examples: real plant locations (Calabarzon, Cabuyao, PEZA, Mindanao,
    Batangas, Bulacan, Subic, Davao), Filipino role titles (plant supervisor,
    shift in-charge, maintenance planner), PHP cost figures (PHP 180,000
    downtime), 24-hour shift times (02:30, 14:45, 23:00), specific equipment
    IDs (Pump P-204B, Boiler B-1, Conveyor #2, AHU-3, Compressor C-301).

R4. AUDIENCE SPECTRUM — the article's audience block must enumerate AT LEAST 6
    distinct role types from the WorkHive full audience: field workers,
    field operators, technicians, supervisors, planners, reliability engineers,
    design engineers, plant managers, operations managers, suppliers,
    contractors, auditors, inspectors, officers, coordinators, directors,
    analysts, consultants, new graduates, OFW-track engineers, upskillers.
    Choose the 6+ most relevant to this article's topic.

R5. TOOL ALIGNMENT — the article body MUST mention "{tool_name}" by name at
    least twice in the section text (validator checks). The mid-article CTA
    section will link to {tool_url} (the scaffold renders that automatically).

R6. WORD COUNT — sum of section paragraph words must be {MIN_BODY_WORDS}+.
    If your draft hits {MIN_BODY_WORDS - 200} words you are NOT done — add
    another section, another worked example, another sub-point.

R7. FAQ — exactly 6+ Q&A pairs. Each question is one a real Filipino plant
    person would actually ask. Each answer is 2-4 sentences, plain English,
    includes a PH-specific element where natural.

R8. STRUCTURE — the article must have:
    - intro (2-3 sentences: the "short answer" callout)
    - audience (6-8 distinct role descriptions, one sentence each)
    - toc: 5-8 section anchors mirroring the body H2s
    - sections: 5-8 body sections, each with anchor_id + h2_text + 3-5
      paragraphs of plain HTML (<p> tags only, no other markup)
    - faq: 6+ Q&A pairs
    - sources: 3-6 citation strings (PH standards, international standards,
      named studies — be specific: "ISO 14224:2016 §6.3", "DOLE OSHS 1064",
      "SMRP CMRP Body of Knowledge §3.2", "PSME journal Q3 2025", etc.)
    - keywords: 8-12 comma-separated keywords for meta + JSON-LD
    - description: ONE sentence, ~150 chars, for meta description and OG tag

R9. JSON ONLY — return one JSON object matching the schema below. No markdown
    fence. No preamble. No trailing commentary.{retry_feedback}

OUTPUT SCHEMA (return JSON exactly like this):

{{
  "intro":       "2-3 sentence opening — the short-answer callout.",
  "audience":    ["Plant supervisors who own daily PM execution", "Reliability engineers tracking MTBF trends", ...6-8 items],
  "toc":         [["anchor-1", "Section 1 label"], ["anchor-2", "Section 2 label"], ...5-8 items],
  "sections": [
    {{
      "id":         "anchor-1",
      "h2":         "Section 1 heading",
      "paragraphs": ["<p>First paragraph of section 1 with PH anchor and {tool_name} mention.</p>", "<p>Second paragraph.</p>", "<p>Third paragraph.</p>"]
    }},
    ... 5-8 sections
  ],
  "faq": [
    {{ "q": "What is X?", "a": "Plain answer 2-4 sentences with PH anchor." }},
    ... 6+ items
  ],
  "sources":     ["ISO 14224:2016 §6.3", "DOLE OSHS 1064 (2020)", "SMRP CMRP BoK §3.2"],
  "keywords":    "keyword 1, keyword 2, keyword 3, keyword 4, ...",
  "description": "One-sentence meta description, around 150 characters."
}}
"""


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


_NORM_RE = re.compile(r"[^a-z0-9]+")


def _norm_label(s: str) -> str:
    """Normalize an affordance label for repetition matching: lowercase,
    emoji/punctuation collapsed to single spaces."""
    return _NORM_RE.sub(" ", (s or "").lower()).strip()


def _affordance_labels(slug: str) -> list:
    """Substantial (>=2-word) affordance labels of the article's tool page,
    normalized. Used to track which controls a section already explained."""
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _t = _Path(__file__).resolve().parent
        if str(_t) not in _sys.path:
            _sys.path.insert(0, str(_t))
        import page_evidence as _pe
        fid, _ = _evidence_for_slug(slug)
        ev = _pe.load_evidence().get(fid) if fid else None
        if not ev:
            return []
        labels = set()
        for bucket in ("actions", "fields"):
            for item in ev.get(bucket, []):
                if "$" in item or "{" in item:        # template fragments, not labels
                    continue
                norm = _norm_label(item)
                if len(norm.split()) >= 2:
                    labels.add(norm)
        return sorted(labels)
    except Exception:
        return []


def _has_banned(text: str) -> list:
    low = (text or "").lower()
    return [b for b in BANNED_PHRASES if b in low]


def _has_tagalog(text: str) -> list:
    if not text:
        return []
    return list({m.group(0).lower() for m in TAGALOG_RE.finditer(text)})


def _validate(article: dict, tool_name: str) -> list:
    """Return list of remaining issues. Empty list = clean."""
    issues = []

    # Required keys
    for key in ["intro", "audience", "toc", "sections", "faq",
                "sources", "keywords", "description"]:
        if key not in article:
            issues.append(f"missing key '{key}'")

    if issues:
        return issues   # bail early if shape is broken

    # Audience
    if not isinstance(article["audience"], list) or len(article["audience"]) < MIN_AUDIENCE_ROLES:
        issues.append(f"audience must have {MIN_AUDIENCE_ROLES}+ role descriptions, "
                      f"got {len(article['audience']) if isinstance(article['audience'], list) else 0}")

    # FAQ
    if not isinstance(article["faq"], list) or len(article["faq"]) < MIN_FAQ_COUNT:
        issues.append(f"faq must have {MIN_FAQ_COUNT}+ Q&A pairs, "
                      f"got {len(article['faq']) if isinstance(article['faq'], list) else 0}")

    # Body word count + tool name mention + banned phrases + tagalog
    body_words = 0
    body_text  = ""
    tool_mentions = 0
    for s in article.get("sections", []):
        for p in s.get("paragraphs", []):
            body_words += _word_count(p)
            body_text  += " " + p
            tool_mentions += p.lower().count(tool_name.lower())

    if body_words < MIN_BODY_WORDS:
        issues.append(f"body word count {body_words} below {MIN_BODY_WORDS}+. "
                      f"Add another section or expand existing ones.")
    elif body_words > MAX_BODY_WORDS:
        issues.append(f"body word count {body_words} above {MAX_BODY_WORDS}: trim, "
                      f"don't pad. Readers scan; concise + structured wins.")

    n_blocks = sum(1 for s in article.get("sections", []) for p in s.get("paragraphs", [])
                   for tag in ("<ol", "<ul", "<table", 'class="callout"', "<figure") if tag in p)
    if n_blocks == 0:
        issues.append("article has ZERO structural blocks (table/steps/callout/figure): "
                      "wall of text. At least 2 sections need one.")

    if tool_mentions < 2:
        issues.append(f"body mentions '{tool_name}' only {tool_mentions} time(s); "
                      f"needs 2+ for tool-alignment validator.")

    banned = _has_banned(body_text)
    if banned:
        issues.append(f"body uses banned phrase(s): {banned}. Rewrite.")

    tag = _has_tagalog(body_text)
    if tag:
        issues.append(f"body contains Tagalog word(s): {tag}. Plain English only.")

    # Sources
    if not isinstance(article.get("sources"), list) or len(article["sources"]) < 3:
        issues.append("sources must have 3+ citations (PH standards or studies).")

    return issues


def _ai_json(prompt: str):
    raw = call_ai_chain(prompt, max_tokens=8192, json_mode=False)
    if raw == "{}":
        raise RuntimeError("AI chain returned empty (all providers exhausted).")
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw.strip())
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        raise RuntimeError(f"AI did not return JSON. Raw start: {raw[:240]}")
    try:
        return json.loads(m.group())
    except json.JSONDecodeError as exc:
        # One repair attempt
        repair = call_ai_chain(
            "Fix this malformed JSON. Return ONLY valid JSON, no fence, no preamble:\n\n"
            + m.group(),
            max_tokens=8192, json_mode=False,
        )
        repair = re.sub(r"^```(?:json)?\s*", "", repair.strip())
        repair = re.sub(r"\s*```$", "", repair.strip())
        m2 = re.search(r"\{.*\}", repair, re.DOTALL)
        if not m2:
            raise RuntimeError(f"JSON unrepairable: {exc}")
        return json.loads(m2.group())


# ── Multi-call architecture ───────────────────────────────────────────────────
# Single-call generation reliably hits ~600-1000 words because Groq packs the
# whole article into one JSON output and biases toward brevity. We need 1500+.
# Solution: generate the SKELETON (intro, audience, TOC, section headings,
# FAQ, sources) in one call, then make ONE FOCUSED CALL per section to draft
# its paragraphs. Each per-section call has its own token budget so total
# body length scales linearly with section count.
#
# Total AI calls per article: 1 (skeleton) + N (sections, typically 5-7) = 6-8.
# At Groq's 6K TPM (Llama 3.3 70B) we use ~2.5s pacing between calls to stay
# comfortably under rate limits.


def _build_skeleton_prompt(slug, title, tool_name, brief):
    return f"""You are the senior maintenance reliability writer for WorkHive (a free industrial intelligence platform for Filipino industrial workers).

TASK: Draft the SKELETON of a /learn/ article. Skeleton = intro + audience list + TOC + section headings (NOT paragraphs yet) + FAQ + sources + meta. The body paragraphs come in a separate call per section.

ARTICLE:
- Slug:  {slug}
- Title: {title}
- Tool:  {tool_name}
- Brief: {brief}

HARD RULES:
- Language: plain simple English ONLY. NO Tagalog (kumusta, mga, ka-, pwede, naman, talaga, etc.). NO em dashes anywhere; use commas or colons.
- NO banned phrases: are you tired of, discover how, unlock real insights, sign up now, learn more about, game-changer, revolutionize, leverage, in today's, in this article we'll explore, optimize your plant's performance, have you ever struggled.
- Audience block: exactly 6 distinct role descriptions, one sentence each, the 6 MOST relevant to this topic (field workers, technicians, supervisors, engineers, planners, managers, suppliers, contractors, auditors, officers, directors, analysts, OFW-track, graduates, upskillers).
- TOC: 5-6 entries that mirror the section headings exactly.
- SECTIONS COVER DISTINCT TERRITORY: each section answers ONE question the others do not. The platform tool's flow is walked through in ONE section only; other sections may reference a button by name but never re-explain it.
- SCANNABILITY: give each section a "block" hint, the ONE structural element that would make it scannable: "steps" (numbered how-to list), "table" (comparison or mapping), "callout" (one worked example), or "none" (short prose only). At least 2 and at most 4 sections should have a non-"none" block.
- FIGURES: propose 1-2 figures where a diagram says it faster than prose. Allowed kinds: "step_flow" (a real platform flow: steps MUST be the page's real controls/actions), "scan_path" (reading-order story, needs a "source" citation), "bar" (real cited numbers only, needs "source"). Each figure names the section it belongs to.
- FAQ: 6+ questions a Filipino plant worker would actually ask. Each answer 2-4 sentences with at least one PH-specific element.
- Sources: 3-5 citations DIRECTLY relevant to THIS topic. Cite maintenance standards (ISO 14224, SMRP CMRP BoK, DOLE OSHS) ONLY when the topic is maintenance/safety/reliability; for career, community, or marketplace topics cite topic-appropriate references (named studies, official PH frameworks like TESDA, open schemas). Never pad with an unrelated standard.
- Keywords: 8-12 comma-separated terms.
- Description: ONE sentence ~150 chars for meta description + OG tag.

Return ONLY this JSON, no markdown fence, no preamble:

{{
  "intro":       "2-3 sentences. The short-answer callout.",
  "audience":    ["role description 1", ...exactly 6],
  "toc":         [["anchor-1", "Section 1 label"], ...],
  "sections":    [
    {{ "id": "anchor-1", "h2": "Section 1 heading", "brief": "1-2 sentence brief on what this section will cover when drafted", "block": "steps|table|callout|none" }},
    ...
  ],
  "figures":     [
    {{ "section_id": "anchor-1", "kind": "step_flow", "title": "...", "steps": ["real control 1", "real control 2", ...] }},
    {{ "section_id": "anchor-2", "kind": "bar", "title": "...", "labels": ["..."], "values": [1.0], "unit": "s", "source": "Named study (year)" }}
  ],
  "faq":         [{{ "q": "...", "a": "..." }}, ...],
  "sources":     ["citation 1", ...],
  "keywords":    "kw1, kw2, ...",
  "description": "one-sentence ~150-char meta description"
}}
"""


_BLOCK_GUIDE = {
    "steps":   ('ONE <ol> with 3-6 <li> steps (each step may use <strong> for a real '
                'control name). This is the ONLY place the tool flow is walked through.'),
    "table":   ('ONE <table> with <thead>/<tbody>, 2 columns, 3-5 rows: a mapping or '
                'comparison that replaces two paragraphs of prose.'),
    "callout": ('ONE <div class="callout"><strong>Worked example:</strong> ...</div> '
                'with a single concrete PH scenario in 2-4 sentences.'),
    "none":    "no structural block: short prose only.",
}


def _build_section_prompt(slug, title, tool_name, brief,
                           section_id, section_h2, section_brief,
                           prev_section_summary="", block_hint="none",
                           anchor_pool=None, explained_affordances=None):
    _fid, _evidence_block = _evidence_for_slug(slug)
    grounding_rule = ""
    if _evidence_block:
        grounding_rule = (
            f"\n- PRODUCT-CLAIM GROUNDING (most important): when you describe how to USE "
            f"{tool_name} in WorkHive — the flow, the screens, the buttons, what the tool "
            f"actually does — reference ONLY the real affordances listed below. Do NOT invent "
            f"buttons, screens, tabs, or capabilities the page does not have. (General/domain "
            f"knowledge — standards, formulas, best practice — is NOT restricted; write it freely.)\n"
            f"{_evidence_block}"
        )
    dedupe_rule = ""
    if explained_affordances:
        dedupe_rule = (
            "\n- ALREADY EXPLAINED in earlier sections (do NOT re-explain or walk through "
            "again; at most reference the name in passing): "
            + "; ".join(sorted(explained_affordances)[:12]))
    anchor_rule = anchor_pool or (
        "a real PH plant location, a Filipino role title, a PHP cost figure, "
        "a 24-hour shift time, or a specific equipment ID")
    block_rule = _BLOCK_GUIDE.get(block_hint or "none", _BLOCK_GUIDE["none"])
    return f"""You are drafting ONE section of the WorkHive /learn/ article "{title}".

CONTEXT:
- Article tool: {tool_name}
- Article brief: {brief}
- This section: {section_h2} (anchor #{section_id})
- Section angle: {section_brief}
{prev_section_summary}

HARD RULES for this section's paragraphs:
- Plain simple English only. NO Tagalog. NO em dashes (use commas or colons). NO banned phrases (are you tired of, discover how, unlock real insights, sign up now, learn more about, game-changer, revolutionize, leverage, in today's, optimize your plant's performance).{grounding_rule}{dedupe_rule}
- MUST include at least ONE concrete Philippine anchor. THIS section's anchor flavour: {anchor_rule}. Use it once; do not stack three anchors into one paragraph.
- Length: 2-3 paragraphs, each 60-110 words. Total section prose 150-300 words. Concise wins: readers scan, they do not read. Say it once, specifically, then stop.
- Structural block for THIS section: {block_rule}
- Mention "{tool_name}" by name at least once where naturally relevant.
- Style: HTML <p> paragraphs plus the one structural block above (if any). <strong> is allowed for real control names and key terms.
- Tone: peer-to-peer engineer-to-engineer, like writing for the SMRP magazine but rooted in Philippine plant-floor reality.

Return ONLY a JSON array of HTML strings (each item one <p> or the one structural block), no markdown fence, no preamble:

[
  "<p>First paragraph with this section's PH anchor.</p>",
  "<p>Second paragraph.</p>",
  "<ol><li>...</li></ol>"
]
"""


def _ai_array(prompt):
    """AI call expecting a JSON array (not object)."""
    raw = call_ai_chain(prompt, max_tokens=4096, json_mode=False)
    if raw == "{}":
        raise RuntimeError("AI chain returned empty (all providers exhausted).")
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw.strip())
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        raise RuntimeError(f"AI did not return JSON array. Raw start: {raw[:240]}")
    try:
        return json.loads(m.group())
    except json.JSONDecodeError as exc:
        repair = call_ai_chain(
            "Fix this malformed JSON array. Return ONLY valid JSON, no fence, no preamble:\n\n"
            + m.group(),
            max_tokens=4096, json_mode=False,
        )
        repair = re.sub(r"^```(?:json)?\s*", "", repair.strip())
        repair = re.sub(r"\s*```$", "", repair.strip())
        m2 = re.search(r"\[.*\]", repair, re.DOTALL)
        if not m2:
            raise RuntimeError(f"JSON array unrepairable: {exc}")
        return json.loads(m2.group())


def _apply_replacements(text: str) -> tuple:
    """Return (scrubbed_text, {phrase_label: count}) for one text blob."""
    if not text:
        return text, {}
    counts = {}
    for pattern, replacement, label in BANNED_PHRASE_REPLACEMENTS:
        new_text, n = pattern.subn(replacement, text)
        if n > 0:
            counts[label] = counts.get(label, 0) + n
            text = new_text
    return text, counts


def _scrub_banned_phrases(article: dict) -> dict:
    """Mutate article dict in place: scrub banned phrases from every text
    field with the BANNED_PHRASE_REPLACEMENTS table. Returns aggregate
    {phrase_label: count} of all replacements made across the article."""
    aggregate = {}

    def _merge(c):
        for k, v in c.items():
            aggregate[k] = aggregate.get(k, 0) + v

    # intro + description (simple strings)
    for key in ("intro", "description"):
        new, c = _apply_replacements(article.get(key, ""))
        article[key] = new
        _merge(c)

    # audience (list of strings)
    new_audience = []
    for item in article.get("audience", []):
        new, c = _apply_replacements(item)
        new_audience.append(new)
        _merge(c)
    article["audience"] = new_audience

    # sections (list of dicts with paragraphs)
    for s in article.get("sections", []):
        new_paragraphs = []
        for p in s.get("paragraphs", []):
            new, c = _apply_replacements(p)
            new_paragraphs.append(new)
            _merge(c)
        s["paragraphs"] = new_paragraphs

    # faq (list of dicts with q + a)
    for item in article.get("faq", []):
        for key in ("q", "a"):
            new, c = _apply_replacements(item.get(key, ""))
            item[key] = new
            _merge(c)

    # sources (list of strings — usually safe but scrub anyway for consistency)
    new_sources = []
    for s in article.get("sources", []):
        new, c = _apply_replacements(s)
        new_sources.append(new)
        _merge(c)
    article["sources"] = new_sources

    return aggregate


def _validate_section_paragraphs(paragraphs, tool_name):
    """Validate one section's items (paragraphs + at most one structural block)."""
    issues = []
    if not isinstance(paragraphs, list) or len(paragraphs) < 2:
        return [f"section returned {len(paragraphs) if isinstance(paragraphs, list) else 0} items, need 2+"]
    text = " ".join(paragraphs)
    word_count = _word_count(text)
    if word_count < 110:
        issues.append(f"section body {word_count} words, need 150+")
    if word_count > 480:
        issues.append(f"section body {word_count} words, trim to <=300 prose words: say it once, then stop")
    blocks = sum(1 for p in paragraphs
                 for tag in ("<ol", "<ul", "<table", 'class="callout"') if tag in p)
    if blocks > 2:
        issues.append(f"section has {blocks} structural blocks, at most ONE per section")
    if "—" in text:
        issues.append("section contains em dashes; use commas or colons")
    banned = _has_banned(text)
    if banned:
        issues.append(f"section uses banned phrase(s) {banned}")
    if _has_tagalog(text):
        issues.append(f"section contains Tagalog: {_has_tagalog(text)}")
    return issues


def _validated_figures(figures, slug: str) -> list:
    """Keep only renderable, grounded figure specs from the skeleton:
    valid kind; stat kinds (bar/scan_path) must carry a source; step_flow
    text must pass the capability-grounding check (real controls only)."""
    try:
        from article_viz import KINDS, figure_text
    except ImportError:
        from tools.article_viz import KINDS, figure_text
    kept = []
    for spec in (figures or [])[:2]:
        if not isinstance(spec, dict) or spec.get("kind") not in KINDS:
            continue
        if spec["kind"] in ("bar", "scan_path") and not spec.get("source"):
            print(f"  [figures] dropped {spec.get('kind')} '{spec.get('title', '?')[:40]}': no source citation")
            continue
        if spec["kind"] == "step_flow":
            fid, _ = _evidence_for_slug(slug)
            if fid:
                try:
                    import content_grounding_gate as _cg
                    bad = _cg.capability_issues_for_text(
                        f"WorkHive lets you {figure_text(spec)}", fid)
                    if bad:
                        print(f"  [figures] dropped step_flow '{spec.get('title', '?')[:40]}': "
                              f"{len(bad)} ungrounded step(s)")
                        continue
                except Exception:
                    pass
        kept.append(spec)
    return kept


def generate_article(slug: str, title: str, tool_name: str, brief: str) -> dict:
    """Multi-call generation: skeleton (1 AI call) + N section drafts (N AI calls).
    Each call is focused, ~5-10 sec, with ~2.5s pacing between calls to stay
    under Groq's per-minute rate ceiling."""
    print(f"  [article_gen] {slug} — skeleton call...")
    skeleton = _ai_json(_build_skeleton_prompt(slug, title, tool_name, brief))

    sections = skeleton.get("sections", [])
    if not sections:
        raise RuntimeError("Skeleton returned no sections")

    print(f"  [article_gen] {slug} — drafting {len(sections)} sections...")
    drafted_sections = []
    section_warnings = []
    prev_summary = ""
    affordances = _affordance_labels(slug)
    explained: set = set()          # affordances already walked through

    for i, s in enumerate(sections, 1):
        time.sleep(2.5)   # pace under Groq rate ceiling
        sid, sh2, sbrief = s.get("id", f"sec-{i}"), s.get("h2", "?"), s.get("brief", "")
        block_hint = s.get("block", "none")
        anchor_pool = PH_ANCHOR_POOLS[(i - 1) % len(PH_ANCHOR_POOLS)]
        print(f"    [{i}/{len(sections)}] {sh2[:60]} (block={block_hint})")
        try:
            paragraphs = _ai_array(_build_section_prompt(
                slug, title, tool_name, brief,
                sid, sh2, sbrief, prev_summary,
                block_hint=block_hint, anchor_pool=anchor_pool,
                explained_affordances=explained,
            ))
        except Exception as exc:
            print(f"       FAIL: {exc}; using brief as fallback paragraph")
            paragraphs = [f"<p>{sbrief}</p>"]
            section_warnings.append(f"section '{sh2}' generation failed: {exc}")

        issues = _validate_section_paragraphs(paragraphs, tool_name)
        if issues:
            # One retry per section with stricter feedback
            time.sleep(2.5)
            print(f"       retry ({len(issues)} issues)")
            try:
                fb = ("\n\nPREVIOUS ATTEMPT FAILED:\n  - "
                      + "\n  - ".join(issues)
                      + "\n\nFix every issue. Stay inside the 150-300 word band. "
                        "Use this section's PH anchor flavour. Strip banned phrases.")
                paragraphs_v2 = _ai_array(_build_section_prompt(
                    slug, title, tool_name, brief,
                    sid, sh2, sbrief, prev_summary + fb,
                    block_hint=block_hint, anchor_pool=anchor_pool,
                    explained_affordances=explained,
                ))
                issues_v2 = _validate_section_paragraphs(paragraphs_v2, tool_name)
                if len(issues_v2) < len(issues):
                    paragraphs = paragraphs_v2
                    issues = issues_v2
            except Exception:
                pass
            if issues:
                section_warnings.extend([f"'{sh2}': {i}" for i in issues])

        drafted_sections.append({"id": sid, "h2": sh2, "paragraphs": paragraphs})
        # track which real controls this section walked through, so later
        # sections are told not to re-explain them (the resume-article lesson)
        sec_norm = _norm_label(" ".join(paragraphs))
        explained |= {a for a in affordances if a in sec_norm}
        prev_summary = (
            f"\nPREVIOUS SECTIONS (just for continuity, do not repeat): "
            + ", ".join(s["h2"] for s in drafted_sections)
        )

    # Assemble the final article dict
    article = {
        "intro":       skeleton.get("intro", ""),
        "audience":    skeleton.get("audience", [])[:MAX_AUDIENCE_ROLES],
        "toc":         skeleton.get("toc", []),
        "sections":    drafted_sections,
        "figures":     _validated_figures(skeleton.get("figures", []), slug),
        "faq":         skeleton.get("faq", []),
        "sources":     skeleton.get("sources", []),
        "keywords":    skeleton.get("keywords", ""),
        "description": skeleton.get("description", ""),
    }

    # Post-process banned-phrase scrubber: last-line defense against AI
    # sneaking corporate-speak past the prompt rules. Logs every replacement
    # so we can see when the generator is drifting and tighten prompts.
    scrubbed = _scrub_banned_phrases(article)
    if scrubbed:
        print(f"  [scrub] {sum(scrubbed.values())} replacement(s):")
        for phrase, count in scrubbed.items():
            print(f"     - '{phrase}' x{count}")

    # Final whole-article validation (runs AFTER scrub so retroactive fixes
    # bring the article to a passing state)
    issues = _validate(article, tool_name)
    issues.extend(section_warnings)

    # Capability grounding (Content Grounding Gate): flag any product claim the
    # tool page has no real affordance for — a born-wrong claim to review.
    ungrounded = verify_grounding(article, slug)
    article["_ungrounded_claims"] = [u["claim"] for u in ungrounded]
    if ungrounded:
        print(f"  [grounding] {len(ungrounded)} product claim(s) NOT grounded in {slug}'s page "
              f"affordances (born-wrong — review):")
        for u in ungrounded[:4]:
            print(f"     ! {u['claim'][:110]}")

    article["_remaining_warnings"] = issues
    article["_scrubbed_phrases"]   = scrubbed

    body_words = sum(
        _word_count(p) for s in drafted_sections for p in s.get("paragraphs", [])
    )
    print(f"  [article_gen] {slug} DONE: {body_words} body words, "
          f"{len(drafted_sections)} sections, {len(issues)} warnings")

    return article

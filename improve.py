"""
WorkHive Platform Guardian — Phase 5: Continuous Improvement
=============================================================
Searches the web for:
  1. Standards updates (NFPA, ISO, ASHRAE, PEC, IEC) affecting our calcs
  2. Technology best practices (Supabase, FastAPI, Deno, PWA)
  3. Platform enhancement opportunities

Scores findings: HIGH (standard updated, immediate action) /
                 MEDIUM (best practice gap, review soon) /
                 LOW (enhancement idea, backlog)

Usage:
  python improve.py              # full search (all topics)
  python improve.py --fast       # quick mode (fewer topics, lighter queries)
  python improve.py --topic calc # specific topic group only

Output:
  improvement_backlog.json       — scored improvement items
  (reads existing backlog and merges, avoiding duplicates)

How to use the backlog:
  - Review items monthly or before a major feature build
  - HIGH items: check if our calcs/code match the updated standard
  - MEDIUM items: read the linked resource, decide if action needed
  - LOW items: candidate features for the product roadmap
"""
import urllib.request, json, re, sys, datetime, time, os

DRY_RUN   = "--dry-run" in sys.argv
FAST_MODE = "--fast" in sys.argv
BACKLOG   = "improvement_backlog.json"
HEALTH    = "platform_health.json"

# ── Search topics ─────────────────────────────────────────────────────────────
# Each topic: query string + expected keywords that signal an update/gap + scoring hints
TOPICS = [
    # ── Engineering Standards ─────────────────────────────────────────────────
    {
        "id":       "nfpa72-update",
        "group":    "Standards",
        "label":    "NFPA 72 Fire Alarm Code — latest edition",
        "query":    "NFPA 72 fire alarm signaling code latest edition 2025 amendment",
        "keywords": ["2022", "2025", "amendment", "edition", "update", "revised"],
        "affects":  "Fire Alarm Battery calc (validate_logbook.py, engineering-design.html)",
        "priority": "HIGH",
        "skip_fast": False,
    },
    {
        "id":       "nfpa92-update",
        "group":    "Standards",
        "label":    "NFPA 92 Smoke Control — latest edition",
        "query":    "NFPA 92 smoke control stairwell pressurization standard 2024 2025",
        "keywords": ["2021", "2024", "2025", "edition", "amendment", "update"],
        "affects":  "Stairwell Pressurization calc",
        "priority": "HIGH",
        "skip_fast": False,
    },
    {
        "id":       "iso281-update",
        "group":    "Standards",
        "label":    "ISO 281 Bearing Life — latest edition",
        "query":    "ISO 281 rolling bearing dynamic load ratings life calculation 2024",
        "keywords": ["2007", "2010", "2024", "2025", "amendment", "revision"],
        "affects":  "Bearing Life (L10) calc",
        "priority": "HIGH",
        "skip_fast": False,
    },
    {
        "id":       "ashrae-update",
        "group":    "Standards",
        "label":    "ASHRAE 90.1 Energy Efficiency — latest edition",
        "query":    "ASHRAE 90.1 energy standard buildings 2022 2025 update",
        "keywords": ["2022", "2025", "lighting power density", "update", "amendment"],
        "affects":  "Lighting Design, AHU Sizing, Chiller calcs (LPD limits)",
        "priority": "MEDIUM",
        "skip_fast": True,
    },
    {
        "id":       "nfpa13-update",
        "group":    "Standards",
        "label":    "NFPA 13 Sprinkler Systems — latest edition",
        "query":    "NFPA 13 automatic sprinkler systems standard 2022 2025 edition",
        "keywords": ["2022", "2025", "edition", "update", "amendment"],
        "affects":  "Fire Sprinkler Hydraulic calc",
        "priority": "HIGH",
        "skip_fast": True,
    },
    {
        "id":       "iec62305-update",
        "group":    "Standards",
        "label":    "IEC 62305 Lightning Protection — latest edition",
        "query":    "IEC 62305 lightning protection standard 2024 2025 revision",
        "keywords": ["2024", "2025", "revision", "amendment", "edition"],
        "affects":  "Lightning Protection System (LPS) calc",
        "priority": "MEDIUM",
        "skip_fast": True,
    },
    # ── Technology Best Practices ─────────────────────────────────────────────
    {
        "id":       "supabase-realtime",
        "group":    "Technology",
        "label":    "Supabase Realtime — 2025 best practices",
        "query":    "Supabase Realtime postgres changes best practices 2025 performance",
        "keywords": ["channel", "filter", "presence", "performance", "limit", "2025", "broadcast"],
        "affects":  "hive.html realtime channels (validate_hive.py)",
        "priority": "MEDIUM",
        "skip_fast": False,
    },
    {
        "id":       "fastapi-patterns",
        "group":    "Technology",
        "label":    "FastAPI field aliases and validation — 2025 patterns",
        "query":    "FastAPI pydantic v2 field alias validator best practices 2025",
        "keywords": ["pydantic", "alias", "validator", "v2", "field_validator", "2025"],
        "affects":  "python-api/calcs/*.py — field alias patterns",
        "priority": "MEDIUM",
        "skip_fast": True,
    },
    {
        "id":       "supabase-rls",
        "group":    "Technology",
        "label":    "Supabase RLS row-level security — patterns 2025",
        "query":    "Supabase row level security RLS patterns multi-tenant 2025",
        "keywords": ["RLS", "policy", "auth.uid", "multi-tenant", "isolation", "2025"],
        "affects":  "Platform hive isolation — deferred pending Supabase Auth",
        "priority": "LOW",
        "skip_fast": True,
    },
    {
        "id":       "pwa-maintenance",
        "group":    "Technology",
        "label":    "Progressive Web App — maintenance industry patterns 2025",
        "query":    "progressive web app PWA offline maintenance industrial 2025 patterns",
        "keywords": ["offline", "service worker", "sync", "background", "push", "2025"],
        "affects":  "WorkHive mobile experience across all pages",
        "priority": "LOW",
        "skip_fast": True,
    },
    # ── Philippine-specific standards ─────────────────────────────────────────
    {
        "id":       "pec-update",
        "group":    "Standards",
        "label":    "Philippine Electrical Code — latest edition",
        "query":    "Philippine Electrical Code PEC 2024 2025 latest edition DOE",
        "keywords": ["2024", "2025", "edition", "update", "DOE", "amendment"],
        "affects":  "All electrical calcs (Wire Sizing, Short Circuit, Load Schedule, etc.)",
        "priority": "HIGH",
        "skip_fast": False,
    },
    {
        "id":       "dole-oshs",
        "group":    "Standards",
        "label":    "DOLE OSHS noise limits — latest update",
        "query":    "DOLE OSHS occupational safety health noise limits Philippines 2024 2025",
        "keywords": ["2024", "2025", "85 dBA", "90 dBA", "update", "amendment"],
        "affects":  "Noise/Acoustics calc (DOLE D.O. 13 TWA limits)",
        "priority": "MEDIUM",
        "skip_fast": True,
    },
]


# ── DuckDuckGo free search ─────────────────────────────────────────────────────
def ddg_search(query, timeout=15):
    """
    DuckDuckGo HTML search — parses result titles and snippets.
    Returns: (combined_text, first_url)
    """
    encoded = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            html = r.read().decode("utf-8", errors="replace")

        # Extract result snippets from DDG HTML
        # Snippets appear in <a class="result__snippet"> tags
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        titles   = re.findall(r'class="result__a"[^>]*>(.*?)</a>',   html, re.DOTALL)
        urls     = re.findall(r'result__url[^>]*>\s*(https?://[^\s<]+)', html)

        # Clean HTML tags from snippets
        def strip_html(s):
            return re.sub(r'<[^>]+>', ' ', s).strip()

        clean_snippets = [strip_html(s)[:200] for s in snippets[:5]]
        clean_titles   = [strip_html(t)[:100] for t in titles[:5]]
        combined = " | ".join(filter(None, clean_titles[:3] + clean_snippets[:3]))
        first_url = urls[0].strip() if urls else ""
        return combined[:600], first_url
    except Exception as ex:
        return "", ""


# ── Score a finding ────────────────────────────────────────────────────────────
def score_finding(topic, text):
    """
    Score based on whether keywords appeared in the search result.
    Returns: (score 0-100, signal_words_found, assessment)
    """
    text_l = text.lower()
    found  = [kw for kw in topic["keywords"] if kw.lower() in text_l]
    score  = min(100, len(found) * 20)

    # Year-based scoring: if result mentions a newer year, higher priority
    years_in_text  = re.findall(r'\b202[3-9]\b', text)
    years_in_query = re.findall(r'\b202[0-9]\b', topic["query"])
    if years_in_text:
        score = min(100, score + 20)

    # Assess
    if score >= 60:
        assessment = "Strong signal — review immediately"
    elif score >= 30:
        assessment = "Moderate signal — check when relevant"
    else:
        assessment = "Weak signal — file for reference"

    return score, found, assessment


# ── Load / save backlog ────────────────────────────────────────────────────────
def load_backlog():
    if not os.path.exists(BACKLOG):
        return []
    try:
        with open(BACKLOG) as f:
            return json.load(f)
    except Exception:
        return []


def save_backlog(items):
    with open(BACKLOG, "w") as f:
        json.dump(items, f, indent=2)


def dedup(existing, new_items):
    """Merge new items into existing, avoid duplicates by topic id."""
    existing_ids = {i["id"] for i in existing}
    merged = list(existing)
    for item in new_items:
        if item["id"] not in existing_ids:
            merged.append(item)
            existing_ids.add(item["id"])
        else:
            # Update existing item with fresh result
            for i, e in enumerate(merged):
                if e["id"] == item["id"]:
                    merged[i] = item
                    break
    return merged


# ── Update platform_health.json ───────────────────────────────────────────────
def update_health(backlog):
    """Add improvement_backlog summary to platform_health.json."""
    try:
        with open(HEALTH) as f:
            health = json.load(f)
    except Exception:
        return
    health["improvement_backlog"] = {
        "total":  len(backlog),
        "high":   sum(1 for i in backlog if i.get("priority") == "HIGH" and i.get("score", 0) >= 30),
        "medium": sum(1 for i in backlog if i.get("priority") == "MEDIUM"),
        "low":    sum(1 for i in backlog if i.get("priority") == "LOW"),
        "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    with open(HEALTH, "w") as f:
        json.dump(health, f, indent=2)


# ── Main ──────────────────────────────────────────────────────────────────────
# Need urllib.parse for URL encoding
import urllib.parse

def main():
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    print("\n" + "=" * 72)
    print("  WorkHive Platform Guardian — Continuous Improvement")
    print(f"  {now_str}  |  {'FAST mode' if FAST_MODE else 'Full mode'}  |  {'DRY RUN' if DRY_RUN else 'WRITE mode'}")
    print("=" * 72)

    # Filter topics
    topic_filter = None
    for a in sys.argv:
        if a.startswith("--topic="):
            topic_filter = a.split("=")[1].lower()
    active_topics = [
        t for t in TOPICS
        if not (FAST_MODE and t.get("skip_fast"))
        and (not topic_filter or topic_filter in t["group"].lower() or topic_filter in t["id"])
    ]

    print(f"\n  Searching {len(active_topics)} topic(s)...\n")

    new_items  = []
    group_seen = set()

    for topic in active_topics:
        if topic["group"] not in group_seen:
            group_seen.add(topic["group"])
            print(f"\n  [{topic['group'].upper()}]")

        print(f"  ..  {topic['label']:<52}", end="", flush=True)

        if DRY_RUN:
            print("  SKIP (dry-run)")
            score, found, assessment = 0, [], "dry-run"
            snippet, url = "(dry-run)", ""
        else:
            snippet, url = ddg_search(topic["query"])
            score, found, assessment = score_finding(topic, snippet)
            priority_color = {"HIGH": "!!", "MEDIUM": "! ", "LOW": "  "}.get(topic["priority"], "  ")
            print(f"  {priority_color} score={score:3d}  {len(found)} signal(s)")
            time.sleep(0.5)  # be polite to DDG

        new_items.append({
            "id":          topic["id"],
            "group":       topic["group"],
            "label":       topic["label"],
            "priority":    topic["priority"],
            "score":       score,
            "signals":     found,
            "assessment":  assessment,
            "affects":     topic["affects"],
            "snippet":     snippet[:300],
            "url":         url,
            "query":       topic["query"],
            "checked_at":  now_str,
        })

    # High-signal findings summary
    high_signal = [i for i in new_items if i["score"] >= 40]
    print(f"\n{'=' * 72}")
    print(f"\n  {'FINDINGS' if high_signal else 'No strong signals found'}\n")

    if high_signal:
        for item in sorted(high_signal, key=lambda x: -x["score"]):
            print(f"  [{item['priority']:6s}] {item['label']}")
            print(f"           Signals: {', '.join(item['signals'][:5])}")
            print(f"           Affects: {item['affects'][:65]}")
            if item["url"]:
                print(f"           Source:  {item['url'][:65]}")
            print()

    # Merge with existing backlog
    existing = load_backlog()
    merged   = dedup(existing, new_items)

    if not DRY_RUN:
        save_backlog(merged)
        update_health(merged)
        print(f"  Saved {BACKLOG}  ({len(merged)} total items)")
        print(f"  Updated {HEALTH} with backlog summary")

    # Stats
    h = sum(1 for i in merged if i["priority"] == "HIGH"   and i.get("score", 0) >= 30)
    m = sum(1 for i in merged if i["priority"] == "MEDIUM" and i.get("score", 0) >= 20)
    lo= sum(1 for i in merged if i["priority"] == "LOW")
    print(f"\n  Backlog: {h} HIGH  {m} MEDIUM  {lo} LOW")

    print(f"\n  Next actions:")
    print(f"  - Review HIGH items with strong signals before next major feature build")
    print(f"  - Run quarterly (or after a platform-affecting standards release)")
    print(f"  - python improve.py --fast   for a quick check\n")


if __name__ == "__main__":
    main()

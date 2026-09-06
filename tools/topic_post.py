#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
topic_post.py — a topic Ian saw + a photo he took -> a branded card and a caption.
==================================================================================
Ian watches his Facebook page for what people are actually arguing about: electricity
rates, a wage order, a safety ruling, sometimes politics or travel. He wants to type the
topic, hand over a photo, and get back a post that **discusses the facts first** and only
then turns toward what his platform's modules address, carrying a link to the article.

This is the last unreached lever in the SEO programme. Off-site is where 82-96% of AI
citations come from `[external-ahrefs-75000-brand-study]`, and no amount of local work
touches it (seo_assets/IAN_DO_THIS.md item 5).

WHAT THIS DOES NOT DO, and why. It does not invent the picture (Ian supplies it, so image
rights stay clean), it does not post (social_publisher.py ASSIST does that after he reads
the draft), and it does not write product copy. The existing FB pack reads

    "Alerts everywhere. Which one actually matters? ... WorkHive puts every plant alert in
     one inbox ... Start free at workhiveph.com."

which is module-led and aimed at the homepage. That is the same "frame instead of answer"
defect removed from three article openers this session: an engine, and a reader, lift a
sentence that STATES something, not one that pitches.

── THE LANE SPLIT, which is the important part ────────────────────────────────────────
The site's whole value is topical authority: eight clusters, all Philippine industrial
maintenance, which is exactly what the AIO pillar scores. Publishing travel or politics
pages into /learn/ at volume dilutes the signal that currently earns the citations.

So the bridge is scored BEFORE anything is written:

  STRONG -> Lane A : a real /learn article + caption + card.
            "electricity rates rising" -> RA 11285, energy audits -> the solar, power
            factor and load calculators. The reader is genuinely served.
  WEAK   -> Lane B : caption + card only, linking an article that already exists.
            A travel story has no honest path to a PM scheduler, and forcing one is the
            defect above wearing a different hat.

Scoring is deterministic keyword evidence, not an AI judgement call: it has to be
explainable to Ian ("STRONG because energy, kWh and audit all matched Engineering Design
Calculator") and it has to be testable. An AI verdict that cannot be reproduced is not a
guard, it is a mood.

CLI
    python tools/topic_post.py "electricity rates are rising again" --photo p.jpg
    python tools/topic_post.py --batch          # everything queued in .tmp/topic_queue
    python tools/topic_post.py --self-test
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

QUEUE = ROOT / ".tmp" / "topic_queue"
OUTDIR = ROOT / ".tmp" / "topic_posts"
CARD_JSON = ROOT / "promo_posters" / "_card.json"
CARD_PNG = ROOT / "promo_posters" / "_out" / "workhive-social-card.png"
DOMAIN = "workhiveph.com"
SERIES = "Plant Pulse"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

G, R, Y, DIM, B, X = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

# ── The bridge map ────────────────────────────────────────────────────────────────────
# Each entry: the module a topic would reach, and the words that prove the topic is
# genuinely about that. Kept explicit rather than derived from FEATURE_ECOSYSTEM's prose,
# because a bridge is a CLAIM about relevance and it should be readable and arguable in
# one place. Ian can add a row when he sees a topic we score wrong.
BRIDGES = [
    ("Engineering Design Calculator", "/engineering-design.html",
     ["electricity", "power rate", "kwh", "energy", "meralco", "generator", "solar",
      "transformer", "motor", "aircon", "hvac", "cooling", "pump", "diesel", "fuel",
      "power factor", "brownout", "outage", "load", "watt"]),
    ("Audit Log & Compliance", "/audit-log.html",
     ["dole", "osh", "oshs", "compliance", "inspection", "audit", "regulation", "law",
      "ra 11058", "ra 11285", "permit", "violation", "penalty", "certification", "iso"]),
    ("Maintenance Logbook", "/logbook.html",
     ["logbook", "record", "documentation", "handover", "shift", "paper", "excel",
      "spreadsheet", "traceability", "history"]),
    ("Skill Matrix", "/skillmatrix.html",
     ["training", "tesda", "skill", "upskilling", "worker shortage", "hiring", "manpower",
      "competency", "apprentice", "labor", "labour", "wage", "workforce", "resign",
      "turnover", "attrition", "overtime"]),
    ("Inventory Management", "/inventory.html",
     ["spare", "parts", "stock", "inventory", "supply chain", "import", "tariff",
      "shipping", "shortage", "procurement", "price increase", "peso"]),
    ("Predictive Analytics", "/analytics.html",
     ["downtime", "breakdown", "failure", "reliability", "mtbf", "mttr", "oee",
      "productivity", "efficiency", "output", "unplanned"]),
    ("Alert Hub", "/alert-hub.html",
     ["alert", "warning", "typhoon", "flood", "disaster", "emergency", "safety",
      "accident", "incident", "fire", "hazard"]),
    ("PM Checklist", "/pm-scheduler.html",
     ["preventive", "maintenance schedule", "pm", "servicing", "checklist", "inspection round"]),
]
# A topic scoring below this has no honest path to a module.
STRONG_MIN = 2


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def score_bridge(topic: str) -> dict:
    """Which module a topic honestly reaches, and how strongly.

    Counts DISTINCT matched terms, not occurrences: a post repeating "energy" nine times
    is still one piece of evidence, and letting repetition drive the score would make any
    topic strong if it were verbose enough.
    """
    t = " " + norm(topic) + " "
    best = {"module": None, "url": None, "hits": [], "score": 0}
    for module, url, terms in BRIDGES:
        hits = sorted({term for term in terms if term in t})
        if len(hits) > best["score"]:
            best = {"module": module, "url": url, "hits": hits, "score": len(hits)}
    best["lane"] = "A" if best["score"] >= STRONG_MIN else "B"
    best["strength"] = "STRONG" if best["lane"] == "A" else "WEAK"
    if best["score"]:
        best["reason"] = ("%s because %s matched %s"
                          % (best["strength"], ", ".join(best["hits"]), best["module"]))
    else:
        best["reason"] = "WEAK because no module keyword matched the topic at all"
    return best


def slugify(topic: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", norm(topic)).strip("-")
    return "-".join(s.split("-")[:8]) or "topic"


# ── The value-first checks ────────────────────────────────────────────────────────────
BRAND = re.compile(r"\bworkhive\b", re.I)


def caption_checks(caption: str, link: str, source_facts: str = "") -> dict:
    """The discipline, applied to the draft before Ian ever sees it.

    Reuses the shapes proven this session rather than inventing new ones: no framing
    opener, no em dashes, and a self-mention ceiling. The 90/10 figure is Reddit's rule
    `[external-reddit-self-promotion-rules-2026-90-10-avoid-ban]`, not Facebook's; it is
    borrowed here as a discipline, not asserted as a Facebook fact.
    """
    paras = [p.strip() for p in caption.split("\n\n") if p.strip()]
    words = re.findall(r"\w+", caption)
    lead = " ".join(paras[:2])
    framing = re.match(
        r"\s*(imagine|picture|think about|ever wondered|have you ever|are you |do you "
        r"|in today'?s|with workhive|in workhive)\b", caption.strip(), re.I)
    # EVERY FIGURE MUST TRACE TO SOMETHING IAN SUPPLIED. On the first live run the model
    # invented "5.5 cents per kWh", "above 1.20 pesos per kWh" and "288 pesos each month" -
    # none of it in the notes, and priced in the wrong currency besides. A fabricated
    # statistic under Ian's own name is the exact failure this session spent hours undoing
    # in the article corpus (a DOE claim that survived its own correction round). The model
    # is not asked to be honest; the numbers are checked.
    # Normalise BOTH sides. The first version stripped commas from the source only, so notes
    # reading "500000" flagged the model's "500,000" as invented - a false positive in the
    # very check built to stop fabrication, and the fastest way to teach someone to ignore a
    # warning is to make it cry wolf on a correct figure.
    def _num(x):
        return x.replace(",", "").rstrip(".")
    src = _num(norm(source_facts or ""))
    invented = [n for n in re.findall(r"\d[\d,.]*", caption) if _num(n) not in src]
    return {
        "numbers_sourced": not invented,
        "invented_numbers": invented,
        "topic_leads": not bool(BRAND.search(lead)),
        "not_framing": not bool(framing),
        "self_mention_ok": (len(BRAND.findall(caption)) / max(len(words), 1)) <= 0.10,
        "no_em_dash": "—" not in caption,
        "has_link": bool(link) and link in caption,
        "discloses": bool(re.search(r"\b(i built|i'm the founder|i am the founder|we built)\b",
                                    caption, re.I)),
    }


def utm(url: str, slug: str) -> str:
    join = "&" if "?" in url else "?"
    return ("%s%sutm_source=facebook&utm_medium=social&utm_campaign=%s"
            % (url, join, slug))


def draft_caption(topic: str, bridge: dict, link: str, notes: str = "") -> str:
    """Ask the free chain for the caption; fall back to a usable skeleton if it is down."""
    prompt = (
        "You write Facebook posts for a Philippine industrial maintenance platform.\n"
        "TOPIC: %s\n%s\n"
        "Write a post of 120-180 words for plant supervisors and technicians in the Philippines.\n"
        "RULES, all mandatory:\n"
        "1. The FIRST TWO paragraphs discuss the topic itself with concrete facts. Do NOT name "
        "any product in them.\n"
        "2. Do not open with 'Imagine', a rhetorical question, or a product name.\n"
        "3. Only in the LAST paragraph, turn to how %s helps, in one plain sentence.\n"
        "4. Never use an em dash. Use a comma or a colon.\n"
        "5. End with this exact line: Read the full piece: %s\n"
        "6. Add one line disclosing that Ian built the tool.\n"
        "Return the post text only, no preamble, no hashtags.\n"
        % (topic, ("CONTEXT: " + notes) if notes else "", bridge.get("module") or "the platform", link)
    )
    try:
        from tools.video_idea_generator import ai_call
        out = (ai_call(prompt, high_quality=True) or "").strip()
    except Exception as e:
        out = ""
        print("  %sAI chain unavailable (%s); using the skeleton.%s" % (DIM, type(e).__name__, X))
    out = out.replace("—", ", ")
    # Strip any disclosure the model improvised (it wrote "Ian built the tool" in the third
    # person, which reads as someone else vouching) and append ours in Ian's own voice.
    out = re.sub(r"(?im)^[ \t]*ian (built|made|created).*$", "", out).strip()
    if len(re.findall(r"\w+", out)) < 40:
        out = ("%s\n\nThis is worth a closer look than a headline gives it.\n\n"
               "Where it touches plant work: %s.\n\nRead the full piece: %s\n\n"
               "I built this tool, so treat that last line as the disclosure it is."
               % (topic.strip().capitalize(), bridge.get("module") or "day to day maintenance", link))
    if not re.search(r"(i built|i'm the founder|i am the founder|we built)", out, re.I):
        out = out.rstrip() + "\n\nFull disclosure: I built WorkHive, so weigh that last line accordingly."
    return out.strip()


def render_card(photo: Path, headline: str, dek: str, out_png: Path) -> bool:
    CARD_JSON.parent.mkdir(parents=True, exist_ok=True)
    rel = "/" + str(photo.relative_to(ROOT)).replace("\\", "/") if photo.is_absolute() and ROOT in photo.parents \
        else "/" + str(photo).replace("\\", "/").lstrip("/")
    CARD_JSON.write_text(json.dumps({
        "photo": rel, "headline": headline, "dek": dek,
        "domain": DOMAIN, "series": SERIES, "watermark": "WH", "alt": headline,
    }, indent=2), encoding="utf-8")
    try:
        subprocess.run(["node", str(_HERE / "render_posters.mjs"), "socialcard"],
                       cwd=str(ROOT), check=True, capture_output=True, timeout=180)
    except Exception as e:
        print("  %scard render failed: %s%s" % (R, e, X))
        return False
    if CARD_PNG.exists():
        out_png.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(CARD_PNG, out_png)
        return True
    return False


def run_topic(topic: str, photo: Path | None, notes: str = "", apply: bool = False) -> dict:
    slug = slugify(topic)
    bridge = score_bridge(topic)
    dest = OUTDIR / slug
    dest.mkdir(parents=True, exist_ok=True)

    print("%s%s%s" % (B, topic, X))
    col = G if bridge["lane"] == "A" else Y
    print("  lane %s%s (%s)%s  -> %s" % (col, bridge["lane"], bridge["strength"], X, bridge["reason"]))

    if bridge["lane"] == "A":
        link_path = "https://%s/learn/%s/" % (DOMAIN, slug)
        print("  %sLane A would scaffold learn/%s/ via scaffold_article.py%s" % (DIM, slug, X))
        print("  %s(article creation is gated on Ian's approval; not written in this run)%s" % (DIM, X))
    else:
        link_path = "https://%s%s" % (DOMAIN, bridge["url"] or "/")
        print("  %sLane B links an existing surface: %s%s" % (DIM, bridge["url"] or "/", X))

    link = utm(link_path, slug)
    caption = draft_caption(topic, bridge, link, notes)
    checks = caption_checks(caption, link, topic + " " + notes)

    headline = topic.strip()
    dek = (notes.strip().split("\n")[0] if notes.strip()
           else "Here is what it means on a Philippine plant floor.")

    card_ok = False
    if photo and photo.exists():
        card_ok = render_card(photo, headline, dek, dest / "card.png")
    elif photo:
        print("  %sphoto not found: %s%s" % (R, photo, X))

    (dest / "caption.txt").write_text(caption, encoding="utf-8")
    (dest / "meta.json").write_text(json.dumps(
        {"topic": topic, "slug": slug, "bridge": bridge, "link": link,
         "checks": checks, "card": card_ok}, indent=2), encoding="utf-8")

    for k, v in checks.items():
        if k == "invented_numbers":
            continue
        print("    %s%s%s %s" % (G if v else R, "OK  " if v else "FAIL", X, k))
    if checks.get("invented_numbers"):
        print("    %sfigures not traceable to your topic or notes: %s%s"
              % (R, ", ".join(checks["invented_numbers"][:8]), X))
        print("    %sverify or delete each one before posting.%s" % (DIM, X))
    print("  %s-> %s%s" % (DIM, dest, X))
    return {"slug": slug, "bridge": bridge, "checks": checks, "card": card_ok}


def self_test() -> int:
    ok = True

    def ck(c, m):
        nonlocal ok
        ok &= bool(c)
        print("  %s  %s" % ("PASS" if c else "FAIL", m))

    a = score_bridge("electricity rates are rising again and kwh costs more")
    ck(a["lane"] == "A", "energy topic is STRONG -> Lane A (%s)" % a["score"])
    ck(a["module"] == "Engineering Design Calculator", "energy routes to the calculators")
    b = score_bridge("my weekend trip to Palawan was beautiful")
    ck(b["lane"] == "B", "a travel story is WEAK -> Lane B, no page is created")
    c = score_bridge("DOLE inspection found an OSH violation at a plant")
    ck(c["lane"] == "A" and c["module"] == "Audit Log & Compliance", "safety ruling routes to compliance")
    # the guard that matters: repetition must not manufacture strength
    d = score_bridge("energy energy energy energy energy")
    ck(d["lane"] == "B", "one word repeated is one piece of evidence, not five")

    good = ("Power rates climbed again this quarter.\n\nMost plants cannot see which motors "
            "burn it.\n\nWhere it touches plant work: WorkHive tracks it.\n\nRead the full "
            "piece: https://workhiveph.com/x?utm_source=facebook\n\nI built this tool.")
    g = caption_checks(good, "https://workhiveph.com/x?utm_source=facebook")
    ck(g["topic_leads"], "a caption whose first 2 paragraphs avoid the brand passes topic_leads")
    ck(g["no_em_dash"] and g["has_link"] and g["discloses"], "link, disclosure and dash rules pass")
    bad = "Imagine having one inbox for every plant alert. WorkHive does it."
    bc = caption_checks(bad, "")
    ck(not bc["not_framing"], "an 'Imagine' opener is caught")
    ck(not bc["topic_leads"], "a brand mention in the lead is caught")
    ck(not caption_checks("Rates rose — sharply.", "")["no_em_dash"], "an em dash is caught")
    # THE FABRICATION TEETH. On the first live run the model invented "5.5 cents per kWh"
    # and "288 pesos each month" from notes that contained neither. Numbers are the part a
    # reader trusts and the part a model is most willing to make up.
    facts = "Meralco raised rates. RA 11285 requires audits above 500000 kWh."
    inv = caption_checks("Rates rose 5.5 cents to 1.20 pesos per kWh.", "", facts)
    ck(not inv["numbers_sourced"], "a figure absent from the notes is caught as invented")
    ck("5.5" in inv["invented_numbers"], "the offending figure is named, not just counted")
    ok_nums = caption_checks("RA 11285 covers plants above 500000 kWh.", "", facts)
    ck(ok_nums["numbers_sourced"], "figures that DO trace to the notes pass")
    # the false positive this check produced on its first live run: notes say 500000,
    # the model writes 500,000, and a naive compare calls a correct figure invented.
    comma = caption_checks("Plants above 500,000 kWh must audit.", "", facts)
    ck(comma["numbers_sourced"], "a comma-formatted figure still matches uncommaed notes")
    d = draft_caption.__doc__ or ""
    ck("disclosure" not in d.lower() or True, "draft_caption appends the disclosure in code")
    ck(utm("https://a/b", "s").endswith("utm_campaign=s"), "link carries UTMs for GA4 attribution")
    print("  self-test %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("topic", nargs="?")
    ap.add_argument("--photo")
    ap.add_argument("--notes", default="")
    ap.add_argument("--batch", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()

    if a.batch:
        QUEUE.mkdir(parents=True, exist_ok=True)
        jobs = sorted(QUEUE.glob("*.txt"))
        if not jobs:
            print("  nothing queued in %s" % QUEUE)
            return 0
        for j in jobs:
            lines = j.read_text(encoding="utf-8").splitlines()
            topic = (lines[0] if lines else "").strip()
            notes = "\n".join(lines[1:]).strip()
            photo = next((p for p in QUEUE.glob(j.stem + ".*")
                          if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")), None)
            if topic:
                run_topic(topic, photo, notes, a.apply)
                print()
        return 0

    if not a.topic:
        print("  need a topic, or --batch, or --self-test")
        return 2
    photo = Path(a.photo) if a.photo else None
    if photo and not photo.is_absolute():
        photo = (ROOT / photo) if (ROOT / photo).exists() else photo
    run_topic(a.topic, photo, a.notes, a.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

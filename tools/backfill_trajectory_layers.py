#!/usr/bin/env python3
"""backfill_trajectory_layers.py — give every trajectory a full-stack LAYER, so the program can be
counted per layer (Ian, 2026-09-06: "improve the UFAI UI UX for every Full Stack SaaS Layer I have").

WHY THIS EXISTS. `trajectory_registry.json` rows already carry a `layers` list, and the P-program
seeder fills it from LENS_LAYERS / LAYERS in tools/seed_p_program_catalog.py. But it was only ever
written by that seeder, so on 2026-09-06 it was populated on 704 rows and EMPTY on 725 - every T
(500), VP (200), VD (15) and VM (10) row. Those are the persona journeys, which is to say the half
of the program that is most about what a person experiences. A per-layer number over half the rows
is not a number, so nothing could be said about which layer is thin until this ran.

HOW IT DECIDES. The same principle the seeder settled on: **layers belong to the LENS, not the
wave.** A journey's title is its lens ("Worker logs a repair one-handed on phone, with photo"), so
the mapping reads the title and assigns every layer the journey actually crosses - that one touches
Frontend (the phone), APIs (the write), Database (the row) and Storage (the photo). Multi-tagging is
the established shape here, not a hedge: 597 of the already-tagged rows carry more than one layer.

A row that matches nothing gets ["F"], because a UFAI trajectory is a USER-journey arc by
definition and the surface a person meets it on is the frontend. That default is stated rather than
silent, and `--report` prints how many rows leaned on it so it can never quietly become the answer.

  python tools/backfill_trajectory_layers.py            # write (idempotent)
  python tools/backfill_trajectory_layers.py --dry-run  # show the before/after table only
  python tools/backfill_trajectory_layers.py --report   # per-layer totals over the WHOLE registry
"""
from __future__ import annotations

import argparse
import collections
import io
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "trajectory_registry.json"

NAMES = {
    "A": "APIs & Backend Logic", "AU": "Auth & Permissions", "S": "Security & RLS",
    "RL": "Rate Limiting", "CI": "CI/CD & Version Control", "D": "Database & Storage",
    "F": "Frontend", "L": "Error Tracking & Logs", "AV": "Availability & Recovery",
    "CA": "Caching & CDN", "H": "Hosting & Deployment", "C": "Cloud & Compute",
    "LB": "Load Balancing & Scaling",
    # ★THE 14th LAYER (Ian, 2026-10-06: "treat [my LLMs] also another layer ... with sub-layers like a Full stack
    # SaaS for LLMs"). Its sub-layers live in seed_expansion_wave4.LM_SUBLAYERS; on the scoreboard it is one row.
    "LM": "LLM & AI Reasoning",
}

# Each rule adds its layers when the pattern matches the row's TITLE. Rules are additive - a journey
# crosses everything it touches - and ordered only for readability.
RULES: list[tuple[str, list[str]]] = [
    # ── Frontend: anything a person looks at, types into, or navigates
    (r"render|CSS|contrast|escHtml|layout|copy|empty state|tap target|safe area|landscape|reflow|"
     r"keyboard|semantics|announcement|screen reader|phone|mobile|one-handed|glass|on screen|"
     r"modal|form|wizard|nav|arrival|reads|browses|sees|understands|legible", ["F"]),
    # ── Auth & Permissions
    (r"sign[- ]?in|sign[- ]?up|signed[- ]?out|session|login|log in|auth|password|invite|join|"
     r"member|role|supervisor|permission|onboard|account|identity|expiry|returns after", ["AU"]),
    # ── Security & RLS
    (r"tenant|RLS|BOLA|BFLA|cross-hive|foreign hive|refusal|authz|forged|escalat|inject|XSS|"
     r"secret|leak|another hive|not allowed|gated action", ["S"]),
    # ── Database & Storage
    (r"canonical|tile ==|ledger|truth|cap is not|reconcile|row|record|entry|logbook|inventory|"
     r"photo|upload|file|attach|export|import|history|lineage|audit", ["D"]),
    # ── APIs & Backend Logic
    (r"edge function|contract & failure|provider fallback|orchestrat|webhook|API|invoke|"
     r"AI |assistant|companion|RAG|agent|semantic|voice|brief|generat", ["A"]),
    # ── Availability & Recovery
    (r"degrad|offline|outage|retry|reconnect|backfill|storm|500|recovery|health|incident|"
     r"partition|expiry mid|unavailable|fails|failure|down", ["AV"]),
    # ── Caching & CDN
    (r"cache|CDN|stale|service worker|shell|_headers|precache|revalidat", ["CA"]),
    # ── Error Tracking & Logs
    (r"\blog\b|logs|trace|error tracking|crash|observab|correlat|greppable|diagnos", ["L"]),
    # ── Rate Limiting
    (r"rate.?limit|quota|throttl|abuse|burst|too many|cooldown", ["RL"]),
    # ── Cloud & Compute
    (r"cold start|compute|cron|scheduled|background job|worker process|queue|batch", ["C"]),
    # ── Load Balancing & Scaling
    (r"scal|concurren|throughput|N\+1|at 20 members|at scale|volume|pagination|load more|"
     r"many rows|large hive|grows", ["LB"]),
    # ── CI/CD & Version Control
    (r"the gate actually runs|deploy|release|version|rollout|flag|migration ship", ["CI"]),
    # ── Hosting & Deployment
    (r"prod-only|deployed origin|hosting|redirect|robots|sitemap|canonical URL|domain|DNS|"
     r"public arrival|crawler|SEO|AEO", ["H"]),
    # ── The persona-journey vocabulary. The first pass left 258 rows on the default, and reading them
    # showed the gap was in the RULES, not in the rows: "Worker completes an assigned PM task",
    # "Seller lists a part with credit reservation", "GCash top-up: the money-in loop" all cross real
    # layers that the lens-shaped patterns above never name. These rules speak the way a journey title
    # speaks - in verbs a person performs and nouns a product has.
    (r"\bconvert|conversion|funnel|from search|lands on|arrives", ["H", "F"]),
    (r"\blists?\b|creates?|issues?|submits?|posts?|saves?|writes?|approves?|assigns?|schedules?|"
     r"completes?|logs\b|records?|updates?|edits?|deletes?", ["D", "A"]),
    (r"PM task|spare part|\bpart\b|\bjob\b|listing|order|inquiry|dispute|credit|top-?up|price|"
     r"pricing|payment|money|invoice|escrow|reservation|stock|asset|equipment", ["D"]),
    (r"multi-?hive|switches hives|another hive|hives\b|tenant", ["AU", "S"]),
    (r"notification|digest|alert|e-?mail|reaches the user|inbox|push\b|announce", ["A", "AV"]),
    (r"search|discovery|browse|filter|sort|find\b|query", ["F", "D"]),
    (r"KPI|analytics|report|metric|dashboard|console|chart|score|leaderboard|reputation", ["D", "F"]),
    (r"persona|manager|executive|contractor|supplier|guest|preview|buyer|seller|stakeholder|"
     r"engineer|technician|planner|visitor|new user|returning", ["F"]),
    (r"promise|page:|deep walk|lane\b|surface\b|comprehension|coherence|quality|transparency|"
     r"honesty|trust|safety|verifies|walks the", ["F"]),
    (r"lifecycle|longitudinal|over N|end-to-end|ripple|chain|hand-?off|the return path", ["A", "D"]),
    (r"language|Filipino|Tagalog|translation|i18n|locale", ["F"]),
    # ── The cross-cutting UX sweeps. Reading the second pass's 130 leftovers showed most are
    # frontend-first by nature ("Iconography & affordance recognition", "Print reality") and a
    # handful quietly cross a second layer nobody would guess from the noun alone: a retention
    # policy is Database, a renamed page is Hosting, a consent moment is Security.
    (r"sweep|census|benchmark|reality|hygiene|literacy|recognition|vocabulary|help system|"
     r"findability|iconograph|affordance|print|kiosk|wall-display|screenshot|share culture|"
     r"tremor|gloved|motor|jargon|pull-help|big screen", ["F"]),
    (r"duplicate|cardinality|zero, one|maximum-length|max-length|dates|times|PHT|clock|skew|"
     r"archive|retention|deletion|forget me|compliance|evidence|freshness|normalizer|race\b|"
     r"where old data goes", ["D"]),
    (r"404|renamed|security-header|headers|Turnstile|bot-defense|privacy|consent|sensitive|"
     r"hardening|first-run", ["S", "H"]),
    (r"presence|multi-?tab|who.s really here|real-?time", ["A"]),
]
COMPILED = [(re.compile(p, re.I), ls) for p, ls in RULES]
DEFAULT = ["F"]

# ★THE LLM LAYER IS ADDED TO ROWS THAT ALREADY HAVE LAYERS (Ian, 2026-10-06). The RULES above only fill rows with
# NO layers, and every row has had layers since 2026-09-06 - so the 14th layer could never be counted from them. An
# AI row keeps its own layers and GAINS "LM", the multi-tag shape the field already uses. Measured exclusions, each
# found in the dry count before writing: "clean agent" is a fire-suppression agent; <summary> is an HTML element;
# "ai-quality" in a title is a PAGE name; and public learn/calculator rows (persona anon) describe an AI feature
# without exercising it. Rows of the seeded LX kinds and BRP keep the layer their lens was built for.
LM_RULE = re.compile(r"\bAI\b(?!-quality)|\bassistant\b(?!\s*·)|\bcompanion\b|\bRAG\b|(?<!clean )\bagents?\b|"
                     r"\bsemantic\b|\bvoice\b|\bbrief(ing)?\b|\bgenerat(e|es|ed|ion|ive)\b|"
                     r"(?<!<)\bsummar(y|ies|ise|ize|iser|izer)\b|\bOCR\b|\btranscri\w*|\bembedding|\bLLM\b|\bprompt\b|"
                     r"\bgrounded\b|\bcitations?\b|\bZaniah\b|hallucinat|language model|\bfabricat\w*|"
                     r"\bextract(s|ed|ion)?\b", re.I)


def lm_candidates(rows: list[dict]) -> list[dict]:
    """In-scope, non-LX, non-BRP, non-public rows whose title is about the platform's AI and lack "LM"."""
    return [r for r in rows
            if r.get("status") != "descoped" and (r.get("lx") or {}).get("kind") is None
            and not str(r.get("id", "")).startswith("BRP")
            and (r.get("persona") or "any") != "anon"
            and "LM" not in (r.get("layers") or []) and LM_RULE.search(r.get("title") or "")]


def layers_for(title: str) -> tuple[list[str], bool]:
    """Every layer this journey crosses, and whether the default had to carry it."""
    out: list[str] = []
    for rx, ls in COMPILED:
        if rx.search(title or ""):
            for x in ls:
                if x not in out:
                    out.append(x)
    if not out:
        return list(DEFAULT), True
    return out, False


# ★LAYER HEALTH - the three faces of "weak" (Ian, 2026-10-06: "I have to see those all layers for its percentage,
# then you have to decide which open we have to close first"). A flat row count against a 90-row target said
# nothing: every layer had passed it 7-50x. What differs between layers is (1) how much is CLOSED - product rows
# and public learn/calc rows told apart, because a layer can look weak only because of public pages; (2) the
# FIX-LANDED rate - of the walked product rows, how many recorded a change that landed, i.e. where walking the
# layer keeps finding real defects; and (3) THIN CELLS - signed-in personas holding fewer than FLOOR rows on the
# layer. The close-first SCORE is fix-landed x open product rows: where the product is proven weak AND still open.
_LANDED = re.compile(r"\b(fixed|now (reads|speaks|says|renders|shows|carries)|landed|repaired|rewired|added|"
                     r"removed|rewritten|corrected|closed the gap)\b", re.I)
_CLEAN = re.compile(r"\b(unchanged|no change|needed no|PASS(ES)?\b(?! after)|no defect|nothing to fix|"
                    r"already correct)", re.I)
HEALTH_FLOOR = 12


def _persona(t: dict) -> str:
    return t.get("persona") or (t.get("lx") or {}).get("persona") or "any"


def sublayer_health(rows: list[dict], closed_ids: set[str]) -> dict:
    """{layer: {sub-layer: (rows, closed)}} in NAMES order (Ian, 2026-10-14: "numbers trajectories for each full stack
    architectural layer and sublayers"). The 13 layers' sub-layers come from the SL rows (tools/sublayer_inventory.py),
    LM's ten from its own rows; `closed_ids` is the headline's closed set, so a sub-layer cannot read done while the
    layer above it reads open."""
    try:
        from sublayer_inventory import SUBLAYERS as _SL
        from seed_expansion_wave4 import LM_SUBLAYERS as _LMS
    except Exception:
        _SL, _LMS = {}, {}
    acc: dict = {}
    for t in rows:
        sl, lx = t.get("sl") or {}, t.get("lx") or {}
        if sl.get("kind") == "sublayer":
            key = (sl.get("layer"), sl.get("sublayer"))
        elif lx.get("kind") == "llm":
            key = ("LM", lx.get("sublayer"))
        else:
            continue
        e = acc.setdefault(key, [0, 0])
        e[0] += 1
        e[1] += t["id"] in closed_ids
    out: dict = {}
    for code in list(_SL) + [c for c in NAMES if c not in _SL]:          # the full-stack order F, D, A ... then LM
        order = list(_LMS) if code == "LM" else list((_SL.get(code) or {}))
        subs = sorted((s for (l, s) in acc if l == code), key=lambda s: order.index(s) if s in order else 99)
        if subs:
            out[code] = {s: tuple(acc[(code, s)]) for s in subs}
    return out


def layer_health(rows: list[dict], closed_ids: set[str]) -> list[dict]:
    """Per layer: active, closed, closed %, open product / open public, fix-landed %, thin cells, score.
    `rows` are the IN-SCOPE registry rows; `closed_ids` comes from live_walk_manifest.row_closed, so every
    percentage here agrees with the headline by construction."""
    try:
        from seed_expansion_wave4 import LX_SIGNED_IN as _signed_in
    except Exception:
        _signed_in = []
    out = []
    subs_all = sublayer_health(rows, closed_ids)
    for code, name in NAMES.items():
        act = [t for t in rows if code in (t.get("layers") or [])]
        if not act:
            continue
        open_ = [t for t in act if t["id"] not in closed_ids]
        prod_open = [t for t in open_ if _persona(t) != "anon"]
        walked = [t for t in act if t.get("status") in ("locking", "locked") and _persona(t) != "anon"]
        landed = sum(1 for t in walked if _LANDED.search(t.get("basis") or "")
                     and not _CLEAN.search((t.get("basis") or "")[:220]))
        per = collections.Counter(_persona(t) for t in act)
        thin = [p for p in _signed_in if per.get(p, 0) < HEALTH_FLOOR]
        rate = landed / len(walked) if walked else 0.0
        closed = len(act) - len(open_)
        subs = subs_all.get(code) or {}
        out.append({"code": code, "name": name, "active": len(act), "closed": closed,
                    "subs": len(subs), "subs_closed": sum(1 for n, c in subs.values() if n and n == c),
                    "pct": round(100.0 * closed / len(act), 1), "open_product": len(prod_open),
                    "open_public": len(open_) - len(prod_open), "landed_pct": round(100.0 * rate),
                    "thin": thin, "score": round(rate * len(prod_open), 1)})
    return out


def walk_order(health: list[dict]) -> tuple[list[dict], list[dict]]:
    """Product lanes by close-first score (ties: more open first), then public lanes by size."""
    prod = sorted((h for h in health if h["open_product"]), key=lambda h: (-h["score"], -h["open_product"]))
    pub = sorted((h for h in health if h["open_public"]), key=lambda h: -h["open_public"])
    return prod, pub


def _atomic_write(path: Path, text: str) -> None:
    """Never open(w) the registry directly: a crash mid-write would truncate the SSOT."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with io.open(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    ap.add_argument("--report", action="store_true", help="per-layer totals over the whole registry")
    ap.add_argument("--add-lm", action="store_true",
                    help="2026-10-06: add the LLM layer to existing AI rows (with --dry-run to only count)")
    args = ap.parse_args()

    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = doc["trajectories"]

    if args.add_lm:
        cand = lm_candidates(rows)
        st = collections.Counter(r.get("status") for r in cand)
        terms = collections.Counter(LM_RULE.search(r["title"]).group(0).lower() for r in cand)
        print(f"  LM backfill: {len(cand)} existing AI row(s) gain the LLM layer "
              f"({', '.join(f'{v} {k}' for k, v in st.most_common())})")
        print("  by matched term: " + " · ".join(f"{k} {v}" for k, v in terms.most_common(12)))
        if args.dry_run:
            print("\n  (nothing written)")
            return 0
        for r in cand:
            r["layers"] = list(r.get("layers") or []) + ["LM"]
        _atomic_write(REGISTRY, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        print(f"\n  wrote {REGISTRY.name}")
        return 0

    before_tagged = sum(1 for r in rows if r.get("layers"))
    filled, defaulted = 0, []
    for r in rows:
        if r.get("layers"):
            continue
        ls, used_default = layers_for(r.get("title", ""))
        if used_default:
            defaulted.append(r["id"])
        r["layers"] = ls
        filled += 1

    after_tagged = sum(1 for r in rows if r.get("layers"))
    counts: collections.Counter = collections.Counter()
    for r in rows:
        for x in (r["layers"] if isinstance(r.get("layers"), list) else [r.get("layers")]):
            if x:
                counts[x] += 1

    print(f"  tagged before {before_tagged} -> after {after_tagged}  (of {len(rows)} rows; {filled} filled)")
    if defaulted:
        print(f"  {len(defaulted)} row(s) matched no rule and took the stated default {DEFAULT}: "
              f"{', '.join(defaulted[:8])}{' ...' if len(defaulted) > 8 else ''}")
    print()
    print("  %-4s %-28s %6s" % ("code", "layer", "rows"))
    for code in sorted(NAMES, key=lambda k: -counts.get(k, 0)):
        print("  %-4s %-28s %6d" % (code, NAMES[code], counts.get(code, 0)))

    if args.report:
        # the same table the generated header shows, from the same closed predicate (2026-10-06)
        try:
            from live_walk_manifest import build as _build, row_closed as _rc
            _m = _build()
            _closed = {r["id"] for r in _m["rows"] if _rc(r)}
            _scoped = [r for r in rows if r.get("status") != "descoped"]
            _h = layer_health(_scoped, _closed)
            print("\n  LAYER HEALTH (weakest closure first)")
            print(f"  {'layer':<34} {'closed':>14} {'open prod':>9} {'open pub':>8} {'landed':>6} {'thin':>4}")
            for h in sorted(_h, key=lambda x: x["pct"]):
                print(f"  {h['code'] + ' ' + h['name']:<34} {h['closed']:>5}/{h['active']:<5} {h['pct']:5.1f}% "
                      f"{h['open_product']:>6} {h['open_public']:>8} {h['landed_pct']:>5}% {len(h['thin']):>4}")
            _p, _u = walk_order(_h)
            print("  WALK ORDER: " + " -> ".join(f"{h['code']} {h['open_product']}" for h in _p)
                  + (" | public: " + " -> ".join(f"{h['code']} {h['open_public']}" for h in _u) if _u else ""))
        except Exception as e:                       # the report must still print its counts
            print(f"  (layer health unavailable: {e!r})")
    if args.dry_run or args.report:
        print("\n  (nothing written)")
        return 0

    doc["trajectories"] = rows
    _atomic_write(REGISTRY, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    print(f"\n  wrote {REGISTRY.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

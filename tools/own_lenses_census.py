#!/usr/bin/env python3
"""own_lenses_census.py - what I add from my own reading of the registry, measured (Wave OWN, 2026-10-26).

Ian, 2026-10-26: "from your understanding of all my number trajectories, you have to add more necessary and appropriate
number of trajectories from your own." Eleven lenses the registry's shape suggested it under-covers were measured as
population (from the repo) x what each unit owes - rows already there; nine held and are here, two did not (money
idempotency: 236 rows already; the RLS matrix: 2,541 rows and the cube's I x D/S x persona), and three others were
found covered elsewhere (the hive's day: SL C1/C3; reduced-motion: a rubric dim; notification kinds: no population).

EVERY LENS BELOW IS A FUNCTION THAT RETURNS ITS EMPTY CELLS - {lens, unit, ask, page, persona, layer, ufai, detail} -
measured from the repo (migrations, CSP, edge functions, the pages) and the live registry (a cell is empty when no
non-descoped row's text names the unit AND the ask). seed_expansion_wave4.py --add-own imports this module; one place
decides the size (the BRP rule).

    python tools/own_lenses_census.py           # the table
    python tools/own_lenses_census.py --json    # the machine population (what the seeder reads)
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "trajectory_registry.json"
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))


def _force_utf8_stdout() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _rd(p) -> str:
    return Path(p).read_text(encoding="utf-8", errors="ignore")


def _target(r: dict):
    p = r.get("pages") or []
    return p[-1] if p else None


class Reg:
    """The registry's text per row, for the coverage test (a row covers a cell when its text names unit AND ask)."""

    def __init__(self) -> None:
        rows = [t for t in json.loads(REGISTRY.read_text(encoding="utf-8"))["trajectories"] if t.get("status") != "descoped"]
        self.rows = [(" ".join(str(t.get(k, "")) for k in ("title", "story", "basis", "note", "wave")), _target(t)) for t in rows]

    def covers(self, unit_rx: str, ask_rx: str, page: str | None = None) -> bool:
        u, a = re.compile(unit_rx, re.I), re.compile(ask_rx, re.I)
        return any(u.search(t) and a.search(t) and (page is None or p == page) for t, p in self.rows)

    def on_page(self, ask_rx: str, page: str) -> bool:
        a = re.compile(ask_rx, re.I)
        return any(p == page and a.search(t) for t, p in self.rows)


def _classes() -> dict:
    import sublayer_inventory as si
    return si.page_classes()


# ─── populations ──────────────────────────────────────────────────────────────────────────────────────────────────

def live_cron_jobs() -> list[str]:
    jobs, unsch = set(), set()
    for f in glob.glob(str(ROOT / "supabase" / "migrations" / "*.sql")):
        s = _rd(f)
        jobs |= set(re.findall(r"cron\.schedule\(\s*'([^']+)'", s))
        unsch |= set(re.findall(r"cron\.unschedule\(\s*'([^']+)'", s))
    return sorted(jobs - unsch)


def external_hosts() -> list[str]:
    hosts: set[str] = set()
    for f in ("index.html", "_headers", "vercel.json", "netlify.toml"):
        p = ROOT / f
        if p.exists():
            for m in re.finditer(r"(connect-src|script-src|font-src|img-src|frame-src|style-src)([^;\"]+)", _rd(p)):
                hosts |= set(re.findall(r"https?://([a-z0-9.*-]+\.[a-z]{2,})", m.group(2)))
    for f in glob.glob(str(ROOT / "supabase" / "functions" / "**" / "*.ts"), recursive=True):
        hosts |= set(re.findall(r"https?://([a-z0-9.-]+\.[a-z]{2,})/", _rd(f)))
    hosts = {h for h in hosts if not re.search(r"localhost|127\.0\.0\.1|workhiveph|supabase\.co$|example\.|schema\.org|w3\.org", h)}
    return sorted(hosts) + ["supabase (the project's database, auth, storage, realtime, edge)", "the host (Vercel: static pages, headers, deployment storage)"]


def ai_functions() -> list[str]:
    out = []
    for f in glob.glob(str(ROOT / "supabase" / "functions" / "*" / "index.ts")):
        if re.search(r"generativelanguage|anthropic|openai|model-chain|modelChain|callModel|embedding-chain|gemini|claude", _rd(f), re.I):
            out.append(Path(f).parent.name)
    return sorted(out)


def search_pages(classes: dict) -> list[str]:
    return [p for p in classes["production"] + classes["founder"]
            if (ROOT / p).exists() and re.search(r'type="search"|id="[^"]*search[^"]*"|placeholder="[^"]*[Ss]earch', _rd(ROOT / p))]


# ─── the lenses ───────────────────────────────────────────────────────────────────────────────────────────────────

def lens_scheduled_work(reg: Reg) -> list[dict]:
    asks = [("fires and its effect is visible", r"fires|ran on (time|schedule)|effect (is )?visible|cron.history"),
            ("a double fire leaves one effect", r"idempoten|double fire|twice"),
            ("its failure is surfaced", r"failure (is )?surfaced|cron.history|founder console|alert")]
    out = []
    for job in live_cron_jobs():
        for ask, rx in asks:
            if not reg.covers(re.escape(job), rx):
                out.append({"lens": "scheduled work", "unit": job, "ask": ask, "page": "founder-console.html", "persona": "oversight",
                            "layer": "RL", "ufai": ["F", "I"],
                            "detail": f"pg_cron job {job}: {ask} - 13 of the 18 live jobs had no row naming them on 2026-10-26"})
    return out


def lens_dependencies(reg: Reg) -> list[dict]:
    states = [("down", r"\bdown\b|refus|unreachable|ECONN|offline"), ("slow", r"\bslow\b|timeout|latency"),
              ("quota or 429", r"\b429\b|quota|rate.?limit|free.?tier"), ("changed API", r"changed|deprecat|new version|breaking")]
    out = []
    for h in external_hosts():
        key = h.split(" ")[0]
        unit_rx = re.escape(key.split(".")[-2]) if "." in key else re.escape(key)
        for st, rx in states:
            if not reg.covers(unit_rx, rx):
                out.append({"lens": "dependency", "unit": h, "ask": st, "page": "index.html", "persona": "oversight", "layer": "AV",
                            "ufai": ["A", "I"],
                            "detail": f"{h} {st}: what the person meets (an honest sentence, never a dev command) and what the founder "
                                      f"sees (headroom before, the incident after)"})
    return out


def lens_ai_failure_modes(reg: Reg) -> list[dict]:
    modes = [("model-chain fallback", r"fallback|next model|model chain|falls? (back|to)"),
             ("cost cap", r"cost cap|budget|spend|token cap|daily cap"),
             ("prompt-injection guard", r"prompt.?injection|ignore previous|jailbreak"),
             ("stale deploy cache", r"deno cache|stale (function|deploy)|served yesterday"),
             ("provenance shown", r"provenance|AI6|written by AI|ai_write")]
    out = []
    for fn in ai_functions():
        for mode, rx in modes:
            if not reg.covers(re.escape(fn), rx):
                out.append({"lens": "AI failure mode", "unit": fn, "ask": mode, "page": "assistant.html", "persona": "worker",
                            "layer": "LM", "ufai": ["F", "A"],
                            "detail": f"supabase/functions/{fn}: {mode} - proven live against the function, as the person who meets it"})
    return out


def lens_webkit_primary_action(reg: Reg, classes: dict) -> list[dict]:
    rx = r"(webkit|safari|\bios\b).{0,120}(primary action|submit|save|create|post|compute)|(primary action|submit|save|create|post|compute).{0,120}(webkit|safari|\bios\b)"
    return [{"lens": "WebKit primary action", "unit": p, "ask": "the primary action completes in WebKit at 390", "page": p,
             "persona": None, "layer": "F", "ufai": ["F", "A"],
             "detail": f"{p}: the page's primary action completes in Playwright WebKit at 390 (the engine that bit Ian); SL AV1/CI2 prove only the start-up"}
            for p in classes["production"] if not reg.on_page(rx, p)]


def lens_two_devices(reg: Reg, classes: dict) -> list[dict]:
    rx = r"second device|two devices|another tab|other tab|both devices|phone and desktop at once|same account on"
    return [{"lens": "two devices, one account", "unit": p, "ask": "a write on the phone appears on the desktop", "page": p,
             "persona": None, "layer": "RL", "ufai": ["F", "A"],
             "detail": f"{p}: one account open at 390 and 1280 at once - a write on one appears on the other within the realtime budget or by an honest refresh, with no conflict and no lost draft"}
            for p in classes["production"] if not reg.on_page(rx, p)]


def lens_back(reg: Reg, classes: dict) -> list[dict]:
    rx = r"browser back|history\.back|back button|popstate|Back lands"
    out = []
    for p in classes["production"]:
        if not reg.on_page(rx, p):
            out.append({"lens": "browser Back", "unit": p, "ask": "one Back leaves the page from any state", "page": p, "persona": None,
                        "layer": "F", "ufai": ["U", "A"],
                        "detail": f"{p}: one press of the browser's Back leaves the page from any state - a sheet or modal closes first and never traps"})
    for p in classes["public"]:
        if not reg.on_page(rx, p):
            out.append({"lens": "browser Back", "unit": p, "ask": "anchor jumps do not pollute history", "page": p, "persona": "anon",
                        "layer": "F", "ufai": ["U", "A"],
                        "detail": f"{p}: after the TOC / FAQ anchor jumps, one Back leaves the page - the reader is not trapped in the article by its own anchors"})
    return out


def lens_search(reg: Reg, classes: dict) -> list[dict]:
    asks = [("an empty query", r"empty (query|search)|blank search"), ("no results said honestly", r"no results|nothing (found|matched)"),
            ("special characters", r"special char|comma|ilike|\b400\b"), ("many results", r"many results|row.?cap|pagination|1000 results")]
    out = []
    for p in search_pages(classes):
        for ask, rx in asks:
            if not reg.on_page(rx, p):
                out.append({"lens": "in-app search", "unit": p, "ask": ask, "page": p, "persona": None, "layer": "F", "ufai": ["F", "U"],
                            "detail": f"{p}: the search box survives {ask}"})
    return out


def lens_text_and_colour_modes(reg: Reg, classes: dict) -> list[dict]:
    modes = [("text grows (200% zoom + text spacing)", r"zoom(ed)? (to )?200|200% zoom|text.?spacing|1\.4\.12|1\.4\.4\b"),
             ("forced colours", r"forced.?colors|high.?contrast mode|prefers-contrast")]
    out = []
    for p in classes["production"] + classes["public"]:
        for ask, rx in modes:
            if not reg.on_page(rx, p):
                out.append({"lens": "text grows / colours taken away", "unit": p, "ask": ask, "page": p, "persona": "assistive-tech",
                            "layer": "F", "ufai": ["U", "A"],
                            "detail": f"{p}: {ask} - nothing clips, no horizontal scroll, every control stays visible and reachable (WCAG 1.4.4 / 1.4.12 / forced-colors)"})
    return out


def lens_low_end_cpu(reg: Reg, classes: dict) -> list[dict]:
    rx = r"\bcpu\b|throttl|4x slow|low.?end"
    return [{"lens": "low-end phone", "unit": p, "ask": "the primary action's INP under 4x CPU throttle at 390", "page": p, "persona": None,
             "layer": "LB", "ufai": ["A"],
             "detail": f"{p}: the primary action's INP stays within budget at 390 with the CPU throttled 4x (chrome-devtools MCP)"}
            for p in classes["production"] if not reg.on_page(rx, p)]


def census() -> dict:
    reg = Reg()
    classes = _classes()
    lenses = [lens_scheduled_work(reg), lens_dependencies(reg), lens_ai_failure_modes(reg), lens_webkit_primary_action(reg, classes),
              lens_two_devices(reg, classes), lens_back(reg, classes), lens_search(reg, classes), lens_text_and_colour_modes(reg, classes),
              lens_low_end_cpu(reg, classes)]
    cells = [c for group in lenses for c in group]
    pop = {"live cron jobs": len(live_cron_jobs()), "external dependencies": len(external_hosts()), "AI functions": len(ai_functions()),
           "search pages": len(search_pages(classes)), "production pages": len(classes["production"]), "public pages": len(classes["public"])}
    return {"population": pop, "cells": cells, "by_lens": dict(Counter(c["lens"] for c in cells)), "total": len(cells)}


def main() -> int:
    _force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    c = census()
    if a.json:
        print(json.dumps(c, indent=1, ensure_ascii=False))
        return 0
    print("\nOWN - what I add from my own reading, measured (population x what each unit owes - rows already there)")
    print("=" * 96)
    print("  population: " + " · ".join(f"{k} {v}" for k, v in c["population"].items()))
    for lens, n in c["by_lens"].items():
        print(f"    {lens:<34} {n:>5}")
    print(f"  = {c['total']} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())

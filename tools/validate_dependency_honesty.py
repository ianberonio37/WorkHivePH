#!/usr/bin/env python3
"""validate_dependency_honesty.py - every dependency can fail, and the person is told honestly (OWN dependency lens, 2026-10-26).

Each row of the lens is a (host, failure) pair - down, slow, quota or 429, changed API - and owes two halves: what the
PERSON meets (an honest sentence or a working fallback, never a dev message or a frozen page) and what the FOUNDER sees
(the failure recorded as client_errors context 'dependency:<host>:<kind>', grouped on the operator console by
founder_client_errors). What the walks found and this holds:

  calc service (Render)  the PDF button sat silent up to 45 s; a 200 that was not a PDF downloaded as a broken file; a
                         diagram answer without svg went into the renderer; production's /pdf answers 503 ("weasyprint not
                         available") so every PDF people download is the device-made fallback - now said
  map tiles              a refused / slow / unreadable style left a blank grey box and no record
  breach-check API       a check that could not run read exactly like "not breached", to the person and to no one else;
                         a visitor's report was refused by the anonymous insert policy (20261026000013 admits it)
  CDN libraries          Chart.js, html2pdf and Mermaid were synchronous: a slow CDN held the whole page (and the
                         calculator) unrendered; Mermaid's inline init threw when the CDN did not deliver it
  web font               a refused font file: system font (readable, no shift) and a record
  client_errors          read by nothing: founder_client_errors (20261026000012) and the console panel
  model providers        a slow provider was asked once PER MODEL (three Google models, 75 s) and the walk had no budget, so
                         the answer arrived after the request had failed for the person; ai_cost_log.providers_tried was read
                         by nothing (a dead Voyage key, a four-day-dead embedder) - founder_model_providers (20261026000015)

STATIC (teeth: the tree at 1045f447 fails every fact) and LIVE (local DB, rolled back: the read is admin-only; a visitor's
dependency row is admitted, a long non-dependency context still refused).

    python tools/validate_dependency_honesty.py
    python tools/validate_dependency_honesty.py --self-test
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["engineering-design.js", "engineering-design.html", "wh-map.js", "marketplace.html", "index.html", "utils.js",
         "skillmatrix.html", "resume.html", "founder-console.html", "supabase/functions/_shared/ai-chain.ts"]

FACTS = {
    "calc PDF: the button locks and says it is working, then why": lambda f: "The PDF service is waking up" in f["engineering-design.js"]
        and 'id="pdf-status"' in f["engineering-design.html"],
    "calc PDF: a 200 that is not a PDF is refused": lambda f: "includes('application/pdf')" in f["engineering-design.js"],
    "calc diagram: an answer without svg is refused": lambda f: "Diagram API answered no svg" in f["engineering-design.js"],
    "calc: the fallback is said and the failure recorded": lambda f: "made on this device" in f["engineering-design.js"]
        and "whDependency('engineering-calc-api.onrender.com'" in f["engineering-design.js"],
    "map: a failed or slow style says so and is recorded": lambda f: "map.on('error'" in f["wh-map.js"] and "taking longer than usual" in f["wh-map.js"]
        and "whDependency(HOST" in f["wh-map.js"] and "failText" in f["marketplace.html"],
    "breach check: an unchecked password is said, never read as clean": lambda f: "BREACH_UNCHECKED_NOTE" in f["index.html"]
        and "changed API" in f["index.html"] and "if (_breachUnchecked) showToast(BREACH_UNCHECKED_NOTE)" in f["index.html"],
    "utils: whDependency + whWatchLibrary + the font listener": lambda f: "function whDependency(" in f["utils.js"]
        and "function whWatchLibrary(" in f["utils.js"] and "addEventListener('loadingerror'" in f["utils.js"],
    "CDN libraries load async, never blocking the page": lambda f: re.search(r'<script async src="https://cdn\.jsdelivr\.net/npm/chart\.js', f["skillmatrix.html"]) is not None
        and re.search(r'<script async src="https://cdn\.jsdelivr\.net/npm/html2pdf', f["resume.html"]) is not None
        and re.search(r'<script async src="https://cdnjs\.cloudflare\.com/ajax/libs/html2pdf', f["engineering-design.html"]) is not None
        and re.search(r'<script async src="https://cdn\.jsdelivr\.net/npm/mermaid', f["engineering-design.html"]) is not None,
    "skills chart redraws when a late library lands": lambda f: "renderRadarChart._waiting" in f["skillmatrix.html"],
    "the console groups what failed on people's screens": lambda f: "rpc('founder_client_errors'" in f["founder-console.html"]
        and "A service we depend on" in f["founder-console.html"],
    # the model providers (server side): a slow provider costs one wait, the walk has a budget, the founder sees which failed
    "AI chain: the whole walk has a budget under the gateway's wait": lambda f: "WALK_BUDGET_MS" in f["supabase/functions/_shared/ai-chain.ts"]
        and "AbortSignal.timeout(Math.min(25000, _left))" in f["supabase/functions/_shared/ai-chain.ts"]
        and "chain/walk=budget" in f["supabase/functions/_shared/ai-chain.ts"],
    "AI chain: a provider that timed out is dead for the rest of the call": lambda f: re.search(
        r'tried\.push\(`\$\{entry\.provider\}/\$\{entry\.model\}=\$\{/timeout\|abort/i[\s\S]{0,400}deadThisCall\.add\(entry\.provider\)',
        f["supabase/functions/_shared/ai-chain.ts"]) is not None,
    "the console shows which model provider is failing": lambda f: "rpc('founder_model_providers'" in f["founder-console.html"],
}


def findings(files: dict) -> list[str]:
    out = []
    for name, ok in FACTS.items():
        try:
            if not ok(files):
                out.append(name)
        except Exception:
            out.append(name)
    return out


def read_tree(rev: str | None) -> dict:
    if rev is None:
        return {n: (ROOT / n).read_text(encoding="utf-8", errors="replace") for n in FILES}
    return {n: subprocess.run(["git", "show", f"{rev}:{n}"], cwd=ROOT, capture_output=True).stdout.decode("utf-8", "replace")
            for n in FILES}


def live_findings() -> list[str]:
    sql = """
begin;
select set_config('request.jwt.claims', '{"sub":"00000000-0000-0000-0000-0000000000ab","role":"authenticated"}', true) is not null;
set local role authenticated;
select count(*) from public.founder_client_errors(7);
rollback;
"""
    r = subprocess.run(["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-At"], input=sql,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    if "could not connect" in (r.stderr or "") or "No such container" in (r.stderr or ""):
        return ["SKIP: the local database could not be read"]
    bad = []
    if "Only a platform admin" not in (r.stderr or ""):
        bad.append("founder_client_errors answered someone who is not a platform admin")
    sql2 = """
begin;
set local role anon;
insert into public.client_errors (context, message, page) values ('dependency:api.pwnedpasswords.com:quota or 429', 'probe', '/index.html');
rollback;
"""
    r2 = subprocess.run(["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-At", "-v", "ON_ERROR_STOP=1"], input=sql2,
                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    if r2.returncode != 0:
        bad.append("a visitor's dependency report is refused: " + (r2.stderr or "")[:120])
    sql3 = """
begin;
set local role anon;
insert into public.client_errors (context, message) values ('some-other-context-that-is-much-longer-than-forty-chars', 'probe');
rollback;
"""
    r3 = subprocess.run(["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-At", "-v", "ON_ERROR_STOP=1"], input=sql3,
                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    if r3.returncode == 0:
        bad.append("the anonymous policy now admits any context, not only dependency:*")
    return bad


def self_test() -> int:
    cur = findings(read_tree(None))
    red = findings(read_tree("1045f447"))
    print(f"  {'PASS' if not cur else 'FAIL'} the tree holds every fact {cur or ''}")
    print(f"  {'PASS' if len(red) == len(FACTS) else 'FAIL'} teeth: the tree at 1045f447 fails {len(red)}/{len(FACTS)}")
    ok = not cur and len(red) == len(FACTS)
    print(("PASS" if ok else "FAIL") + " dependency-honesty self-test")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    print("dependency-honesty (OWN): a dependency can fail and the person is told honestly; the founder sees it")
    bad = findings(read_tree(None))
    live = live_findings()
    skip = [x for x in live if x.startswith("SKIP")]
    bad += [x for x in live if not x.startswith("SKIP")]
    print(f"  {len(FACTS) - len([b for b in bad if b in FACTS])}/{len(FACTS)} static facts hold" + (f"; {skip[0]}" if skip else ""))
    for b in bad:
        print(f"  - {b}")
    print("PASS" if not bad else "FAIL")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())

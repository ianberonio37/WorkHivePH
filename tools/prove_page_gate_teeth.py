#!/usr/bin/env python3
"""prove_page_gate_teeth.py - SL sub-layer CI1 (2026-10-15): "The platform must have a registered gate that reddens
when this page's contract breaks."

A gate "holds" a page only if two things are true of THAT page: the gate reads it (its roster includes the page), and
the gate's detector fires when the page breaks. A gate that reads every page but whose check is blind to one page's
shape holds nothing there. So this prover breaks each page - in a temporary copy, never the file itself - and runs
the registered gates' own detectors on the copy:

  csp-covers-what-ships   the page loads a script from an origin its own policy does not name (an external
                          <script src="https://unlisted-origin.invalid/...">): the gate's audit(), on the page's code
                          with that copy in place and against the policy vercel.json resolves for the page's path
                          (serve_vercel_headers.headers_for - the one matcher), must report it
  scripts-parse           the page carries an inline script that does not parse: the gate's own scriptProblems()
                          (tools/validate_scripts_parse.mjs) must report it

and first that both read the page CLEAN today (a detector that always fires proves nothing either). A page is held when
both bite on its breach and neither fires on the page as it is.

  python tools/prove_page_gate_teeth.py [--page a.html,...] [--json .tmp/page_gate_teeth_results.json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_csp_profiles import code_closure  # noqa: E402
from serve_vercel_headers import headers_for, load_rules  # noqa: E402
from validate_csp_covers_what_ships import audit  # noqa: E402

UNLISTED = "unlisted-origin.invalid"
BREACH_SCRIPT = f'<script src="https://{UNLISTED}/breach.js"></script>'
BREACH_PARSE = "<script>if (</script>"

PARSE_JS = r"""
import { scriptProblems } from './tools/validate_scripts_parse.mjs';
let raw = ''; process.stdin.on('data', (c) => { raw += c; });
process.stdin.on('end', () => {
  const docs = JSON.parse(raw);
  const out = docs.map((d) => scriptProblems(d.name, d.src, true).length);
  process.stdout.write(JSON.stringify(out));
});
"""


def _insert(html: str, snippet: str) -> str:
    i = html.lower().find("</head>")
    return html[:i] + snippet + html[i:] if i >= 0 else snippet + html


def parse_counts(docs: list[dict]) -> list[int]:
    r = subprocess.run(["node", "--input-type=module", "-e", PARSE_JS], cwd=ROOT, input=json.dumps(docs),
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise SystemExit(f"the scripts-parse detector could not run: {r.stderr[:300]}")
    return json.loads(r.stdout)


def roster() -> dict[str, str]:
    reg = json.loads((ROOT / "trajectory_registry.json").read_text(encoding="utf-8"))
    return {t["sl"]["page"]: t.get("persona") for t in reg["trajectories"]
            if (t.get("sl") or {}).get("sublayer") == "CI1" and t.get("status") != "descoped"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page")
    ap.add_argument("--json", default=str(ROOT / ".tmp" / "page_gate_teeth_results.json"))
    a = ap.parse_args()
    cast = roster()
    pages = a.page.split(",") if a.page else sorted(cast)
    rules = load_rules(ROOT)
    docs, rows = [], []
    with tempfile.TemporaryDirectory() as d:
        for page in pages:
            html = (ROOT / page).read_text(encoding="utf-8", errors="replace")
            files = [str(f) for f in code_closure(page)]
            hdr = headers_for("/" + page, rules)
            policy = "\n".join(f"{k}: {v}" for k, v in hdr.items() if k.lower() in ("content-security-policy", "permissions-policy"))
            clean = [p for p in audit(files[:1], policy)[0] if UNLISTED in p]
            tmp = Path(d) / (page.replace("/", "__"))
            tmp.write_text(_insert(html, BREACH_SCRIPT), encoding="utf-8")
            bitten = [p for p in audit([str(tmp)], policy)[0] if UNLISTED in p]
            rows.append({"page": page, "cast": cast.get(page), "covers_clean": not clean, "covers_bites": bool(bitten),
                         "covers_said": (bitten[0] if bitten else "")[:200]})
            docs.append({"name": page, "src": html})
            docs.append({"name": page + " (breached)", "src": _insert(html, BREACH_PARSE)})
    counts = parse_counts(docs)
    results, bad = [], 0
    for i, r in enumerate(rows):
        r["parse_clean"], r["parse_bites"] = counts[2 * i] == 0, counts[2 * i + 1] > counts[2 * i]
        problems = []
        if not r["covers_clean"]:
            problems.append("csp-covers-what-ships already fires on the page as it is")
        if not r["covers_bites"]:
            problems.append("csp-covers-what-ships did NOT redden on a script from an origin the page's policy does not name")
        if not r["parse_clean"]:
            problems.append("scripts-parse already fires on the page as it is")
        if not r["parse_bites"]:
            problems.append("scripts-parse did NOT redden on an inline script that does not parse")
        r.update({"engine": "static", "condition": "breach", "problems": problems, "ok": not problems,
                  "gates": ["csp-covers-what-ships", "scripts-parse"]})
        bad += 0 if r["ok"] else 1
        results.append(r)
        print(f"  {'ok  ' if r['ok'] else 'FAIL'} {r['page']:<56} covers {'bites' if r['covers_bites'] else 'BLIND'}, parse {'bites' if r['parse_bites'] else 'BLIND'}"
              + ("" if r["ok"] else "\n         " + "\n         ".join(problems)))
    out = Path(a.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    teeth = {"bit": bad == 0, "pages": len(results), "breaches": [BREACH_SCRIPT, BREACH_PARSE]}
    out.write_text(json.dumps({"generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "sublayer": "CI1", "pages": len(results),
                               "failed": bad, "teeth": teeth, "results": results}, indent=1), encoding="utf-8")
    print(f"\n{'FAIL' if bad else 'PASS'} page-gate-teeth - on {len(results) - bad}/{len(results)} page(s) both registered gates "
          f"read the page clean and redden on its breach -> {out}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

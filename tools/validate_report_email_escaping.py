#!/usr/bin/env python3
"""validate_report_email_escaping.py — Analytics Engine arc (I3/I6) gate: send-report-email HTML-injection.

THE RISK: `send-report-email` builds a WorkHive-branded HTML email from client-supplied `reports[].type`
+ `reports[].summary` and a stored `hiveName`, then relays it to an attacker-chosen `recipient_email`.
`r.summary` was escaped, but the sibling sinks were NOT: `r.type` (→ `meta.label` on the unknown-type
fallback) is fully client-controlled, and `hiveName` is stored DB text. An unescaped sink = HTML/link
injection (phishing) in an authenticated, branded email — the classic "escaped one field, missed the
sibling" bug.

THE CONTROL: `buildEmailHtml` routes EVERY dynamic sink through `esc()` (summary, meta.label, hiveName,
sentAt) before interpolation.

This validator does NOT just grep — it EXTRACTS the real `esc` + `buildEmailHtml` from the edge fn,
strips TS types, and EXECUTES `buildEmailHtml` (via node) with XSS payloads injected into hiveName /
r.type / r.summary, asserting no live tag/handler survives. Running the real code on adversarial input
is a live behavioral proof.

Run:  python tools/validate_report_email_escaping.py
Self-test: --self-test (a deliberately-unescaped label sink must FAIL → proves teeth)
Skills: security (XSS/output-encoding), ai-engineer/notifications (email relay), analytics-engineer (report send).
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FN = ROOT / "supabase" / "functions" / "send-report-email" / "index.ts"
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"
SELF_TEST = "--self-test" in sys.argv[1:]

PAYLOADS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "</p><svg/onload=alert(1)>",
    '"><iframe src=javascript:alert(1)></iframe>',
]


def extract_fn(src: str, name: str) -> str | None:
    """Pull `function <name>(...) { ... }` out of the source with balanced braces.

    NB: the parameter list can itself contain a `{` (a TS generic like `Array<{...}>`),
    so we FIRST balance-match the parens to skip the whole signature, THEN find the body
    brace — starting the brace scan at the first `{` would grab the generic's brace.
    """
    m = re.search(r"function\s+" + re.escape(name) + r"\s*\(", src)
    if not m:
        return None
    # 1) balance the param-list parens, starting at the '(' the regex matched.
    p = src.index("(", m.start()); pdepth = 0; sig_end = None
    for k in range(p, len(src)):
        if src[k] == "(": pdepth += 1
        elif src[k] == ")":
            pdepth -= 1
            if pdepth == 0:
                sig_end = k + 1
                break
    if sig_end is None:
        return None
    # 2) the body's opening brace is the first '{' AFTER the param list (past any return type).
    i = src.index("{", sig_end); depth = 0
    for j in range(i, len(src)):
        if src[j] == "{": depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[m.start():j + 1]
    return None


def strip_ts(code: str) -> str:
    """Remove the (few, known) TS type annotations so node can run the function."""
    code = re.sub(r":\s*Array<[^>]*>", "", code)          # `reports: Array<{...}>` param type (whole annotation)
    code = code.replace(": unknown", "").replace(": string", "")
    return code


def run(esc_src: str, build_src: str) -> tuple[bool, str]:
    harness = f"""
{strip_ts(esc_src)}
const REPORT_META = {{}};   // force the unknown-type fallback so meta.label === r.type (the client-controlled sink)
{strip_ts(build_src)}
const payloads = {json.dumps(PAYLOADS)};
// The static template legitimately contains <meta>/<div>/<h1>/<p>/<a>/<body>/<html>/<title>/<head> only —
// NONE of script|iframe|svg|img|object|embed. A dangerous handler (onerror=) is only exploitable INSIDE a
// RAW tag; escape-first turns the injected `<` into `&lt;`, so a surviving RAW tag is the true leak signal
// (an `onerror=` sitting in escaped `&lt;img …&gt;` text is harmless literal, not a match — same discipline
// as validate_companion_output_escaping).
const LEAK = /<\\s*\\/?\\s*(script|iframe|svg|img|object|embed|on\\w+)[\\s/>]/i;
let bad = [];
for (const p of payloads) {{
  const html = buildEmailHtml(p /*hiveName*/, [{{ type: p, summary: p }}], p /*sentAt*/);
  if (LEAK.test(html)) bad.push({{ payload: p.slice(0,40) }});
}}
console.log(JSON.stringify({{ ok: bad.length === 0, bad }}));
"""
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8", dir=ROOT) as f:
        f.write(harness); path = f.name
    try:
        p = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=30)
        out = (p.stdout or "").strip().splitlines()[-1] if p.stdout.strip() else (p.stderr or "")[:300]
        d = json.loads(out)
        return bool(d.get("ok")), str(d.get("bad"))
    except Exception as e:
        return False, f"{type(e).__name__}: {e} :: {(p.stderr[:200] if 'p' in dir() else '')}"
    finally:
        try: Path(path).unlink()
        except Exception: pass


def main() -> int:
    print(f"\n{'='*64}\n  Analytics arc I3/I6 — send-report-email HTML-injection\n{'='*64}")
    if not FN.exists():
        print(f"{RED}  FAIL  {FN} not found{RST}"); return 1
    src = FN.read_text(encoding="utf-8", errors="replace")
    esc_src = extract_fn(src, "esc")
    build_src = extract_fn(src, "buildEmailHtml")
    if not esc_src or not build_src:
        print(f"{RED}  FAIL  esc()/buildEmailHtml() not found in send-report-email/index.ts{RST}"); return 1

    if SELF_TEST:
        # A build fn that interpolates the raw r.type label must be caught.
        broken = build_src.replace("${safeLabel}", "${meta.label}")
        ok_b, _ = run(esc_src, broken)
        print(f"  self-test: an UNESCAPED label sink is caught = {not ok_b} "
              f"({GREEN+'teeth OK'+RST if not ok_b else RED+'NO TEETH'+RST})")

    ok, detail = run(esc_src, build_src)
    print(f"  {GREEN+'PASS'+RST if ok else RED+'FAIL'+RST}  LIVE: buildEmailHtml escapes {len(PAYLOADS)} "
          f"XSS payloads across hiveName / r.type / r.summary (no live tag/handler survives)")
    if not ok:
        print(f"  {RED}leak detail: {detail[:300]}{RST}")
    print("-" * 64)
    print(f"{(GREEN if ok else RED)}  RESULT: {'GREEN — report email escapes all dynamic sinks.' if ok else 'RED — an unescaped email sink is an HTML/link-injection vector.'}{RST}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

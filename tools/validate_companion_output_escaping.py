#!/usr/bin/env python3
"""validate_companion_output_escaping.py — Arc H H4/I gate: improper-output-handling (OWASP LLM05).

THE RISK: an LLM reply is UNTRUSTED output. If the companion rendered it via innerHTML without escaping,
a model that emits `<script>` / `<img onerror=…>` (whether jailbroken, prompt-injected, or echoing a
malicious knowledge-base entry) becomes a stored-XSS vector in the operator's browser.

THE CONTROL: companion-launcher.js `renderMarkdown` is ESCAPE-FIRST — it replaces & < > to entities BEFORE
applying any markdown→HTML formatting, so model-supplied angle brackets can never open a real tag.

This validator does NOT just grep for the property — it EXECUTES the actual `renderMarkdown` from
companion-launcher.js on real XSS payloads (via node) and asserts the output is escaped (no live `<script>`
or `onerror=` tag survives). Running the real code on an adversarial input is a live behavioral proof.

Run:  python tools/validate_companion_output_escaping.py
Self-test: --self-test (a deliberately-unescaped renderer must FAIL → proves teeth)
Skills: security (LLM05 output handling, XSS), frontend (escape-first render), ai-engineer (untrusted LLM output).
"""
from __future__ import annotations
import re
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"
SELF_TEST = "--self-test" in sys.argv[1:]

PAYLOADS = [
    "<script>alert(document.cookie)</script>",
    "<img src=x onerror=alert(1)>",
    "Here is your report **bold** and <iframe src=javascript:alert(1)></iframe>",
    "</div><svg/onload=alert(1)>",
]


def extract_render_markdown(src: str) -> str | None:
    """Pull the `function renderMarkdown(text) { ... }` body out of companion-launcher.js (balanced braces)."""
    m = re.search(r"function\s+renderMarkdown\s*\(([^)]*)\)\s*\{", src)
    if not m:
        return None
    i = src.index("{", m.start()); depth = 0
    for j in range(i, len(src)):
        if src[j] == "{": depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[m.start():j + 1]
    return None


def run(fn_src: str) -> tuple[bool, str]:
    """Execute the extracted renderMarkdown on the payloads via node; return (all_escaped, detail)."""
    harness = fn_src + "\n" + r"""
const tests = %s;
let bad = [];
for (const t of tests) {
  let out;
  try { out = renderMarkdown(t); } catch (e) { out = "THREW:" + e.message; }
  // A leak = a RAW dangerous tag survived. Escape-first turns user `<` into `&lt;`, so any live
  // `<script|iframe|svg|img|...>` here means escaping FAILED. The renderer's OWN markdown output
  // (<strong>/<em>/<code>) is intentional + safe and never one of these tags; an `onerror=` inside
  // an escaped `&lt;img …&gt;` is harmless literal text, so we check for a RAW tag, not the substring.
  if (/<\s*(script|iframe|svg|img|object|embed|form|input|link|meta|style|base|on\w+)[\s/>]/i.test(out) || out.startsWith("THREW")) {
    bad.push({ in: t.slice(0,40), out: String(out).slice(0,80) });
  }
}
console.log(JSON.stringify({ ok: bad.length === 0, bad }));
""" % __import__("json").dumps(PAYLOADS)
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8", dir=ROOT) as f:
        f.write(harness); path = f.name
    try:
        p = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=30)
        out = (p.stdout or "").strip().splitlines()[-1] if p.stdout.strip() else (p.stderr or "")[:200]
        import json as _j
        d = _j.loads(out)
        return bool(d.get("ok")), str(d.get("bad"))
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    finally:
        try: Path(path).unlink()
        except Exception: pass


def main() -> int:
    print(f"\n{'='*64}\n  ARC H H4/I — companion output escaping (OWASP LLM05 / XSS)\n{'='*64}")
    src = (ROOT / "companion-launcher.js").read_text(encoding="utf-8", errors="replace")
    fn = extract_render_markdown(src)
    if not fn:
        print(f"{RED}  FAIL  renderMarkdown not found in companion-launcher.js{RST}")
        return 1
    # structural: escape MUST precede the first tag-producing markdown replace
    esc_pos = min([fn.find(p) for p in ("&amp;", "&lt;", "&gt;") if fn.find(p) >= 0] or [10**9])
    tag_pos = min([fn.find(p) for p in ("<strong>", "<em>", "<code") if fn.find(p) >= 0] or [10**9])
    escape_first = esc_pos < tag_pos
    print(f"  {GREEN+'PASS'+RST if escape_first else RED+'FAIL'+RST}  escape-first: &/</>→entities occurs before any markdown→tag replace")

    if SELF_TEST:
        broken = "function renderMarkdown(text){ return '<div>'+text+'</div>'; }"  # no escaping
        ok_b, _ = run(broken)
        print(f"  self-test: an UNESCAPED renderer is caught = {not ok_b} ({GREEN+'teeth OK'+RST if not ok_b else RED+'NO TEETH'+RST})")

    ok, detail = run(fn)
    print(f"  {GREEN+'PASS'+RST if ok else RED+'FAIL'+RST}  LIVE execution: renderMarkdown escapes {len(PAYLOADS)} XSS payloads (no live tag/handler survives)")
    if not ok:
        print(f"  {RED}leak detail: {detail[:200]}{RST}")
    allok = escape_first and ok
    print("-" * 64)
    print(f"{(GREEN if allok else RED)}  RESULT: {'GREEN — untrusted LLM output is escaped before render (no XSS-via-LLM).' if allok else 'RED — output-handling gap.'}{RST}")
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit(main())

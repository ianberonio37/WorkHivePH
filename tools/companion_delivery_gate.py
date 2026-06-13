"""
Companion Delivery Gate  —  AI Companion Dev Tool · Layer 0 (Static)
====================================================================
The missing Layer-0 of the Companion Dev Tool. Every other companion layer
(substrate / discover / eval / battery / optimize) measures the **brain** —
does the model say the right thing. NONE of them check **delivery** — does the
answer the brain produced actually reach the user's screen.

The 2026-06-11 live walk proved the gap: the gateway returned perfect answers
(`{ok, data:{answer}}`) but the floating launcher and the voice journal both
rendered BLANK, because their client code read the answer FLAT (`data.answer`)
instead of unwrapping the envelope (`data.data.answer`). The dev tool stayed
green the whole time because its battery builds its own client and unwraps the
envelope *in its own code* — it never executes the product's delivery path.

This gate is the static counterpart to that finding: cheap grep/AST checks that
read the **product** delivery code and FAIL when the wiring can't deliver. It is
the companion's `run_platform_checks --fast` (Mega Gate G0 / Layer 0), scoped to
the companion surfaces.

Checks (grown one at a time, each individually exercised live via Playwright MCP):
  • gateway_unwrap  — a client reader of an ai-gateway response must unwrap
                      `data.data.answer`; a flat `data.answer` read returns ''
                      on every successful turn → blank reply. (FLOP #1 + #2)
  • client_wiring   — [pending]  a client global read but never assigned is a dead path
  • feedback_sink   — [pending]  the thumbs handler must reach a real client (harvest fuel)
  • single_mount    — [pending]  no double-mount of the launcher (static include + nav-hub inject)

Ratchet semantics (forward-only) — identical to content_grounding_gate.py:
  • first run establishes the baseline at the current violation count;
  • a check FAILs only when its current count EXCEEDS its baseline (NEW breakage);
  • a baseline only ratchets DOWN (when a violation is fixed), never up;
  • --strict ignores the baseline and FAILs on ANY violation > 0 (the red→green knob);
  • --update-baseline lowers the baseline to current (only downward).

Lives in tools/ (not a root validate_*.py) so run_platform_checks.py's
auto-discovery does not pull it into the platform gate — it is a COMPANION-gate
citizen, invoked by companion_dev.py, mirroring how content_grounding_gate.py is
folded behind --with-content rather than auto-discovered.

Usage:
    python tools/companion_delivery_gate.py            # ratcheted (gate mode)
    python tools/companion_delivery_gate.py --strict   # FAIL on ANY violation
    python tools/companion_delivery_gate.py --update-baseline
    python tools/companion_delivery_gate.py --self-test # synthetic good/bad fixtures
"""
import sys, os, re, json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / "companion_delivery_baseline.json"
REPORT_PATH = ROOT / "companion_delivery_report.json"

# ── Surface scope ────────────────────────────────────────────────────────────
# The companion's outward delivery surfaces = root-level *.html / *.js that talk
# to the ai-gateway to render a companion reply. We exclude test harnesses
# (*battery*), the gate tooling itself, and non-companion endpoints.
_EXCLUDE_NAME = re.compile(r"battery|\.min\.|sw\.js$", re.IGNORECASE)


def _strip_js_comments(text: str) -> str:
    """Blank out // line comments and /* */ blocks, preserving newlines + line
    numbers (comment chars → spaces). String literals are respected so a `//`
    inside a quoted URL is not treated as a comment. A comment that merely
    *mentions* `data.answer` (e.g. a bug note) must never count as a violation."""
    out, i, n = [], 0, len(text)
    in_block = in_line = False
    in_str = None
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if in_block:
            if ch == "*" and nxt == "/":
                in_block = False; out.append("  "); i += 2; continue
            out.append("\n" if ch == "\n" else " "); i += 1; continue
        if in_line:
            if ch == "\n":
                in_line = False; out.append("\n")
            else:
                out.append(" ")
            i += 1; continue
        if in_str:
            # A quoted string can't span a newline in JS (single/double); a stray
            # apostrophe in surrounding HTML/CSS prose would otherwise desync the
            # whole rest of the file. Reset string-state at each newline so any
            # mis-parse is bounded to one line.
            if ch == "\n":
                in_str = None; out.append("\n"); i += 1; continue
            out.append(ch)
            if ch == "\\" and nxt:
                out.append(nxt); i += 2; continue
            if ch == in_str:
                in_str = None
            i += 1; continue
        if ch == "/" and nxt == "*":
            in_block = True; out.append("  "); i += 2; continue
        if ch == "/" and nxt == "/":
            in_line = True; out.append("  "); i += 2; continue
        if ch in ("\"", "'", "`"):
            in_str = ch
        out.append(ch); i += 1
    return "".join(out)


def _surface_files() -> list[Path]:
    files: list[Path] = []
    for p in sorted(ROOT.glob("*.html")) + sorted(ROOT.glob("*.js")):
        if _EXCLUDE_NAME.search(p.name):
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "ai-gateway" in txt:
            files.append(p)
    return files


# ── Check 1: gateway_unwrap ──────────────────────────────────────────────────
# A flat read of `data.answer` off the RAW ai-gateway response is the bug. The
# correct read unwraps the success envelope: `data.data.answer`. We flag a flat
# read ONLY when the `data` it reads was not unwrapped — i.e. neither its nearest
# preceding assignment nor the lines between that assignment and the read carry
# an unwrap signal. This precisely separates:
#   FLAG  companion-launcher.js  `return String(data.answer || '')`     (raw fetch body)
#   FLAG  voice-journal.html     `return String(data.answer || '')`     (raw invoke data)
#   SAFE  companion-launcher.js  `(data.data.answer) || (data.answer)`  (line has data.data.answer)
#   SAFE  voice-handler.js       `const data = _unwrapGateway(...)`     (assignment unwraps)
#   SAFE  assistant.html         `orchData.answer` after `env.data`     (var isn't bare `data`)
_FLAT_READ = re.compile(r"(?<![.\w])data\.answer\b")
_NESTED_READ = re.compile(r"\bdata\.data\.answer\b")
_DATA_ASSIGN = re.compile(r"\b(?:const|let|var)\s*(?:\{\s*[^}]*\bdata\b|data\s*=)|^\s*data\s*=")
_UNWRAP_SIGNAL = re.compile(r"_unwrap|data\.data\b|\.data\.answer\b|env\.data\b|\?\.data\?\.")


def _gateway_unwrap_violations_in(text: str, fname: str) -> list[dict]:
    raw_lines = text.splitlines()
    lines = _strip_js_comments(text).splitlines()  # match on comment-free code
    out: list[dict] = []
    for i, line in enumerate(lines):
        if not _FLAT_READ.search(line):
            continue
        if _NESTED_READ.search(line):
            continue  # this very line unwraps (data.data.answer) — safe
        # Walk up to the nearest `data` assignment that feeds this read.
        j = i
        while j >= 0 and not _DATA_ASSIGN.search(lines[j]):
            j -= 1
        start = j if j >= 0 else max(0, i - 30)
        window = "\n".join(lines[start:i + 1])
        if _UNWRAP_SIGNAL.search(window):
            continue  # the data feeding this read was unwrapped — safe
        out.append({
            "file": fname,
            "line": i + 1,
            "code": (raw_lines[i].strip() if i < len(raw_lines) else line.strip())[:160],
            "why": "reads flat data.answer off an un-unwrapped ai-gateway response "
                   "→ undefined on every success → blank reply",
        })
    return out


def check_gateway_unwrap() -> dict:
    violations: list[dict] = []
    for p in _surface_files():
        txt = p.read_text(encoding="utf-8", errors="ignore")
        violations.extend(_gateway_unwrap_violations_in(txt, p.name))
    return {
        "count": len(violations),
        "violations": violations,
        "fix": "unwrap the envelope: (data && data.data && data.data.answer) || (data && data.answer) || ''",
    }


# ── Check 2: client_wiring ───────────────────────────────────────────────────
# A companion surface that uses a Supabase client off a window global (e.g.
# `window.WH_DB.functions.invoke(...)` / `window.WH_DB.from(...)`) is wiring a
# code path to that global. If the global is NEVER assigned anywhere in the
# codebase, the path is DEAD — the guard `if (window.WH_DB)` is always false, so
# the branch (session-authed invoke, feedback write) never runs. That is exactly
# why the launcher silently fell through to the unauthenticated fetch fallback
# and why every 👍/👎 no-oped. The fix is to read the real client the page
# already builds (`window._whSupabaseClient`, assigned by getDb() in utils.js).
_CLIENT_USE = re.compile(r"window\.([A-Z_][A-Z0-9_]*)\s*\.\s*(?:functions\b|from\s*\()")


def _client_assigned_anywhere(name: str) -> bool:
    pat = re.compile(r"(?:window\.)?" + re.escape(name) + r"\s*=")
    for p in (sorted(ROOT.glob("*.js")) + sorted(ROOT.glob("*.html"))):
        try:
            txt = _strip_js_comments(p.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        # ignore equality / arrow / comparison (== === =>) — require a real assign
        for m in pat.finditer(txt):
            tail = txt[m.end():m.end() + 2]
            if not tail.startswith("=") and not tail.startswith(">"):
                return True
    return False


def check_client_wiring() -> dict:
    violations: list[dict] = []
    for p in _surface_files():
        text = _strip_js_comments(p.read_text(encoding="utf-8", errors="ignore"))
        seen = set()
        for m in _CLIENT_USE.finditer(text):
            name = m.group(1)
            if name in seen:
                continue
            seen.add(name)
            if not _client_assigned_anywhere(name):
                line = text[:m.start()].count("\n") + 1
                violations.append({
                    "file": p.name, "line": line,
                    "code": f"window.{name}.functions/.from — client global never assigned",
                    "why": f"window.{name} is used as a client but assigned nowhere → dead path "
                           f"(authed invoke + feedback write never run)",
                })
    return {
        "count": len(violations),
        "violations": violations,
        "fix": "read the real client the page builds: window._whSupabaseClient (assigned by getDb in utils.js)",
    }


# ── Check 3: feedback_sink ───────────────────────────────────────────────────
# The 👍/👎 affordance is the harvest mine's ONLY inflow (companion_harvest.py
# reads ai_reply_feedback). A surface that renders thumbs (data-rate buttons) but
# does NOT insert into ai_reply_feedback silently loses every rating — which is
# exactly the legacy bug (ratings written to ai_cost_log.quality_rating via a
# missing RPC + RLS-denied UPDATE = no-op end to end; see migration 20260609000006).
# This guards sink CORRECTNESS (distinct from client_wiring, which guards that the
# client is real): a thumbs affordance must write the canonical ai_reply_feedback.
_THUMBS_AFFORDANCE = re.compile(r"data-rate\b")
_CANON_SINK = re.compile(r"\.from\(\s*['\"]ai_reply_feedback['\"]\s*\)\s*\.insert")
_DEAD_SINK = re.compile(r"record_ai_reply_rating|quality_rating\s*:")


def _feedback_sink_violations_in(text: str, fname: str) -> list[dict]:
    code = _strip_js_comments(text)
    if not _THUMBS_AFFORDANCE.search(code):
        return []
    if _CANON_SINK.search(code):
        return []  # writes the canonical harvest sink — good
    m = _THUMBS_AFFORDANCE.search(code)
    line = code[:m.start()].count("\n") + 1
    dead = "→ writes the legacy no-op sink (ai_cost_log/RPC)" if _DEAD_SINK.search(code) else ""
    return [{
        "file": fname, "line": line,
        "code": "thumbs affordance (data-rate) with no ai_reply_feedback insert",
        "why": f"a 👍/👎 affordance that never inserts into ai_reply_feedback silently "
               f"loses every rating {dead} → the harvest mine is starved",
    }]


def check_feedback_sink() -> dict:
    violations: list[dict] = []
    for p in (sorted(ROOT.glob("*.html")) + sorted(ROOT.glob("*.js"))):
        if _EXCLUDE_NAME.search(p.name):
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        violations.extend(_feedback_sink_violations_in(txt, p.name))
    return {
        "count": len(violations),
        "violations": violations,
        "fix": "the thumbs handler must insert into ai_reply_feedback via a real client (window._whSupabaseClient)",
    }


# ── Check 4: single_mount ────────────────────────────────────────────────────
# nav-hub.js injects companion-launcher.js into <head>, AND ~29 pages also carry a
# static <script src="companion-launcher.js"> at end-of-body. nav-hub's dedupe
# guard runs BEFORE the parser reaches that late static tag, so its querySelector
# can't see it yet → both load → two stacked widgets (duplicate #wh-ai-widget /
# #wh-ai-input, mismatched headers). The robust, zero-page-churn fix is an
# idempotency guard at the top of companion-launcher.js so a second execution is a
# no-op regardless of how many times the script is included. This check asserts
# that guard exists (the launcher is double-mount-safe).
_INIT_GUARD = re.compile(r"window\.__whLauncherInit\b")
_LAUNCHER = "companion-launcher.js"


def check_single_mount() -> dict:
    p = ROOT / _LAUNCHER
    violations: list[dict] = []
    if p.exists():
        code = _strip_js_comments(p.read_text(encoding="utf-8", errors="ignore"))
        guarded = bool(_INIT_GUARD.search(code) and re.search(r"window\.__whLauncherInit[\s\S]{0,80}?\breturn\b", code))
        if not guarded:
            violations.append({
                "file": _LAUNCHER, "line": 1,
                "code": "no idempotency init-guard at top of IIFE",
                "why": "launcher can double-mount (nav-hub inject + static include) → two stacked widgets; "
                       "needs `if (window.__whLauncherInit) return; window.__whLauncherInit = true;`",
            })
    return {
        "count": len(violations),
        "violations": violations,
        "fix": "add `if (window.__whLauncherInit) return; window.__whLauncherInit = true;` at the top of the IIFE",
    }


# ── Check registry (grows one at a time) ─────────────────────────────────────
CHECKS = {
    "gateway_unwrap": check_gateway_unwrap,
    "client_wiring": check_client_wiring,
    "feedback_sink": check_feedback_sink,
    "single_mount": check_single_mount,
}


def run_checks() -> dict:
    return {name: fn() for name, fn in CHECKS.items()}


# ── Forward-only ratchet (mirrors content_grounding_gate.py) ─────────────────
def _load_baseline() -> dict:
    if BASELINE_PATH.exists():
        try:
            return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def evaluate(strict: bool = False, update_baseline: bool = False) -> tuple[int, dict]:
    prior = _load_baseline().get("checks", {})
    established = bool(prior)
    results = run_checks()

    rows, fails = [], 0
    new_baseline = {}
    for name, res in results.items():
        cur = res["count"]
        base = prior.get(name, cur)            # first sight: baseline = current
        ratcheted = min(base, cur)             # forward-only: only ever lower
        new_baseline[name] = ratcheted
        if strict:
            failed = cur > 0
            shown_base = 0
        else:
            failed = cur > ratcheted
            shown_base = ratcheted
        if failed:
            fails += 1
        rows.append({"check": name, "current": cur, "baseline": shown_base,
                     "failed": failed, "violations": res["violations"], "fix": res["fix"]})

    report = {
        "gate": "companion_delivery",
        "layer": "L0 (static delivery)",
        "mode": "strict" if strict else "ratcheted",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checks": rows,
        "fails": fails,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if not strict and not update_baseline:
        BASELINE_PATH.write_text(json.dumps({
            "checks": new_baseline,
            "established": (_load_baseline().get("established") if established
                            else datetime.now(timezone.utc).isoformat(timespec="seconds")),
        }, indent=2), encoding="utf-8")
    elif update_baseline:
        BASELINE_PATH.write_text(json.dumps({
            "checks": {n: r["count"] for n, r in results.items()},
            "established": _load_baseline().get("established") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }, indent=2), encoding="utf-8")

    return (1 if fails else 0), report


def _print_report(report: dict) -> None:
    def c(code, t): return f"\033[{code}m{t}\033[0m"
    print(f"\nCompanion Delivery Gate · {report['layer']} ({report['mode']})  ·  {report['generated_at']}")
    for row in report["checks"]:
        ok = not row["failed"]
        tag = c("92", "PASS") if ok else c("91", "FAIL")
        print(f"  {tag}  {row['check']:<16} current={row['current']} baseline={row['baseline']}")
        if row["failed"]:
            for v in row["violations"]:
                print(f"        {c('91','✗')} {v['file']}:{v['line']}  {v['code']}")
                print(f"           {v['why']}")
            print(f"           {c('93','fix:')} {row['fix']}")
    verdict = c("91", "BLOCK") if report["fails"] else c("92", "PASS")
    print(f"\n  Verdict: {verdict}  ({report['fails']} check(s) failing)\n")


# ── Self-test: synthetic good/bad fixtures (teeth must be synthetic, not live drift) ──
def _self_test() -> int:
    bad = "const { data } = await db.functions.invoke('ai-gateway', {});\n  return String(data.answer || '').trim();"
    good_nested = "const { data } = await db.functions.invoke('ai-gateway', {});\n  return String((data && data.data && data.data.answer) || (data && data.answer) || '');"
    good_unwrap = "const data = _unwrapGateway(await resp.json()); // ai-gateway\n  const answer = String((data && data.answer) || '').trim();"
    good_var = "const env = r.data; const orchData = env.ok ? env.data : env; // ai-gateway\n  reply = orchData.answer;"
    cases = [("bad", bad, 1), ("good_nested", good_nested, 0),
             ("good_unwrap", good_unwrap, 0), ("good_var", good_var, 0)]
    ok = True
    print("  · gateway_unwrap")
    for name, src, expected in cases:
        got = len(_gateway_unwrap_violations_in(src, name))
        flag = "PASS" if got == expected else "FAIL"
        if got != expected:
            ok = False
        print(f"    [{flag}] {name:<12} expected {expected} violation(s), got {got}")

    # feedback_sink fixtures
    fb_bad = "'<button data-rate=\"1\">👍</button>'; // no canonical sink anywhere"
    fb_dead = "'<button data-rate=\"1\">👍</button>'; await rpc('record_ai_reply_rating', { quality_rating: r });"
    fb_good = "'<button data-rate=\"1\">👍</button>'; await db.from('ai_reply_feedback').insert({ rating: r });"
    fb_none = "const x = 1; // no thumbs affordance on this surface"
    fb_cases = [("fb_bad", fb_bad, 1), ("fb_dead", fb_dead, 1), ("fb_good", fb_good, 0), ("fb_none", fb_none, 0)]
    print("  · feedback_sink")
    for name, src, expected in fb_cases:
        got = len(_feedback_sink_violations_in(src, name))
        flag = "PASS" if got == expected else "FAIL"
        if got != expected:
            ok = False
        print(f"    [{flag}] {name:<12} expected {expected} violation(s), got {got}")

    print(f"\n  Self-test: {'PASS — discriminates good vs bad' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if "--self-test" in sys.argv:
        return _self_test()
    code, report = evaluate(strict="--strict" in sys.argv,
                            update_baseline="--update-baseline" in sys.argv)
    _print_report(report)
    return code


if __name__ == "__main__":
    sys.exit(main())

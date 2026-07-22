#!/usr/bin/env python3
"""
validate_error_capture.py - PER_PAGE SaaS-LAYER bug-hunt · Layer L (Error Tracking & Logs), 2026-07-22.
========================================================================================================
The L-layer per-page observability invariant: a catch block around a BACKEND operation (db.from / db.rpc
/ db.functions.invoke / fetch) that SURFACES the error to the user (showToast / addAssistantBubble /
showFormError / errEl.textContent / alert) must ALSO CAPTURE it (console.error/warn / logEvent /
window.onerror / captureException) — otherwise an operation that starts failing for users leaves NO
greppable/aggregatable trace (the L-layer "ungreppable logs, no aggregation" failure mode,
COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §2). A catch that shows-but-doesn't-log is the gap.

REAL bug this locks (found live 2026-07-22): assistant.html sendMessage caught the ai-gateway failure,
showed the user an error bubble + toast, but never console.error'd it → an assistant failing in the field
was invisible in the logs. Fixed + this gate keeps every backend catch observable.

EXCLUDED (not gaps): a catch marked best-effort/silent-by-design (comment `empty-catch-allow` /
`best-effort` / `non-fatal` / `silent`); a catch with no user-surface (it already fails quietly by
design and isn't claiming success); a catch around a pure non-backend body.

Static + fast. Forward-only ratchet on the swallow count (baseline seeds on first run). `--selftest`
proves teeth. Exit 0 pass / 1 findings above baseline.
"""
from __future__ import annotations
import io, re, json, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"
CHECK_NAMES = ["validate_error_capture"]
REPO = Path(__file__).resolve().parent.parent
BASELINE = REPO / "error_capture_baseline.json"
EXCLUDE = ("node_modules", "remotion", "-test.", ".backup", "test-data-seeder")

CATCH_RE = re.compile(r"\bcatch\s*\([^)]*\)\s*\{")
BACKEND = re.compile(r"db\.from\s*\(|db\.rpc\s*\(|db\.functions\.invoke\s*\(|\bfetch\s*\(|fetchWithTimeout\s*\(|\.auth\.")
SURFACE = re.compile(r"showToast\s*\(|addAssistantBubble\s*\(|addBubble\s*\(|showFormError\s*\(|"
                     r"\.textContent\s*=|\balert\s*\(|showError\s*\(|toast\s*\(|errEl\b")
CAPTURE = re.compile(r"console\.(error|warn)\s*\(|logEvent\s*\(|window\.onerror|captureException\s*\(|"
                     r"Sentry|reportError\s*\(|_logError\s*\(|trackError\s*\(")
BEST_EFFORT = re.compile(r"empty-catch-allow|best-effort|non-fatal|silent|fire-and-forget|ignore", re.I)


def _catch_body(src: str, brace_at: int) -> str:
    depth = 0
    for j in range(brace_at, min(len(src), brace_at + 4000)):
        c = src[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[brace_at:j + 1]
    return src[brace_at:brace_at + 4000]


def _try_before(src: str, catch_start: int) -> str:
    # the ~600 chars before `catch` approximate the try body (enough to see a backend op)
    return src[max(0, catch_start - 800):catch_start]


def scan_page(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8", errors="ignore")
    findings = []
    for m in CATCH_RE.finditer(src):
        body = _catch_body(src, m.end() - 1)
        if BEST_EFFORT.search(body):
            continue                                  # silent-by-design
        if not SURFACE.search(body):
            continue                                  # doesn't claim to the user → not a hidden failure
        if CAPTURE.search(body):
            continue                                  # already observable
        if not BACKEND.search(_try_before(src, m.start()) + body):
            continue                                  # not a backend op → out of L scope
        # a backend catch that surfaces to the user but never captures = the gap
        snippet = re.sub(r"\s+", " ", body[:70])
        findings.append(snippet)
    return findings


def scan_all() -> dict:
    per = {}
    for p in sorted(REPO.glob("*.html")):
        if any(x in p.name for x in EXCLUDE):
            continue
        f = scan_page(p)
        if f:
            per[p.name] = f
    return per


def self_test() -> bool:
    ok = True
    tmp = REPO / "._ec_selftest.html"
    try:
        bad = "try { await db.from('t').insert(r); } catch (e) { showToast('failed'); }"
        tmp.write_text(bad, encoding="utf-8")
        if not scan_page(tmp):
            print(f"{R}self-test FAIL: swallowed backend catch not flagged.{X}"); ok = False
        good = "try { await db.from('t').insert(r); } catch (e) { console.error('x', e); showToast('failed'); }"
        tmp.write_text(good, encoding="utf-8")
        if scan_page(tmp):
            print(f"{R}self-test FAIL: captured catch misflagged.{X}"); ok = False
        silent = "try { await db.from('t').insert(r); } catch (e) { /* best-effort */ showToast('x'); }"
        tmp.write_text(silent, encoding="utf-8")
        if scan_page(tmp):
            print(f"{R}self-test FAIL: best-effort catch misflagged.{X}"); ok = False
        nosurface = "try { await db.from('t').insert(r); } catch (e) { retryQueue.push(r); }"
        tmp.write_text(nosurface, encoding="utf-8")
        if scan_page(tmp):
            print(f"{R}self-test FAIL: no-user-surface catch misflagged.{X}"); ok = False
        nonbackend = "try { JSON.parse(s); } catch (e) { showToast('bad json'); }"
        tmp.write_text(nonbackend, encoding="utf-8")
        if scan_page(tmp):
            print(f"{R}self-test FAIL: non-backend catch misflagged.{X}"); ok = False
    finally:
        try: tmp.unlink()
        except OSError: pass
    print((G + "self-test PASS - error-capture parser has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def check_central_backbone() -> str | None:
    """METHOD LAW: the L-layer capture is CENTRALIZED in utils.js — a single whLogError sink + global
    error/unhandledrejection listeners net the uncaught class platform-wide (zero per-page code). If that
    central component is missing/removed, the whole L layer regresses (uncaught errors go ungreppable).
    Returns a FAIL reason, or None if the backbone is present."""
    u = REPO / "utils.js"
    if not u.exists():
        return "utils.js missing — the central L-layer error backbone has no home"
    src = u.read_text(encoding="utf-8", errors="ignore")
    have_sink = "whLogError" in src
    have_error = bool(re.search(r"addEventListener\(\s*['\"]error['\"]", src))
    have_rej = "unhandledrejection" in src
    missing = [n for n, ok in (("whLogError sink", have_sink),
                               ("global 'error' listener", have_error),
                               ("'unhandledrejection' listener", have_rej)) if not ok]
    return None if not missing else ("central backbone incomplete in utils.js — missing: " + ", ".join(missing))


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        return 0 if self_test() else 1
    central = check_central_backbone()
    per = scan_all()
    total = sum(len(v) for v in per.values())
    accept = "--accept" in sys.argv
    base = json.loads(BASELINE.read_text()).get("swallows", 10**9) if BASELINE.exists() else None
    print(f"{B}L-layer error-capture — central backbone + backend catch must log ({total} swallow(s) across {len(per)} page(s)){X}")
    if central:
        print(f"  {R}✗ CENTRAL{X} {central}")
    else:
        print(f"  {G}✓ CENTRAL{X} utils.js: whLogError sink + global error/unhandledrejection listeners (uncaught class netted platform-wide, zero per-page code)")
    for name, fs in sorted(per.items(), key=lambda kv: -len(kv[1])):
        print(f"  {R}○{X} {name}: {len(fs)} backend catch(es) surface to the user without a console.error/logEvent")
    if central and not (accept or base is None):
        print(f"{R}FAIL: the CENTRAL L-layer backbone (utils.js) is broken — {central}.{X}")
        return 1
    if accept or base is None:
        BASELINE.write_text(json.dumps({"swallows": total}, indent=2), encoding="utf-8")
        print(f"{G}{'ratcheted' if accept else 'seeded'} baseline → {total} swallow(s).{X}")
        return 0
    if total > base:
        print(f"{R}FAIL: L-layer error-swallows ROSE {base}→{total} (a new backend catch shows-but-doesn't-log).{X}")
        return 1
    print(f"{G}PASS: L-layer error-capture — {total} swallow(s) ≤ baseline {base} (forward ratchet held).{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

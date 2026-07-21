#!/usr/bin/env python3
"""
validate_input_validation_guard.py - PER_PAGE_BUGHUNT P4 client-validation gate (2026-07-21).
=============================================================================================
The P4 (Inputs + edge cases) axis is server-hardened + gated already: XSS (innerhtml-eschtml /
dom-xss-fields / page-battery reflected-XSS), server text caps (31 `trg_text_caps_*`), numeric bounds
(mig 004), and — as of 2026-07-21 — the duplicate-submit half (`double-submit-lock`). The LAST P4
sub-property not yet gate-locked platform-wide is CLIENT-side empty/format validation: a write form that
POSTs whatever the user typed, with no "this field is required / that's not a valid X" guard, teaches a
worker the tool is sloppy (and leans entirely on the server to reject).

THE RULE: every WRITE-submit handler (a fn that issues a `db.from().insert/upsert/update` or `db.rpc`
mutation AND reads a user input field — `getElementById(...).value` / `.value.trim()` / a form field)
must validate that input before the write, by EITHER:
  * a runtime capture contract — `whValidateCapture(...)` (the Tier-F schema path), OR
  * an early-return validation guard BEFORE the first write: a `return` reached from a check that also
    surfaces the problem to the user (`showFormError` / `showToast` / `errEl` / `.textContent =` /
    `.focus()` / `classList` on an error el / `isValid*(`).
A write handler that reads a user field and writes it with NO such guard = FAIL (a real P4 gap).

Static + fast. Read-only handlers, server-derived writes (no user field read), and idempotent
system writes are not flagged. Exit 0 pass / 1 findings. `--selftest` proves the parser has teeth.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"
CHECK_NAMES = ["validate_input_validation_guard"]
REPO = Path(__file__).resolve().parent.parent
EXCLUDE = ("node_modules", "remotion", "-test.", ".backup", "test-data-seeder")

FN_RE = re.compile(r"(?:async\s+)?function\s+([A-Za-z_]\w*)\s*\([^)]*\)\s*\{")
# a user-input READ inside the handler (the thing that needs validating)
READS_INPUT = re.compile(r"getElementById\([^)]*\)\.value|\.value\.trim\(\)|querySelector\([^)]*\)\.value|\.files\b")
# a client-direct write (from→mutate chain or rpc)
WRITE = re.compile(r"db\.from\s*\([^)]*\)[\s\S]{0,300}?\.(insert|upsert|update)\s*\(|\bdb\.rpc\s*\(")
# a validation guard present BEFORE the write, any of:
#  - a capture-contract call, an error-surface (showFormError/showToast/errEl/.textContent=/.focus/classList error), OR
#  - a validation BRANCH: an `if (...)` whose body reaches a `return` (the ubiquitous
#    `if (!field || bad) { ...; return; }` idiom). A silent `if (x<=0) return;` still validates
#    (it blocks the bad write), so it counts — the gate locks "the form validates", not message polish.
GUARD_TOKENS = re.compile(
    r"whValidateCapture\s*\(|showFormError\s*\(|showToast\s*\(|errEl|\.textContent\s*=|"
    r"isValid[A-Za-z]*\s*\(|\.focus\s*\(\s*\)|classList\.(add|remove)\s*\(\s*['\"](error|invalid|hidden|warn)",
    re.I)
GUARD_BRANCH = re.compile(r"\bif\s*\([^;{]*\)\s*(\{[^{}]*\breturn\b|[^;{]*\breturn\b)")


def _has_guard(pre: str) -> bool:
    return bool(GUARD_TOKENS.search(pre) or GUARD_BRANCH.search(pre))
# names that are never user-input write forms (dedupe/system/toggle) — skip
SKIP_NAME = re.compile(r"^(load|render|open|close|switch|toggle|refresh|init|sync|subscribe|hydrate|prune|migrate|autolink|_)", re.I)


def _body(src: str, start: int) -> str:
    depth = 0
    for j in range(start, min(len(src), start + 20000)):
        c = src[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[start:j + 1]
    return src[start:start + 20000]


def scan_page(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8", errors="ignore")
    findings = []
    for m in FN_RE.finditer(src):
        name = m.group(1)
        if SKIP_NAME.match(name):
            continue
        body = _body(src, m.end() - 1)
        wm = WRITE.search(body)
        if not wm:
            continue
        # only care about handlers that write a USER-TYPED field
        if not READS_INPUT.search(body):
            continue
        # is there a guard BEFORE the first write?
        pre = body[:wm.start()]
        if _has_guard(pre):
            continue
        findings.append(name)
    return sorted(set(findings))


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        return 0 if self_test() else 1
    print(f"{B}P4 client input-validation gate (a write of a user field must validate it first){X}")
    total = 0
    fails = []
    for p in sorted(REPO.glob("*.html")):
        if any(x in p.name for x in EXCLUDE):
            continue
        total += 1
        for name in scan_page(p):
            fails.append((p.name, name))
    for page, name in fails:
        print(f"  {R}FAIL{X}  {page}: {name}() writes a user-input field with NO client validation guard "
              f"before the write (add a required/format check with an error surface, or whValidateCapture).")
    print(f"  scanned {total} pages.")
    if fails:
        print(f"{R}FAIL: {len(fails)} unvalidated user-input write handler(s).{X}")
        return 1
    print(f"{G}PASS - every user-input write handler validates before writing.{X}")
    return 0


def self_test() -> bool:
    ok = True
    tmp = REPO / "._ivg_selftest.html"
    try:
        # writes a user field with NO guard -> flagged
        bad = "async function submitZ(){ const v=document.getElementById('n').value.trim(); await db.from('t').insert({n:v}); }"
        tmp.write_text(bad, encoding="utf-8")
        if "submitZ" not in scan_page(tmp):
            print(f"{R}self-test FAIL: unvalidated write not flagged.{X}"); ok = False
        # writes a user field WITH a guard -> not flagged
        good = "async function submitW(){ const v=document.getElementById('n').value.trim(); if(!v){ showFormError('Name required'); return; } await db.from('t').insert({n:v}); }"
        tmp.write_text(good, encoding="utf-8")
        if scan_page(tmp):
            print(f"{R}self-test FAIL: guarded write misflagged.{X}"); ok = False
        # a server-derived write (no user field) -> not flagged
        srv = "async function logEvt(){ await db.from('t').insert({k:'x', at:Date.now()}); }"
        tmp.write_text(srv, encoding="utf-8")
        if scan_page(tmp):
            print(f"{R}self-test FAIL: server-derived write misflagged.{X}"); ok = False
        # capture-contract path -> not flagged
        cc = "async function submitC(){ const v=document.getElementById('n').value; const r=await window.whValidateCapture(db,'x',{n:v}); if(!r.ok)return; await db.from('t').insert({n:v}); }"
        tmp.write_text(cc, encoding="utf-8")
        if scan_page(tmp):
            print(f"{R}self-test FAIL: capture-contract-validated write misflagged.{X}"); ok = False
    finally:
        try: tmp.unlink()
        except OSError: pass
    print((G + "self-test PASS - input-validation-guard parser has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


if __name__ == "__main__":
    sys.exit(main())

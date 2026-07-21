#!/usr/bin/env python3
"""
validate_double_submit_lock.py - PER_PAGE_BUGHUNT P7 double-submit lock gate (2026-07-21).
==========================================================================================
A submit button wired straight to an async WRITE handler with no single-flight lock is a double-submit
bug: a fast double-tap (common on a factory-floor phone) re-fires the handler before the first await
resolves. For a NON-idempotent write that means a DOUBLE effect — the canonical PRODUCTION_FIXES #47 /
button-lock.js concern. Live-found 2026-07-21: inventory.html's submitUse/submitRestock/submitPart wired
`addEventListener('click', submitUse)` bare while submitUse calls the non-idempotent `inventory_deduct`
RPC → two taps = a double stock deduction; logbook.html's submitAsset (bare) → a 2nd tap 23505s on the
(hive_id,tag) unique index.

THE RULE: every `getElementById('...').addEventListener('click', H)` (or `onclick="H(...)"`) whose
handler H is a WRITE handler (name matches submit/save/confirm/create/add/send/publish/approve/reject/
delete, OR the handler body issues a db write/rpc) MUST be single-flight-locked, by EITHER:
  * the binding wraps H in `withButtonLock(this, H)` / `lockButtonDuring(...)`, OR
  * H's own body disables its button (`<btn>.disabled = true` before the await).
A bare click→write binding whose handler never self-disables = FAIL.

Static + fast (no DB). Exit 0 pass / 1 findings. `--selftest` proves the parser has teeth.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"
CHECK_NAMES = ["validate_double_submit_lock"]
REPO = Path(__file__).resolve().parent.parent
EXCLUDE = ("node_modules", "remotion", "-test.", ".backup", "test-data-seeder")

# a click binding to a BARE handler name (not an inline arrow / not already wrapped)
BIND_RE = re.compile(r"""addEventListener\(\s*['"]click['"]\s*,\s*([A-Za-z_]\w*)\s*\)""")
# handler names that denote a write/submit action
WRITE_NAME = re.compile(r"^(submit|save|confirm|create|add|send|publish|approve|reject|delete|post|register|book|assign|record)", re.I)
# a DB WRITE inside the handler body: a supabase `db.from('t')...insert/upsert/update/delete(` chain,
# or a `db.rpc(` mutation. Keyed on `db.` + the from→write chain so (a) a JS Set/Array/Map `.delete(`
# (e.g. `_jdSelected.delete(term)`) is NOT misread as a write (Map.size class), and (b) a READ-ONLY
# handler whose db.from() calls are all `.select(` (e.g. runAutofill) is NOT flagged.
BODY_WRITE = re.compile(r"db\.from\s*\([^)]*\)[\s\S]{0,300}?\.(insert|upsert|update|delete)\s*\(|\bdb\.rpc\s*\(")
# the handler self-locks (any of these tokens inside its body)
SELF_LOCK = re.compile(r"\.disabled\s*=\s*true|withButtonLock\s*\(|lockButtonDuring\s*\(|\bbusy\b\s*=\s*true|_saving\s*=\s*true")
# handler names that are pure navigation/close/render (never a write) — skip fast
NON_WRITE = re.compile(r"^(close|open|switch|render|clear|cancel|toggle|show|hide|goto|nav|refresh|load|select|filter|search|expand|collapse|update(View|Send|Btn|Ui))", re.I)


def _extract_handler_body(src: str, name: str) -> str | None:
    """Return the source of `function name(...) { ... }` / `async function name` (brace-matched)."""
    m = re.search(r"(?:async\s+)?function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", src)
    if not m:
        return None
    i = m.end() - 1
    depth = 0
    for j in range(i, min(len(src), i + 20000)):
        c = src[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
    return src[i:i + 20000]


def scan_page(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8", errors="ignore")
    findings = []
    for m in BIND_RE.finditer(src):
        name = m.group(1)
        if NON_WRITE.match(name):
            continue
        body = _extract_handler_body(src, name)
        if body is None:
            continue
        is_write = bool(WRITE_NAME.match(name)) or bool(BODY_WRITE.search(body))
        if not is_write:
            continue
        # bound bare (not wrapped). Is it single-flight-locked in its own body?
        if SELF_LOCK.search(body):
            continue
        # is the BINDING itself wrapped? (BIND_RE only matches a bare name, so if we're here it isn't)
        findings.append(name)
    return sorted(set(findings))


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        return 0 if self_test() else 1
    print(f"{B}P7 double-submit lock gate (bare click->write handler must single-flight-lock){X}")
    total = 0
    fails = []
    for p in sorted(REPO.glob("*.html")):
        if any(x in p.name for x in EXCLUDE):
            continue
        total += 1
        bad = scan_page(p)
        for name in bad:
            fails.append((p.name, name))
    for page, name in fails:
        print(f"  {R}FAIL{X}  {page}: click->{name}() is a bare write binding with no single-flight lock "
              f"(wrap `withButtonLock(this, {name})` or disable the button before the await) — double-tap = double write.")
    print(f"  scanned {total} pages.")
    if fails:
        print(f"{R}FAIL: {len(fails)} unlocked click->write binding(s) — double-submit risk.{X}")
        return 1
    print(f"{G}PASS - every bare click->write binding is single-flight-locked.{X}")
    return 0


def self_test() -> bool:
    ok = True
    # a bare write binding whose handler does not self-lock -> flagged
    bad = "document.getElementById('b').addEventListener('click', submitX);\nasync function submitX(){ await db.from('t').insert(r); }"
    tmp = REPO / "._dsl_selftest.html"
    try:
        tmp.write_text(bad, encoding="utf-8")
        if "submitX" not in scan_page(tmp):
            print(f"{R}self-test FAIL: unlocked write binding not flagged.{X}"); ok = False
        # a self-locking handler -> NOT flagged
        good = "document.getElementById('b').addEventListener('click', submitY);\nasync function submitY(){ const btn=document.getElementById('b'); btn.disabled=true; await db.from('t').insert(r); btn.disabled=false; }"
        tmp.write_text(good, encoding="utf-8")
        if scan_page(tmp):
            print(f"{R}self-test FAIL: self-locking handler misflagged.{X}"); ok = False
        # a nav handler -> skipped even though bound bare
        nav = "document.getElementById('b').addEventListener('click', closeModal);\nfunction closeModal(){ document.getElementById('m').style.display='none'; }"
        tmp.write_text(nav, encoding="utf-8")
        if scan_page(tmp):
            print(f"{R}self-test FAIL: nav handler misflagged as write.{X}"); ok = False
        # a router whose only ".delete(" is a JS Set method (not db.) -> NOT flagged (Map.size class)
        setfp = "document.getElementById('b').addEventListener('click', onPanelClick);\nfunction onPanelClick(ev){ if(sel.has(t)) sel.delete(t); else sel.add(t); }"
        tmp.write_text(setfp, encoding="utf-8")
        if scan_page(tmp):
            print(f"{R}self-test FAIL: JS Set.delete misread as a DB write.{X}"); ok = False
        # a READ-ONLY handler (db.from().select only) bound to a non-write-named fn -> NOT flagged
        ro = "document.getElementById('b').addEventListener('click', runAutofillX);\nasync function runAutofillX(){ const {data}=await db.from('t').select('a').eq('x',1); render(data); }"
        tmp.write_text(ro, encoding="utf-8")
        if scan_page(tmp):
            print(f"{R}self-test FAIL: read-only select handler misflagged as a write.{X}"); ok = False
    finally:
        try: tmp.unlink()
        except OSError: pass
    print((G + "self-test PASS - double-submit-lock parser has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""success-is-checked - a page may not announce a write it never confirmed (2026-08-27, T63).

The mirror of unconfirmed-write-is-not-a-failure, and the worse half. Telling someone their work
FAILED when it landed costs a retry. Telling them it SAVED when it did not is a lie they ACT on:
they close the tab, they walk away from the machine, they stop chasing the payment.

*supabase-js DOES NOT THROW WHEN A WRITE IS REFUSED. It resolves with { error }. So a
`try { await db.from(t).delete()... } catch` is not protection - the catch only ever sees thrown
errors, and an RLS refusal never throws. This is the same root as the bare-builder class
([[feedback_supabase_builders_never_send_unawaited]]) seen from the other end: there the promise was
never sent, here it was sent, refused, and the refusal discarded.

IT FOUND ONE, AND IT WAS THE WORST PLACE TO FIND IT. integrations' rollbackBatch ran three writes -
delete from external_sync, delete the imported rows from the target table, mark the audit entry
rolled back - discarded all three results, and said "Import rolled back successfully." An RLS
refusal on any step left every imported row in place while the person was told the import had been
undone. On a REVERSAL that is the worst available lie: they stop looking, and the bad data stays.
Fixed; the class is now empty platform-wide, so this gate carries NO baseline - any hit is new.

*A ROWS-RETURNED CHECK COUNTS AS A CHECK. pm-scheduler verifies with
`if (upgraded && upgraded.length)` rather than by reading `error`, which is equally valid; an
earlier draft of this detector called it a defect, so the rule accepts either shape.

Self-test: `--selftest`.
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

WRITE_AWAIT = re.compile(r"await\s+(?:db|supabase|_db)\s*\.from\([^)]*\)\s*\.(insert|update|upsert|delete)\(", re.S)
SUCCESS_TOAST = re.compile(r"showToast\(\s*(['\"`])(?P<msg>(?:[^'\"`\\]|\\.){3,120}?)\1\s*(?:,\s*['\"]success['\"]\s*)?\)")
# either shape is a real check: consult the error, or require the rows back
CHECKED = re.compile(r"\berror\b|\berr\b|\.error\b|catch\s*\(|"
                     r"\w+\s*&&\s*\w+\.length|!\s*\w+\s*\|\||\.length\s*\)")


def scan(src: str, label: str = "source") -> list:
    out = []
    for m in WRITE_AWAIT.finditer(src):
        ls = src.rfind("\n", 0, m.start()) + 1
        stmt = src[ls:m.start()]
        window = src[m.end():m.end() + 700]
        t = SUCCESS_TOAST.search(window)
        if not t:
            continue
        if CHECKED.search(window[:t.start()]) or CHECKED.search(stmt):
            continue
        line = src[:m.start()].count("\n") + 1
        out.append(f'{label}:{line} a {m.group(1)} whose result is discarded, then '
                   f'"{t.group("msg")[:60]}" - the refusal would never reach the reader')
    return out


def selftest() -> int:
    ok = True

    def chk(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}: got {got}, want {want}")

    bad = "await db.from('t').delete().eq('id', x); showToast('Rolled back successfully.');"
    chk("a discarded result then a success toast fails", len(scan(bad)), 1)

    good = ("const { error } = await db.from('t').delete().eq('id', x);"
            "if (error) return; showToast('Rolled back successfully.');")
    chk("consulting the error passes", len(scan(good)), 0)

    rows = ("const { data: up } = await db.from('t').update({a:1}).select();"
            "if (up && up.length) { showToast('Done.'); }")
    chk("a rows-returned check also passes", len(scan(rows)), 0)

    err_toast = "await db.from('t').delete().eq('id', x); showToast('That failed.', 'error');"
    chk("an error toast is not a success claim", len(scan(err_toast)), 0)

    live = []
    for f in sorted(glob.glob(str(ROOT / "*.html"))):
        n = Path(f).name
        if n.startswith("_") or "backup" in n or "-test" in n:
            continue
        live += scan(io.open(f, encoding="utf-8", errors="replace").read(), n)
    chk("no page announces an unchecked write", live, [])
    print(f"\n  SELFTEST: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    problems, writes = [], 0
    for f in sorted(glob.glob(str(ROOT / "*.html"))):
        n = Path(f).name
        if n.startswith("_") or "backup" in n or "-test" in n:
            continue
        src = io.open(f, encoding="utf-8", errors="replace").read()
        writes += len(WRITE_AWAIT.findall(src))
        problems += scan(src, n)
    print("a page may not announce a write it never confirmed")
    print(f"  awaited writes: {writes}  ·  announcing success unchecked: {len(problems)}")
    if not problems:
        print("\n  PASS - every announced write was confirmed first.")
        return 0
    print("\n  FAIL - these tell the reader it worked without knowing:")
    for p in problems:
        print(f"    {p}")
    print("\n  supabase-js RESOLVES on a refused write - read the error (or require the rows back)\n"
          "  before saying it worked. A try/catch does not see a refusal.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

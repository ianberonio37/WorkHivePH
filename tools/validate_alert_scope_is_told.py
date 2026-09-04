#!/usr/bin/env python3
"""alert-scope-is-told - T19: hiding a plant alert is a HIVE action, and must say so (2026-08-27).

alert_dismissals is keyed onConflict 'hive_id,alert_key'. There is one row per alert per hive, so
every control that writes it changes what the WHOLE CREW sees - marking handled, snoozing, and
marking seen alike. Nothing about the controls says that. The local state reads `_seen`, the control
is an aria-pressed toggle, and the copy was two words: everything about the surface says personal
bookmark while the write says shared state.

★THE FAILURE THIS PREVENTS is written in dismissAlert's own comment, and it is the one an alert
inbox cannot afford: "a plant alert quietly blinded for the whole crew by someone who thought they
were tidying their own view." That path was fixed when it was written. Its sibling acknowledgeAlert
was not - it announced nothing about scope on the way in, and on the way out (un-marking, which
DELETES the hive's row and returns the alert to unseen for everyone) it said nothing at all.

★THE RULE: every user-facing message on a successful alert_dismissals write must name the scope.
Matched by MEANING across EN and FIL, not a fixed sentence - the platform's copy is bilingual via
_t(en, fil), and a gate that pins wording is a gate that punishes improving it.

Self-test: `--selftest`.
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "alert-hub.html"

WRITE = re.compile(r"\.from\(\s*['\"]alert_dismissals['\"]\s*\)")
# scope, in either language the platform ships
SCOPE = re.compile(r"whole hive|your hive|the hive|everyone|buong hive", re.I)
TOAST = re.compile(r"showToast\(")
LITERAL = re.compile(r"'((?:\\.|[^'\\])*)'|\"((?:\\.|[^\"\\])*)\"")


def messages_near(src: str, at: int, span: int = 3000):
    """User-facing strings announced on a write's SUCCESS path.

    Bounded by the `catch (` that ends the success path, not by a character count. A fixed window
    read as silence here: both announcements sit past a writeAuditLog call and a long comment, so a
    900-char window ended before the toast and reported two correct paths as saying nothing. The
    success path ends where the catch begins, which is a real boundary rather than a guess.
    """
    window = src[at:at + span]
    end = window.find("catch (")
    if end > 0:
        window = window[:end]
    out = []
    for m in TOAST.finditer(window):
        seg = window[m.start():m.start() + 400]
        for lit in LITERAL.finditer(seg):
            s = lit.group(1) or lit.group(2) or ""
            if len(s) >= 10:
                out.append(s)
    return out


def scan_source(src: str):
    """Alert-state writes whose announcement never names the hive."""
    problems = []
    for m in WRITE.finditer(src):
        # only the WRITE paths - a plain read of the table announces nothing and owes nothing
        head = src[m.start():m.start() + 220]
        if not re.search(r"\.(upsert|insert|delete|update)\s*\(", head):
            continue
        said = messages_near(src, m.start())
        if not said:
            problems.append(("silent", src[max(0, m.start() - 120):m.start()].strip()[-60:]))
            continue
        if not any(SCOPE.search(s) for s in said):
            problems.append(("no-scope", "; ".join(said)[:90]))
    return problems


def selftest() -> int:
    ok = True

    def chk(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}: got {got}, want {want}")

    scoped = ("await db.from('alert_dismissals').upsert(row);\n"
              "showToast(_t('Marked seen -> your whole hive sees it as seen.', 'buong hive na.'));")
    chk("a message naming the hive passes", len(scan_source(scoped)), 0)

    bare = ("await db.from('alert_dismissals').upsert(row);\n"
            "showToast(_t('Marked seen', 'Minarkahang nakita'));")
    chk("two words with no scope fails", len(scan_source(bare)), 1)

    silent = "await db.from('alert_dismissals').delete().eq('alert_key', k);\n renderFeed();"
    chk("a silent write fails", len(scan_source(silent)), 1)

    read_only = "const { data } = await db.from('alert_dismissals').select('*');"
    chk("a read owes nothing", len(scan_source(read_only)), 0)

    chk("the live page passes", len(scan_source(io.open(PAGE, encoding='utf-8', errors='replace').read())), 0)
    print(f"\n  SELFTEST: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()

    src = io.open(PAGE, encoding="utf-8", errors="replace").read()
    problems = scan_source(src)
    writes = sum(1 for m in WRITE.finditer(src)
                 if re.search(r"\.(upsert|insert|delete|update)\s*\(", src[m.start():m.start() + 220]))

    print("T19 alert scope is told")
    print(f"  alert_dismissals write paths: {writes}")
    print(f"  announcing hive scope:        {writes - len(problems)}")

    if not problems:
        print("\n  PASS - every control that changes what the crew sees says so.")
        return 0
    print("\n  FAIL - these change shared alert state without saying it is shared:")
    for kind, detail in problems:
        print(f"    [{kind}] {detail}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

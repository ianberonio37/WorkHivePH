#!/usr/bin/env python3
"""report-clobber-guard - a spot-check must never destroy a full sweep's report (2026-08-27).

MEASURED, not hypothesised: prove_retry_path.mjs wrote retry_path_report.json on every run, whether
it had walked 22 pages or 1. A single `--page <fixture>` probe replaced the whole sweep's verdicts
with one UNGRADED row, and the real ones were gone.

★WHY THIS IS WORSE THAN A LOST LOG. tools/bank_prover_reports.py READS these files to bank whole
families, and run_platform_checks registers several of them as a gate's `report`. A truncated report
does not announce itself - it looks like a small run - so a narrowed probe can quietly feed one page
of verdicts into a bank that believed it was getting twenty-two.

★AND IT WAS A KNOWN CLASS THAT NEVER TRAVELLED. prove_journey.mjs carries the fix in its own header,
in these words: "a fixed filename let a one-page test DESTROY a 66-persona run ... A spot-check
should never be able to clobber the run it is checking." That was written for one prover. Twenty-nine
others had the same shape and none of them had the guard. A lesson recorded in one file's comments is
not a lesson the platform has learned; this gate is where it becomes one.

THE RULE: if a prover accepts a narrowing flag (--page / --case / --journeys / --only / --lane /
--family), the path it writes its report to must DEPEND on that flag. A literal filename cannot, so
it is reported. What the guard looks like is not prescribed - a ternary at the write, or a variable
derived from the flag, both satisfy it.

Self-test: `--selftest`.
"""
import glob
import io
import os
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# ★THE GUARD'S OWN DENOMINATOR WAS TOO SMALL (widened 2026-08-27, from a census not a guess).
# It knew six flags. Counting what tools/*.mjs actually declare found provers narrowing by --view (3),
# --phase (2), --persona (2), and one each of --journey, --surface, --scope and --role - none of which
# it could see, so a fixed report path behind any of them was not merely passing, it was never
# examined. That is the same shape as the constant-parked path this gate missed on live_page_journeys:
# a check whose scope is narrower than reality reports zero and means nothing by it.
#
# Only flags that narrow the DENOMINATOR are listed. --limit, --workers, --median, --settle, --out and
# --members were deliberately left out: they tune how a run measures or where it writes, they do not
# shrink WHAT it covers, so a full report from one of them is still a full report.
FLAG_DECL = re.compile(
    r"const\s+(\w+)\s*=\s*\(\(\)\s*=>\s*\{[^}]*?indexOf\('--"
    r"(?:page|case|journeys?|only|lane|family|view|phase|persona|surface|scope|role)'\)")
WRITE = re.compile(r"writeFileSync\(\s*([^,]+?),", re.S)
REPORTISH = re.compile(r"_(?:report|results)\.json")
CONST_LIT = re.compile(r"""\bconst\s+([A-Za-z_$][\w$]*)\s*=\s*['"`]([^'"`]+)['"`]\s*;""")
CONST_ANY = re.compile(r"\bconst\s+([A-Za-z_$][\w$]*)\s*=\s*([^;]*);", re.S)
IDENT = re.compile(r"[A-Za-z_$][\w$]*")


def _const_literals(src: str) -> dict:
    """name -> its literal, only where the name resolves to exactly ONE literal in this file.

    Same safety rule the localStorage key gate learned: a name reused for two different values is
    skipped rather than guessed, because merging them could hide a genuinely bad one.
    """
    seen: dict = {}
    for m in CONST_LIT.finditer(src):
        seen.setdefault(m.group(1), set()).add(m.group(2))
    return {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}


def _flag_derived(src: str, flags: list) -> set:
    """Every name whose assignment reaches a narrowing flag, directly or through other consts."""
    reached = set(flags)
    for _ in range(4):                                 # converges in one or two hops in practice
        grew = False
        for m in CONST_ANY.finditer(src):
            name, rhs = m.group(1), m.group(2)
            if name in reached:
                continue
            if any(re.search(rf"\b{re.escape(d)}\b", rhs) for d in reached):
                reached.add(name)
                grew = True
        if not grew:
            break
    return reached


def scan_source(src: str):
    """Report targets in one prover that cannot vary with its narrowing flag."""
    flags = [m.group(1) for m in FLAG_DECL.finditer(src)]
    if not flags:
        return []
    consts = _const_literals(src)
    derived = _flag_derived(src, flags)
    bad = []
    for m in WRITE.finditer(src):
        target = " ".join(m.group(1).split())
        # ★A PATH PARKED IN A CONSTANT IS STILL THAT PATH (2026-08-27). The pre-filter used to test
        # REPORTISH against the write site's literal TEXT, so `const RESULTS = 'x_results.json'` +
        # `writeFileSync(RESULTS, ...)` matched nothing and was skipped before any flag check ran -
        # silently EXEMPT rather than satisfied, which is a false PASS and the worst kind. That is
        # precisely the shape live_page_journeys.mjs had, and it let a --page run overwrite a
        # 110-journey sweep with 14 rows while this gate reported "0 offenders" over 67 provers.
        if not REPORTISH.search(target):
            resolved = " ".join(consts.get(v, "") for v in IDENT.findall(target))
            if not REPORTISH.search(resolved):
                continue
        # The path must vary with the flag - named at the write, or reached through the consts that
        # build it. Tied to THIS target's names: the old test asked only whether SOME const in the
        # file mentioned a flag, which would clear a target that never touched one.
        if any(re.search(rf"\b{re.escape(v)}\b", target) for v in derived):
            continue
        bad.append(target[:70])
    return bad


def selftest() -> int:
    ok = True

    def chk(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}: got {got}, want {want}")

    narrowing = ("const ONE = (() => { const i = args.indexOf('--page'); return i >= 0 ? args[i + 1] : null; })();\n")
    chk("catches a fixed filename behind a narrowing flag",
        len(scan_source(narrowing + "writeFileSync('x_report.json', JSON.stringify(o));")), 1)
    chk("accepts a ternary at the write site",
        len(scan_source(narrowing + "writeFileSync((ONE ? 'x_report.partial.json' : 'x_report.json'), o);")), 0)
    chk("accepts a variable derived from the flag",
        len(scan_source(narrowing + "const OUT = ONE ? 'x_report.partial.json' : 'x_report.json';\n"
                                    "writeFileSync(path.join(ROOT, OUT), o);")), 0)
    # ★THE SHAPE THAT GOT THROUGH: the path parked in a constant, written as a bare variable. The
    # pre-filter tested the write site's TEXT, saw no ".json" in the word "OUT", and skipped it.
    chk("catches a report path parked in a constant",
        len(scan_source(narrowing + "const OUT = 'x_results.json';\nwriteFileSync(OUT, o);")), 1)
    chk("accepts that constant once it varies with the flag",
        len(scan_source(narrowing + "const NARROW = ONE ? `page-${ONE}` : '';\n"
                                    "const OUT = NARROW ? `x_results.${NARROW}.json` : 'x_results.json';\n"
                                    "writeFileSync(OUT, o);")), 0)
    chk("a constant path in a tool that cannot narrow is not at risk",
        len(scan_source("const OUT = 'x_results.json';\nwriteFileSync(OUT, o);")), 0)
    # The flags added 2026-08-27 need teeth of their own, or the widening is only a claim.
    for flag in ("journey", "view", "persona", "surface", "scope", "role", "phase"):
        decl = ("const ONE = (() => { const i = args.indexOf('--%s'); return i >= 0 ? args[i + 1] : null; })();\n"
                % flag)
        chk(f"--{flag} is recognised as narrowing",
            len(scan_source(decl + "writeFileSync('x_report.json', JSON.stringify(o));")), 1)
    chk("a tuning flag is NOT treated as narrowing",
        len(scan_source("const N = (() => { const i = args.indexOf('--limit'); return i >= 0 ? args[i+1] : null; })();\n"
                        "writeFileSync('x_report.json', JSON.stringify(o));")), 0)
    chk("a tool that cannot narrow is not at risk",
        len(scan_source("writeFileSync('x_report.json', JSON.stringify(o));")), 0)
    chk("a non-report write is out of scope",
        len(scan_source(narrowing + "writeFileSync('scratch.json', JSON.stringify(o));")), 0)
    print(f"\n  SELFTEST: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()

    narrowing, offenders = 0, []
    for f in sorted(glob.glob(str(ROOT / "tools" / "*.mjs"))):
        src = io.open(f, encoding="utf-8", errors="replace").read()
        if not FLAG_DECL.search(src):
            continue
        narrowing += 1
        for target in scan_source(src):
            offenders.append((os.path.basename(f), target))

    print("report-clobber guard — a spot-check must not destroy a full sweep")
    print(f"  provers accepting a narrowing flag: {narrowing}")
    print(f"  writing a report path that cannot vary with it: {len(offenders)}")

    if not offenders:
        print("\n  PASS - every narrowed run writes its own report.")
        return 0

    print("\n  FAIL - these would let a --page/--case probe overwrite a full run's verdicts,")
    print("  which bank_prover_reports.py then reads as if it were the whole sweep:")
    for tool, target in offenders:
        print(f"    {tool:40} -> {target}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

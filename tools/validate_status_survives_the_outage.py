#!/usr/bin/env python3
"""status-survives-the-outage - T71: the page that reports the outage must load during it.

whReadError sends a person to status.html when a read fails on good internet - "is it me or them?"
is the one question a failure state can actually answer. That pointer is only honest if the status
page works when the platform does not.

★TWO WAYS A STATUS PAGE LIES, and this asserts against both:
  1. IT DEPENDS ON WHAT IT REPORTS. A status page that needs the database to render cannot report a
     database outage - it fails exactly when someone finally needs it, and the reader concludes the
     whole product is gone. So status.html must contain no supabase client, no getDb, no table read.
  2. IT IS HARDCODED GREEN. "All systems operational" baked into the markup is a trust signal with no
     living producer behind it - it stays green through the outage and is worse than no page,
     because it actively contradicts what the person is experiencing.

★WHAT IT DOES INSTEAD IS THE RIGHT SHAPE: it pings each edge function's public /health endpoint and
renders one card per service, ambering when a round-trip exceeds the interactive SLO, with a Refresh
to re-check. Live per service, independent of the database - which is precisely why it can still
answer when the database is the thing that is down.

Re-drive: python tools/validate_status_survives_the_outage.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


def check_status_page(src: str, utils_src: str) -> list:
    """The four properties, as a pure function so they can be shown to FAIL.

    ★A GATE THAT CANNOT FAIL IS NOT A CHECK, and this one had no selftest: it read the live page,
    passed, and nothing ever demonstrated it would go red. A resurrection proof is the usual answer,
    but there is no pre-fix world here - status.html was born database-independent and
    health-pinging, verified against its FIRST commit (cbac3136), which passes every check. This is
    a PROACTIVE regression guard rather than a lock on a past fix, and the right teeth for that
    shape are SYNTHETIC negatives: mutate the source in memory and require each property to catch
    it. Recorded because the distinction matters - demanding a git-history resurrection from a gate
    that never had a violation to resurrect is how a good gate gets marked unfinishable.
    """
    failures = []
    code = re.sub(r"<!--.*?-->", " ", src, flags=re.S)
    code = re.sub(r"/\*.*?\*/", " ", code, flags=re.S)

    # 1. it must not depend on the thing it reports
    for pat, what in [(r"createClient\s*\(", "a Supabase client"),
                      (r"\bgetDb\s*\(", "getDb()"),
                      (r"\.from\(\s*['\"]", "a table read")]:
        if re.search(pat, code):
            failures.append(f"status.html uses {what} - a status page that needs the database cannot "
                            f"report a database outage, and fails exactly when someone finally needs it")

    # 2. it must actually check something live
    if not re.search(r"/health", code):
        failures.append("status.html no longer pings any /health endpoint - whatever it shows is not "
                        "a measurement")
    if not re.search(r"fetch\s*\(", code):
        failures.append("status.html makes no request at all, so its state cannot change with reality")

    # 3. and it must not be hardcoded green
    static_green = re.search(r"All systems (?:are )?operational|Everything is (?:fine|working)", code, re.I)
    if static_green:
        failures.append(f"status.html hardcodes '{static_green.group(0)}' - a trust signal with no "
                        f"living producer stays green through the outage and contradicts what the "
                        f"reader is experiencing")

    # 4. the pointer that sends people here must still exist
    if "status.html" not in utils_src:
        failures.append("utils.js no longer points a failed read at status.html - every failure state "
                        "goes back to answering 'is it me or them?' with silence")

    return failures


def main() -> int:
    p = ROOT / "status.html"
    if not p.exists():
        print("FAIL status-survives-the-outage - status.html is gone, and whReadError still sends "
              "people there when a read fails on good internet")
        return 1
    failures = check_status_page(
        io.open(p, encoding="utf-8", errors="replace").read(),
        io.open(ROOT / "utils.js", encoding="utf-8", errors="replace").read())
    if failures:
        print("FAIL status-survives-the-outage:")
        for f in failures:
            print("    - " + f)
        return 1

    print("  status.html: no database dependency · live /health checks per service · not hardcoded · "
          "still linked from whReadError")
    print("PASS status-survives-the-outage - the page that answers 'is it me or them?' can load while "
          "the platform cannot.")
    return 0


def selftest() -> int:
    """One synthetic negative per property, plus the live page, which must stay green."""
    ok = True

    def chk(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}: got {got}, want {want}")

    good = ("<html><script>fetch('/health').then(r=>r.json());</script>"
            "<div id='s'>checking each service…</div></html>")
    utils_ok = "showToast('… open status.html to see whether it is us')"

    chk("a clean status page passes", check_status_page(good, utils_ok), [])
    chk("a page that needs the database fails",
        len(check_status_page(good.replace("fetch(", "createClient('u','k'); fetch("), utils_ok)), 1)
    chk("a page that pings nothing fails",
        len(check_status_page(good.replace("'/health'", "'/'"), utils_ok)), 1)
    chk("a hardcoded green fails",
        len(check_status_page(good.replace("checking each service…", "All systems operational"), utils_ok)), 1)
    chk("losing the pointer in utils.js fails",
        len(check_status_page(good, "showToast('try again later')")), 1)

    live = check_status_page(
        io.open(ROOT / "status.html", encoding="utf-8", errors="replace").read(),
        io.open(ROOT / "utils.js", encoding="utf-8", errors="replace").read())
    chk("the live page still passes", live, [])
    print("\n  SELFTEST: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else main())

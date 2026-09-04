#!/usr/bin/env python3
"""removal-tells-the-worker - T25: being removed from a hive must not arrive as an empty screen.

A supervisor kicks someone. The supervisor's side is a confirm and a roster that shrinks. The
WORKER's side is the one that matters: they open the app and their hive is simply gone. Without a
word, the honest readings available to them are "the app broke" and "my work was deleted", and one
of those is frightening enough to end their use of the product.

★THREE THINGS A REMOVED PERSON NEEDS, and the page says all three: WHAT HAPPENED (removed from the
named hive, by a supervisor - not a glitch), WHAT SURVIVED ("your personal records are still yours",
which is the fear underneath), and WHAT NOW (join another hive or create one). A notice that says
only the first leaves someone assuming the worst about the second.

★AND IT MUST BE HELD LONG ENOUGH TO READ, which is the part usually missed: the page's toast hides
at a fixed 3 seconds, and this notice overrides that to 12. Three seconds is fine for "saved"; it is
not enough for two sentences about your identity and your work, and a message nobody finishes
reading was not delivered. That is the zero-millisecond-refusal lesson wearing a longer coat, so the
duration is asserted as part of the disclosure rather than treated as styling.

Re-drive: python tools/validate_removal_tells_the_worker.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MIN_HOLD_MS = 8000          # two sentences about your identity need more than a "saved" toast


def main() -> int:
    failures = []
    src = io.open(ROOT / "hive.html", encoding="utf-8", errors="replace").read()

    if not re.search(r"wh_removed_notice", src):
        failures.append("nothing carries a removal notice to the worker - they open the app, the hive "
                        "is gone, and the readings left to them are 'the app broke' or 'my work was "
                        "deleted'")

    m = re.search(r"showToast\(\s*_t\(\s*'You were removed from[^']*'", src)
    if not m:
        failures.append("the removal notice no longer says the worker was removed - a hive that "
                        "vanishes without a sentence is indistinguishable from a bug")
    else:
        notice = src[m.start():m.start() + 400]
        if not re.search(r"by a supervisor", notice):
            failures.append("the notice does not say a SUPERVISOR removed them - without an actor it "
                            "reads as a malfunction")
        if not re.search(r"records are still yours|records are still", notice):
            failures.append("the notice does not say their personal records survive - that is the "
                            "fear underneath, and silence about it is read as loss")
        if not re.search(r"join another hive|create your own", notice):
            failures.append("the notice offers no next step - it tells someone their place is gone "
                            "and leaves them there")

    # the hold: a removal notice must outlast the page's ordinary toast
    hold = re.search(r"_toastTimer\s*=\s*setTimeout\([^,]+,\s*(\d+)\s*\)", src)
    if not hold:
        failures.append("the removal notice no longer overrides the toast timer, so it hides at the "
                        "page's fixed 3s - two sentences about your identity and your work, gone "
                        "before they can be read")
    elif int(hold.group(1)) < MIN_HOLD_MS:
        failures.append(f"the removal notice is held {hold.group(1)}ms, under the {MIN_HOLD_MS}ms a "
                        f"two-sentence identity event needs - a message nobody finishes reading was "
                        f"not delivered")

    if failures:
        print("FAIL removal-tells-the-worker:")
        for f in failures:
            print("    - " + f)
        return 1

    print(f"  removal notice: names the hive and the actor · says records survive · offers a next "
          f"step · held {hold.group(1)}ms")
    print("PASS removal-tells-the-worker - a removed worker is told what happened, what they keep, "
          "and what they can do, for long enough to read it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

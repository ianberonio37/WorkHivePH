#!/usr/bin/env python3
"""return-promise-survives-reauth - T8: re-authenticating costs one sign-in, not your place.

When a token expires, session-timeout.js sends the worker to index.html?signin=1&return=<where they
were>, and index.html validates that value before honouring it - an open-redirect guard, and a
correct instinct. But the guard's character class did not include the characters the platform's own
pages WRITE into their URLs.

★THE MEASURED FAILURE: URLSearchParams.set() encodes a space as '+', and audit-log.html mirrors its
filters into the URL - including `actor`, which is a worker's NAME. Round-tripped for real (page
writes filter -> session-timeout captures -> index re-reads): `audit-log.html?actor=Leandro+Marquez`
and `audit-log.html?q=pump+seal` both failed the guard and were dropped IN SILENCE, landing the
supervisor on the dashboard. That is T28's exact scenario - someone mid-investigation into who
changed what - losing their place to a token refresh, with nothing on screen explaining why.

★WHY WIDENING IS SAFE, argued rather than assumed: the guard's real job is to refuse a scheme, a
protocol-relative //, and a foreign absolute path. Its anchor already requires the value to begin
with <name>.html or /workhive/, so '+', ',' and ':' can only ever appear AFTER the ? or # - where a
colon cannot read as a scheme and a plus is just a space. This gate proves both halves rather than
trusting that argument: the real destinations survive AND every attack shape is still refused.

★IT EXTRACTS THE REGEX FROM index.html rather than restating it, because a gate holding its own copy
of the pattern proves only that the copy is fine. All three guards (sign-in, signup, entry bridge)
must agree - a fix that reaches one path and not the others is how this class survives.

Re-drive: python tools/validate_return_promise_survives_reauth.py
"""
import io
import re
import sys
from pathlib import Path
from urllib.parse import quote, parse_qs, urlencode

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# where a worker actually is when the token dies -> (page, params)
REAL = [
    ("audit-log.html", {"actor": "Leandro Marquez"}, "audit log filtered by a worker's NAME"),
    ("audit-log.html", {"q": "pump seal"},           "audit log free-text search"),
    ("audit-log.html", {"action": "kick_member"},    "audit log filtered by action"),
    ("asset-hub.html", {"asset": "084c113b-99c0-45c6-a8e8-b4b8349da46d"}, "an asset deep link"),
    ("community.html", {"post": "1234"},             "a community post"),
    ("pm-scheduler.html", {"filter": "overdue", "view": "today"}, "a filtered PM list"),
    ("inventory.html", {"part": "6205,SKF"},         "a part number containing a comma"),
    ("dayplanner.html", {"date": "2026-08-26"},      "a planned day"),
]

ATTACKS = [
    "//evil.com/x", "https://evil.com/x", "http://evil.com", "javascript:alert(1)",
    "/etc/passwd", "../../secret.html", "evil.com/index.html", "\\\\evil.com\\x",
    "https:/evil.com", "index.html@evil.com",
]


def _js_class_to_py(cls: str) -> str:
    return cls.replace(r"\/", "/")


def main() -> int:
    page = io.open(ROOT / "index.html", encoding="utf-8", errors="replace").read()

    guards = re.findall(
        r"/\^\[A-Za-z0-9\._~\\-\]\+\\\.html\(\[\?#\]\[([^\]]+)\]\*\)\?\$/", page)
    workhive = re.findall(r"/\^\\/workhive\\/\[([^\]]+)\]\*\$/", page)
    if not guards or not workhive:
        print("FAIL return-promise-survives-reauth - could not find the return-to guards in "
              "index.html; they moved or changed shape, so this gate no longer knows what it guards")
        return 1
    if len(set(guards)) != 1 or len(set(workhive)) != 1:
        print(f"FAIL return-promise-survives-reauth - the {len(guards)} return-to guards do NOT agree "
              f"on what they accept ({sorted(set(guards))}). A fix that reaches one path (sign-in, "
              f"signup, entry bridge) and not the others is how a dropped return survives.")
        return 1

    q_cls = _js_class_to_py(guards[0])
    w_cls = _js_class_to_py(workhive[0])
    bare = re.compile(r"^[A-Za-z0-9._~\-]+\.html([?#][" + q_cls + r"]*)?$")
    scoped = re.compile(r"^/workhive/[" + w_cls + r"]*$")

    def accepted(v: str) -> bool:
        return (not v.startswith("//")) and bool(bare.match(v) or scoped.match(v))

    def round_trip(pg: str, params: dict) -> str:
        """page writes filters -> session-timeout captures -> index re-reads ?return="""
        on_page = pg + "?" + urlencode(params)                       # URLSearchParams.set()
        signin = "index.html?signin=1&return=" + quote(on_page, safe="")
        return parse_qs(signin.split("?", 1)[1])["return"][0]

    failures = []
    for pg, params, label in REAL:
        back = round_trip(pg, params)
        if not accepted(back):
            failures.append(f"re-auth would DROP {label} ({back}) - the worker lands on the "
                            f"dashboard having lost their place, with nothing explaining why")
    for bad in ATTACKS:
        if accepted(bad):
            failures.append(f"the guard now ACCEPTS {bad!r} - widening the return-to class has "
                            f"opened a redirect")

    if failures:
        print("FAIL return-promise-survives-reauth:")
        for f in failures:
            print("    - " + f)
        return 1

    print(f"PASS return-promise-survives-reauth - all {len(guards)} guards agree; {len(REAL)} real "
          f"destinations survive the round trip (including the '+'-encoded spaces a worker's name and "
          f"a search term produce) and all {len(ATTACKS)} redirect shapes are still refused.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

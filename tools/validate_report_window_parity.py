#!/usr/bin/env python3
"""report-window-parity - the window on the chip must be the window in the email (2026-08-27, T23).

The four selectable reports cover wildly different periods: Shift Handover is the last EIGHT HOURS,
Failure Digest the last 7 days, Predictive the last NINETY DAYS, PM Overdue a current-status
snapshot. report-sender's chip showed a coloured dot and a label, so a supervisor could send an
8-hour snapshot and a quarter of history to their boss in one email with nothing on screen
distinguishing them.

The window was never unknown. send-report-email's REPORT_META has carried it all along and prints it
INSIDE the delivered email - it simply never reached the person CHOOSING. Putting it on the chip
means the client now holds a SECOND COPY of a server fact, which is the hazard this repo already has
a name for: two windows, one metric name ([[feedback_two_windows_one_metric_name]]). Two copies that
can drift are worse than one copy nobody can see, unless something asserts they agree.

THE RULE: every report id the client offers must exist in REPORT_META, and where the client states a
window it must match the server's string EXACTLY. A phase3 (unselectable) chip may omit its window -
it cannot be sent, so there is nothing to promise.

Self-test: `--selftest`.
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CLIENT = ROOT / "report-sender.html"
SERVER = ROOT / "supabase" / "functions" / "send-report-email" / "index.ts"

# ★MATCH THE ROW, THEN LOOK INSIDE IT. The first version tried to capture the window in the same
# pattern with an OPTIONAL group behind a lazy prefix - `[^}]*?(?:window:\s*'([^']*)')?` - and a lazy
# quantifier in front of an optional group will always prefer to skip the group, so `window` came
# back None for every row even though all four carried one. Its own self-test caught it: five logic
# cases passed while the live check reported four chips "stating no window" that plainly stated one.
CLIENT_ROW = re.compile(r"\{\s*id:\s*'(?P<id>[a-z_]+)'(?P<body>[^}]*)\}")
CLIENT_WINDOW = re.compile(r"window:\s*'(?P<window>[^']*)'")
SERVER_ROW = re.compile(
    r"^\s*(?P<id>[a-z_]+):\s*\{[^}]*?window:\s*\"(?P<window>[^\"]*)\"", re.M)


def parse_client(src: str) -> dict:
    m = re.search(r"const REPORTS = \[(.*?)\];", src, re.S)
    if not m:
        return {}
    out = {}
    for row in CLIENT_ROW.finditer(m.group(1)):
        w = CLIENT_WINDOW.search(row.group("body"))
        out[row.group("id")] = {
            "window": w.group("window") if w else None,
            "phase3": "phase3" in row.group("body"),
        }
    return out


def parse_server(src: str) -> dict:
    return {m.group("id"): m.group("window") for m in SERVER_ROW.finditer(src)}


def compare(client: dict, server: dict) -> list:
    problems = []
    for rid, meta in client.items():
        if rid not in server:
            problems.append(f"the chip offers '{rid}' but send-report-email has no REPORT_META for it")
            continue
        want = server[rid]
        got = meta["window"]
        if got is None:
            if not meta["phase3"] and want:
                problems.append(f"'{rid}' is selectable and covers \"{want}\" but the chip states no window")
            continue
        if got != want:
            problems.append(f"'{rid}' says \"{got}\" on the chip and \"{want}\" in the email")
    return problems


def selftest() -> int:
    ok = True

    def chk(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}: got {got}, want {want}")

    srv = {"a": "last 7 days", "b": "last 8 hours", "c": ""}
    chk("matching windows pass", compare({"a": {"window": "last 7 days", "phase3": False}}, srv), [])
    chk("a drifted window fails",
        len(compare({"a": {"window": "last 30 days", "phase3": False}}, srv)), 1)
    chk("a selectable chip with no window fails",
        len(compare({"a": {"window": None, "phase3": False}}, srv)), 1)
    chk("a phase3 chip may omit its window",
        compare({"c": {"window": None, "phase3": True}}, srv), [])
    chk("an id the server does not know fails",
        len(compare({"zz": {"window": "x", "phase3": False}}, srv)), 1)

    live = compare(parse_client(io.open(CLIENT, encoding="utf-8", errors="replace").read()),
                   parse_server(io.open(SERVER, encoding="utf-8", errors="replace").read()))
    chk("the live pages agree", live, [])
    print(f"\n  SELFTEST: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    if not CLIENT.exists() or not SERVER.exists():
        print("SKIP report-window-parity - report-sender.html or send-report-email not present")
        return 0
    client = parse_client(io.open(CLIENT, encoding="utf-8", errors="replace").read())
    server = parse_server(io.open(SERVER, encoding="utf-8", errors="replace").read())
    problems = compare(client, server)
    stated = sum(1 for m in client.values() if m["window"])
    print("the window on the chip must be the window in the email")
    print(f"  chips: {len(client)}  ·  stating a window: {stated}  ·  server report kinds: {len(server)}"
          f"  ·  disagreements: {len(problems)}")
    if not problems:
        print("\n  PASS - every chip promises the period its email actually covers.")
        return 0
    print("\n  FAIL - the chooser and the email disagree about what is in the report:")
    for p in problems:
        print(f"    {p}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

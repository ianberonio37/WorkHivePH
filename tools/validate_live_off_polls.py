#!/usr/bin/env python3
"""live-off-polls - SL AV3 (2026-10-20): when a page's live channel cannot join - a plant firewall that closes the
websocket, a proxy that strips the upgrade, a realtime outage - the page keeps itself current by checking for changes on
a timer, and it SAYS that it is not live and how often it checks. It is never frozen on its first read while a line on
it still says "updates automatically".

WHAT THE AV3 WALK FOUND (receipts SL1607-SL1620: 14 pages, phone-390 and desktop-1280, each as its row's cast, the
realtime socket closed the moment it opened, then 70 s of watching every read and every word):
  * 9 of the 11 pages with a live channel never read again. A teammate's log entry, a used part, a posted reply, a
    completed PM - none arrived for the whole visit. Only alert-hub and platform-actions (their own 60 s refreshes) and
    audit-log (a 30 s poll, no channel) moved; founder-console is retired and opens none, and asset-hub's channels
    belong to an open asset (walked on one).
  * Three still claimed to be live while frozen: project-manager and hive "updates automatically", community
    "ONLINE NOW" over a presence list nobody could fill; audit-log said "Live updates on" for what is a 30 s poll.
  * The helper that degrades to polling (whRealtimeSubscribe) had no adopters: every page subscribes through rtConn(),
    which only painted a connection state. hive and community re-read on a re-SUBSCRIBED after a drop - with the socket
    closed from the start nothing ever subscribed, so nothing re-read.

WHAT THIS HOLDS (static; the walk is the live floor):
  1. rtConn(onState, ms, opts) - a channel that cannot JOIN (CHANNEL_ERROR, TIMED_OUT, or no answer in `ms`) runs
     opts.reload on whPoll (paused while the tab is hidden) until it is SUBSCRIBED; CLOSED - a page removing its own
     channel - stops that poll and never starts one. _whLiveState says it: the source line's "updates automatically"
     becomes "live updates off - checks for changes every N s" (renderSourceChip says the same for a line drawn again
     while it is off), and one notice, information-toned, with no Reload (a reload cannot open a firewall).
  2. whRealtimeBackfill (hive, community) - the same refetch it runs after a drop runs every 60 s while no channel can
     join (measured 11 and 15 reads per round - alert-hub's own cadence), and stops when one does.
  3. Every page that hands rtConn to a channel names what it keeps current - no bare rtConn() (the shell-missing
     fallback beside whRealtimeBackfill excepted) - and the four pages whose channel carried rows the page merged
     itself carry a quiet re-read of their own (achievements, logbook, marketplace, founder-console's inbox).
  4. The words: community's presence says it is not shown while live is off; audit-log says it refreshes every 30 s;
     founder-console's empty inbox no longer promises "real time".

    python tools/validate_live_off_polls.py
    python tools/validate_live_off_polls.py --self-test
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# (file, regex that must match the code with comments stripped, what breaks without it)
ANCHORS = [
    ("utils.js", r"function rtConn\(onState, ms, opts\)",
     "rtConn takes no options again - a channel that cannot join has nothing to poll and nothing to say"),
    ("utils.js", r"poll = whPoll\(function \(\) \{ return o\.reload\(\); \}, o\.pollMs \|\| 30000, \{ immediate: false \}\);",
     "a channel that cannot join no longer re-reads its page on a timer - the page freezes on its first read"),
    ("utils.js", r"if \(o\) _whLiveState\(o\.name \|\| 'this page', 'offline', o\.pollMs \|\| 30000\);",
     "a channel that cannot join no longer says the page is not live"),
    ("utils.js", r"if \(!settled\) \{ settled = true; degrade\(\); cb\('offline'\); \}",
     "a channel that never answers (no status within `ms`) is not degraded to polling"),
    ("utils.js", r"\} else if \(status === 'CHANNEL_ERROR' \|\| status === 'TIMED_OUT'\) \{\s*settled = true; clearTimeout\(timer\); degrade\(\); cb\('offline'\);",
     "CHANNEL_ERROR / TIMED_OUT no longer start the poll"),
    ("utils.js", r"if \(status === 'SUBSCRIBED'\) \{\s*settled = true; clearTimeout\(timer\); stopPoll\(\);",
     "a channel that joins keeps polling as well"),
    ("utils.js", r"\} else if \(status === 'CLOSED'\) \{\s*settled = true; clearTimeout\(timer\); stopPoll\(\);",
     "CLOSED - a page removing its own channel - does not stop that channel's poll"),
    ("utils.js", r"const NOT_LIVE = 'live updates off - checks for changes every ' \+ secs \+ ' s';",
     "the source line no longer says live updates are off and how often the page checks"),
    ("utils.js", r"window\.__whLiveDownSecs = secs;",
     "a source line drawn again while live is off cannot know it - it says 'updates automatically' again"),
    ("utils.js", r"_whShowNotice\('wh-live-notice', 'Live updates are off on this connection, so this page checks for changes every ' \+ secs",
     "the moment live goes off is no longer said"),
    ("utils.js", r"if \(_ldS && /updates automatically/i\.test\(_fp\)\) _fp = _fp\.replace\(/updates automatically/i, 'live updates off - checks for changes every ' \+ _ldS \+ ' s'\);",
     "renderSourceChip claims 'updates automatically' while the page's live channel is down"),
    ("utils.js", r"id !== 'wh-live-notice'\) el\.appendChild\(_rb\);",
     "the live-off notice offers a Reload that cannot open a firewall"),
    ("utils.js", r"var _info = \(id === 'wh-update-notice' \|\| id === 'wh-live-notice'\);",
     "the live-off notice is painted in the red kept for things that broke"),
    ("utils.js", r"var pollMs = opts\.pollMs \|\| 60000, poll = null, tag = opts\.tag \|\| 'this page';",
     "the backfill pages (hive, community) lost their once-a-minute check"),
    ("utils.js", r"if \(!poll && typeof whPoll === 'function'\) poll = whPoll\(function \(\) \{ return refetch\(\); \}, pollMs, \{ immediate: false \}\);",
     "the backfill pages no longer re-read while no channel can join"),
    ("utils.js", r"else if \(status === 'TIMED_OUT' \|\| status === 'CHANNEL_ERROR'\) \{ rt\.wasDown = true; degrade\(\); \}",
     "a backfill channel that fails to join no longer starts the page's check"),
    ("utils.js", r"if \(!rt\._joined && chans > 0\) degrade\(\);",
     "a backfill page whose channels never answer is never degraded"),
    ("utils.js", r"if \(status === 'SUBSCRIBED'\) \{ rt\._joined = true; recover\(\);",
     "a backfill page keeps polling after its channel joins"),
    # each page names what it keeps current, and how
    ("inventory.html", r"rtConn\(undefined, undefined, \{ name: 'the parts list', reload: \(\) => reload\(\) \}\)",
     "inventory's parts list freezes when live is off"),
    ("pm-scheduler.html", r"rtConn\(undefined, undefined, \{ name: 'PM completions', reload: async \(\) => \{",
     "pm-scheduler freezes when live is off"),
    ("project-manager.html", r"rtConn\(undefined, undefined, \{ name: 'projects', reload: \(\) => \{ loadProjects\(\); if \(_detailId\) refreshDetail\(\); \} \}\)",
     "project-manager freezes when live is off"),
    ("platform-actions.html", r"rtConn\(undefined, undefined, \{ name: 'the feedback inbox', pollMs: 60000 \}\)",
     "platform-actions does not say its inbox is not live (its own 60 s refresh keeps it current)"),
    ("achievements.html", r"rtConn\(undefined, undefined, \{ name: 'your achievements', reload: _pollAchievements \}\)",
     "achievements freezes when live is off"),
    ("achievements.html", r"async function _pollAchievements\(\)", "achievements has no re-read to poll"),
    ("logbook.html", r"rtConn\(undefined, undefined, \{ name: 'team entries', reload: _pollLogbookTeam \}\)",
     "logbook never learns of a teammate's entry when live is off"),
    ("logbook.html", r"async function _pollLogbookTeam\(\)", "logbook has no team-entry check to poll"),
    ("dayplanner.html", r"rtConn\(undefined, undefined, \{ name: 'your schedule', reload: \(\) => \{",
     "dayplanner freezes when live is off"),
    ("asset-hub.html", r"\}, 8000, \{ name: 'this asset', reload: \(\) => \{",
     "an open asset freezes when live is off"),
    ("asset-hub.html", r"rtConn\(undefined, undefined, \{ name: 'sensor readings', reload: \(\) => loadDetailTelemetry\(nodeId\) \}\)",
     "an asset's sensor readings freeze when live is off"),
    ("marketplace.html", r"rtConn\(undefined, undefined, \{ name: 'new listings', reload: _pollNewListings \}\)",
     "marketplace never shows a new listing when live is off"),
    ("marketplace.html", r"async function _pollNewListings\(\)", "marketplace has no new-listing check to poll"),
    # the operator console's inbox is Platform Actions' since OPC (2026-10-22): run there from operator-actions.js, the cut
    # of platform-actions.html's script, it keeps the same 60 s refresh and says so when live is off
    ("operator-actions.js", r"rtConn\(undefined, undefined, \{ name: 'the feedback inbox', pollMs: 60000 \}\)",
     "the operator console's inbox does not say it is not live (the queues' own 60 s refresh keeps it current)"),
    ("alert-hub.html", r"rtConn\(undefined, undefined, \{ name: 'the alert board', pollMs: 60000 \}\)",
     "alert-hub does not say its board is not live (its own 60 s refresh keeps it current)"),
    ("alert-hub.html", r"rtConn\(undefined, undefined, \{ name: 'anomaly signals', pollMs: 60000 \}\)",
     "alert-hub does not say its anomaly signals are not live"),
    ("hive.html", r"whRealtimeBackfill\(refreshAfterDrop, \{ tag: 'hive' \}\)", "hive's channels lost the backfill and its poll"),
    ("community.html", r"whRealtimeBackfill\(refreshAfterDrop, \{ tag: 'community' \}\)", "community's channels lost the backfill and its poll"),
    # the words
    ("community.html", r"function _presenceUnavailable\(on\)", "community's presence has nothing to say when live is off"),
    ("community.html", r"else if \(status === 'CHANNEL_ERROR' \|\| status === 'TIMED_OUT'\) \{\s*setConn\('offline'\);\s*_presenceUnavailable\(true\);",
     "community keeps 'Online now' over a presence list nobody can fill"),
    ("community.html", r"Not shown while live updates are off on this connection\.", "community's presence says nothing true when live is off"),
    ("audit-log.html", r"freshness: 'Live · refreshes every 30 s'", "audit-log's source line claims more than its 30 s poll"),
    ("audit-log.html", r"' PHT · refreshes every 30 s'", "audit-log's footer claims more than its 30 s poll"),
]
# what a page must never say again
FORBIDDEN = [
    ("audit-log.html", r"Live updates on", "audit-log says 'Live updates on' for a 30 s poll"),
    ("audit-log.html", r"freshness: 'Live · updates automatically'", "audit-log's chip claims live updates it does not have"),
    ("founder-console.html", r"land in this tab in real time", "the founder console's empty inbox promises real time"),
]
# a page that hands rtConn() to a channel with no options freezes silently when the channel cannot join; the one bare
# call allowed is the shell-missing fallback beside whRealtimeBackfill (an old utils.js, healed by skew-heal)
BARE_OK = re.compile(r"whRealtimeBackfill\(")


def _code(src: str) -> str:
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    src = re.sub(r"<!--[\s\S]*?-->", "", src)
    return re.sub(r"(?m)(?<![:\"'`\\/])//[^\n]*$", "", src)


def bare_rtconn(name: str, src: str) -> list[str]:
    """Every rtConn( call on a page whose argument list does not name what it keeps current."""
    code = _code(src)
    out = []
    for m in re.finditer(r"\brtConn\(", code):
        i, depth = m.end(), 1
        while i < len(code) and depth:
            depth += {"(": 1, ")": -1}.get(code[i], 0)
            i += 1
        args = code[m.end():i - 1]
        line_start = code.rfind("\n", 0, m.start()) + 1
        line = code[line_start:code.find("\n", m.start())]
        if "name:" in args or BARE_OK.search(line):
            continue
        out.append(f"{name}: rtConn({args.strip()[:40]}) hands a channel no options - it freezes silently when live is off")
    return out


def problems(files: dict[str, str]) -> list[str]:
    bad = []
    for f, rx, why in ANCHORS:
        if not re.search(rx, _code(files.get(f, ""))):
            bad.append(f"{f}: {why}")
    for f, rx, why in FORBIDDEN:
        if re.search(rx, _code(files.get(f, ""))):
            bad.append(f"{f}: {why}")
    for f, src in files.items():
        if f.endswith(".html"):
            bad.extend(bare_rtconn(f, src))
    return bad


def load() -> dict[str, str]:
    names = {a[0] for a in ANCHORS} | {b[0] for b in FORBIDDEN}
    names |= {p.name for p in ROOT.glob("*.html") if "rtConn(" in p.read_text(encoding="utf-8", errors="replace")}
    return {f: (ROOT / f).read_text(encoding="utf-8") for f in sorted(names)}


def run() -> int:
    files = load()
    bad = problems(files)
    if bad:
        for b in bad:
            print("  FAIL " + b)
        print(f"FAIL live-off-polls - {len(bad)} problem(s)")
        return 1
    pages = sum(1 for f, s in files.items() if f.endswith(".html") and "rtConn(" in s)
    print(f"PASS live-off-polls - a live channel that cannot join polls its page and says it is not live (rtConn and the "
          f"hive/community backfill), {pages} subscribing pages each name what they keep current, and no line claims "
          f"updates it does not have; {len(ANCHORS)} anchors hold")
    return 0


def self_test() -> int:
    ok = True

    def expect(name, cond):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + name)
        ok = ok and cond
    files = load()
    expect("the real tree passes", not problems(files))

    def mut(f, a, b):
        m = dict(files)
        assert a in m[f], (f, a[:60])
        m[f] = m[f].replace(a, b, 1)
        return bool([x for x in problems(m) if x.startswith(f + ":")])
    expect("CHANNEL_ERROR no longer degrading fails", mut("utils.js",
        "settled = true; clearTimeout(timer); degrade(); cb('offline');\n    } else if (status === 'CLOSED')",
        "settled = true; clearTimeout(timer); cb('offline');\n    } else if (status === 'CLOSED')"))
    expect("CLOSED starting a poll fails", mut("utils.js",
        "} else if (status === 'CLOSED') {\n      settled = true; clearTimeout(timer); stopPoll();",
        "} else if (status === 'CLOSED') {\n      settled = true; clearTimeout(timer); degrade();"))
    expect("the source line back to 'updates automatically' fails", mut("utils.js",
        "const NOT_LIVE = 'live updates off - checks for changes every ' + secs + ' s';",
        "const NOT_LIVE = 'updates automatically';"))
    expect("a redrawn source line ignoring live-off fails", mut("utils.js",
        "if (_ldS && /updates automatically/i.test(_fp))", "if (false && _ldS)"))
    expect("the backfill without its poll fails", mut("utils.js",
        "else if (status === 'TIMED_OUT' || status === 'CHANNEL_ERROR') { rt.wasDown = true; degrade(); }",
        "else if (status === 'TIMED_OUT' || status === 'CHANNEL_ERROR') { rt.wasDown = true; }"))
    expect("a page handing rtConn() bare to its channel fails", mut("inventory.html",
        "rtConn(undefined, undefined, { name: 'the parts list', reload: () => reload() })", "rtConn()"))
    expect("a NEW page subscribing bare fails", bool(bare_rtconn("new-page.html", "db.channel('x').on('postgres_changes', {}, f).subscribe(rtConn());")))
    expect("the shell-missing fallback stays allowed", not bare_rtconn("hive.html",
        "const _rtBackfill = (typeof whRealtimeBackfill === 'function') ? whRealtimeBackfill(r, { tag: 'hive' }) : (typeof rtConn === 'function' ? rtConn() : undefined);"))
    expect("a commented-out bare call is not a call", not bare_rtconn("x.html", "// rtConn() guards the silent freeze\n"))
    expect("audit-log claiming live again fails", mut("audit-log.html",
        "freshness: 'Live · refreshes every 30 s'", "freshness: 'Live · updates automatically'"))
    expect("community's presence claim back fails", mut("community.html",
        "setConn('offline');\n          _presenceUnavailable(true);", "setConn('offline');"))
    expect("the operator console's inbox without its poll fails", mut("operator-actions.js",
        "{ name: 'the feedback inbox', pollMs: 60000 }", "{ name: 'the feedback inbox' }"))
    print("PASS self-test" if ok else "FAIL self-test")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else run())

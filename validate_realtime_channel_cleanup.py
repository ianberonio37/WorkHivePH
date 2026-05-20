"""
Realtime Channel Cleanup Validator (L0, ratcheted).
=====================================================
Every `db.channel(...)` opened on a page should have:
  - A matching `db.removeChannel(...)` (explicit cleanup), OR
  - A `beforeunload` / unmount listener that removes channels.

Without cleanup, navigating between pages leaks WebSocket connections;
Supabase free-tier hits its 200-channel limit and silently stops
delivering events. Hard to debug because the bug appears only after
heavy SPA-style navigation.

Output: realtime_channel_cleanup_report.json. Exit 1 on regression.
Allow with `// channel-cleanup-allow: <reason>` near the channel.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "realtime_channel_cleanup_report.json"
BASELINE_PATH = ROOT / "realtime_channel_cleanup_baseline.json"

PAGES = [
    "index.html", "hive.html", "logbook.html", "inventory.html",
    "pm-scheduler.html", "analytics.html", "analytics-report.html",
    "skillmatrix.html", "community.html", "public-feed.html",
    "marketplace.html", "marketplace-seller.html", "dayplanner.html",
    "engineering-design.html", "assistant.html", "report-sender.html",
    "platform-health.html", "project-manager.html", "integrations.html",
    "ph-intelligence.html", "project-report.html", "predictive.html",
    "ai-quality.html", "plant-connections.html", "achievements.html",
    "asset-hub.html", "shift-brain.html", "alert-hub.html",
    "audit-log.html", "voice-journal.html",
]

CHANNEL_RE = re.compile(r"""\bdb\.channel\(""")
REMOVE_RE  = re.compile(r"""\bdb\.removeChannel\(""")
UNMOUNT_RE = re.compile(r"""\b(?:beforeunload|pagehide|removeAllChannels)\b""")
ALLOW_RE = re.compile(r"channel-cleanup-allow", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


# Sentinel binding: name the L2 test `test('realtime_channel_cleanup: ...')` for coverage credit.
CHECK_NAMES = ["realtime_channel_cleanup"]


def main() -> int:
    per_page = []
    total_channels = 0
    total_unsafe = 0

    for name in PAGES:
        page = ROOT / name
        if not page.exists(): continue
        body = HTML_COMMENT_RE.sub("", page.read_text(encoding="utf-8", errors="replace"))
        channels = list(CHANNEL_RE.finditer(body))
        removes  = list(REMOVE_RE.finditer(body))
        unmounts = list(UNMOUNT_RE.finditer(body))
        n_channels = len(channels)
        n_removes  = len(removes)
        has_unmount = bool(unmounts)
        total_channels += n_channels

        # Unsafe: page opens channels AND has no removeChannel + no unmount hook
        if n_channels > 0 and n_removes == 0 and not has_unmount:
            # Check allow window — any allow marker anywhere on the page
            if not ALLOW_RE.search(body):
                total_unsafe += 1
                per_page.append({"page": name, "channels": n_channels,
                                 "removes": 0, "has_unmount": False})
                continue
        per_page.append({"page": name, "channels": n_channels,
                         "removes": n_removes, "has_unmount": has_unmount})

    drifted = [p for p in per_page if p["channels"] > 0 and p["removes"] == 0 and not p["has_unmount"]]

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("unsafe", 0)
        except Exception: baseline = 0
    else:
        baseline = len(drifted)
        BASELINE_PATH.write_text(json.dumps({"unsafe": baseline, "established": True}, indent=2), encoding="utf-8")
    if len(drifted) < baseline:
        baseline = len(drifted)
        BASELINE_PATH.write_text(json.dumps({"unsafe": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"pages_scanned": len(per_page), "total_channels": total_channels,
                    "unsafe_pages": len(drifted), "baseline": baseline},
        "per_page": per_page,
    }, indent=2), encoding="utf-8")

    print(f"\nRealtime Channel Cleanup Validator (L0)")
    print("=" * 56)
    print(f"  pages scanned:    {len(per_page)}")
    print(f"  total channels:   {total_channels}")
    print(f"  unsafe pages:     {len(drifted)}  (baseline: {baseline})")
    if not drifted:
        print("\n  PASS — every page with channels has cleanup hooks.")
        return 0
    for d in drifted[:15]:
        print(f"  {d['page']}  channels={d['channels']}  removeChannel=0  no beforeunload/pagehide")
    return 1 if len(drifted) > baseline else 0


if __name__ == "__main__":
    sys.exit(main())

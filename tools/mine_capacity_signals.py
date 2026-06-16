"""
Capacity / Connection-Signal Substrate Miner (Maturity Phase 1, 2026-06-16).
============================================================================
Closes the (LB, G-1.5) cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4.

The Load-Balancing & Scaling layer's dominant failure mode (study §2) is
"connection saturation; realtime channel exhaustion at 1000". You cannot
ratchet what you cannot see — so this miner surfaces the SHAPE of the
platform's connection/scaling load BEFORE it saturates:

  - realtime channel subscriptions per surface   (each = a held connection)
  - subscribe() without a matching teardown        (leak → channel exhaustion)
  - unbounded select('*')                          (payload amplification at scale)

It is the substrate (shape) layer that feeds the (LB, GH) saturation ratchet
(validate_connection_pool_saturation.py) and the (LB, G-1) discovery gate
(validate_connection_surface_discovery.py).

Inputs:
  *.html + *.js at repo root (the client app surface)

Output:
  capacity_signals_report.json

Exit code:
  0  always (informational miner — the SHAPE layer, not a gate)
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "capacity_signals_report.json"

CHECK_NAMES = ["capacity_signals"]

# Directories we never scan (vendored / generated / server-side).
SKIP_DIRS = {"node_modules", "tools", "tests", ".tmp", ".git", "test-data-seeder",
             "supabase", "python-api", "sentinels", "docs", "venv"}

CHANNEL_RE     = re.compile(r"\.channel\s*\(")
SUBSCRIBE_RE   = re.compile(r"\.subscribe\s*\(")
TEARDOWN_RE    = re.compile(r"\.removeChannel\s*\(|\.unsubscribe\s*\(")
UNBOUNDED_RE   = re.compile(r"\.select\s*\(\s*['\"]\*['\"]\s*\)")
# strip line comments so a commented example doesn't inflate the shape
LINE_COMMENT_RE = re.compile(r"^\s*(//|\*|/\*)")


def _client_files() -> list[Path]:
    out: list[Path] = []
    for p in sorted(ROOT.glob("*.html")) + sorted(ROOT.glob("*.js")):
        out.append(p)
    # one level of app subdirs (js/, assets/) if they exist — never the skip set
    for sub in ROOT.iterdir():
        if sub.is_dir() and sub.name not in SKIP_DIRS and not sub.name.startswith("."):
            for p in sorted(sub.glob("*.js")):
                out.append(p)
    return out


def _scan(text: str) -> dict:
    channels = subscribes = teardowns = unbounded = 0
    for raw in text.splitlines():
        if LINE_COMMENT_RE.match(raw):
            continue
        channels  += len(CHANNEL_RE.findall(raw))
        subscribes += len(SUBSCRIBE_RE.findall(raw))
        teardowns += len(TEARDOWN_RE.findall(raw))
        unbounded += len(UNBOUNDED_RE.findall(raw))
    return {"channels": channels, "subscribes": subscribes,
            "teardowns": teardowns, "unbounded_selects": unbounded}


def main() -> int:
    surfaces: list[dict] = []
    tot = {"channels": 0, "subscribes": 0, "teardowns": 0, "unbounded_selects": 0}
    files_scanned = 0

    for f in _client_files():
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        files_scanned += 1
        s = _scan(text)
        for k in tot:
            tot[k] += s[k]
        if s["subscribes"] > 0 or s["channels"] > 0:
            leak = s["subscribes"] > s["teardowns"]
            surfaces.append({
                "file": str(f.relative_to(ROOT)).replace("\\", "/"),
                **s,
                "leak_risk": leak,
            })

    leak_surfaces = [x for x in surfaces if x["leak_risk"]]
    out = {
        "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files_scanned": files_scanned,
        "totals": {
            **tot,
            "realtime_surfaces": len(surfaces),
            "leak_risk_surfaces": len(leak_surfaces),
        },
        "surfaces": sorted(surfaces, key=lambda x: (-x["subscribes"], x["file"])),
    }
    REPORT.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"Capacity-signals miner: {files_scanned} client files scanned.")
    print(f"  realtime surfaces (channel/subscribe): {len(surfaces)}")
    print(f"  channels={tot['channels']} subscribes={tot['subscribes']} teardowns={tot['teardowns']} unbounded select('*')={tot['unbounded_selects']}")
    print(f"  leak-risk surfaces (subscribe > teardown): {len(leak_surfaces)}")
    for x in leak_surfaces[:8]:
        print(f"    - {x['file']}: {x['subscribes']} subscribe / {x['teardowns']} teardown")
    print(f"  See: {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

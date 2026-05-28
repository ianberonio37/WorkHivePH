"""
Cache-Name Drift Miner (L-1, P1 roadmap 2026-05-27).
========================================================
Closes the (CA, G-1) cell from COMPREHENSIVE_STUDY_FULLSTACK_GATE.md §4.

Detects "SHELL_FILE changed but sw.js CACHE_NAME wasn't bumped" patterns
BEFORE the PWA gate FAILs. PWA staleness is the single most recurring
gate FAIL (it's the only remaining FAIL across 5 flywheel turns). This
miner surfaces the drift proactively so the next sw.js bump can include
ALL recent SHELL_FILE changes in one re-prime cycle.

Inputs:
  sw.js                       (parse CACHE_NAME + SHELL_FILES array)
  git log on each SHELL_FILE  (last-commit time vs sw.js last-commit time)

Output:
  cache_name_drift_report.json

Exit code:
  0  always (informational miner)
"""
from __future__ import annotations
import io, json, re, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SW   = ROOT / "sw.js"
REPORT = ROOT / "cache_name_drift_report.json"

CACHE_NAME_RE = re.compile(r"const\s+CACHE_NAME\s*=\s*['\"]([^'\"]+)['\"]")
SHELL_FILES_RE = re.compile(r"const\s+SHELL_FILES\s*=\s*\[([\s\S]*?)\];")
FILE_ENTRY_RE = re.compile(r"['\"]([./][^'\"\n]+)['\"]")


def git_last_commit_ts(path: Path) -> str | None:
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", str(path.relative_to(ROOT))],
            cwd=str(ROOT), capture_output=True, text=True, timeout=10,
        )
        return r.stdout.strip() or None
    except Exception:
        return None


def main() -> int:
    if not SW.exists():
        REPORT.write_text(json.dumps({"error": "sw.js missing"}), encoding="utf-8")
        return 0
    text = SW.read_text(encoding="utf-8", errors="replace")
    m_name = CACHE_NAME_RE.search(text)
    m_shell = SHELL_FILES_RE.search(text)
    cache_name = m_name.group(1) if m_name else None

    sw_ts = git_last_commit_ts(SW)
    shell_files: list[str] = []
    if m_shell:
        for em in FILE_ENTRY_RE.finditer(m_shell.group(1)):
            shell_files.append(em.group(1).lstrip("./"))

    drift_rows: list[dict] = []
    for f in shell_files:
        p = ROOT / f
        if not p.exists(): continue
        ts = git_last_commit_ts(p)
        if not ts or not sw_ts: continue
        if ts > sw_ts:
            drift_rows.append({
                "file":           f,
                "file_commit_ts": ts,
                "sw_commit_ts":   sw_ts,
            })

    out = {
        "scanned_at":         datetime.now(timezone.utc).isoformat(),
        "cache_name":         cache_name,
        "sw_commit_ts":       sw_ts,
        "shell_file_count":   len(shell_files),
        "drift_count":        len(drift_rows),
        "drift_files":        drift_rows,
    }
    REPORT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Cache-name drift miner: CACHE_NAME={cache_name}, {len(shell_files)} SHELL_FILES scanned.")
    print(f"  Drift (files committed AFTER sw.js): {len(drift_rows)}")
    if drift_rows:
        print(f"  → bump CACHE_NAME on next commit to re-prime ({len(drift_rows)} file(s) stale)")
    print(f"  See: {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

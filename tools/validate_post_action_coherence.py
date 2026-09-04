#!/usr/bin/env python3
"""
validate_post_action_coherence.py — MK12: after a write succeeds, the page must not contradict itself.

BORN FROM THE WALK (the roadmap's spoke-5 rule: a harvest refills the queue). Saving a marketplace
search toasted "Search saved." while the counter immediately beside it still read 0, and stayed 0 until
a full page reload. The handler refreshed the SHEET and never called updateSavedSearchBadge(), which
already existed. Nothing was broken in the write; the page simply disagreed with its own receipt, and a
receipt contradicted by the number next to it teaches the user to trust neither.

THE RULE: a handler that performs a client WRITE and then tells the user it SUCCEEDED must also refresh
the derived surfaces it just invalidated — a render/reload/update/refresh call, or an explicit local
state update. A success message with no refresh anywhere leaves the page showing pre-write truth.

WHY IT IS A HEURISTIC, HONESTLY: some handlers legitimately need no refresh — the write's only visible
effect IS the toast (a "report sent" with nothing on screen derived from it), or the page navigates
away immediately, or the surface is realtime-subscribed and updates itself. Those are recognised and
skipped rather than counted, because a gate that cries wolf on correct code gets ignored, which is
worse than not having it. The forward-only baseline holds the rest.

Static + offline. Self-test: `--selftest`.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "post_action_coherence_baseline.json"
GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"

SKIP_SUFFIXES = ("-test.html", ".backup.html", ".backup2.html")
SKIP_DIRS = {".emoji_bak", ".hexvar_bak", ".leftover_bak", ".tmp", "radbak", "radbak2", "learn", "node_modules"}

WRITE_RE   = re.compile(r"\.(insert|upsert|update|delete)\s*\(|\.rpc\s*\(")
# A message that asserts the write LANDED (not a neutral status line).
SUCCESS_RE = re.compile(r"showToast\(\s*[`'\"][^`'\"]*\b(saved|added|created|updated|posted|sent|removed|deleted|approved|verified|resolved|published)\b",
                        re.I)
# "saved offline / will sync / showing saved entries only" announce a DEGRADED or QUEUED
# state, not a committed write, so leaving derived surfaces alone is correct.
DEGRADED_RE = re.compile(r"offline|will sync|unavailable|queued|reconnect", re.I)
# Any re-derivation of what the write changed.
# `sync*` earns its place here: syncHeartIcons() re-derives the heart state from _watchlist and is a
# genuine refresh. The self-test caught its absence — the real marketplace file was passing only because
# an unrelated updateCountBadges() happened to sit inside the scan window, which is passing by accident.
REFRESH_RE = re.compile(
    r"\b(render\w*|reload\w*|refresh\w*|sync\w*|update\w*Badge|update\w*Count|load\w*|fetch\w*|open\w+Sheet|"
    r"\w+\.textContent\s*=|\w+\.innerHTML\s*=|location\.reload|location\.href\s*=)", re.I)
# Legitimate reasons a handler needs no local refresh.
EXEMPT_RE  = re.compile(r"location\.href\s*=|location\.assign|window\.open|\.reset\(\)|"
                        r"realtime|subscribe\(|coherence-allow", re.I)


def _block(src: str, start: int) -> str:
    """Balanced-brace slice of the enclosing function body, from its opening brace."""
    depth, i, n = 0, start, len(src)
    while i < n:
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1
    return src[start:start + 4000]


def scan_source(src: str) -> list[str]:
    """Handlers that write, claim success, and never re-derive anything."""
    out = []
    for m in SUCCESS_RE.finditer(src):
        # Look back for the enclosing try/handler: a window generous enough to hold the write.
        lo = max(0, m.start() - 2500)
        window = src[lo:m.start()]
        if not WRITE_RE.search(window):
            continue                                  # the toast is not about a write
        if DEGRADED_RE.search(src[m.start():m.start() + 160]):
            continue                                  # a degraded/queued notice, not a commit receipt
        # Look at the whole surrounding region for a refresh (before OR after the toast).
        # 1200 -> 2400 (2026-08-25): T10's defer-path additions (embed guard + comments) pushed
        # pm-scheduler's closeSheet/renderDetail 2,077 chars past its mirror-failed toast — the
        # refresh was ALWAYS there; the ruler was short (the fixed-window lesson).
        after = src[m.start():min(len(src), m.start() + 2400)]
        region = window + after
        if EXEMPT_RE.search(region):
            continue                                  # navigates away / resets / realtime-backed
        # A refresh BEFORE the toast is the optimistic-UI pattern and is BETTER than one after.
        if REFRESH_RE.search(region):
            continue
        out.append(re.sub(r"\s+", " ", src[m.start():m.start() + 80]))
    return out


def scan_all() -> dict:
    per = {}
    for p in sorted(ROOT.glob("*.html")):
        if p.name.endswith(SKIP_SUFFIXES) or any(x in p.parts for x in SKIP_DIRS):
            continue
        hits = scan_source(p.read_text(encoding="utf-8", errors="replace"))
        if hits:
            per[p.name] = hits
    return per


def selftest() -> int:
    ok = True

    def chk(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {GREEN+'PASS'+RESET if good else RED+'FAIL'+RESET}  {label}: got {got}, want {want}")

    # The live defect this class was born from.
    bad = "await db.from('t').insert(r); showToast('Search saved.', 'success');"
    chk("flags a success with no re-derivation", len(scan_source(bad)), 1)

    fixed = ("await db.from('t').insert(r); showToast('Search saved.', 'success'); "
             "openSavedSearchesSheet(); updateSavedSearchBadge();")
    chk("accepts a success that refreshes", len(scan_source(fixed)), 0)

    nav = "await db.from('t').insert(r); showToast('Listing posted.', 'success'); location.href = 'x.html';"
    chk("exempts a handler that navigates away", len(scan_source(nav)), 0)

    neutral = "await db.from('t').insert(r); showToast('Working on it', 'info');"
    chk("ignores a non-success message", len(scan_source(neutral)), 0)

    nowrite = "showToast('Saved.', 'success');"
    chk("ignores a success with no write behind it", len(scan_source(nowrite)), 0)

    optimistic = ("_watchlist.add(id); syncHeartIcons(id); await db.from('w').insert(r); "
                  "showToast('Saved to watchlist.', 'success');")
    chk("accepts an OPTIMISTIC refresh made before the write", len(scan_source(optimistic)), 0)

    degraded = "await db.from('t').upsert(r); showToast('Saved offline, will sync when you reconnect.');"
    chk("ignores a degraded/queued notice", len(scan_source(degraded)), 0)
    print(f"\n  SELFTEST: {GREEN+'PASS'+RESET if ok else RED+'FAIL'+RESET}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    per = scan_all()
    total = sum(len(v) for v in per.values())
    base = json.loads(BASELINE.read_text(encoding="utf-8")).get("total", total) if BASELINE.exists() else total
    if not BASELINE.exists():
        BASELINE.write_text(json.dumps({"total": total}, indent=2), encoding="utf-8")

    print(f"{BOLD}MK12 post-action coherence — a success message must not outrun the page{RESET}")
    print(f"  pages with a success-toast that re-derives nothing: {len(per)}")
    for name, hits in per.items():
        print(f"  {RED}HIT {RESET} {name}: {len(hits)}")
        for h in hits[:2]:
            print(f"        {h}")
    if "--accept" in sys.argv:
        BASELINE.write_text(json.dumps({"total": total}, indent=2), encoding="utf-8")
        print(f"  {GREEN}ACCEPTED{RESET}  baseline -> {total}")
        return 0
    if total > base:
        print(f"  {RED}FAIL{RESET}  rose {base} -> {total}: a new write claims success without refreshing")
        return 1
    print(f"  {GREEN}PASS{RESET}  {total} (baseline {base})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

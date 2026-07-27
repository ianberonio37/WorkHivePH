#!/usr/bin/env python3
"""
validate_reachable_capability.py — MK13: a surface must not imply a capability nothing can produce.

BORN FROM THE WALK. Both admin consoles rendered "No open disputes." — which reads as "none right now,
but there could be." On a contact-only marketplace no buyer can EVER file one: the dispute flow left
with the payment rail, and `marketplace_disputes` has no client insert path anywhere in the app. So the
queue was not empty, it was unreachable, and the empty state quietly asserted a capability the platform
does not have. Same family as an unbacked rating: the interface claiming something the system cannot
deliver.

THE RULE: if a page renders a LIST from table T and shows a "nothing here yet" state for it, then some
client path must be able to INSERT into T — otherwise the empty state must say the queue is closed
rather than merely empty.

HOW IT DECIDES, and its honest limits: it reads which tables each page SELECTs and which tables the
whole app INSERTs into. A table that is read-and-listed but never written by ANY page is unreachable
from the UI. Server-only tables are the obvious false positive — a queue filled by a trigger, an edge
function or a cron is legitimately unwritable from the client — so a table is only reported when the
page ALSO shows an empty state that implies future arrivals, and an explicit allowlist carries the ones
we have deliberately reviewed.

Static + offline. Self-test: `--selftest`.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "reachable_capability_baseline.json"
GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"

SKIP_SUFFIXES = ("-test.html", ".backup.html", ".backup2.html")
SKIP_DIRS = {".emoji_bak", ".hexvar_bak", ".leftover_bak", ".tmp", "radbak", "radbak2", "learn", "node_modules"}

FROM_RE   = re.compile(r"\.from\(\s*['\"]([a-z0-9_]+)['\"]\s*\)", re.I)
INSERT_RE = re.compile(r"\.from\(\s*['\"]([a-z0-9_]+)['\"]\s*\)\s*(?:\r?\n\s*)*\.(insert|upsert)\s*\(", re.I)
# An empty state that promises future arrivals rather than declaring the queue closed.
PROMISE_RE = re.compile(
    r"(no\s+(open\s+)?\w[\w\s]{0,24}(yet|so far)?\b[^<]{0,60}?)(will appear|appear here|show up here|"
    r"when (they|buyers|workers|you)|nothing to review|none right now)", re.I)

# Tables whose rows arrive from the SERVER by design (trigger / edge fn / cron), reviewed once and
# recorded here so the gate does not re-litigate them every run.
SERVER_FED_ALLOW = {
    "analytics_events", "ai_cost_log", "ai_audit_log", "client_errors", "hive_audit_log",
    "analytics_snapshots", "db_size_history", "ops_artifact_metrics", "agent_memory",
    "agent_episodic_memory", "failure_alerts", "notifications",
    # Reviewed 2026-07-24 during the MK13 sweep — each is genuinely written off-client:
    "agentic_rag_traces",             # written by the RAG edge functions as they answer
    "equipment_reading_templates",    # migration-seeded catalog (see the catalog-tables rule: these are
                                      # INSERT-only from migrations and must never be in RESET_TABLES)
    "parts_staging_recommendations",  # produced by the scheduled parts-staging agent
}


def _pages():
    for p in sorted(ROOT.glob("*.html")):
        if p.name.endswith(SKIP_SUFFIXES) or any(x in p.parts for x in SKIP_DIRS):
            continue
        yield p


def analyse(sources: dict) -> list[dict]:
    """sources: {page_name: html}. Returns unreachable-but-promised findings."""
    written = set()
    for src in sources.values():
        written |= {t.lower() for t, _ in INSERT_RE.findall(src)}

    out = []
    for name, src in sources.items():
        if not PROMISE_RE.search(src):
            continue                                   # no forward-looking empty state on this page
        read = {t.lower() for t in FROM_RE.findall(src)}
        for t in sorted(read - written):
            if t in SERVER_FED_ALLOW or t.startswith("v_"):
                continue                               # server-fed, or a view (never client-written)
            out.append({"page": name, "table": t})
    return out


def selftest() -> int:
    ok = True

    def chk(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {GREEN+'PASS'+RESET if good else RED+'FAIL'+RESET}  {label}: got {got}, want {want}")

    # The live defect: a listed table nothing can insert into, with a forward-looking empty state.
    bad = {"admin.html": "db.from('marketplace_disputes').select('*'); '<div>No open disputes. They will appear here.</div>'"}
    chk("flags an unreachable queue that promises arrivals", len(analyse(bad)), 1)

    # Same table, but some page CAN write it -> reachable, so not a finding.
    reachable = {
        "admin.html": "db.from('tickets').select('*'); '<div>No tickets yet. They will appear here.</div>'",
        "file.html":  "db.from('tickets').insert([r]);",
    }
    chk("accepts a queue some page can write", len(analyse(reachable)), 0)

    # Honest closed-queue wording makes no promise, so nothing to flag.
    honest = {"admin.html": "db.from('marketplace_disputes').select('*'); '<div>No disputes, and none can arrive.</div>'"}
    chk("accepts an honestly-closed queue", len(analyse(honest)), 0)

    server = {"a.html": "db.from('analytics_events').select('*'); '<div>No events yet. They will appear here.</div>'"}
    chk("exempts a reviewed server-fed table", len(analyse(server)), 0)

    view = {"a.html": "db.from('v_marketplace_listings_truth').select('*'); '<div>No rows yet. They will appear here.</div>'"}
    chk("exempts a view", len(analyse(view)), 0)
    print(f"\n  SELFTEST: {GREEN+'PASS'+RESET if ok else RED+'FAIL'+RESET}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    sources = {p.name: p.read_text(encoding="utf-8", errors="replace") for p in _pages()}
    findings = analyse(sources)
    total = len(findings)
    base = json.loads(BASELINE.read_text(encoding="utf-8")).get("total", total) if BASELINE.exists() else total
    if not BASELINE.exists():
        BASELINE.write_text(json.dumps({"total": total}, indent=2), encoding="utf-8")

    print(f"{BOLD}MK13 reachable capability — an empty state must not promise what nothing can produce{RESET}")
    print(f"  pages scanned: {len(sources)}   findings: {total}")
    for f in findings[:12]:
        print(f"  {RED}HIT {RESET} {f['page']}: lists '{f['table']}', which no client path inserts into")
    if "--accept" in sys.argv:
        BASELINE.write_text(json.dumps({"total": total}, indent=2), encoding="utf-8")
        print(f"  {GREEN}ACCEPTED{RESET}  baseline -> {total}")
        return 0
    if total > base:
        print(f"  {RED}FAIL{RESET}  rose {base} -> {total}")
        return 1
    print(f"  {GREEN}PASS{RESET}  {total} (baseline {base})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
followup-queue-wiring — L0 ratchet for the Prospective layer (layer 06) of the
AI Agent Memory Stack (Turn 6 of the memory-stack flywheel).

Asserts the per-(hive,worker) deferred follow-up queue is wired end to end: the
agent_followups store exists with locked (non-open) RLS, the matcher module
enqueues (capped) + recalls only DUE items (and marks them surfaced), and
ai-gateway both surfaces due follow-ups into context and enqueues new ones from
the specialist envelope. Sibling to episodic/verified-state/cold-archive/
semantic-fact/skill-library wiring. Forward-only: baseline 0 issues.

  W01  _shared/followups.ts exists + exports enqueue/recall/format + normalizeFollowup
  W02  migration creates agent_followups (status CHECK) with NON-open RLS (no USING(true))
  W03  recall is due-filtered (pending + due_at <= now + limit) and marks rows surfaced
  W04  enqueue caps the batch + enforces a per-worker pending cap + validates via normalizeFollowup
  W05  ai-gateway imports the queue, declares FOLLOWUP_AGENTS, surfaces due items + enqueues envelope followups
  W06  matcher is scope-guarded + bounded (clampDueDays window; [] on no-scope)
"""
from __future__ import annotations
import os, sys, glob

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

MODULE  = os.path.join("supabase", "functions", "_shared", "followups.ts")
GATEWAY = os.path.join("supabase", "functions", "ai-gateway", "index.ts")
MIG_DIR = os.path.join("supabase", "migrations")


def _flat(s: str) -> str: return s.replace(" ", "").replace("\n", "")

def _strip_sql_comments(s: str) -> str:
    # Drop `-- ...` line comments so a token check doesn't false-positive on
    # explanatory prose (Turn-3 lesson: forbidden-token greps trip on comments).
    out = []
    for line in s.splitlines():
        i = line.find("--")
        out.append(line if i < 0 else line[:i])
    return "\n".join(out)


def check_module() -> list[dict]:
    if not os.path.isfile(MODULE):
        return [{"check": "module", "reason": f"{MODULE} not found"}]
    src = read_file(MODULE) or ""
    issues = []
    for fn in ("enqueueFollowups", "recallDueFollowups"):
        if f"export async function {fn}" not in src:
            issues.append({"check": "module", "reason": f"followups.ts must export async {fn}"})
    for fn in ("formatFollowups", "normalizeFollowup", "clampDueDays"):
        if f"export function {fn}" not in src:
            issues.append({"check": "module", "reason": f"followups.ts must export pure {fn}"})
    return issues


def check_migration() -> list[dict]:
    issues = []
    found = False
    for p in glob.glob(os.path.join(MIG_DIR, "*agent_followups*.sql")):
        src = read_file(p) or ""
        flat = _flat(_strip_sql_comments(src))  # comment-free, so token checks don't trip on prose
        if "agent_followups" not in src:
            continue
        found = True
        if "CREATE TABLE" not in src.upper():
            issues.append({"check": "migration", "reason": "migration must CREATE TABLE agent_followups"})
        if "'pending'" not in src or "'surfaced'" not in src:
            issues.append({"check": "migration", "reason": "status CHECK must include 'pending' + 'surfaced'"})
        if "ENABLE ROW LEVEL SECURITY" not in src.upper():
            issues.append({"check": "migration", "reason": "must ENABLE ROW LEVEL SECURITY"})
        # Non-open: writes locked, and no FOR SELECT USING (true) open policy.
        if "WITHCHECK(false)" not in flat:
            issues.append({"check": "migration", "reason": "INSERT policy must be locked (WITH CHECK (false)) - service-role writes only"})
        if "USING(true)" in flat:
            issues.append({"check": "migration", "reason": "no open USING(true) policy allowed (would bump the RLS-open baseline)"})
    if not found:
        issues.append({"check": "migration", "reason": "no *agent_followups*.sql migration found"})
    return issues


def check_recall(src: str) -> list[dict]:
    flat = _flat(src)
    issues = []
    if '.eq("status","pending")' not in flat:
        issues.append({"check": "recall", "reason": "recall must filter status='pending'"})
    if '.lte("due_at"' not in flat:
        issues.append({"check": "recall", "reason": "recall must filter due_at <= now (.lte(\"due_at\", ...))"})
    if ".limit(" not in flat:
        issues.append({"check": "recall", "reason": "recall must be bounded with .limit(...)"})
    if 'status:"surfaced"' not in flat and "status:'surfaced'" not in flat:
        issues.append({"check": "recall", "reason": "recall must mark returned rows status='surfaced' (raise once)"})
    return issues


def check_enqueue(src: str) -> list[dict]:
    issues = []
    if "MAX_ENQUEUE_BATCH" not in src:
        issues.append({"check": "enqueue", "reason": "enqueue must cap the batch (MAX_ENQUEUE_BATCH)"})
    if "MAX_PENDING_PER_WORKER" not in src:
        issues.append({"check": "enqueue", "reason": "enqueue must enforce a per-worker pending cap (MAX_PENDING_PER_WORKER)"})
    if "normalizeFollowup(" not in src:
        issues.append({"check": "enqueue", "reason": "enqueue must validate items via normalizeFollowup()"})
    return issues


def check_gateway() -> list[dict]:
    src = read_file(GATEWAY) or ""
    flat = _flat(src)
    issues = []
    if "followups.ts" not in src:
        issues.append({"check": "gateway", "reason": "ai-gateway must import from _shared/followups.ts"})
    if "FOLLOWUP_AGENTS" not in src:
        issues.append({"check": "gateway", "reason": "ai-gateway must declare FOLLOWUP_AGENTS"})
    if "recallDueFollowups(" not in flat or "formatFollowups(" not in flat:
        issues.append({"check": "gateway", "reason": "ai-gateway must surface due follow-ups (recallDueFollowups + formatFollowups)"})
    if "enqueueFollowups(" not in flat:
        issues.append({"check": "gateway", "reason": "ai-gateway must enqueue specialist-emitted follow-ups"})
    if ".followups" not in flat and "followups?:unknown" not in flat:
        issues.append({"check": "gateway", "reason": "ai-gateway must parse `followups` from the specialist envelope"})
    if "FOLLOWUP_AGENTS.has(" not in flat:
        issues.append({"check": "gateway", "reason": "follow-up surfacing/enqueue must be gated on FOLLOWUP_AGENTS membership"})
    return issues


def check_bounded(src: str) -> list[dict]:
    flat = _flat(src)
    issues = []
    if "if(!hiveId&&!workerName)return[]" not in flat:
        issues.append({"check": "bounded", "reason": "recallDueFollowups must require a hive/worker scope (return [] otherwise)"})
    if "MAX_DUE_DAYS" not in src or "MIN_DUE_DAYS" not in src:
        issues.append({"check": "bounded", "reason": "clampDueDays must bound the due window (MIN_DUE_DAYS..MAX_DUE_DAYS)"})
    return issues


CHECKS = [
    ("module",    "W01 followups.ts exists + exports enqueue/recall/format/normalize", check_module),
    ("migration", "W02 agent_followups migration + non-open RLS",                      check_migration),
    ("recall",    "W03 recall due-filtered + marks surfaced",                          lambda: check_recall(read_file(MODULE) or "")),
    ("enqueue",   "W04 enqueue batch + pending caps + validation",                     lambda: check_enqueue(read_file(MODULE) or "")),
    ("gateway",   "W05 ai-gateway surfaces due + enqueues envelope followups",          check_gateway),
    ("bounded",   "W06 scope-guarded + due-window bounded",                            lambda: check_bounded(read_file(MODULE) or "")),
]


def main() -> int:
    print("\033[1m\nfollowup-queue-wiring — Turn 6 (Prospective / layer 06, deferred follow-up queue)\033[0m")
    print("=" * 70)
    all_issues = []
    keys = [c[0] for c in CHECKS]
    labels = {c[0]: c[1] for c in CHECKS}
    for key, _label, fn in CHECKS:
        for issue in fn():
            issue.setdefault("check", key)
            all_issues.append(issue)
    n_pass, n_skip, n_fail = format_result(keys, labels, all_issues)
    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())

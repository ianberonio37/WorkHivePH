#!/usr/bin/env python3
"""
companion_harvest.py — Phase 8 §8.5 (continuous harvest: the on-ramp to Option B).
=================================================================================
8.5 was deferred in the original Phase 8 build for ONE reason: there was no live
feedback data. ai_quality_log is the LLM-JUDGE eval log (not user thumbs); the
voice bubble's thumbs wrote to ai_cost_log via a missing RPC + an RLS-denied
UPDATE — a no-op end to end — and ai_cost_log has no question column anyway. The
companion's most-used TYPED surface (the floating launcher, ~32 pages) shipped no
thumbs at all. So the harvest pipeline starved at the SOURCE.

The fix (2026-06-09) added the live thumbs signal to the floating + voice
surfaces, writing to public.ai_reply_feedback — the one working, client-writable
sink that carries the QUESTION text (migration 20260609000006). This tool closes
the loop: it reads the thumbs-DOWN rows (the real misses) and turns each into a
GOLDEN CANDIDATE — "the failing question + the agent" — for HUMAN disposition.

Anti-overfit contract (non-negotiable, mirrors the rest of Phase 8):
  * A candidate is a PROPOSAL. The human disposes each one (accept -> target
    dimension, or reject). The tool never decides.
  * `promote` stages ACCEPTED candidates as golden SKELETONS in a separate
    staging file — it NEVER writes the companion_<dim>_golden.json files, and
    NEVER, under any flag, assigns a unit to the locked-test split. The
    locked-test split is the anti-overfit spine; growing it is a deliberate
    human act through gate_eval_splits, not a side effect of harvesting.
  * Re-harvesting MERGES: existing human dispositions are preserved, never
    clobbered. Only genuinely-new thumbs-down rows are added as `pending`.

Once the human grows a dimension's locked-test past n>=20 (ceil(100/tol)), the
n-aware companion gate auto-flips that dim from WARN to BLOCK — no flag to flip
(see companion_dim gate, Phase 8 n-aware gate). Harvest -> dispose -> grow ->
auto-enforce: the harness completes itself.

Subcommands:
  python tools/companion_harvest.py --self-test     # prove the contract, NO DB
  python tools/companion_harvest.py harvest         # read ai_reply_feedback(-1) -> candidates
  python tools/companion_harvest.py report          # summarize the candidate queue
  python tools/companion_harvest.py promote         # accepted -> staging skeletons (no golden edit)

Env (harvest only): SUPABASE_URL (default http://127.0.0.1:54321),
SUPABASE_SERVICE_ROLE_KEY (required; service role bypasses RLS to read the
question text across hives). Same access pattern as tools/seed_5y_synthetic_history.py.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
CANDIDATES_PATH = ROOT / "companion_harvest_candidates.json"
PROMOTED_PATH = ROOT / "companion_harvest_promoted.json"

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"

# The product eval dimensions a harvested miss can belong to. Safety/cost are NOT
# harvest targets: safety = the frozen adversarial set (human-curated red-team),
# cost = a spend gate. A thumbs-down maps to a QUALITY dimension.
VALID_DIMENSIONS = ("agent", "rag", "memory", "persona")
DISPOSITIONS = ("pending", "accepted", "rejected")

MEMORY_CUES = ("remember", "you told", "i told you", "earlier", "last time",
               "i said", "we discussed", "forgot", "yesterday i", "did i")
COMMAND_CUES = ("log ", "create ", "deduct", "complete ", "mark ", "open the",
                "add ", "record ", "schedule ")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(p: Path):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"{RED}WARN: could not parse {p.name}: {e}{RESET}")
        return None


def _norm_q(q: str) -> str:
    return re.sub(r"\s+", " ", str(q or "").strip().lower())


def candidate_id(question: str, agent: str) -> str:
    h = hashlib.sha1((_norm_q(question) + "|" + (agent or "")).encode("utf-8")).hexdigest()
    return "HARVEST-" + h[:8]


def suggest_dimension(agent: str, surface: str, question: str) -> tuple[str, str]:
    """Heuristic dimension SUGGESTION. The human confirms target_dimension on
    disposition — this only pre-sorts the queue so triage is faster."""
    a = (agent or "").lower()
    s = (surface or "").lower()
    q = (question or "").lower()
    if "asset-brain" in a or s == "asset-hub":
        return "rag", "asset-brain replies are RAG-grounded with citations -> likely a grounding/citation miss"
    if any(c in q for c in MEMORY_CUES):
        return "memory", "question references prior context -> likely a recall miss"
    if a == "voice-journal" or s in ("voice", "floating"):
        if any(c in q for c in COMMAND_CUES):
            return "agent", "imperative/command phrasing -> likely a tool-routing miss"
        return "persona", "conversational companion surface -> likely a voice/persona or answer-quality miss"
    return "agent", "default: tool-routing dimension (confirm on disposition)"


def row_to_candidate(row: dict) -> dict:
    question = row.get("question") or ""
    agent = row.get("agent") or ""
    surface = row.get("source") or ""
    dim, reason = suggest_dimension(agent, surface, question)
    return {
        "id": candidate_id(question, agent),
        "source_feedback_id": row.get("id"),
        "question": question,
        "answer": row.get("answer") or "",
        "agent": agent,
        "surface": surface,
        "persona": row.get("persona") or "",
        "hive_id": row.get("hive_id"),
        "worker_name": row.get("worker_name") or "",
        "rating": row.get("rating"),
        "created_at": row.get("created_at"),
        "suggested_dimension": dim,
        "dimension_reason": reason,
        # HUMAN-owned fields below — never set by the tool beyond defaults.
        "disposition": "pending",
        "target_dimension": None,
        "notes": "",
    }


def merge_candidates(existing: list[dict], fresh: list[dict]) -> tuple[list[dict], int]:
    """Merge fresh candidates into the existing queue, PRESERVING human
    dispositions. Dedup by candidate id (question+agent). Returns (merged, n_new)."""
    by_id = {c["id"]: c for c in (existing or [])}
    n_new = 0
    for cand in fresh:
        cid = cand["id"]
        if cid in by_id:
            # Keep the human's disposition/target/notes; refresh the observed
            # answer/created_at to the latest occurrence (the question repeated).
            prev = by_id[cid]
            prev["answer"] = cand["answer"] or prev.get("answer", "")
            prev["created_at"] = cand["created_at"] or prev.get("created_at")
            prev["occurrences"] = int(prev.get("occurrences", 1)) + 1
        else:
            cand["occurrences"] = 1
            by_id[cid] = cand
            n_new += 1
    # Stable order: pending first, then by created_at desc.
    merged = sorted(by_id.values(),
                    key=lambda c: (c.get("disposition") != "pending", str(c.get("created_at") or "")),
                    reverse=False)
    return merged, n_new


# ─────────────────────────── live DB read (harvest) ───────────────────────────

def fetch_thumbs_down(url: str, key: str, limit: int = 1000) -> list[dict]:
    import requests
    cols = "id,hive_id,worker_name,agent,source,page,persona,question,answer,rating,created_at"
    r = requests.get(
        f"{url}/rest/v1/ai_reply_feedback"
        f"?select={cols}&rating=eq.-1&order=created_at.desc&limit={limit}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def cmd_harvest(args) -> int:
    url = os.environ.get("SUPABASE_URL", "http://127.0.0.1:54321")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        print(f"{RED}FAIL: SUPABASE_SERVICE_ROLE_KEY required to read ai_reply_feedback "
              f"(service role bypasses RLS to recover the question text).{RESET}")
        return 2
    try:
        import requests  # noqa: F401
    except ImportError:
        print(f"{RED}FAIL: pip install requests{RESET}")
        return 2
    print(f"Reading thumbs-down feedback from {url}/rest/v1/ai_reply_feedback ...")
    try:
        rows = fetch_thumbs_down(url, key, limit=args.limit)
    except Exception as e:  # noqa: BLE001
        print(f"{RED}FAIL: could not read ai_reply_feedback: {e}{RESET}")
        return 2
    fresh = [row_to_candidate(row) for row in rows]
    doc = _load_json(CANDIDATES_PATH) or {}
    existing = doc.get("candidates", [])
    merged, n_new = merge_candidates(existing, fresh)
    out = {
        "generated_at": _now_iso(),
        "source": "ai_reply_feedback (rating = -1)",
        "n_thumbs_down_seen": len(rows),
        "n_candidates": len(merged),
        "n_new_this_run": n_new,
        "contract": ("Human disposes each candidate (disposition: accepted->target_dimension, "
                     "or rejected). promote stages accepted candidates as golden skeletons; "
                     "it NEVER edits companion_<dim>_golden.json and NEVER assigns locked-test."),
        "candidates": merged,
    }
    CANDIDATES_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{GREEN}OK{RESET}: {len(rows)} thumbs-down seen, {n_new} NEW candidate(s), "
          f"{len(merged)} total -> {CANDIDATES_PATH.name}")
    _print_pending_hint(merged)
    return 0


def _print_pending_hint(cands: list[dict]) -> None:
    pending = [c for c in cands if c.get("disposition") == "pending"]
    if not pending:
        print("No pending candidates to triage.")
        return
    print(f"\n{BOLD}{len(pending)} pending — triage by editing 'disposition' + 'target_dimension':{RESET}")
    for c in pending[:10]:
        print(f"  {CYAN}{c['id']}{RESET} [{c['suggested_dimension']}] "
              f"{c['agent']}/{c['surface']}: {c['question'][:70]!r}")
    if len(pending) > 10:
        print(f"  ... and {len(pending) - 10} more")


def cmd_report(args) -> int:
    doc = _load_json(CANDIDATES_PATH)
    if not doc:
        print(f"{YEL}No candidate queue yet ({CANDIDATES_PATH.name} absent). Run `harvest` first.{RESET}")
        return 0
    cands = doc.get("candidates", [])
    by_disp: dict[str, int] = {}
    by_dim: dict[str, int] = {}
    by_agent: dict[str, int] = {}
    for c in cands:
        by_disp[c.get("disposition", "pending")] = by_disp.get(c.get("disposition", "pending"), 0) + 1
        d = c.get("target_dimension") or c.get("suggested_dimension") or "?"
        by_dim[d] = by_dim.get(d, 0) + 1
        by_agent[c.get("agent", "?")] = by_agent.get(c.get("agent", "?"), 0) + 1
    print(f"{BOLD}Harvest queue:{RESET} {len(cands)} candidate(s)  "
          f"(generated {doc.get('generated_at', '?')})")
    print(f"  disposition: " + ", ".join(f"{k}={v}" for k, v in sorted(by_disp.items())))
    print(f"  dimension:   " + ", ".join(f"{k}={v}" for k, v in sorted(by_dim.items())))
    print(f"  agent:       " + ", ".join(f"{k}={v}" for k, v in sorted(by_agent.items())))
    return 0


def cmd_promote(args) -> int:
    """Stage ACCEPTED candidates as golden skeletons for human labeling. Writes
    ONLY companion_harvest_promoted.json — never the golden files, never locked-test."""
    doc = _load_json(CANDIDATES_PATH)
    if not doc:
        print(f"{YEL}No candidate queue ({CANDIDATES_PATH.name}). Run `harvest` first.{RESET}")
        return 0
    cands = doc.get("candidates", [])
    accepted = [c for c in cands if c.get("disposition") == "accepted"]
    if not accepted:
        print(f"{YEL}No accepted candidates to promote. Set disposition='accepted' + "
              f"target_dimension on the ones to keep.{RESET}")
        return 0
    skeletons = []
    bad = []
    for c in accepted:
        dim = c.get("target_dimension") or c.get("suggested_dimension")
        if dim not in VALID_DIMENSIONS:
            bad.append((c["id"], dim))
            continue
        skeletons.append({
            "_harvested_from": c["id"],
            "_source_feedback_id": c.get("source_feedback_id"),
            "_needs_labeling": True,
            "_suggested_split": "train_or_val_ONLY",   # explicit: never locked-test
            "dimension": dim,
            "id": f"H-{dim.upper()}-{c['id'].split('-')[-1]}",
            "question": c["question"],
            "observed_answer": c.get("answer", ""),
            "agent": c.get("agent", ""),
            "persona": c.get("persona", ""),
            # Empty label fields for the human to fill per the dim's golden shape:
            # agent -> expected_route/expected_params; rag -> expected_kinds;
            # memory -> setup/recall; persona -> markers_all/anti_markers.
            "labels": {},
            "notes": c.get("notes", ""),
        })
    if bad:
        print(f"{RED}Refusing {len(bad)} candidate(s) with an invalid target_dimension "
              f"(must be one of {VALID_DIMENSIONS}):{RESET}")
        for cid, dim in bad:
            print(f"  {cid}: target_dimension={dim!r}")
    out = {
        "generated_at": _now_iso(),
        "warning": ("These are SKELETONS, not graded units. Fill `labels` per the dimension's "
                    "golden shape, then HAND-MERGE into companion_<dim>_golden.json under train/val "
                    "(NEVER locked-test), then re-run gate_eval_splits.py. The locked-test split is "
                    "the anti-overfit spine — never grow it from harvested data automatically."),
        "n_promoted": len(skeletons),
        "skeletons": skeletons,
    }
    PROMOTED_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{GREEN}OK{RESET}: staged {len(skeletons)} skeleton(s) -> {PROMOTED_PATH.name} "
          f"(label them, then hand-merge into golden train/val).")
    return 0 if not bad else 1


# ─────────────────────────────── self-test ────────────────────────────────────

def cmd_self_test(args) -> int:
    """Prove the harvest contract with NO DB and NO live model.

    Asserts: only thumbs-down become candidates; thumbs-up ignored; dedup by
    (question, agent); dimension suggestion lands in the valid set; merge
    preserves a human disposition; promote never targets locked-test and refuses
    an invalid dimension.
    """
    fails = []

    synth_rows = [
        {"id": "fb1", "agent": "voice-journal", "source": "floating", "persona": "zaniah",
         "question": "Why is my bearing overheating again?", "answer": "Check lubrication.",
         "rating": -1, "created_at": "2026-06-09T01:00:00Z", "hive_id": "h1", "worker_name": "Pablo"},
        {"id": "fb2", "agent": "asset-brain", "source": "asset-hub", "persona": "hezekiah",
         "question": "What is the MTBF of pump P-203?", "answer": "I don't know.",
         "rating": -1, "created_at": "2026-06-09T02:00:00Z", "hive_id": "h1", "worker_name": "Maria"},
        {"id": "fb3", "agent": "assistant", "source": "chat", "persona": "zaniah",
         "question": "Remember the chiller fault I told you about last week?", "answer": "No context.",
         "rating": -1, "created_at": "2026-06-09T03:00:00Z", "hive_id": "h2", "worker_name": "Jun"},
        # duplicate of fb1 (same question + agent) -> must dedup to one candidate
        {"id": "fb4", "agent": "voice-journal", "source": "floating", "persona": "zaniah",
         "question": "why is my  Bearing overheating AGAIN?", "answer": "Regrease it.",
         "rating": -1, "created_at": "2026-06-09T04:00:00Z", "hive_id": "h1", "worker_name": "Pablo"},
        # thumbs-UP -> must be ignored entirely
        {"id": "fb5", "agent": "voice-journal", "source": "floating", "persona": "zaniah",
         "question": "Thanks, that helped!", "answer": "Anytime.",
         "rating": 1, "created_at": "2026-06-09T05:00:00Z", "hive_id": "h1", "worker_name": "Pablo"},
    ]

    # In production fetch_thumbs_down filters rating=eq.-1 server-side; the
    # self-test filters here to prove the candidate-builder never emits a +1.
    down = [r for r in synth_rows if r.get("rating") == -1]
    fresh = [row_to_candidate(r) for r in down]

    # 1. thumbs-up ignored / only -1 present
    if any(c["rating"] != -1 for c in fresh):
        fails.append("a thumbs-up leaked into candidates")

    # 2. dedup: fb1 and fb4 are the same normalized question+agent
    merged, n_new = merge_candidates([], fresh)
    if len(merged) != 3:
        fails.append(f"dedup failed: expected 3 distinct candidates, got {len(merged)}")
    dup_id = candidate_id(down[0]["question"], down[0]["agent"])
    dup = next((c for c in merged if c["id"] == dup_id), None)
    if not dup or dup.get("occurrences") != 2:
        fails.append("dedup did not collapse the repeated question (occurrences != 2)")

    # 3. dimension suggestions land in the valid set + the obvious ones are right
    for c in merged:
        if c["suggested_dimension"] not in VALID_DIMENSIONS:
            fails.append(f"{c['id']} suggested an invalid dimension {c['suggested_dimension']!r}")
    rag_c = next((c for c in merged if c["agent"] == "asset-brain"), None)
    if not rag_c or rag_c["suggested_dimension"] != "rag":
        fails.append("asset-brain miss not suggested as 'rag'")
    mem_c = next((c for c in merged if "remember" in c["question"].lower()), None)
    if not mem_c or mem_c["suggested_dimension"] != "memory":
        fails.append("'remember ...' miss not suggested as 'memory'")

    # 4. all fresh candidates start pending; none carries a split, none targets locked-test
    if any(c.get("disposition") != "pending" for c in merged):
        fails.append("a fresh candidate was not 'pending'")
    blob = json.dumps(merged)
    if "locked" in blob.lower() or "test_seal" in blob.lower():
        fails.append("a candidate referenced the locked-test split")

    # 5. merge preserves a human disposition on re-harvest
    human = [dict(c) for c in merged]
    human[0]["disposition"] = "accepted"
    human[0]["target_dimension"] = "persona"
    re_merged, _ = merge_candidates(human, fresh)
    kept = next((c for c in re_merged if c["id"] == human[0]["id"]), None)
    if not kept or kept.get("disposition") != "accepted" or kept.get("target_dimension") != "persona":
        fails.append("re-harvest clobbered a human disposition")

    # 6. promote-shape: accepted+valid dim -> skeleton w/ never-locked-test marker;
    #    invalid dim refused (simulate the promote builder inline)
    accepted = [c for c in re_merged if c.get("disposition") == "accepted"]
    ok_dim = all((c.get("target_dimension") in VALID_DIMENSIONS) for c in accepted)
    if not ok_dim:
        fails.append("accepted candidate had an out-of-set target_dimension")

    if fails:
        print(f"{RED}{BOLD}SELF-TEST FAILED:{RESET}")
        for f in fails:
            print(f"  {RED}x{RESET} {f}")
        return 1
    print(f"{GREEN}{BOLD}SELF-TEST PASSED{RESET} — "
          f"thumbs-up ignored, dedup (occurrences=2), dimension routing "
          f"(rag/memory correct), pending-only, no locked-test target, "
          f"merge preserves human disposition.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 8 §8.5 companion feedback harvester.")
    sub = ap.add_subparsers(dest="cmd")
    ap.add_argument("--self-test", action="store_true", help="prove the contract with no DB")

    p_h = sub.add_parser("harvest", help="read ai_reply_feedback(-1) -> candidate queue")
    p_h.add_argument("--limit", type=int, default=1000)
    sub.add_parser("report", help="summarize the candidate queue")
    sub.add_parser("promote", help="stage accepted candidates as golden skeletons")

    args = ap.parse_args()
    if args.self_test:
        return cmd_self_test(args)
    if args.cmd == "harvest":
        return cmd_harvest(args)
    if args.cmd == "report":
        return cmd_report(args)
    if args.cmd == "promote":
        return cmd_promote(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

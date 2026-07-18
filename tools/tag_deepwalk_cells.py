#!/usr/bin/env python3
"""tag_deepwalk_cells.py — seed `# DEEPWALK-CELL:` tags on existing validators (Ian 2026-07-08).

The flywheel v2 binder (deepwalk_flywheel.py Δ2) lights a grid cell only when an on-disk
validator self-declares `# DEEPWALK-CELL: <surface> <dim>`. This one-shot seeds that convention
across the validators we ALREADY have — each mapping is evidence-based (the validator genuinely
checks that dimension for that surface). Idempotent: skips a file already carrying the tag.
After this, a NEW tagged validator auto-joins with zero edits — this script is only the seed.

The tag is inserted as a plain `#` comment right after the shebang (always valid, always inside
the 4000-char head the binder reads). Run:  python tools/tag_deepwalk_cells.py
"""
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")

# validator stem -> [(surface, dim), ...]  ·  surface: `*`=all pages, `ai:*`=all AI fns,
# a page stem (logbook), or an AI fn name (ai-gateway).  Evidence-based, honest seed.
MAP = {
    # --- D2 data-integrity (ARC DI's platform-wide write locks + the per-page reconcilers) ---
    "validate_attribution":                 [("*", "D2")],            # auth_uid on every client write
    "validate_rpc_write_integrity":         [("*", "D2")],            # every RPC covers NOT NULL + real tables
    "validate_inventory_ledger_reconciled": [("inventory", "D2")],
    "validate_logbook_asset_linkage":       [("logbook", "D2")],
    "validate_embedding_no_stale_duplicates": [("logbook", "D2")],
    "validate_reliability_kpi_faithfulness": [("analytics", "D2"), ("analytics-report", "D2")],
    "validate_benchmark_rollup_faithfulness": [("analytics", "D2")],
    # --- D8 RLS / tenant-isolation + BOLA (platform-wide) ---
    "validate_rls_tenant_isolation":        [("*", "D8")],
    "validate_definer_tenant_gate":         [("*", "D8")],
    # --- D7 XSS / escHtml (platform-wide sinks) ---
    "validate_dom_xss_fields":              [("*", "D7")],
    "validate_sast_owasp_complete":         [("*", "D7")],
    # --- D4 accessibility (keyboard/aria, platform-wide) ---
    "validate_clickable_keyboard_a11y":     [("*", "D4")],
    # --- AI dims (per-fn boundary oracles) ---
    "validate_ai_retrieval_isolation":      [("ai:*", "D24")],        # cross-hive RAG isolation
    "validate_private_memory_isolation":    [("ai:*", "D24")],
    "validate_grounding_contract":          [("ai:*", "D10")],        # grounding contract
    "validate_ai_prompt_injection":         [("ai:*", "D11")],        # OWASP LLM01
    "validate_redact_iso":                  [("ai:*", "D25")],        # PII multi-turn redaction
    "validate_quota_coverage":              [("ai:*", "D12")],
    "validate_cumulative_quota_enforcement": [("ai:*", "D12")],
    "validate_ai_daily_ceiling":            [("ai:*", "D12")],
    "validate_ai_rate_limit_coverage":      [("ai:*", "D12")],
    "validate_assistant_recall":            [("ai-gateway", "D26")],
    "validate_agent_memory_persist_complete": [("agent-memory-store", "D26")],
    # --- FOLD ~15 arcs: existing registered gates that own a whole dim-row ---
    "validate_plain_language":              [("*", "D23")],   # jargon LOCK on all user-facing copy
    "cwv_gate":                             [("*", "D6")],     # Core Web Vitals scoreboard (ratcheted)
    "audit_displayed_values":               [("*", "D1")],     # rendered value == canonical/formula_contracts
    "validate_interactive_lineage":         [("*", "D22")],    # interactive topology/redundancy ratchet
    "validate_public_fn_write_authz":       [("*", "D9")],     # BFLA: every write edge fn enforces authz
    "validate_public_fn_authz":             [("*", "D9")],     # BFLA: open-LLM-proxy fn guard
    "validate_supervisor_approval_backstop": [("*", "D9")],    # worker can't self-approve (BEFORE-trigger)
    "validate_reactivity_wiring":           [("*", "D3")],     # cross-surface receipt (write-A fans out to B) — advisory-ratcheted
    # NOTE: validate_ai_live_invoke is deliberately NOT report-bound. A fresh run 2026-07-08 showed
    # env-dependent 403s (edge runtime restarted → JWT/AI-env flake) + free-tier rate-limits → its
    # report is NON-DETERMINISTIC. The report-backed engine path is for STABLE reports (frontend
    # U/A/F lens, cwv measurements); a flaky live-LLM battery would flip the ruler red on env
    # flakiness, not code regressions. D13/D26 for AI fns need DETERMINISTIC per-fn oracles instead.
}


def tag_file(stem, cells):
    path = os.path.join(TOOLS, f"{stem}.py")
    if not os.path.isfile(path):
        return "MISSING"
    src = open(path, encoding="utf-8", errors="replace").read()
    if "DEEPWALK-CELL" in src[:4000]:
        return "ALREADY"
    tag_block = "".join(
        f"# DEEPWALK-CELL: {c[0]} {c[1]}" + (f" report={c[2]}" if len(c) > 2 else "") + "\n"
        for c in cells)
    lines = src.splitlines(keepends=True)
    insert_at = 1 if lines and lines[0].startswith("#!") else 0
    lines.insert(insert_at, tag_block)
    open(path, "w", encoding="utf-8").write("".join(lines))
    return "TAGGED"


def main():
    counts = {}
    for stem, cells in MAP.items():
        r = tag_file(stem, cells)
        counts[r] = counts.get(r, 0) + 1
        cell_str = ", ".join(f"{c[0]} {c[1]}" + (f"[report]" if len(c) > 2 else "") for c in cells)
        print(f"  [{r:7}] {stem}  ->  {cell_str}")
    print(f"\nSummary: " + " · ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())

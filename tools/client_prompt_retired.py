"""client_prompt_retired - the voice companion's browser-built prompt was retired on 2026-10-27 (BRH-AO); what each old check
should ask instead.

voice-handler.js used to await ten reads every turn, fold them into a system prompt and send it as context.platform_prompt.
No server code reads that field - ai-gateway builds the voice-journal prompt itself - so every capability those reads
carried reached the model only if the SERVER also carried it. Measured before the removal: 31 requests and a 32 KB upload
before each question (tools/prove_companion_turn_cost.mjs). About a dozen gates certified pieces of that prompt ("the
skill-gap fetch is called", "routerContext is passed to the builder"), so each was certifying something no model received.

A check that certified a piece of the client prompt now asks `retired_check(vh, key)`:
  - while the client sends no prompt, it passes ONLY if the capability is found where it lives now (the gateway's source
    or the server's companion source registry), and says where; a capability with no server home is reported as
    never having reached the model - true then and now, and recorded rather than hidden;
  - if the client prompt ever comes back (platform_prompt sent, or the builder called per turn), it returns None and the
    old check runs as before.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATEWAY = ROOT / "supabase" / "functions" / "ai-gateway" / "index.ts"
REGISTRY = ROOT / "supabase" / "functions" / "_shared" / "companion_source_registry.json"

# key -> (where it lives now, a predicate over (gateway source, registry views)) ; None = no server home
HOMES = {
    "kpi": ("ai-gateway's ops snapshot reads hive_kpis() (registry: v_kpi_truth)",
            lambda gw, views: "hive_kpis" in gw or "v_kpi_truth" in views),
    "alerts": ("ai-gateway buildOpsSnapshot reads v_alert_truth (the count and the top three)",
               lambda gw, views: "v_alert_truth" in gw),
    "skill_gap": ("the server's companion source registry carries v_worker_skill_truth",
                  lambda gw, views: "v_worker_skill_truth" in views),
    "repeated_issue": ("the server's registry carries the logbook (v_logbook_truth); a chronic-machine flag has no server form",
                       lambda gw, views: "v_logbook_truth" in views),
    "memory": ("ai-gateway loads agent memory and journal recall itself",
               lambda gw, views: "loadJournalRecall" in gw),
    "rag": ("ai-gateway's journal recall + knowledge base + procedures (strict, budgeted)",
            lambda gw, views: "buildKnowledgeContext" in gw and "loadJournalRecall" in gw),
    "scraper": ("ai-gateway buildOpsSnapshot + the companion source registry",
                lambda gw, views: "buildOpsSnapshot" in gw and len(views) > 10),
    "glossary": None,
    "cross_hive": None,
    "offline_snapshot": None,
    "router_context": None,
    # an anonymous worker's session turns were merged into the client prompt; the server keeps no memory for anon turns
    "anon_session_memory": None,
}


def client_prompt_gone(vh: str) -> bool:
    """True when the browser neither sends a prompt nor builds one per turn."""
    sends = re.search(r"\bplatform_prompt\s*:", vh)
    called = re.search(r"(?<!function )\b_buildVoiceSystemPrompt\(\s*persona\b", vh)
    return not sends and not called


def retired_check(vh: str, key: str) -> tuple | None:
    """(passes, sentence) for a retired check, or None when the client prompt is back and the old check should run."""
    if not client_prompt_gone(vh):
        return None
    home = HOMES[key]
    if home is None:
        return True, (f"RETIRED (BRH-AO 2026-10-27): the client prompt never reached the model, and '{key}' has no server "
                      "form - it never reached a reply, then or now")
    where, ok = home
    gw = GATEWAY.read_text(encoding="utf-8", errors="replace") if GATEWAY.exists() else ""
    try:
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
        items = reg.get("sources") or reg.get("items") or [] if isinstance(reg, dict) else reg
        views = {str(x.get("view") or x.get("source") or x.get("table") or "") for x in items if isinstance(x, dict)}
    except Exception:
        views = set()
    if ok(gw, views):
        return True, f"RETIRED (BRH-AO 2026-10-27): the client prompt never reached the model; this lives server-side - {where}"
    return False, f"RETIRED client check, but its server home is missing: {where}"

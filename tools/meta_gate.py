"""
meta_gate.py — C4 Phase 2b of SELF_IMPROVING_GATE_ROADMAP.md.
================================================================
Composition policy that resolves per-domain verdicts by **blast radius**.

The roadmap's §8 note 7 is the load-bearing idea: "When SaaS says 'ship'
and AI says 'eval regressed 3%,' the meta-gate decides by blast radius
(an AI-eval regression blocks an AI-feature deploy, not a CSS-only SaaS
change)." Per-domain green is not system green — but per-domain *FAIL*
is not always system FAIL either.

The C-track stack already gives the meta-gate everything it needs:
  - C1 (verdict contract) — every ledger validator is tagged
    {domain ∈ general/saas/ai, dimension}.
  - C4 Phase 1 (seam catalog) — every saas→ai / ai→ai / ai→tenant /
    ai→quota call site is enumerated with its caller file/fn.
  - C4 Phase 2a (contract coverage) — each seam carries a
    `contract_test:` field saying whether the wire format is verified.
  - C5 (asset versioning) — the AI asset manifest tells us which
    non-code files are AI-domain.

`decide`:
  1. Compute the diff (default HEAD~1..HEAD or --base/--head).
  2. Classify each diffed path into {ai-fn, ai-asset, saas-touches-ai,
     saas} using the seam catalog + asset manifest.
  3. Read per-domain verdicts from the efficacy ledger
     (any validator tagged in that domain with last_status=FAIL
      contributes a FAIL).
  4. Apply the composition policy (see _apply_policy below).
  5. Emit a structured decision (JSON + readable summary) and append a
     line to `meta_gate_decisions.jsonl` for the macro-loop.

Offline + read-only: it never runs validators; it READS the latest
committed reports. The paid step (running the gate) is what produced
those reports. Promote `decide` to a G0 validator
(`validate_meta_gate_decision.py`) when it's time to make the meta-gate
ship-blocking — Phase 2c, deliberately deferred.

Exit codes:
  0  ship  (no domain FAIL applies to this PR's blast radius).
  1  block (at least one applicable domain FAIL — see decision JSON
            for which and why).
  2  insufficient input (no ledger, no diff, no catalog).
"""
from __future__ import annotations
import argparse, io, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT             = Path(__file__).resolve().parent.parent
LEDGER_PATH      = ROOT / "gate_efficacy_ledger.json"
SEAMS_PATH       = ROOT / "ai_seams_catalog.json"
ASSETS_PATH      = ROOT / "ai_asset_baseline.json"
DECISIONS_PATH   = ROOT / "meta_gate_decisions.jsonl"

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"

DOMAINS = ("general", "saas", "ai")


# --- Diff ---------------------------------------------------------------------
def compute_diff(base: str, head: str, explicit: list[str] | None) -> list[str]:
    """Return a list of repo-relative file paths changed between base..head."""
    if explicit is not None:
        return [p.strip() for p in explicit if p.strip()]
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{base}..{head}"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    if proc.returncode != 0:
        # Common case in fresh repos with one commit; fall back to "everything
        # in HEAD" so the meta-gate at least has a meaningful blast radius.
        proc = subprocess.run(
            ["git", "show", "--name-only", "--format=", head],
            cwd=str(ROOT), capture_output=True, text=True,
        )
    return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]


# --- Classification -----------------------------------------------------------
def load_seam_catalog() -> dict:
    if not SEAMS_PATH.exists():
        return {"seams": [], "ai_fns": []}
    return json.loads(SEAMS_PATH.read_text(encoding="utf-8"))


def load_asset_files() -> set[str]:
    if not ASSETS_PATH.exists():
        return set()
    doc = json.loads(ASSETS_PATH.read_text(encoding="utf-8"))
    return {rec.get("file", "") for rec in (doc.get("assets") or {}).values() if rec.get("file")}


def classify_diff(diff: list[str], catalog: dict, asset_files: set[str]) -> dict:
    """Return blast radius: per-kind file lists + the touched seam ids."""
    ai_fns = set(catalog.get("ai_fns", []))
    seams = catalog.get("seams", [])
    # caller_file → list of seam dicts (so we can surface contract coverage).
    by_caller_file = {}
    for s in seams:
        by_caller_file.setdefault(s.get("file", ""), []).append(s)

    out = {
        "ai_fn":            [],   # touches an AI edge fn
        "ai_asset":         [],   # touches a versioned AI asset (C5)
        "saas_touches_ai":  [],   # SaaS file that is a known saas→ai seam caller
        "saas":             [],   # everything else
        "touched_seams":    [],   # seam_ids whose caller file appears in diff
    }

    for path in diff:
        path_n = path.replace("\\", "/")
        # AI edge fn?
        is_ai_fn = False
        if path_n.startswith("supabase/functions/"):
            parts = path_n.split("/")
            if len(parts) >= 3 and parts[2] in ai_fns:
                is_ai_fn = True
        if is_ai_fn:
            out["ai_fn"].append(path_n)
            continue
        # AI asset?
        if path_n in asset_files:
            out["ai_asset"].append(path_n)
            continue
        # SaaS but touches a known saas→ai seam (= consumer-side risk)?
        if path_n in by_caller_file:
            kinds_for_file = {s["kind"] for s in by_caller_file[path_n]}
            if "saas→ai" in kinds_for_file:
                out["saas_touches_ai"].append(path_n)
                out["touched_seams"].extend(
                    s["id"] for s in by_caller_file[path_n] if s["kind"] == "saas→ai"
                )
                continue
        out["saas"].append(path_n)

    # Dedup touched_seams while preserving order.
    seen = set()
    out["touched_seams"] = [sid for sid in out["touched_seams"]
                            if not (sid in seen or seen.add(sid))]
    return out


# --- Verdicts -----------------------------------------------------------------
def load_ledger() -> dict:
    if not LEDGER_PATH.exists():
        return {"validators": {}}
    return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))


def domain_verdicts(ledger: dict) -> dict:
    """For each domain ∈ {general,saas,ai}: collect FAIL validators + counts."""
    out = {d: {"status": "PASS", "fail_ids": [], "n_validators": 0, "n_fail": 0,
               "fail_dimensions": {}} for d in DOMAINS}
    for vid, v in (ledger.get("validators") or {}).items():
        d = v.get("domain", "general")
        if d not in out:
            d = "general"
        out[d]["n_validators"] += 1
        if v.get("last_status") == "FAIL":
            out[d]["status"] = "FAIL"
            out[d]["n_fail"] += 1
            out[d]["fail_ids"].append(vid)
            dim = v.get("dimension", "unknown")
            out[d]["fail_dimensions"][dim] = out[d]["fail_dimensions"].get(dim, 0) + 1
    return out


# --- Policy -------------------------------------------------------------------
def _apply_policy(verdicts: dict, blast: dict, contract_map: dict) -> dict:
    """The composition policy. Returns {ship: bool, reasons: [...]}.

    Rules:
      1. general FAIL  -> always block (base layer; no override).
      2. saas FAIL     -> block IF diff touches any saas/saas_touches_ai files.
      3. ai FAIL       -> block IF diff touches any ai_fn/ai_asset/saas_touches_ai.
         SEAM-SHARPENING: if EVERY touched saas→ai seam has a contract_test,
         the ai FAIL is downgraded to WARN (the wire format is verified — the
         eval drift can't surprise this PR's seam silently).
    """
    reasons: list[dict] = []
    ship = True

    # Rule 1 — general always blocks.
    if verdicts["general"]["status"] == "FAIL":
        ship = False
        reasons.append({
            "domain":   "general",
            "severity": "block",
            "rule":     "general-always-blocks",
            "detail":   f"{verdicts['general']['n_fail']} general validator(s) FAIL",
            "fail_ids": verdicts["general"]["fail_ids"][:10],
        })

    # Rule 2 — saas blocks only when touched.
    saas_touched = bool(blast["saas"]) or bool(blast["saas_touches_ai"])
    if verdicts["saas"]["status"] == "FAIL":
        if saas_touched:
            ship = False
            reasons.append({
                "domain":   "saas",
                "severity": "block",
                "rule":     "saas-blocks-on-saas-blast",
                "detail":   f"{verdicts['saas']['n_fail']} saas validator(s) FAIL; diff touches saas files",
                "fail_ids": verdicts["saas"]["fail_ids"][:10],
            })
        else:
            reasons.append({
                "domain":   "saas",
                "severity": "warn-only",
                "rule":     "saas-fail-but-no-saas-blast",
                "detail":   "saas FAIL exists but this PR doesn't touch saas surfaces",
                "fail_ids": verdicts["saas"]["fail_ids"][:5],
            })

    # Rule 3 — ai blocks only when touched, with seam-sharpening.
    ai_touched = bool(blast["ai_fn"]) or bool(blast["ai_asset"]) or bool(blast["saas_touches_ai"])
    if verdicts["ai"]["status"] == "FAIL":
        if ai_touched:
            touched_seams = blast["touched_seams"]
            covered = [sid for sid in touched_seams if contract_map.get(sid)]
            uncovered = [sid for sid in touched_seams if not contract_map.get(sid)]
            seam_sharpened = bool(touched_seams) and not uncovered
            if seam_sharpened:
                # All touched seams verified by contract -> downgrade.
                reasons.append({
                    "domain":   "ai",
                    "severity": "warn-only",
                    "rule":     "ai-fail-but-touched-seams-all-contract-covered",
                    "detail":   f"{verdicts['ai']['n_fail']} ai validator(s) FAIL; every touched saas→ai seam has a wire-format contract test ({len(covered)}/{len(touched_seams)})",
                    "covered_seams":   covered,
                    "fail_ids": verdicts["ai"]["fail_ids"][:10],
                })
            else:
                ship = False
                reasons.append({
                    "domain":   "ai",
                    "severity": "block",
                    "rule":     "ai-blocks-on-ai-blast",
                    "detail":   f"{verdicts['ai']['n_fail']} ai validator(s) FAIL; diff touches ai surfaces; {len(uncovered)}/{len(touched_seams)} touched seam(s) uncovered",
                    "uncovered_seams": uncovered,
                    "covered_seams":   covered,
                    "fail_ids": verdicts["ai"]["fail_ids"][:10],
                })
        else:
            reasons.append({
                "domain":   "ai",
                "severity": "warn-only",
                "rule":     "ai-fail-but-no-ai-blast",
                "detail":   "ai FAIL exists but this PR doesn't touch ai surfaces",
                "fail_ids": verdicts["ai"]["fail_ids"][:5],
            })

    if not reasons:
        reasons.append({"domain": "all", "severity": "info", "rule": "all-green", "detail": "no domain FAILs in ledger"})
    return {"ship": ship, "reasons": reasons}


# --- Decide -------------------------------------------------------------------
def cmd_decide(args) -> int:
    catalog = load_seam_catalog()
    if not catalog.get("seams") and args.explicit is None:
        print(f"{YEL}WARN{RESET}  No seams catalog at {SEAMS_PATH.name} — meta-gate can't classify saas-touches-ai. Run `python tools/mine_ai_seams.py` first.")
    asset_files = load_asset_files()
    ledger = load_ledger()
    if not ledger.get("validators"):
        print(f"{YEL}SKIP{RESET}  ledger empty ({LEDGER_PATH.name}) — meta-gate has no verdicts to compose. Run a gate first.")
        return 2

    diff = compute_diff(args.base, args.head, args.explicit)
    blast = classify_diff(diff, catalog, asset_files)
    verdicts = domain_verdicts(ledger)
    contract_map = {s["id"]: s.get("contract_test")
                    for s in catalog.get("seams", [])}
    result = _apply_policy(verdicts, blast, contract_map)

    decision = {
        "ts":          datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base":        args.base,
        "head":        args.head,
        "n_changed":   len(diff),
        "blast":       {k: len(v) if isinstance(v, list) else v
                        for k, v in blast.items()},
        "touched_seams":   blast["touched_seams"],
        "domains":     {d: {"status": verdicts[d]["status"],
                            "n_validators": verdicts[d]["n_validators"],
                            "n_fail":       verdicts[d]["n_fail"]} for d in DOMAINS},
        "ship":        result["ship"],
        "reasons":     result["reasons"],
    }

    # Persist for the macro-loop.
    if args.write_decision:
        with DECISIONS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(decision, sort_keys=False) + "\n")

    # Print readable summary.
    bar = "─" * 70
    print(bar)
    head_label = f"{GREEN}SHIP{RESET}" if result["ship"] else f"{RED}BLOCK{RESET}"
    print(f"{BOLD}meta-gate decision:{RESET} {head_label}   diff: {len(diff)} file(s) {args.base}..{args.head}")
    print(bar)
    print(f"  blast radius:  ai_fn={decision['blast']['ai_fn']}  "
          f"ai_asset={decision['blast']['ai_asset']}  "
          f"saas_touches_ai={decision['blast']['saas_touches_ai']}  "
          f"saas={decision['blast']['saas']}")
    if blast["touched_seams"]:
        print(f"  touched seams: {len(blast['touched_seams'])}  "
              f"e.g. {blast['touched_seams'][:3]}")
    for d in DOMAINS:
        v = verdicts[d]
        mark = f"{RED}FAIL{RESET}" if v["status"] == "FAIL" else f"{GREEN}PASS{RESET}"
        print(f"  domain {d:<7}: {mark}  ({v['n_validators']} validators, {v['n_fail']} fail)")
    print(bar)
    for r in result["reasons"]:
        sev_colors = {"block": RED, "warn-only": YEL, "info": CYAN}
        sev = r["severity"]
        col = sev_colors.get(sev, RESET)
        print(f"  {col}{sev:<10}{RESET} [{r['domain']:<7}] {r['rule']}: {r['detail']}")
    print(bar)

    if args.json:
        print(json.dumps(decision, indent=2))

    return 0 if result["ship"] else 1


# --- Policy printer -----------------------------------------------------------
POLICY_TEXT = """
Composition policy (C4 Phase 2b)
-------------------------------------------------------------------------------
1. GENERAL ALWAYS BLOCKS
   If any validator tagged domain=general has last_status=FAIL, the meta-gate
   blocks. No override. This is the base layer that protects shared surfaces.

2. SAAS BLOCKS WITH SAAS BLAST
   If any validator tagged domain=saas has last_status=FAIL, the meta-gate
   blocks IF AND ONLY IF the diff touches at least one saas file (or any
   saas→ai seam caller). A CSS-only commit gets a pass even with saas FAIL
   elsewhere; a marketplace commit does not.

3. AI BLOCKS WITH AI BLAST + SEAM-SHARPENING
   If any validator tagged domain=ai has last_status=FAIL, the meta-gate
   blocks IF AND ONLY IF the diff touches an ai-fn, an ai-asset, or a
   saas→ai seam caller.
   EXCEPTION: when every touched saas→ai seam has a wire-format
   contract_test (C4 Phase 2a), the ai FAIL is downgraded to warn-only —
   the contract caught the wire-format risk, so a deeper eval drift does
   not surprise this PR's surface silently.

Inputs:
  - gate_efficacy_ledger.json   (C1: tagged {domain,dimension} verdicts)
  - ai_seams_catalog.json       (C4 Phase 1: seam map + contract_test)
  - ai_asset_baseline.json      (C5: AI asset manifest)
  - git diff <base>..<head>     (blast radius)

Output:
  exit 0 = ship, exit 1 = block, exit 2 = insufficient input
  meta_gate_decisions.jsonl     (one line per `decide --write-decision`)
"""


def cmd_policy(args) -> int:
    print(POLICY_TEXT)
    return 0


# --- CLI ----------------------------------------------------------------------
def main() -> int:
    p = argparse.ArgumentParser(description="C4 Phase 2b — meta-gate composition policy.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pd = sub.add_parser("decide", help="apply policy to the current diff + ledger")
    pd.add_argument("--base", default="HEAD~1", help="diff base ref (default HEAD~1)")
    pd.add_argument("--head", default="HEAD",   help="diff head ref (default HEAD)")
    pd.add_argument("--explicit", nargs="*", default=None,
                    help="explicit file list (overrides git diff; for testing)")
    pd.add_argument("--write-decision", action="store_true",
                    help="append decision to meta_gate_decisions.jsonl")
    pd.add_argument("--json", action="store_true", help="also print the decision JSON")
    pd.set_defaults(func=cmd_decide)

    pp = sub.add_parser("policy", help="print the composition policy in readable form")
    pp.set_defaults(func=cmd_policy)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

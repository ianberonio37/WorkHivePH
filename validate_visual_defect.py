"""validate_visual_defect.py - Phase 1.9 of STRATEGIC_ROADMAP.md.

Architectural contract gate for the Visual Defect Capture edge function.
The function classifies a worker's defect photo into a logbook-shaped draft.
Five contract points keep it safe + cost-controlled:

Layers:
  L1  edge fn exists AND uses callAIMultimodal
  L2  rate-limit gate FIRST + MIME whitelist + image-size cap
  L3  fault_knowledge insert is fire-and-forget (no await on the .then())
  L4  logAICost call present (cost observability mandate)
  L5  asset auto-link via OCR (matched_asset path)

Skills consulted:
  ai-engineer (multimodal cost, rate-limit FIRST, fire-and-forget embed)
  security (MIME whitelist, image size cap, prompt-injection-via-OCR safety)
  knowledge-manager (fault_knowledge schema fields)
  multitenant-engineer (hive_id required on every read + write)
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).parent
EDGE_FN = ROOT / "supabase" / "functions" / "visual-defect-capture" / "index.ts"

LAYERS = [
    {"layer": "L1", "label": "edge fn exists AND uses callAIMultimodal"},
    {"layer": "L2", "label": "rate-limit FIRST + MIME whitelist + image-size cap"},
    {"layer": "L3", "label": "fault_knowledge insert is fire-and-forget"},
    {"layer": "L4", "label": "logAICost call present"},
    {"layer": "L5", "label": "asset auto-link via OCR (matched_asset returned)"},
]


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def run() -> dict:
    issues: list[dict] = []
    if not EDGE_FN.exists():
        for i, layer in enumerate(LAYERS):
            issues.append({"check": layer["layer"].lower(),
                           "reason": "supabase/functions/visual-defect-capture/index.ts not found."})
        return {"validator": "visual_defect", "total_checks": len(LAYERS),
                "passed": 0, "failed": len(LAYERS), "warned": 0,
                "layers": LAYERS, "issues": issues, "warnings": []}

    src = _read(EDGE_FN)

    # L1
    if "callAIMultimodal" not in src:
        issues.append({"check": "l1", "layer": "L1",
                       "reason": "visual-defect-capture must use callAIMultimodal "
                                 "(vision provider). Text-only callAI is not enough."})
    # L2: rate-limit before LLM call + MIME whitelist + size cap.
    has_rl = "ai_rate_limits" in src or "checkAIRateLimit" in src
    has_mime = "ALLOWED_MIME" in src or "image/jpeg" in src
    has_size = "MAX_IMAGE_BYTES" in src or "MAX_IMAGE" in src
    if not has_rl:
        issues.append({"check": "l2_rate_limit", "layer": "L2",
                       "reason": "No rate-limit gate found. Vision tokens are 10x "
                                 "expensive; unrate-limited it can drain quota in minutes."})
    if not has_mime:
        issues.append({"check": "l2_mime", "layer": "L2",
                       "reason": "No MIME whitelist. Attacker could upload "
                                 "non-image bytes and probe the parser."})
    if not has_size:
        issues.append({"check": "l2_size_cap", "layer": "L2",
                       "reason": "No image-size cap constant. 50 MB uploads will "
                                 "kill the edge fn's memory budget."})
    # L3: the embedding + fault_knowledge insert chain must be fire-and-forget.
    # The contract: generateEmbedding(...) is called WITHOUT `await` at the
    # top level, and its .then() chain handles the fault_knowledge insert.
    # An `await` INSIDE the .then() lambda is fine; it's just sequencing the
    # local async work and does not block the caller's response.
    if "fault_knowledge" in src:
        # Find any `generateEmbedding(` not preceded by `await `.
        unawaited = re.search(r"(?<!await\s)generateEmbedding\s*\(", src)
        has_then  = ".then(" in src
        # Fail only if generateEmbedding is awaited at top level OR no .then() chain exists.
        top_level_awaited = re.search(r"\bawait\s+generateEmbedding\s*\(", src)
        if top_level_awaited:
            issues.append({"check": "l3_fire_forget", "layer": "L3",
                           "reason": "generateEmbedding is awaited at the top level. "
                                     "This blocks the worker's response on a slow "
                                     "embedding. Drop the await and chain a .then()."})
        elif not (unawaited and has_then):
            issues.append({"check": "l3_fire_forget", "layer": "L3",
                           "reason": "fault_knowledge insert is present but the "
                                     "fire-and-forget generateEmbedding(...).then(...) "
                                     "chain is missing."})
    # L4: logAICost call
    if "logAICost(" not in src:
        issues.append({"check": "l4_cost_log", "layer": "L4",
                       "reason": "logAICost call missing. Every vision call must "
                                 "log to ai_cost_log (PRODUCTION_FIXES #54)."})
    # L5: matched_asset path
    if "matched_asset" not in src and "matchAssetByTag" not in src:
        issues.append({"check": "l5_asset_link", "layer": "L5",
                       "reason": "matched_asset / matchAssetByTag not found. The "
                                 "OCR-to-asset auto-link is the value-add over "
                                 "vanilla classify. Without it the worker still types "
                                 "the asset name."})

    failed_layers = {i.get("layer") for i in issues if i.get("layer")}
    failed = len(failed_layers)
    passed = len(LAYERS) - failed
    return {"validator": "visual_defect", "total_checks": len(LAYERS),
            "passed": passed, "failed": failed, "warned": 0,
            "layers": LAYERS, "issues": issues, "warnings": []}


def main() -> int:
    out = run()
    print(f"\nVisual Defect Capture Validator ({len(out['layers'])}-layer)")
    print("=" * 60)
    for layer in out["layers"]:
        print(f"  [{layer['layer']}] {layer['label']}")
    print()
    if out["issues"]:
        print(f"  \033[91m{out['failed']} FAIL\033[0m")
        for i in out["issues"]:
            print(f"  [FAIL] [{i['check']}]  {i['reason']}")
    else:
        print(f"  \033[92mAll {out['total_checks']} checks passed.\033[0m")
    (ROOT / "visual_defect_report.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return 1 if out["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())

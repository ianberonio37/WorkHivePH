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
  L6  a signed-in person with NO hive is served on their VERIFIED identity (LM-V walk, LM479, 2026-10-07):
      no hive_id refusal for a non-service caller; an anonymous caller is 401 "Sign in to analyze a photo.";
      the solo rate-limit key is the uid from resolveIdentity (never a body field); the asset match reads
      their own register (hive_id NULL + auth_uid); the analyze-time fault_knowledge row is hive-only
      (a hive-less row has no reader - RLS and every knowledge search filter on hive_id).
  L7  logbook.html's photo path (vdcAnalyze) does not refuse a person for having no hive.

Self-test:  python validate_visual_defect.py --self-test   (8 mutants of L6/L7 must each FAIL; current files PASS)

Skills consulted:
  ai-engineer (multimodal cost, rate-limit FIRST, fire-and-forget embed)
  security (MIME whitelist, image size cap, prompt-injection-via-OCR safety)
  knowledge-manager (fault_knowledge schema fields)
  multitenant-engineer (hive_id required on every read + write)
"""
from __future__ import annotations
import json, re, sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

ROOT = Path(__file__).parent
EDGE_FN = ROOT / "supabase" / "functions" / "visual-defect-capture" / "index.ts"
PAGE = ROOT / "logbook.html"

LAYERS = [
    {"layer": "L1", "label": "edge fn exists AND uses callAIMultimodal"},
    {"layer": "L2", "label": "rate-limit FIRST + MIME whitelist + image-size cap"},
    {"layer": "L3", "label": "fault_knowledge insert is fire-and-forget"},
    {"layer": "L4", "label": "logAICost call present"},
    {"layer": "L5", "label": "asset auto-link via OCR (matched_asset returned)"},
    {"layer": "L6", "label": "a hive-less signed-in caller is served on the verified uid; anon is 401"},
    {"layer": "L7", "label": "logbook's photo path does not refuse a person for having no hive"},
]


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return ""


def _strip_comments(src: str) -> str:
    """Drop /* */ and // comments so a rule quoted in a comment can neither satisfy nor trip a check."""
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    return re.sub(r"(?m)(^|[^:\"'\\])//.*$", r"\1", src)


def hiveless_issues(fn_src: str, page_src: str) -> list[dict]:
    """L6 + L7: the photo path serves a signed-in person with no hive, on their verified identity.

    ★WHY (LM-V walk, LM479, 2026-10-07): a solo owner pressed Photo defect capture and was told "Join a hive to
    analyze defects with AI." - the page refused before calling, and the function would have answered 400
    "Missing required field: hive_id" anyway. Each clause below is the one a regression would remove."""
    out: list[dict] = []
    s = _strip_comments(fn_src)

    # L6a - no hive_id refusal for a person: the old `if (!hive_id) return 400` is gone, and any remaining
    # "Missing required field: hive_id" answer sits inside a service-role branch.
    if re.search(r"if\s*\(\s*!\s*hive_id\s*\)\s*\{?\s*return\b", s):
        out.append({"check": "l6_no_hive_refusal", "layer": "L6",
                    "reason": "visual-defect-capture returns early when hive_id is missing - a signed-in solo owner "
                              "is refused a photo draft that needs no hive data (LM479)."})
    for m in re.finditer(r"Missing required field: hive_id", s):
        if "isServiceRole" not in s[max(0, m.start() - 400):m.start()]:
            out.append({"check": "l6_no_hive_refusal", "layer": "L6",
                        "reason": "a 'Missing required field: hive_id' answer is reachable outside the service-role "
                                  "branch - only a service-role caller (who names nobody) may be refused for no hive."})
            break

    # L6b - an anonymous caller is refused 401 with the sign-in sentence, before any model call.
    m401 = re.search(r"Sign in to analyze a photo\.", s)
    if not m401 or not re.search(r"status\s*:\s*401", s[m401.end():m401.end() + 300]):
        out.append({"check": "l6_anon_401", "layer": "L6",
                    "reason": "no 401 'Sign in to analyze a photo.' for an anonymous caller - with hive-less callers "
                              "served, identity is the only thing standing between the public URL and a vision call."})

    # L6c - the solo bucket is keyed on the VERIFIED uid: soloRateLimitKey(<v>, ...) where <v> is assigned only from
    # authUid, and authUid is destructured from `await resolveIdentity(...)`.
    key = re.search(r"checkSoloRateLimit\(\s*\w+\s*,\s*soloRateLimitKey\(\s*([A-Za-z_$][\w$]*)\s*,", s)
    verified_uid = re.search(r"\{[^}]*\bauthUid\b[^}]*\}\s*=\s*await\s+resolveIdentity\(", s)
    if not key or not verified_uid:
        out.append({"check": "l6_solo_key_verified", "layer": "L6",
                    "reason": "no checkSoloRateLimit(db, soloRateLimitKey(<verified uid>, ip)) for the hive-less caller "
                              "(or authUid is not taken from resolveIdentity) - a hive-less vision call must draw on "
                              "the person's own solo bucket."})
    else:
        var = key.group(1)
        assigns = [a.group(1).strip() for a in
                   re.finditer(r"(?<![\w$.])" + re.escape(var) + r"\s*(?::\s*[^=;]+)?=(?!=)\s*([^;]+);", s)]
        tainted = [a for a in assigns if re.search(r"\bbody\b|_whBody|\bpayload\b|req\.json", a)]
        from_uid = [a for a in assigns if re.fullmatch(r"authUid", a)]
        if tainted or not from_uid:
            out.append({"check": "l6_solo_key_verified", "layer": "L6",
                        "reason": f"the solo rate-limit key `{var}` is not the verified authUid "
                                  f"(assignments: {assigns[:3]}) - a body-named id lets any caller spend, or "
                                  f"escape, someone else's budget (Pillar P)."})
        # L6d - the asset match reads the same person's own register, never an unscoped one.
        if not re.search(r"matchAssetByTag\([^)]*\b" + re.escape(var) + r"\b[^)]*\)", s):
            out.append({"check": "l6_own_assets", "layer": "L6",
                        "reason": f"matchAssetByTag is not given the hive-less caller's verified uid `{var}` - their "
                                  f"OCR'd tag can never match their own registered assets."})
    if len(re.findall(r"\.is\(\s*[\"']hive_id[\"']\s*,\s*null\s*\)\s*\.eq\(\s*[\"']auth_uid[\"']", s)) < 2:
        out.append({"check": "l6_own_assets", "layer": "L6",
                    "reason": "both asset reads (explicit asset_id + OCR tag match) must scope a hive-less caller to "
                              "hive_id IS NULL AND auth_uid = <verified uid> - this runs on the service-role client."})

    # L6e - the analyze-time knowledge row is hive-only (a hive_id NULL row has no reader).
    if "fault_knowledge" in s and not re.search(r"if\s*\(\s*(?:verifiedHiveId|hive_id)\s*&&[^)]*draft\.confidence\s*>=", s):
        out.append({"check": "l6_knowledge_hive_only", "layer": "L6",
                    "reason": "the analyze-time fault_knowledge write is not gated on a hive - a hive-less row would be "
                              "an embedding spent on a model draft no RLS policy or knowledge search can ever read."})

    # L7 - the page's analyze handler never refuses for a missing hive.
    p = page_src or ""
    fn = re.search(r"async function vdcAnalyze\s*\([\s\S]*?(?=\n(?:async\s+)?function\s)", p)
    if not fn:
        out.append({"check": "l7_client_no_hive_refusal", "layer": "L7",
                    "reason": "logbook.html has no vdcAnalyze() - the photo path this gate protects must exist."})
    else:
        body = _strip_comments(fn.group(0))
        if re.search(r"!\s*HIVE_ID\b", body) or re.search(r"Join a hive", body, re.I):
            out.append({"check": "l7_client_no_hive_refusal", "layer": "L7",
                        "reason": "vdcAnalyze() refuses (or tells the person to join a hive) when HIVE_ID is empty - a "
                                  "solo owner is turned away from a draft the server now serves them (LM479)."})
        if "visual-defect-capture" not in body:
            out.append({"check": "l7_client_no_hive_refusal", "layer": "L7",
                        "reason": "vdcAnalyze() no longer calls visual-defect-capture."})
    return out


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
    issues.extend(hiveless_issues(src, _read(PAGE)))

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
        # Find any `generateEmbedding(` / `generateEmbeddingTagged(` (the strict-ingest form, 2026-10-26) not preceded by `await `.
        unawaited = re.search(r"(?<!await\s)generateEmbedding(?:Tagged)?\s*\(", src)
        has_then  = ".then(" in src
        # Fail only if generateEmbedding is awaited at top level OR no .then() chain exists.
        top_level_awaited = re.search(r"\bawait\s+generateEmbedding(?:Tagged)?\s*\(", src)
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


def self_test() -> int:
    """Teeth for L6/L7: the current files pass, and each regression below must FAIL. A mutant whose replacement no
    longer applies to the source is itself a failure (a STALE mutant would read as a kill while testing nothing)."""
    fn, pg = _read(EDGE_FN), _read(PAGE)
    if not fn or not pg:
        print("SELF-TEST FAIL: visual-defect-capture/index.ts or logbook.html is missing")
        return 1
    old_guard = "if (!hive_id) {\n      return new Response(JSON.stringify({ error: \"Missing required field: hive_id\" }), { status: 400 });\n    }\n"
    mutants = [
        ("client refuses a hive-less person again", "pg",
         "if (!_vdcDataUrl) { showToast('Capture a photo first.'); return; }",
         "if (!_vdcDataUrl) { showToast('Capture a photo first.'); return; }\n  if (!HIVE_ID) { showToast('Join a hive to analyze defects with AI.'); return; }"),
        ("server restores the hive_id 400 for everyone", "fn",
         "    let soloUid: string | null = null;\n", "    let soloUid: string | null = null;\n    " + old_guard),
        ("solo bucket keyed on a body field", "fn",
         "soloRateLimitKey(soloUid,", "soloRateLimitKey(body.auth_uid,"),
        ("solo uid taken from the body", "fn",
         "soloUid = authUid;", "soloUid = String(body.auth_uid || \"\");"),
        ("anonymous caller no longer refused", "fn",
         "Sign in to analyze a photo.", "Please try again."),
        ("tag match ignores the person's own register", "fn",
         "matchAssetByTag(db, verifiedHiveId, draft.asset_tag_extracted, soloUid)",
         "matchAssetByTag(db, verifiedHiveId, draft.asset_tag_extracted)"),
        ("explicit asset read unscoped for a hive-less caller", "fn",
         "_assetBase.is(\"hive_id\", null).eq(\"auth_uid\", soloUid as string)", "_assetBase"),
        ("analyze-time knowledge row written with no hive", "fn",
         "if (verifiedHiveId && draft.confidence >= 0.4", "if (draft.confidence >= 0.4"),
    ]
    ok = True
    base = hiveless_issues(fn, pg)
    print(f"  [{'ok' if not base else 'WRONG'}] current files: {'pass' if not base else 'fail ' + str([i['check'] for i in base])}")
    ok &= not base
    for label, which, old, new in mutants:
        src = fn if which == "fn" else pg
        if old not in src:
            print(f"  [STALE] {label}: the text it mutates is gone - update the mutant")
            ok = False
            continue
        mf, mp = (src.replace(old, new, 1), pg) if which == "fn" else (fn, src.replace(old, new, 1))
        got = hiveless_issues(mf, mp)
        killed = bool(got)
        ok &= killed
        print(f"  [{'ok' if killed else 'SURVIVED'}] {label}: "
              f"{'fail ' + str(sorted({i['check'] for i in got})) if killed else 'pass (want fail)'}")
    print(("SELF-TEST PASS" if ok else "SELF-TEST FAIL") + f": current passes, {len(mutants)} mutants")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else main())

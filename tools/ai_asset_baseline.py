"""
ai_asset_baseline.py — C5 of SELF_IMPROVING_GATE_ROADMAP.md.
=============================================================

Versions and baselines the AI assets the gate scores against (prompts,
model IDs, eval sets, judge model) the same way `migration_hashes.json`
versions schema. The contract: every AI asset declares a content version
(int). Editing the file requires bumping the version. The validator
FAILs if the content hash changed without the declared version moving.

Why this matters: C2 (`tools/ai_eval_gate.py`) compares persisted eval
results against a frozen golden (`ai_eval_baseline.json`) on the
held-out P6 split. If the golden fixtures, the judge prompt, the model
chain, or the persona block change silently, every prior baseline is
invalidated and the eval gate's verdicts become noise. C5 catches that
at G-1, cheaply.

Subcommands:
  build     Record any new assets at their declared version. Bump
            recorded version + hash when declared version moves AND
            content hash moves together. Writes ai_asset_baseline.json.
  verify    Same checks as build, but NEVER writes; exit 1 on any
            policy violation. This is what the validator wraps.
  report    Print a human-readable summary of the current baseline +
            file state side-by-side.

Manifest is inlined (5-7 entries today, small enough to live in code).
Add an entry here when a new versioned AI asset enters the gate's
trust boundary.

Asset kinds:
  json   read JSON; pull version from `_meta.ai_asset_version` (or a
         caller-supplied dotted path).
  ts     read file as text; pull version from
         `// AI_ASSET_VERSION: <int>` (or a caller-supplied prefix).

Optional assets (e.g. `ai_eval_baseline.json`, which C2 ships honest-
empty) are skipped if the file is missing; their absence is NOT a fail.
The asset stops being optional the moment it exists.

Exit codes:
  0  every asset matches its baseline OR was newly recorded.
  1  one or more policy violations detected (verify-only; build never
     hard-fails on the FAIL cases — it writes what it can and prints
     the diff so a human can decide).
"""
from __future__ import annotations
import argparse, hashlib, io, json, re, sys
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "ai_asset_baseline.json"
REPORT = ROOT / "ai_asset_baseline_report.json"

# --- Manifest -----------------------------------------------------------------
# Add a new versioned AI asset here. Keep entries small + explicit.
ASSETS = [
    {
        "id":   "evals.canonical_questions",
        "file": "evals/canonical_questions.json",
        "kind": "json",
        "version_path": "_meta.ai_asset_version",
        "owner": "ai-engineer",
        "note":  "Golden eval fixtures C2 (ai_eval_gate) scores against on the held-out split.",
    },
    {
        "id":   "shared.ai-chain",
        "file": "supabase/functions/_shared/ai-chain.ts",
        "kind": "ts",
        "marker": "AI_ASSET_VERSION",
        "owner": "ai-engineer",
        "note":  "Multi-provider fallback chain. Changing provider order/models drifts every eval.",
    },
    {
        "id":   "shared.persona",
        "file": "supabase/functions/_shared/persona.ts",
        "kind": "ts",
        "marker": "AI_ASSET_VERSION",
        "owner": "ai-engineer",
        "note":  "Hezekiah/Zaniah persona prompts. Tone shift = different answers from same fixtures.",
    },
    {
        "id":   "ai-eval-runner.judge",
        "file": "supabase/functions/ai-eval-runner/index.ts",
        "kind": "ts",
        "marker": "AI_ASSET_VERSION",
        "hash_region": r"const JUDGE_PROMPT = `(.*?)`;",
        "owner": "ai-engineer",
        "note":  "JUDGE_PROMPT template (prompt + embedded score rubric) — the judge definition. hash_region scopes the hash to this constant so infra edits (imports, serve()/serveObserved wrapper) never masquerade as judge drift, per the marker's own 'bump only when JUDGE_PROMPT/model/rubric/threshold changes' contract. Judge drift invalidates the C2 baseline.",
    },
    {
        "id":   "ai_eval_baseline",
        "file": "ai_eval_baseline.json",
        "kind": "json",
        "version_path": "_meta.ai_asset_version",
        "owner": "ai-engineer",
        "optional": True,
        "note":  "C2's frozen golden floor. Honest-empty today; gets versioned the first real run.",
    },
]


# --- Helpers ------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hash_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def asset_hash(asset: dict, raw: bytes) -> tuple[str | None, str | None]:
    """Content hash for an asset. By default hashes the whole file. If the asset
    declares a `hash_region` regex, hashes ONLY the first captured group instead
    — so the asset tracks its actual AI-relevant content (a judge prompt, a
    rubric) and is NOT tripped by infra edits to the same file (imports, the
    serve()/serveObserved() wrapper). A declared region that no longer matches
    is an ERROR (the tracked content was removed/renamed — must be noticed),
    never a silent fall-back to whole-file. Returns (sha, error)."""
    region = asset.get("hash_region")
    if not region:
        return hash_bytes(raw), None
    text = raw.decode("utf-8", errors="replace")
    m = re.search(region, text, re.DOTALL)
    if not m:
        return None, f"hash_region /{region}/ matched nothing (tracked content removed/renamed?)"
    captured = m.group(1) if m.groups() else m.group(0)
    return hash_bytes(captured.encode("utf-8")), None


def get_dotted(d: dict, path: str):
    cur = d
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


# Trailing `\r?` so CRLF and LF files both match (this was a real bug in the
# first cut — ai-chain.ts had CRLF while persona.ts had LF, so half the TS
# assets silently failed parseable detection. Always normalise EOL in regexes
# that touch source files on Windows.)
_TS_VERSION_RE_TEMPLATE = r"^[ \t/*]*{marker}[ \t]*:[ \t]*(\d+)[ \t]*\r?$"


def extract_version(asset: dict, raw_bytes: bytes) -> tuple[int | None, str | None]:
    """Return (version, error_message). version is None on failure."""
    kind = asset["kind"]
    if kind == "json":
        try:
            doc = json.loads(raw_bytes.decode("utf-8"))
        except Exception as e:
            return None, f"invalid JSON: {e}"
        path = asset.get("version_path", "_meta.ai_asset_version")
        v = get_dotted(doc, path)
        if not isinstance(v, int):
            return None, f"missing/non-int version at '{path}'"
        return v, None
    if kind == "ts":
        marker = asset.get("marker", "AI_ASSET_VERSION")
        text = raw_bytes.decode("utf-8", errors="replace")
        pat = re.compile(_TS_VERSION_RE_TEMPLATE.format(marker=re.escape(marker)), re.MULTILINE)
        m = pat.search(text)
        if not m:
            return None, f"missing '{marker}: <int>' marker (anywhere on its own line)"
        return int(m.group(1)), None
    return None, f"unknown asset kind '{kind}'"


def load_baseline() -> dict:
    if not BASELINE.exists():
        return {"_meta": {"format_version": "1.0",
                          "description": "C5: versioned baseline of AI assets. Validator FAILs if file hash moves without version bump.",
                          "asset_count": 0,
                          "test_seal": ""},
                "assets": {}}
    try:
        return json.loads(BASELINE.read_text(encoding="utf-8"))
    except Exception:
        return {"_meta": {"format_version": "1.0",
                          "description": "C5: versioned baseline of AI assets. Validator FAILs if file hash moves without version bump.",
                          "asset_count": 0,
                          "test_seal": ""},
                "assets": {}}


def compute_seal(baseline: dict) -> str:
    pairs = sorted(f"{aid}|{rec.get('current_version', 0)}"
                   for aid, rec in baseline.get("assets", {}).items())
    return hashlib.sha256("\n".join(pairs).encode("utf-8")).hexdigest()[:16]


# --- Core compare -------------------------------------------------------------
def evaluate(write: bool) -> tuple[int, dict]:
    """Walk the manifest, compare to baseline.
    Returns (exit_code, summary_dict)."""
    baseline = load_baseline()
    assets_baseline = baseline.setdefault("assets", {})

    findings = {
        "ok":              [],   # asset_id list — no change
        "recorded_new":    [],   # newly added to baseline
        "version_bumped":  [],   # legitimate bump recorded
        "missing_optional": [],  # optional asset whose file is missing
        "fail_silent_change":  [],  # FAIL — hash changed, version unchanged
        "fail_no_op_bump":     [],  # FAIL — version bumped but hash unchanged
        "fail_downgrade":      [],  # FAIL — declared version went backward
        "fail_unparseable":    [],  # FAIL — version field missing or malformed
        "fail_missing_file":   [],  # FAIL — required asset file is missing
    }

    for asset in ASSETS:
        aid = asset["id"]
        path = ROOT / asset["file"]
        optional = asset.get("optional", False)
        prior = assets_baseline.get(aid)

        if not path.exists():
            if optional:
                findings["missing_optional"].append(aid)
            else:
                findings["fail_missing_file"].append({"id": aid, "file": asset["file"]})
            continue

        raw = path.read_bytes()
        sha, herr = asset_hash(asset, raw)
        if herr:
            findings["fail_unparseable"].append({"id": aid, "file": asset["file"], "error": herr})
            continue
        declared, err = extract_version(asset, raw)
        if declared is None:
            findings["fail_unparseable"].append({"id": aid, "file": asset["file"], "error": err})
            continue

        # CASE 1 — new asset.
        if not prior:
            entry = {
                "file": asset["file"],
                "kind": asset["kind"],
                "current_version": declared,
                "sha256": sha,
                "history": [{"version": declared, "sha256": sha, "recorded_at": now_iso()}],
                "owner": asset.get("owner", ""),
            }
            assets_baseline[aid] = entry
            findings["recorded_new"].append({"id": aid, "version": declared})
            continue

        recorded_ver = int(prior.get("current_version", 0))
        recorded_sha = prior.get("sha256", "")

        # CASE 7 — declared version went backward.
        if declared < recorded_ver:
            findings["fail_downgrade"].append({
                "id": aid, "declared": declared, "recorded": recorded_ver,
            })
            continue

        # CASE 2 — no change at all.
        if declared == recorded_ver and sha == recorded_sha:
            findings["ok"].append(aid)
            continue

        # CASE 3 — hash changed but version didn't.
        if declared == recorded_ver and sha != recorded_sha:
            findings["fail_silent_change"].append({
                "id": aid, "version": declared,
                "old_sha": recorded_sha, "new_sha": sha,
            })
            continue

        # CASE 4 — version bumped but hash unchanged (no-op bump).
        if declared > recorded_ver and sha == recorded_sha:
            findings["fail_no_op_bump"].append({
                "id": aid, "old_version": recorded_ver, "new_version": declared,
                "sha": sha,
            })
            continue

        # CASE 5 / 6 — version bumped AND hash changed → legitimate bump.
        history = prior.get("history", [])
        history.append({"version": declared, "sha256": sha, "recorded_at": now_iso()})
        prior["current_version"] = declared
        prior["sha256"] = sha
        prior["history"] = history
        findings["version_bumped"].append({
            "id": aid, "from": recorded_ver, "to": declared,
        })

    fail_buckets = ["fail_silent_change", "fail_no_op_bump",
                    "fail_downgrade", "fail_unparseable", "fail_missing_file"]
    has_fail = any(findings[b] for b in fail_buckets)
    exit_code = 1 if has_fail else 0

    baseline["_meta"]["asset_count"] = len(assets_baseline)
    baseline["_meta"]["test_seal"] = compute_seal(baseline)
    baseline["_meta"]["last_evaluated"] = now_iso()

    summary = {
        "exit_code": exit_code,
        "manifest_size": len(ASSETS),
        "baseline_size": len(assets_baseline),
        "findings": findings,
        "test_seal": baseline["_meta"]["test_seal"],
    }

    if write and not has_fail:
        BASELINE.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if write and has_fail:
        # Even when failing, record any new-asset registrations + legitimate
        # bumps — they were correct. But leave the failed assets untouched.
        BASELINE.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    REPORT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return exit_code, summary


# --- CLI ----------------------------------------------------------------------
def cmd_build() -> int:
    code, summary = evaluate(write=True)
    print_summary(summary, mode="build")
    return code


def cmd_verify() -> int:
    code, summary = evaluate(write=False)
    print_summary(summary, mode="verify")
    return code


def cmd_report() -> int:
    code, summary = evaluate(write=False)
    print_summary(summary, mode="report")
    baseline = load_baseline()
    print("\n--- Baseline ---")
    for aid, rec in sorted(baseline.get("assets", {}).items()):
        print(f"  {aid:36s}  v{rec.get('current_version', '?')}  {rec.get('sha256','?')[:12]}  ({rec.get('file','?')})")
    print(f"\ntest_seal: {baseline.get('_meta',{}).get('test_seal','')}")
    return code


def print_summary(summary: dict, mode: str) -> None:
    f = summary["findings"]
    bar = "─" * 70
    print(bar)
    print(f"ai-asset-versioning ({mode}) — manifest={summary['manifest_size']}  "
          f"baseline={summary['baseline_size']}  seal={summary['test_seal']}")
    print(bar)
    if f["ok"]:                print(f"  ok               : {len(f['ok'])}  {', '.join(f['ok'])}")
    if f["recorded_new"]:      print(f"  recorded_new     : {len(f['recorded_new'])}  {f['recorded_new']}")
    if f["version_bumped"]:    print(f"  version_bumped   : {len(f['version_bumped'])}  {f['version_bumped']}")
    if f["missing_optional"]:  print(f"  missing_optional : {len(f['missing_optional'])}  {', '.join(f['missing_optional'])}")
    if f["fail_silent_change"]:
        print(f"\n  \033[91mFAIL silent_change\033[0m ({len(f['fail_silent_change'])}):")
        for e in f["fail_silent_change"]:
            print(f"    {e['id']} — version still {e['version']}, but hash {e['old_sha'][:12]} → {e['new_sha'][:12]}")
            print( "      Fix: bump the AI_ASSET_VERSION marker (or _meta.ai_asset_version) on this file.")
    if f["fail_no_op_bump"]:
        print(f"\n  \033[91mFAIL no_op_bump\033[0m ({len(f['fail_no_op_bump'])}):")
        for e in f["fail_no_op_bump"]:
            print(f"    {e['id']} — version {e['old_version']} → {e['new_version']} but content unchanged")
    if f["fail_downgrade"]:
        print(f"\n  \033[91mFAIL downgrade\033[0m ({len(f['fail_downgrade'])}):")
        for e in f["fail_downgrade"]:
            print(f"    {e['id']} — declared v{e['declared']} < recorded v{e['recorded']}")
    if f["fail_unparseable"]:
        print(f"\n  \033[91mFAIL unparseable\033[0m ({len(f['fail_unparseable'])}):")
        for e in f["fail_unparseable"]:
            print(f"    {e['id']} ({e['file']}) — {e['error']}")
    if f["fail_missing_file"]:
        print(f"\n  \033[91mFAIL missing_file\033[0m ({len(f['fail_missing_file'])}):")
        for e in f["fail_missing_file"]:
            print(f"    {e['id']} — {e['file']} does not exist (and is not marked optional)")
    print(bar)


def main() -> int:
    p = argparse.ArgumentParser(description="C5 — version/baseline AI assets like migrations.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    sub.add_parser("verify")
    sub.add_parser("report")
    args = p.parse_args()
    return {"build": cmd_build, "verify": cmd_verify, "report": cmd_report}[args.cmd]()


if __name__ == "__main__":
    sys.exit(main())

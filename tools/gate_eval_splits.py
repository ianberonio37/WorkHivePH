"""
Held-Out Evaluation Splits — P6 of SELF_IMPROVING_GATE_ROADMAP.md.
==================================================================
SkillOpt's #1 anti-overfit idea, made concrete: partition the rollout evidence into
**train / validation / locked-test** so the gate (and the skill files it edits) can never
declare success on the same data used to author the change.

  - train       : used to author rules / skill edits.
  - validation  : the accept/reject gate for a candidate edit.
  - test (LOCKED): touched ONLY for a periodic honest-score report; never tuned against.

The eval corpus = the L2 Playwright specs (`tests/*.spec.ts`) + the companion probe bank
(`tools/companion_probe_bank.json`). RAG evals are represented by their journey specs, which
are part of the spec corpus. Each unit is tagged with the SAME {domain, dimension} taxonomy
the efficacy ledger uses (imported from gate_efficacy_ledger), so per-domain scoring lines up.

Frozen like a migration hash
----------------------------
Assignment is a deterministic salted hash of the unit id -> bucket -> split, so it is
reproducible. Existing assignments in `gate_eval_splits.json` are PRESERVED on rebuild
(only NEW units get assigned), so the corpus can grow without reshuffling — and the locked
test set's membership is stable. A `test_seal` (sha256 over the sorted test-set ids) makes
the locked set tamper-evident: `verify` FAILs if current test membership != the committed
seal. Legitimate growth re-`build`s and re-commits the seal (a git trail); silently moving a
unit OUT of test to flatter a score is caught.

Usage:
  python tools/gate_eval_splits.py build      # enumerate corpus, assign NEW units, write splits + seal
  python tools/gate_eval_splits.py report     # per-split / per-domain / per-dimension breakdown
  python tools/gate_eval_splits.py verify      # check the locked test seal + corpus freshness (exit 1 on drift)
  python tools/gate_eval_splits.py resolve --split train --kind spec      # emit membership (one per line)
  python tools/gate_eval_splits.py resolve --split test --kind companion_probe --format json

State: `gate_eval_splits.json` (frozen assignment, like a migration hash).
Exit code: 0 normally; `verify` returns 1 if the locked test seal drifted.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT       = Path(__file__).resolve().parent.parent
TOOLS_DIR  = Path(__file__).resolve().parent
SPLITS_PATH = ROOT / "gate_eval_splits.json"
SPECS_DIR   = ROOT / "tests"
PROBE_BANK  = TOOLS_DIR / "companion_probe_bank.json"

# Reuse the ONE taxonomy from the efficacy ledger (C1). The split tool and the ledger must
# never drift apart on what "domain"/"dimension" mean.
sys.path.insert(0, str(TOOLS_DIR))
try:
    from gate_efficacy_ledger import classify_domain_dimension, DOMAINS, DIMENSIONS
except Exception:  # pragma: no cover — keep the tool runnable even if the ledger moves
    DOMAINS    = ("general", "saas", "ai")
    DIMENSIONS = ("usability", "functionality", "adaptability", "internal_control", "safety", "cost")
    def classify_domain_dimension(vid, label="", group="", overrides=None):
        return "general", "functionality"

SALT       = "wh-gate-eval-splits-v1"   # change only with a deliberate full re-split
TRAIN_PCT  = 60
VAL_PCT    = 20   # test = the remaining 20
KINDS      = ("spec", "companion_probe")
SPLITS     = ("train", "val", "test")

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"


def _load_json(p: Path):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _assign_split(kind: str, unit_id: str) -> str:
    """Deterministic salted-hash bucket -> split. Stable across runs and machines."""
    h = hashlib.sha1(f"{SALT}:{kind}:{unit_id}".encode("utf-8")).hexdigest()
    bucket = int(h, 16) % 100
    if bucket < TRAIN_PCT:
        return "train"
    if bucket < TRAIN_PCT + VAL_PCT:
        return "val"
    return "test"


def _classify_probe(entry: dict) -> tuple[str, str]:
    """Companion probes are AI-domain; adversarial/robustness probes exercise the AI
    Safety dimension, everything else exercises Functionality."""
    cat = str(entry.get("category", "")).lower()
    if cat.startswith("robustness") or "injection" in cat or "jailbreak" in cat or "gibberish" in cat:
        return "ai", "safety"
    return "ai", "functionality"


def _enumerate_corpus() -> list[dict]:
    """Walk the eval corpus -> [{id, kind, domain, dimension}]. Pure read, no writes."""
    units: list[dict] = []

    # 1) L2 Playwright specs (forward-slash ids for cross-platform stability)
    for p in sorted(SPECS_DIR.glob("*.spec.ts")):
        stem = p.stem.replace(".spec", "")
        dom, dim = classify_domain_dimension(stem, stem.replace("-", " "), "spec")
        units.append({"id": f"tests/{p.name}", "kind": "spec", "domain": dom, "dimension": dim})

    # 2) Companion probe bank (baseline + adversarial + held-out templates)
    bank = _load_json(PROBE_BANK) or {}
    for section in ("baseline", "adversarial", "held_out_templates"):
        for entry in (bank.get(section) or []):
            pid = entry.get("id")
            if not pid:
                continue
            dom, dim = _classify_probe(entry)
            units.append({"id": pid, "kind": "companion_probe", "domain": dom, "dimension": dim})

    return units


def _key(kind: str, unit_id: str) -> str:
    return f"{kind}:{unit_id}"


def _test_seal(items: dict) -> str:
    """sha256 over the sorted ids of every unit currently assigned to the locked test split."""
    test_ids = sorted(k for k, v in items.items() if v.get("split") == "test")
    return hashlib.sha256("\n".join(test_ids).encode("utf-8")).hexdigest()


def build() -> dict:
    """Enumerate the corpus, PRESERVE existing split assignments, assign only NEW units,
    recompute the test seal, write the splits file. Idempotent when the corpus is unchanged."""
    prev = _load_json(SPLITS_PATH) or {}
    prev_items = prev.get("items") or {}
    prev_seal  = prev.get("test_seal")

    items: dict = {}
    new_units, new_test = [], []
    for u in _enumerate_corpus():
        k = _key(u["kind"], u["id"])
        existing = prev_items.get(k)
        split = existing.get("split") if isinstance(existing, dict) and existing.get("split") in SPLITS \
            else _assign_split(u["kind"], u["id"])
        if k not in prev_items:
            new_units.append(k)
            if split == "test":
                new_test.append(k)
        items[k] = {"id": u["id"], "kind": u["kind"], "domain": u["domain"],
                    "dimension": u["dimension"], "split": split}

    dropped = [k for k in prev_items if k not in items]
    seal = _test_seal(items)
    counts = {s: sum(1 for v in items.values() if v["split"] == s) for s in SPLITS}

    out = {
        "version": 1,
        "salt": SALT,
        "ratios": {"train": TRAIN_PCT, "val": VAL_PCT, "test": 100 - TRAIN_PCT - VAL_PCT},
        "built_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "counts": counts,
        "total": len(items),
        "test_seal": seal,
        "items": dict(sorted(items.items())),
    }
    SPLITS_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"{GREEN}Splits built.{RESET} {len(items)} units  "
          f"(train {counts['train']} / val {counts['val']} / 🔒test {counts['test']})")
    if new_units:
        print(f"  {CYAN}+{len(new_units)} new unit(s){RESET}; {len(new_test)} of them entered the locked test set.")
    if dropped:
        print(f"  {YEL}-{len(dropped)} unit(s) no longer in the corpus (removed from splits).{RESET}")
    if prev_seal and prev_seal != seal:
        print(f"  {YEL}test_seal changed{RESET} {prev_seal[:12]}… -> {seal[:12]}…  "
              f"(legitimate only if the test set grew/shrank with the corpus — commit it).")
    elif not new_units and not dropped:
        print(f"  corpus unchanged — seal stable ({seal[:12]}…).")
    return out


def verify() -> int:
    """Tamper-evidence for the locked test set + corpus-freshness check. Exit 1 on drift."""
    data = _load_json(SPLITS_PATH)
    if not data or not data.get("items"):
        print(f"{YEL}No splits file yet — run `python tools/gate_eval_splits.py build` first.{RESET}")
        return 1
    items = data["items"]
    stored = data.get("test_seal")
    current = _test_seal(items)

    ok = True
    if stored != current:
        ok = False
        print(f"{RED}LOCKED-TEST SEAL DRIFT{RESET} — test membership changed vs the committed seal.")
        print(f"    stored : {stored}")
        print(f"    current: {current}")
        print(f"    -> the locked test set was edited. If this was a legitimate corpus change, "
              f"re-run `build` and COMMIT the new seal (leaves a git trail). Otherwise revert.")
    else:
        n_test = sum(1 for v in items.values() if v["split"] == "test")
        print(f"{GREEN}Locked test seal OK{RESET} — {n_test} test units, seal {current[:16]}… intact.")

    # Freshness: are there corpus units not yet in the file? (file stale -> rebuild)
    corpus_keys = {_key(u["kind"], u["id"]) for u in _enumerate_corpus()}
    missing = corpus_keys - set(items.keys())
    stale   = set(items.keys()) - corpus_keys
    if missing:
        ok = False
        print(f"{RED}{len(missing)} corpus unit(s) missing from splits{RESET} — run `build`. "
              f"e.g. {sorted(missing)[:3]}")
    if stale:
        print(f"{YEL}{len(stale)} split unit(s) no longer in the corpus{RESET} — `build` will prune. "
              f"e.g. {sorted(stale)[:3]}")
    return 0 if ok else 1


def report() -> None:
    data = _load_json(SPLITS_PATH)
    if not data or not data.get("items"):
        print(f"{YEL}No splits file yet — run `python tools/gate_eval_splits.py build` first.{RESET}")
        return
    items = data["items"]
    total = len(items)
    counts = {s: sum(1 for v in items.values() if v["split"] == s) for s in SPLITS}

    print(f"\n{BOLD}Held-Out Eval Splits{RESET}  ·  {total} units  ·  built {data.get('built_ts','?')}")
    print("=" * 70)
    print(f"  train {counts['train']}   val {counts['val']}   🔒test {counts['test']}   "
          f"(ratio {data.get('ratios')})")
    print(f"  test_seal: {str(data.get('test_seal'))[:24]}…  (run `verify` to check integrity)")

    # by kind x split
    print(f"\n{CYAN}{BOLD}  By kind{RESET}")
    for kind in KINDS:
        row = {s: sum(1 for v in items.values() if v["kind"] == kind and v["split"] == s) for s in SPLITS}
        n = sum(row.values())
        if n:
            print(f"    {kind:<16} train {row['train']:>4}  val {row['val']:>4}  test {row['test']:>4}   (n={n})")

    # by domain x split  (the per-domain honesty the scorecard needs)
    print(f"\n{CYAN}{BOLD}  By domain x split{RESET}")
    doms = list(DOMAINS) + sorted({v.get("domain", "?") for v in items.values()} - set(DOMAINS))
    for dom in doms:
        row = {s: sum(1 for v in items.values() if v.get("domain") == dom and v["split"] == s) for s in SPLITS}
        n = sum(row.values())
        if n:
            print(f"    {dom:<10} train {row['train']:>4}  val {row['val']:>4}  test {row['test']:>4}   (n={n})")

    # by dimension x split
    print(f"\n{CYAN}{BOLD}  By dimension x split{RESET}")
    dims = list(DIMENSIONS) + sorted({v.get("dimension", "?") for v in items.values()} - set(DIMENSIONS))
    for dim in dims:
        row = {s: sum(1 for v in items.values() if v.get("dimension") == dim and v["split"] == s) for s in SPLITS}
        n = sum(row.values())
        if n:
            print(f"    {dim:<18} train {row['train']:>4}  val {row['val']:>4}  test {row['test']:>4}   (n={n})")
    print()


def resolve(split: str, kind: str | None, fmt: str) -> None:
    """Emit the membership of a split (optionally filtered by kind) for a runner to consume:
       playwright test $(python tools/gate_eval_splits.py resolve --split train --kind spec)"""
    data = _load_json(SPLITS_PATH) or {}
    items = data.get("items") or {}
    members = [v["id"] for v in items.values()
               if v["split"] == split and (kind in (None, "all") or v["kind"] == kind)]
    members.sort()
    if fmt == "json":
        print(json.dumps(members))
    else:
        for m in members:
            print(m)


def members_for_split(split: str, kind: str | None = None) -> set:
    """Importable helper for runners/graders: the set of unit ids in a split (optional kind)."""
    data = _load_json(SPLITS_PATH) or {}
    items = data.get("items") or {}
    return {v["id"] for v in items.values()
            if v["split"] == split and (kind in (None, "all") or v["kind"] == kind)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Held-out eval splits (train/val/locked-test) — P6")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("build",  help="enumerate corpus, assign NEW units, write splits + seal")
    sub.add_parser("report", help="per-split / per-domain / per-dimension breakdown")
    sub.add_parser("verify", help="check the locked test seal + corpus freshness (exit 1 on drift)")
    rp = sub.add_parser("resolve", help="emit membership of a split for a runner to consume")
    rp.add_argument("--split", required=True, choices=list(SPLITS))
    rp.add_argument("--kind", default="all", choices=list(KINDS) + ["all"])
    rp.add_argument("--format", default="lines", choices=["lines", "json"])
    args = ap.parse_args()

    cmd = args.cmd or "report"
    if cmd == "build":
        build()
    elif cmd == "verify":
        return verify()
    elif cmd == "resolve":
        resolve(args.split, args.kind, args.format)
    else:
        report()
    return 0


if __name__ == "__main__":
    sys.exit(main())

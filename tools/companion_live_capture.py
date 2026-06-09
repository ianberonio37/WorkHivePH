"""
Companion Live Capture (headless) — Probe Taxonomy families F/G/H/E live capture.
================================================================================
Drives a marker-graded golden set (companion_{domain,robustness,doctrine,safety_gaps}_golden.json)
through the LIVE ai-gateway `voice-journal` route and captures the prose reply (body.data.answer)
into a normalized observation map .tmp/<dim>_golden_observed.json keyed by unit id: { answer }.

This is the headless twin of tests/persona-golden-capture.spec.ts — SAME mechanism (reset the
ephemeral rate-limit/cache tables before each call so nothing is 429'd or cached, pace between
calls, unwrap the gateway `.data` envelope) but via Python+anon-key instead of Playwright, because
the F/G/H/E families are GENERAL-KNOWLEDGE questions that need no user records, so an anon/null
context is both sufficient and clean (no per-user contamination). NO mocking: real edge fn, real
free-tier LLM chain. The map feeds `python tools/companion_<fam>_eval.py --observed`.

The floating-widget grounding posture (DOC-H3) is reproduced exactly by this null-records context:
voice-journal does no asset RAG, so with no asset_id it cannot see the user's logbook — which is
the whole point of H3 (the floating widget must say "I can't see your records, go to the assistant").

Usage:
  python tools/companion_live_capture.py --family all-new     # domain+robustness+doctrine+safety_gaps
  python tools/companion_live_capture.py --family domain      # one family
  python tools/companion_live_capture.py --golden X.json --out .tmp/y_observed.json --dim z
"""
from __future__ import annotations
import argparse
import io
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / ".tmp"

SUPABASE_URL = "http://127.0.0.1:54321"
SUPABASE_KEY = "sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ"
GATEWAY = f"{SUPABASE_URL}/functions/v1/ai-gateway"
DB_DSN = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"

# family -> (golden file, observed out, dimension label)
FAMILIES = {
    "domain":      ("companion_domain_golden.json",      OUT_DIR / "domain_golden_observed.json",      "domain"),
    "robustness":  ("companion_robustness_golden.json",  OUT_DIR / "robustness_golden_observed.json",  "robustness"),
    "doctrine":    ("companion_doctrine_golden.json",    OUT_DIR / "doctrine_golden_observed.json",    "safety"),
    "safety_gaps": ("companion_safety_gaps_golden.json", OUT_DIR / "safety_gaps_golden_observed.json", "safety"),
}

RESET_SQL = [
    "DELETE FROM ai_rate_limits WHERE hive_id IS NOT NULL OR hive_id IS NULL",
    "DELETE FROM ai_user_rate_limits WHERE user_id IS NOT NULL OR user_id IS NULL",
    "DELETE FROM ai_cache WHERE key IS NOT NULL OR key IS NULL",
]


def reset_counters(conn) -> None:
    """Clear the ephemeral rate-limit + cache tables so no reply is 429'd or served from cache."""
    if conn is None:
        return
    try:
        with conn.cursor() as cur:
            for sql in RESET_SQL:
                try:
                    cur.execute(sql)
                except Exception:
                    conn.rollback()
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass


def call_voice_journal(message: str, persona: str = "zaniah", lang: str = "auto") -> dict:
    t0 = time.time()
    body = {"agent": "voice-journal", "message": message,
            "context": {"persona": persona, "lang": lang}, "hive_id": None}
    headers = {"Content-Type": "application/json",
               "Authorization": f"Bearer {SUPABASE_KEY}", "apikey": SUPABASE_KEY}
    try:
        resp = requests.post(GATEWAY, json=body, headers=headers, timeout=60)
        latency_ms = int((time.time() - t0) * 1000)
        try:
            payload = resp.json()
        except Exception:
            payload = {"raw": resp.text}
        return {"ok": resp.ok, "status": resp.status_code, "latency_ms": latency_ms, "body": payload}
    except Exception as e:
        return {"ok": False, "status": 0, "latency_ms": int((time.time() - t0) * 1000), "body": {"error": str(e)}}


def answer_of(body: dict) -> str:
    """Gateway wraps success under `.data`; voice-journal is conversational -> data.answer."""
    data = (body or {}).get("data") or body or {}
    rr = data.get("route_result") or {}
    return str(data.get("answer") or rr.get("answer") or rr.get("narration") or "")


def _units(golden: dict) -> list[dict]:
    return list(golden.get("probes") or golden.get("units") or [])


def capture_family(golden_path: Path, out_path: Path, dim: str, conn, pace: float) -> dict:
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    units = _units(golden)
    observed: dict[str, dict] = {}
    raw: list[dict] = []
    ok = rate_limited = 0
    print(f"\n{BOLD}{CYAN}== {dim} =={RESET}  {golden_path.name}  ({len(units)} units)")
    for u in units:
        uid = u.get("id")
        q = u.get("question") or u.get("utterance") or ""
        reset_counters(conn)
        r = call_voice_journal(q)
        if r["ok"]:
            ok += 1
        if r["status"] == 429:
            rate_limited += 1
        ans = answer_of(r["body"])
        observed[uid] = {"answer": ans}
        raw.append({"id": uid, "status": r["status"], "ok": r["ok"], "latency_ms": r["latency_ms"],
                    "ability": u.get("ability"), "probe_type": u.get("probe_type"),
                    "answer_len": len(ans)})
        flag = GREEN + "ok" + RESET if r["ok"] and ans else (RED + f"FAIL({r['status']})" + RESET)
        print(f"  {uid:<10} {flag:<18} {r['latency_ms']:>6}ms  {ans[:70].replace(chr(10), ' ')}")
        time.sleep(pace)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(observed, indent=2), encoding="utf-8")
    raw_path = out_path.with_name(out_path.stem.replace("_observed", "_raw") + ".json")
    raw_path.write_text(json.dumps({"dim": dim, "ok": ok, "rate_limited": rate_limited,
                                    "total": len(units), "generated_ts": datetime.now(timezone.utc).isoformat(),
                                    "raw": raw}, indent=2), encoding="utf-8")
    print(f"  -> {out_path.relative_to(ROOT)}  ({ok}/{len(units)} ok, {rate_limited} rate-limited)")
    return {"dim": dim, "ok": ok, "total": len(units), "rate_limited": rate_limited, "out": str(out_path)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Headless live capture of marker-graded golden sets via ai-gateway.")
    ap.add_argument("--family", default=None, help="domain | robustness | doctrine | safety_gaps | all-new")
    ap.add_argument("--golden", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--dim", default=None)
    ap.add_argument("--pace", type=float, default=4.0, help="seconds between calls (rate-limit pacing)")
    ap.add_argument("--no-reset", action="store_true", help="do NOT reset rate-limit counters between calls")
    args = ap.parse_args()

    conn = None
    if not args.no_reset and psycopg2 is not None:
        try:
            conn = psycopg2.connect(DB_DSN)
        except Exception as e:
            print(f"{YEL}WARN: could not connect to local DB for counter reset ({e}); pacing only.{RESET}")

    jobs: list[tuple[Path, Path, str]] = []
    if args.family == "all-new":
        for fam in ("domain", "robustness", "doctrine", "safety_gaps"):
            g, o, d = FAMILIES[fam]
            jobs.append((ROOT / g, o, d))
    elif args.family in FAMILIES:
        g, o, d = FAMILIES[args.family]
        jobs.append((ROOT / g, o, d))
    elif args.golden and args.out:
        jobs.append((Path(args.golden), Path(args.out), args.dim or "domain"))
    else:
        print(f"{RED}Specify --family <name|all-new> or --golden + --out.{RESET}")
        return 2

    summaries = []
    for golden_path, out_path, dim in jobs:
        if not golden_path.exists():
            print(f"{RED}missing golden: {golden_path}{RESET}")
            continue
        summaries.append(capture_family(golden_path, out_path, dim, conn, args.pace))

    print(f"\n{BOLD}Capture summary{RESET}")
    total_rl = sum(s["rate_limited"] for s in summaries)
    for s in summaries:
        print(f"  {s['dim']:<12} {s['ok']}/{s['total']} ok  ({s['rate_limited']} rate-limited)")
    if total_rl:
        print(f"{YEL}WARNING: {total_rl} calls rate-limited — do NOT freeze a baseline from this run.{RESET}")
    else:
        print(f"{GREEN}clean run (0 rate-limited) — safe to grade + freeze.{RESET}")
    if conn:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

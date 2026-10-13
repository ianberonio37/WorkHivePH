#!/usr/bin/env python3
"""ping_ai_chain.py - ask EVERY entry of the platform's AI chain one tiny question and report who answers.

validate_groq_fallback.py's check_models_are_live proves a configured name EXISTS in its provider's /models list.
That is not the same as answering: on 2026-10-07 two OpenRouter :free models that the list reported answered
403 "only available on agentic harnesses", two Gemma models were rate-limited upstream, and two reasoning models
returned no content inside a small token budget. This tool sends each entry of supabase/functions/_shared/ai-chain.ts
(the chain is READ from that file, never re-typed) one request - "Reply with the single word OK.", max_tokens 64 -
with the keys in supabase/functions/.env, and prints status, latency, tokens and the answer.

Every provider on the chain is a free tier, so the spend is $0; the tokens are printed anyway (Ian's rule: state the
spend). Network and keys are required; an entry whose key is missing is reported as NOT ASKED, never as a pass.

  python tools/ping_ai_chain.py            all entries
  python tools/ping_ai_chain.py --json     machine-readable, written to .tmp/ai_chain_ping.json

PACED (2026-10-08, tools/lib/chain_pacer.py): one request per entry, at least --gap seconds apart (default 3 s:
OpenRouter's :free models allow 20 requests/minute and six of them sit in a row), at most --max-calls requests
(default: every selected entry), and it STOPS EARLY with a "QUOTA EXHAUSTED" line - exit 0, not a failure - once every
provider it has asked has answered 429 and nothing has answered. A ping that keeps asking after that only spends the
daily free quota it is trying to measure.
  --only mistral,gemini-2.5      entries whose provider or model contains any of these substrings
  --budget-file .tmp/x.json      a session's hard ceiling on live calls (LiveCallBudget): checked BEFORE each request
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "lib"))
from chain_pacer import GAP_DIRECT_CALL_S, ChainPacer, LiveCallBudget  # noqa: E402
CHAIN = ROOT / "supabase" / "functions" / "_shared" / "ai-chain.ts"
ENV = ROOT / "supabase" / "functions" / ".env"
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def chain_entries() -> list[dict]:
    src = CHAIN.read_text(encoding="utf-8")
    body = src[src.index("PROVIDER_CHAIN"):] if "PROVIDER_CHAIN" in src else src
    body = body[:body.index("];") + 2]
    out = []
    body = "\n".join("" if ln.lstrip().startswith("//") else ln for ln in body.splitlines())
    for m in re.finditer(r'\{\s*provider:\s*"([^"]+)",\s*baseUrl:\s*"([^"]+)",\s*model:\s*"([^"]+)",\s*envKey:\s*"([^"]+)"([^\n]*)', body):
        # the entry's own extraBody rides along (gpt-oss needs reasoning_effort "low" or its reasoning eats a small
        # max_tokens and the ping reads EMPTY for a model that answers the platform fine)
        xb = re.search(r"extraBody:\s*(\{[^}]*\})", m.group(5))
        extra = json.loads(re.sub(r"(\w+)\s*:", r'"\1":', xb.group(1))) if xb else {}
        out.append({"provider": m.group(1), "base": m.group(2), "model": m.group(3), "env": m.group(4), "extra": extra})
    return out


def env_keys() -> dict:
    keys = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            keys[k.strip()] = v.strip().strip('"')
    return keys


def ping(e: dict, key: str) -> dict:
    body = json.dumps({"model": e["model"], "messages": [{"role": "user", "content": "Reply with the single word OK."}],
                       "max_tokens": 64, **e.get("extra", {})}).encode()
    # an explicit User-Agent: Groq sits behind Cloudflare, which answers Python-urllib's default UA with
    # 403 "error code: 1010" (browser-signature ban) - a reading about this tool, not about the provider (2026-10-07)
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "WorkHive-ai-chain-ping/1.0"}
    if e["provider"] == "openrouter":
        headers.update({"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"})
    req = urllib.request.Request(e["base"].rstrip("/") + "/chat/completions", data=body, method="POST", headers=headers)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            j = json.loads(r.read().decode())
            u = j.get("usage") or {}
            txt = ((j.get("choices") or [{}])[0].get("message") or {}).get("content")
            return {"status": 200, "s": round(time.time() - t0, 1), "tokens": u.get("total_tokens"),
                    "answer": (txt or "").strip()[:40], "verdict": "ANSWERS" if (txt or "").strip() else "EMPTY"}
    except urllib.error.HTTPError as ex:
        detail = ex.read().decode(errors="replace")[:140]
        verdict = {429: "RATE-LIMITED", 404: "GONE", 403: "REFUSED", 401: "KEY-REJECTED"}.get(ex.code, "ERROR")
        return {"status": ex.code, "s": round(time.time() - t0, 1), "tokens": 0, "answer": detail, "verdict": verdict}
    except Exception as ex:  # timeout, DNS
        return {"status": None, "s": round(time.time() - t0, 1), "tokens": 0, "answer": str(ex)[:140], "verdict": "NO-ANSWER"}


def _arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv and sys.argv.index(flag) + 1 < len(sys.argv) else default


def main() -> int:
    keys = env_keys()
    rows = []
    only = [x.strip().lower() for x in (_arg("--only") or "").split(",") if x.strip()]
    chain = list(enumerate(chain_entries()))
    sel = [(i, e) for i, e in chain if not only or any(o in (e["provider"] + " " + e["model"]).lower() for o in only)]
    pacer = ChainPacer("ping", float(_arg("--gap", GAP_DIRECT_CALL_S)), int(_arg("--max-calls", len(sel))))
    budget = LiveCallBudget(_arg("--budget-file")) if _arg("--budget-file") else None
    providers = {e["provider"] for _, e in sel if keys.get(e["env"])}
    # "every provider answered 429": a run of consecutive 429s that covers every selected provider and is at least
    # max(4, 2 x providers) long. Limits are partly PER MODEL (2026-10-08: codestral answered 200 while mistral medium
    # and small were 429), so one 429 per provider is not enough evidence that the rest of its entries are walled too.
    streak = []
    for i, e in sel:
        k = keys.get(e["env"], "")
        if not k:
            r = {"status": None, "s": 0, "tokens": 0, "answer": f"{e['env']} not set", "verdict": "NOT ASKED"}
        elif not pacer.wait():
            break
        elif budget and not budget.take(f"ping {e['provider']}/{e['model']}"):
            break
        else:
            r = ping(e, k)
        rows.append({**e, **r, "depth": i})
        print(f"{i:>2} {e['provider']:<10} {e['model']:<48} {r['verdict']:<12} {str(r['status']):<4} {r['s']:>5}s "
              f"tok={r['tokens']} {r['answer'][:40]!r}")
        if r["status"] == 429:
            streak.append(e["provider"])
        elif r["status"] is not None:
            streak = []
        if (providers and set(streak) >= providers and len(streak) >= max(4, 2 * len(providers))
                and not any(x["verdict"] == "ANSWERS" for x in rows)):
            print(f"  [ping] QUOTA EXHAUSTED: every provider asked ({', '.join(sorted(providers))}) answered 429 and none "
                  f"answered - stopping early; the rest are NOT ASKED, not failed")
            return 0
    tot = sum(r["tokens"] or 0 for r in rows)
    ans = sum(r["verdict"] == "ANSWERS" for r in rows)
    print(f"\n{ans}/{len(rows)} entries answered; {tot} tokens in all (free tiers: $0)")
    first = next((r for r in rows if r["verdict"] == "ANSWERS"), None)
    print("first answering entry:", f"depth {first['depth']} {first['provider']} {first['model']}" if first else "NONE")
    if "--json" in sys.argv:
        (ROOT / ".tmp" / "ai_chain_ping.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return 0 if ans or not rows else 1


if __name__ == "__main__":
    sys.exit(main())

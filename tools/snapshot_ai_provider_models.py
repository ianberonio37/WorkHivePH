#!/usr/bin/env python3
"""snapshot_ai_provider_models.py - ask every AI-chain provider which models it serves, and keep the answer.

The chain in supabase/functions/_shared/ai-chain.ts names models at five free-tier providers. Models are retired,
renamed and moved behind a paywall without notice (v5: 11 of 18 dead; v6: 4 more; v7: 2 more; 2026-10-08: the whole
Cerebras tier answered 402 payment_required). validate_groq_fallback.check_models_are_live asks the providers at gate
time, which is right but NETWORK-OPTIONAL: offline it skips, so a board run without keys proves nothing. This tool
writes what the providers said to tools/ai_provider_models_snapshot.json, and the static gate
tools/validate_ai_chain_models_snapshot.py fails any chain entry that snapshot does not contain - offline, every run.

It calls ONLY each provider's models-list endpoint (no generation, no tokens, $0), with the keys in
supabase/functions/.env (falling back to .env), reusing validate_groq_fallback's own endpoint table and key reader so
there is one answer to "who do we ask".

What a models list cannot tell you is whether THIS key may use a listed model: Cerebras listed both of its models on
2026-10-08 while every chat call to them answered 402 "Payment required". Those measured refusals live in the
snapshot's hand-kept "unavailable_on_key" map ("provider/model" -> status, reason, date). A listed model that answers
but cannot serve the chain's request shape (JSON mode, a thinking budget) goes in "rejected_for_chain" the same way.
--write PRESERVES both maps, and the gate fails a chain entry named in either, even though the provider lists it.

  python tools/snapshot_ai_provider_models.py            print each provider's list (free models only for OpenRouter)
  python tools/snapshot_ai_provider_models.py --write    also rewrite tools/ai_provider_models_snapshot.json
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "tools" / "ai_provider_models_snapshot.json"
sys.path.insert(0, str(ROOT))

import validate_groq_fallback as V  # noqa: E402  (endpoint table + key reader - one source of truth)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _fetch(provider: str):
    url, env_key = V.LIVE_LIST_ENDPOINTS[provider]
    key = V._env_value(env_key) if env_key else ""
    if env_key and not key:
        return None, f"{env_key} not set here"
    headers = {"User-Agent": "workhive-chain-validator/1.0", "Accept": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
            return json.loads(r.read().decode("utf-8")).get("data", []), None
    except Exception as e:  # noqa: BLE001 - reported, never swallowed into a pass
        return None, f"{type(e).__name__}: {str(e)[:100]}"


def _is_free_openrouter(m: dict) -> bool:
    p = m.get("pricing") or {}
    try:
        return float(p.get("prompt", 1)) == 0 and float(p.get("completion", 1)) == 0
    except (TypeError, ValueError):
        return False


def survey() -> dict:
    out = {}
    for provider in V.LIVE_LIST_ENDPOINTS:
        data, err = _fetch(provider)
        if err:
            out[provider] = {"error": err}
            continue
        rows = {}
        for m in data:
            mid = str(m.get("id", "")).replace("models/", "")
            if not mid:
                continue
            if provider == "openrouter" and not _is_free_openrouter(m):
                continue  # a paid OpenRouter slug is not a candidate for a $0 chain, so it is not "available"
            if provider == "groq" and m.get("active") is False:
                continue
            mods = (m.get("architecture") or {}).get("input_modalities") or m.get("input_modalities") or []
            ctx = (m.get("context_length") or m.get("context_window") or m.get("max_context_length")
                   or (m.get("top_provider") or {}).get("context_length") or "")
            info = {"ctx": ctx, "in": ",".join(mods)}
            if provider == "mistral":
                caps = m.get("capabilities") or {}
                info["chat"] = bool(caps.get("completion_chat"))
                if m.get("deprecation"):
                    info["deprecation"] = m.get("deprecation")
                for alias in m.get("aliases") or []:
                    rows.setdefault(alias, {"alias_of": mid})
            rows[mid] = {**rows.get(mid, {}), **info}
        out[provider] = {"models": rows}
    return out


def main() -> int:
    res = survey()
    for provider, r in res.items():
        print("=" * 78)
        if "error" in r:
            print(f"{provider.upper()} - NOT ASKED: {r['error']}")
            continue
        print(f"{provider.upper()} - {len(r['models'])} models" + (" (zero-priced only)" if provider == "openrouter" else ""))
        for mid, info in sorted(r["models"].items()):
            extra = " ".join(f"{k}={v}" for k, v in info.items() if v not in ("", None))
            print(f"  {mid[:56]:<56} {extra}")
    if "--write" in sys.argv:
        if any("error" in r for r in res.values()):
            print("\nNOT WRITTEN: a provider could not be asked; a partial snapshot would read as 'those models are gone'.")
            return 1
        prev = {}
        if SNAPSHOT.exists():
            try:
                prev = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
            except Exception:
                prev = {}
        snap = {
            "_doc": "Each AI-chain provider's own models list (OpenRouter: zero-priced models only; Groq: active only). "
                    "Written by tools/snapshot_ai_provider_models.py --write; read by tools/validate_ai_chain_models_snapshot.py. "
                    "unavailable_on_key and rejected_for_chain are hand-kept and preserved across refreshes: a model the "
                    "provider LISTS but this platform's key may not use, or that cannot serve the chain's request shape, "
                    "each with the measured reason.",
            "captured_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "removed_providers": prev.get("removed_providers", {}),
            "unavailable_on_key": prev.get("unavailable_on_key", {}),
            "rejected_for_chain": prev.get("rejected_for_chain", {}),
            "providers": {p: sorted(r["models"].keys()) for p, r in res.items()},
        }
        SNAPSHOT.write_text(json.dumps(snap, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(f"\nwrote {SNAPSHOT.relative_to(ROOT)} ({sum(len(v) for v in snap['providers'].values())} ids)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

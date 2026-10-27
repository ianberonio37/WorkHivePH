"""Python replica of supabase/functions/_shared/ai-chain.ts.

Same free-tier fallback chain (Groq → Gemini → Mistral → OpenRouter, code
models last) the edge functions use — kept in lockstep with
_shared/ai-chain.ts PROVIDER_CHAIN (and tools/ai_chain.py). Missing API
keys cause silent skip — script keeps working with whatever's configured.
429 / 413 / 503 are recoverable; we move to the next entry (honoring
Retry-After, P2). Hard errors raise.

PACED (2026-10-08): every call_ai() goes through tools/lib/chain_pacer.process_pacer() - the same process-wide gap,
cap and quota-exhausted stop as tools/ai_chain.py. A stopped pacer raises AIQuotaExhausted (an AIChainError) without
sending anything.

Why a local replica:
  - Edge functions can't be invoked from one-shot Python tools cleanly
  - Tools running against local Supabase (psycopg2) need direct LLM access
  - Keeps Python tools aligned with the platform's chain semantics
  - When the TS chain grows a new provider, mirror it here

Usage:
    from tools.lib.ai_chain import call_ai
    out = call_ai("Translate to Cebuano: oil leak", json_mode=False)
"""
from __future__ import annotations

import os
import random
import re
import time
from dataclasses import dataclass
from typing import Optional

import requests


# ── Reasoning-strip parity with TS _shared/ai-chain.ts stripReasoningBlocks ──
# Case 1/2: <think>…</think> blocks. Case 3 (V5, 2026-07-13): untagged persona-scaffold
# leaks ("We need to respond as Zaniah, strategist… the worker says:…") that some free-tier
# models emit as bare prose — caught live by voice_family_probe. Returns "" when the reply
# is reasoning-only, so the caller tries the next model.
_THINK_PAIR_RE = re.compile(r"<think[\s>][\s\S]*?</think>", re.IGNORECASE)
_PLAN_START_RE = re.compile(
    r"^\s*(?:okay,?\s*|so,?\s*|alright,?\s*|well,?\s*)?(?:we|i|let(?:'s| us| me))\b"
    r"[^.!?\n]{0,60}?(?:\b(?:need(?:s)? to|should|must|will|have to|'ll|'re going to|going to|want to)\b[^.!?\n]{0,60}?)?"
    r"\b(?:respond|reply|answer|say|be|act|write|give|frame|craft|address|produce|consider)\b",
    re.IGNORECASE)
_SCAFFOLD_META_RE = re.compile(
    r"\b(?:as\s+(?:zaniah|hezekiah)|as\s+the\s+(?:strategist|technician)|1\s*-\s*3\s+sentences|"
    r"short\s+1-3|kpis?\s+verbatim|sisterly\s+ph\s+english|persona|system\s+prompt|"
    r"the\s+worker\s+(?:says|said)|snapshot\s+data|memory\s+block)\b",
    re.IGNORECASE)


def _strip_reasoning_blocks(text: str) -> str:
    if not text:
        return text or ""
    out = _THINK_PAIR_RE.sub("", text).strip()
    if out.lower().startswith("<think"):
        idx = out.lower().find("</think>")
        out = out[idx + len("</think>"):].strip() if idx != -1 else ""
    if out and _PLAN_START_RE.search(out) and _SCAFFOLD_META_RE.search(out):
        return ""
    return out


@dataclass
class _Provider:
    provider:      str
    base_url:      str
    model:         str
    env_key:       str
    max_tokens_cap: Optional[int] = None
    extra_headers: Optional[dict[str, str]] = None
    extra_body:    Optional[dict] = None   # provider-specific request fields, as ai-chain.ts extraBody
    last_resort:   bool = False            # a code model: tried after every general model, as ai-chain.ts lastResort


# Order mirrors _shared/ai-chain.ts exactly — change one, change both.
_CHAIN: list[_Provider] = [
    # Tier 1: Groq (LPU hardware, fastest)
    # ★MIRRORED 2026-09-10 - the THIRD copy of this list. Seven of the first nine entries named
    # models that no longer exist, measured against each provider's /models endpoint. This file's
    # own header says "change one, change both", and there are in fact THREE: _shared/ai-chain.ts,
    # tools/ai_chain.py and this one. All three carried the same dead names.
    # ...AND IT DRIFTED AGAIN ON 2026-09-28, for the reason the note above only half-names: the gate
    # written after that lesson, validate_ai_chain_mirror.py, compares ai-chain.ts against
    # tools/ai_chain.py and has never opened THIS file. So the pair stayed in lockstep, reported
    # "15 == 15, all pairs match", and this third copy kept four models none of the providers serve.
    # A mirror gate that reads two of three mirrors is a gate whose reach is narrower than its rule.
    # It now reads all three; see its L5.
    _Provider("groq", "https://api.groq.com/openai/v1", "qwen/qwen3.8-27b",                           "GROQ_API_KEY"),
    # v9 (2026-10-08): reasoning_effort "low" - at the default effort gpt-oss spent the whole max_tokens reasoning and
    # Groq answered 400 json_validate_failed (failed_generation ""). Mirrors the TS chain.
    _Provider("groq", "https://api.groq.com/openai/v1", "openai/gpt-oss-20b",                         "GROQ_API_KEY", extra_body={"reasoning_effort": "low"}),
    _Provider("groq", "https://api.groq.com/openai/v1", "openai/gpt-oss-120b",                        "GROQ_API_KEY", extra_body={"reasoning_effort": "low"}),
    # (Tier 2 was Cerebras: REMOVED from the platform 2026-10-08 - 402 payment_required on every call since 2026-09-10.)
    # Tier 3: Google Gemini (free tier)
    _Provider("google", "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash",      "GEMINI_API_KEY", extra_body={"reasoning_effort": "none"}),
    # v10: a separate per-model free quota; "low" thinking kept a 320-token JSON answer whole. Mirrors the TS chain.
    _Provider("google", "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.1-flash-lite", "GEMINI_API_KEY", extra_body={"reasoning_effort": "low"}),
    _Provider("google", "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash-lite", "GEMINI_API_KEY"),
    # Tier 4: Mistral (free tier)
    _Provider("mistral", "https://api.mistral.ai/v1", "mistral-medium-latest", "MISTRAL_API_KEY"),
    # v9: fills a slot Cerebras held. Mirrors the TS chain.
    _Provider("mistral", "https://api.mistral.ai/v1", "mistral-small-latest",  "MISTRAL_API_KEY"),
    # Tier 5: OpenRouter (200 req/day on :free models)
    # (v14: nvidia/nemotron-3-super-120b-a12b:free removed - openrouter answers 404 for it; mirrors the TS chain)
    _Provider("openrouter", "https://openrouter.ai/api/v1", "google/gemma-4-31b-it:free",
              "OPENROUTER_API_KEY", extra_headers={"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"}),
    _Provider("openrouter", "https://openrouter.ai/api/v1", "google/gemma-4-26b-a4b-it:free",
              "OPENROUTER_API_KEY", extra_headers={"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"}),
    _Provider("openrouter", "https://openrouter.ai/api/v1", "nvidia/nemotron-3-ultra-550b-a55b:free",
              "OPENROUTER_API_KEY", extra_headers={"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"}),
    _Provider("openrouter", "https://openrouter.ai/api/v1", "dots-studio/dots-3-note-preview:free",
              "OPENROUTER_API_KEY", extra_headers={"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"}),
    # v8 (2026-10-07): code-specialist models are last resorts for general calls (mirrors the TS chain).
    _Provider("mistral", "https://api.mistral.ai/v1", "codestral-latest",     "MISTRAL_API_KEY", last_resort=True),
    _Provider("openrouter", "https://openrouter.ai/api/v1", "poolside/laguna-s-2.1:free",
              "OPENROUTER_API_KEY", extra_headers={"HTTP-Referer": "https://workhiveph.com", "X-Title": "WorkHive"},
              last_resort=True),
]


class AIChainError(RuntimeError):
    pass


class AIQuotaExhausted(AIChainError):
    """The process pacer stopped (cap reached, or every provider answered 429 twice running). Nothing was sent."""


# ── Resilience mirror of _shared/ai-chain.ts P1–P3 (2026-06-14) ───────────────
# Ported so burst Python tools (the companion sweep, seeders) survive the same
# thundering-herd the edge does. The replica has no per-slot penalty state, so P1
# shuffles WITHIN each provider tier (the equal-"penalty" proxy) rather than by
# penalty; P2 honors Retry-After; P3 adds one bounded jittered retry pass.

def _reorder_chain(spread: bool) -> list[_Provider]:
    """P1 herd-spread (mirrors ai-chain.ts reorderChain spread=true). Shuffle WITHIN each
    provider tier so N concurrent calls don't all stampede the same head model and 429 in
    lockstep. Tier order (groq -> google -> mistral -> openrouter) preserved, and last-resort (code) entries
    stay behind every general one, as in ai-chain.ts. OFF by default so the deterministic order is kept for
    non-burst callers + the Node-parity test."""
    if not spread:
        return list(_CHAIN)
    out: list[_Provider] = []
    chain = [e for e in _CHAIN if not e.last_resort] + [e for e in _CHAIN if e.last_resort]
    i = 0
    while i < len(chain):
        j = i + 1
        while j < len(chain) and chain[j].provider == chain[i].provider:
            j += 1
        group = chain[i:j]
        random.shuffle(group)          # Fisher-Yates within the equal-tier group
        out.extend(group)
        i = j
    return out


def _parse_retry_after(h: Optional[str]) -> Optional[float]:
    """P2 (mirrors parseRetryAfter). A 429 Retry-After header -> seconds-from-now.
    Accepts delta-seconds ("12") or an HTTP-date. None if absent/unparseable."""
    if not h:
        return None
    try:
        return max(0.0, float(h))
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime
        import datetime
        when = parsedate_to_datetime(h)
        if when is not None:
            now = datetime.datetime.now(when.tzinfo)
            return max(0.0, (when - now).total_seconds())
    except Exception:
        pass
    return None


def _attempt_chain(
    chain: list[_Provider], messages: list, *,
    temperature: float, max_tokens: int, json_mode: bool, timeout_s: int, verbose: bool,
) -> tuple[Optional[tuple[str, str]], float, list[str]]:
    """Walk a given ordered chain once. Returns (result_or_None, max_retry_after_s, errors)."""
    errors: list[str] = []
    max_ra = 0.0
    statuses = _LAST.setdefault("statuses", [])
    for entry in chain:
        api_key = os.environ.get(entry.env_key)
        if not api_key or api_key.startswith("PASTE_"):
            continue
        effective_max = min(max_tokens, entry.max_tokens_cap) if entry.max_tokens_cap else max_tokens
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        if entry.extra_headers:
            headers.update(entry.extra_headers)
        body = {"model": entry.model, "messages": messages,
                "temperature": temperature, "max_tokens": effective_max}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if entry.extra_body:
            body.update(entry.extra_body)
        label = f"{entry.provider}/{entry.model.split('/')[-1]}"
        try:
            res = requests.post(f"{entry.base_url}/chat/completions",
                                headers=headers, json=body, timeout=timeout_s)
        except requests.RequestException as e:
            errors.append(f"{label}: network {e.__class__.__name__}")
            if verbose: print(f"  [ai-chain] {label} network err — next")
            statuses.append(0)
            continue
        statuses.append(res.status_code)
        if res.status_code in (429, 413, 503):
            ra = _parse_retry_after(res.headers.get("retry-after"))   # P2: honor Retry-After
            if ra is not None:
                max_ra = max(max_ra, ra)
            errors.append(f"{label}: HTTP {res.status_code}{f' retry-after {ra:.0f}s' if ra else ''}")
            if verbose: print(f"  [ai-chain] {label} skipped (HTTP {res.status_code})")
            continue
        if not res.ok:
            snippet = res.text[:120].replace("\n", " ")
            errors.append(f"{label}: HTTP {res.status_code}: {snippet}")
            if verbose: print(f"  [ai-chain] {label} HTTP {res.status_code}: {snippet} — next")
            continue
        try:
            content = res.json()["choices"][0]["message"]["content"]
        except (KeyError, ValueError, IndexError) as e:
            errors.append(f"{label}: bad payload {e}")
            continue
        content = _strip_reasoning_blocks(content or "")
        if not content:
            errors.append(f"{label}: empty content")   # incl. reasoning-only after strip
            continue
        if verbose: print(f"  [ai-chain] {label} OK ({len(content)} chars)")
        return (content, label), max_ra, errors
    return None, max_ra, errors


def _try_local_llm(messages: list, *, temperature: float, max_tokens: int,
                   json_mode: bool, timeout_s: int, verbose: bool) -> Optional[tuple[str, str]]:
    """Sovereign local LLM slot (mirror of _shared/ai-chain.ts tryLocalLLM, NATIVE_AI_ROADMAP.md #2b).
    When WH_LLM_URL is set, try the plant's own OpenAI-compatible endpoint (Ollama / llama.cpp) FIRST so
    inference + data stay in-plant. Returns (content, label) on success; None when WH_LLM_URL is unset or
    on ANY failure (fails OPEN to the cloud chain below). Env-gated + additive: prod chain unchanged."""
    base = (os.environ.get("WH_LLM_URL") or "").rstrip("/")
    if not base:
        return None
    model = os.environ.get("WH_LLM_MODEL") or "llama3.1"
    key = os.environ.get("WH_LLM_API_KEY")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    try:
        res = requests.post(f"{base}/chat/completions", headers=headers, json=body, timeout=timeout_s)
    except requests.RequestException as e:
        if verbose: print(f"  [ai-chain] WH_LLM_URL network {e.__class__.__name__} -> cloud chain")
        return None
    if res.status_code != 200:
        if verbose: print(f"  [ai-chain] WH_LLM_URL {res.status_code} -> cloud chain")
        return None
    try:
        content = (res.json().get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
    except Exception:
        return None
    content = _strip_reasoning_blocks(content)     # <think> + untagged persona-scaffold leak
    if content:
        if verbose: print(f"  [ai-chain] served by WH_LLM_URL (sovereign local) / {model}")
        return content, f"wh-llm-local:{model}"
    return None


def call_ai(
    prompt:         str,
    *,
    system_prompt:  Optional[str] = None,
    temperature:    float = 0.2,
    max_tokens:     int   = 1024,
    json_mode:      bool  = True,
    timeout_s:      int   = 60,
    spread:         bool  = False,
    verbose:        bool  = False,
) -> tuple[str, str]:
    """Run prompt through the fallback chain. Returns (content, provider_label).

    Skips providers without a configured key. On 429/413/503 -> try next (honoring Retry-After,
    P2). Pass `spread=True` from BURST tools (concurrent sweeps) to herd-spread the head within
    each provider tier (P1). After a full chain failure, one bounded jittered-retry pass runs
    before giving up (P3) — a short backoff lets per-second token buckets refill + de-syncs this
    call from the herd. Raises AIChainError if every configured provider fails twice.
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    common = dict(temperature=temperature, max_tokens=max_tokens,
                  json_mode=json_mode, timeout_s=timeout_s, verbose=verbose)

    # Sovereign local LLM first (NATIVE_AI_ROADMAP.md #2b): if WH_LLM_URL is set, keep inference +
    # data in-plant; unset -> skip to the cloud chain (unchanged); any failure falls open below.
    _sovereign = _try_local_llm(messages, **common)
    if _sovereign is not None:
        return _sovereign

    pm = _pacer()
    pacer = pm.process_pacer()
    _LAST.clear()
    _LAST.update({"statuses": [], "served_by": None})
    if not pacer.wait():
        raise AIQuotaExhausted(pacer.stop_reason + " - nothing sent")

    # Pass 1 — herd-spread chain (P1)
    result, ra1, errs1 = _attempt_chain(_reorder_chain(spread), messages, **common)
    if result is not None:
        _LAST["served_by"] = result[1]
        pacer.record("served")
        return result

    # P3 — one bounded jittered retry before failing. Wait the larger of a jitter (0.3–1.2s) or
    # the longest Retry-After we saw (capped at 5s so a one-shot tool never hangs), then re-spread.
    wait = max(0.3 + random.random() * 0.9, min(ra1, 5.0))
    if verbose:
        print(f"  [ai-chain] all slots failed pass 1 — P3 jittered retry in {wait:.1f}s")
    time.sleep(wait)
    result2, _ra2, errs2 = _attempt_chain(_reorder_chain(spread), messages, **common)
    if result2 is not None:
        _LAST["served_by"] = result2[1]
        pacer.record("served")
        return result2
    pacer.record(pm.outcome_from_statuses(_LAST["statuses"], served=False))

    raise AIChainError(
        "All providers failed or unconfigured (2 passes). Tried:\n  " + "\n  ".join(errs1 + errs2)
    )


_LAST: dict = {}


def last_outcome() -> dict:
    """What the most recent call_ai() did: {"statuses": [HTTP status per entry asked], "served_by": label|None}."""
    return dict(_LAST)


def _pacer():
    """The process-wide pacer from tools/lib/chain_pacer.py, loaded by file path so it is ONE object whichever mirror
    (and whichever sys.path layout) the caller came through."""
    import importlib.util
    import sys as _sys
    mod = _sys.modules.get("wh_chain_pacer")
    if mod is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chain_pacer.py")
        spec = importlib.util.spec_from_file_location("wh_chain_pacer", path)
        mod = importlib.util.module_from_spec(spec)
        _sys.modules["wh_chain_pacer"] = mod
        spec.loader.exec_module(mod)
    return mod

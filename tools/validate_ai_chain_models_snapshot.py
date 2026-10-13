#!/usr/bin/env python3
"""validate_ai_chain_models_snapshot.py - every model the AI chain names must be one its provider still serves to us.

THE CLASS (five recurrences): the free-tier chain in supabase/functions/_shared/ai-chain.ts names models at five
providers, and providers retire, rename and paywall models without notice - v5 found 11 of 18 entries dead, v6 four
more, v7 two more, and on 2026-10-08 both Cerebras entries were answering 402 payment_required to every call and had
been for a month (480 in the runtime log, not one answer). Each time the chain kept "working" because the next entry
answered, so nothing failed - the calls just walked past dead entries and, under load, ended on the code model kept
as a last resort.

validate_groq_fallback.check_models_are_live asks the providers, which is the right source, but it is
NETWORK-OPTIONAL: with no key or no network it SKIPS, so most board runs prove nothing about the chain. This gate
is the offline half. It reads tools/ai_provider_models_snapshot.json - each provider's own models list, written by
tools/snapshot_ai_provider_models.py from the list endpoints (no generation, $0) - and FAILs any chain entry that:
  - names a provider the snapshot does not cover,
  - names a model that provider's list does not contain (retired, renamed, or - for OpenRouter - not zero-priced),
  - is recorded under unavailable_on_key (listed, but this platform's key is refused: Cerebras 402), or
  - is recorded under rejected_for_chain (listed and answering, but unable to serve the chain's request shape), or
  - names a provider under removed_providers (Cerebras, removed from the platform 2026-10-08).
And because a removed provider can come back through a side door rather than a chain entry, it also scans live code
(supabase/functions/**/*.ts, tools/**/*.py, tools/*.mjs, root *.py) for that provider's API host or key variable and
FAILs on any hit outside a comment - except in the files listed in REMOVED_SCAN_ALLOW, each with the reason.

Scope is every place a chain is written, because a gate whose reach is narrower than its rule is how two of the
earlier rots survived (validate_ai_chain_mirror's own header): the TS PROVIDER_CHAIN, its two Python mirrors
(tools/ai_chain.py, tools/lib/ai_chain.py - parsed with validate_ai_chain_mirror's own parsers), and
voice-model-call's private chain. A parse that finds no entries FAILs - an empty list must never read as a clean one.

When it fails because a provider retired a model: run `python tools/snapshot_ai_provider_models.py` to see what the
provider serves now, replace the entry in all chain copies, then `--write` the snapshot.

  python tools/validate_ai_chain_models_snapshot.py             static, offline, fast
  python tools/validate_ai_chain_models_snapshot.py --selftest  proves it catches a retired name, a paywalled name,
                                                                an unknown provider, and ignores a commented-out entry
"""
from __future__ import annotations

import datetime as _dt

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SNAPSHOT = ROOT / "tools" / "ai_provider_models_snapshot.json"
TS_CHAIN = ROOT / "supabase" / "functions" / "_shared" / "ai-chain.ts"
VOICE_FN = ROOT / "supabase" / "functions" / "voice-model-call" / "index.ts"
STALE_DAYS = 45

_HOSTS = {"api.groq.com": "groq", "api.cerebras.ai": "cerebras", "api.mistral.ai": "mistral",
          "generativelanguage.googleapis.com": "google", "openrouter.ai": "openrouter"}


def _drop_line_comments(src: str) -> str:
    # whole-line // comments only: a URL inside a string ("https://...") must survive
    return "\n".join("" if ln.lstrip().startswith("//") else ln for ln in src.splitlines())


def parse_ts_chain(src: str) -> list[tuple[str, str]]:
    m = re.search(r"const PROVIDER_CHAIN[^=]*=\s*\[([\s\S]*?)\n\];", src)
    if not m:
        return []
    body = _drop_line_comments(m.group(1))
    return re.findall(r'\{\s*provider:\s*"(\w+)"[^}]*?\bmodel:\s*"([^"]+)"', body)


def parse_voice_chain(src: str) -> list[tuple[str, str]]:
    out = []
    for model, host in re.findall(r'model:\s*"([^"]+)",\s*api_url:\s*"https://([^/"]+)/', _drop_line_comments(src)):
        out.append((_HOSTS.get(host, host), model))
    return out


def check(entries: list[tuple[str, str]], snap: dict, source: str) -> list[str]:
    providers = snap.get("providers") or {}
    blocked = {**(snap.get("rejected_for_chain") or {}), **(snap.get("unavailable_on_key") or {})}
    removed = snap.get("removed_providers") or {}
    bad = []
    for provider, model in entries:
        key = f"{provider}/{model}"
        if provider in removed:
            bad.append(f"{source}: {key} - provider '{provider}' was REMOVED from the platform "
                       f"({removed[provider].get('removed', '')}): {removed[provider].get('reason', '')[:140]}")
        elif provider not in providers:
            bad.append(f"{source}: {key} - provider '{provider}' is not in the snapshot (no models list was taken)")
        elif model not in set(providers[provider]):
            bad.append(f"{source}: {key} - {provider} does not list it (retired, renamed"
                       + (", or not zero-priced" if provider == "openrouter" else "") + ")")
        elif key in blocked:
            bad.append(f"{source}: {key} - listed, but unusable: {blocked[key].get('reason', '')[:160]}")
    return bad


# Files allowed to NAME a removed provider's host or key, each for a reason that is not "calling it".
REMOVED_SCAN_ALLOW = {
    "tools/validate_ai_chain_models_snapshot.py": "this gate: its own patterns and selftest fixtures",
    "tools/validate_no_ai_gateway_bypass.py": "a bypass DETECTOR - its docstring lists the provider hosts it flags",
}
_REMOVED_PATTERNS = {"cerebras": ("api.cerebras.ai", "CEREBRAS_API_KEY", 'provider: "cerebras"', '"provider": "cerebras"')}


def _code_lines(text: str, suffix: str):
    """(line_no, line) for lines that are not whole-line comments in their language."""
    marks = ("#",) if suffix == ".py" else ("//", "*", "/*")
    for i, ln in enumerate(text.splitlines(), 1):
        if not ln.lstrip().startswith(marks):
            yield i, ln


def scan_for_removed(files, removed: dict) -> list[str]:
    """files: iterable of (relpath, text). A removed provider's host/key/entry in live code = FAIL."""
    pats = [(prov, p) for prov in removed for p in _REMOVED_PATTERNS.get(prov, (prov,))]
    bad = []
    for rel, text in files:
        if rel in REMOVED_SCAN_ALLOW:
            continue
        for i, ln in _code_lines(text, Path(rel).suffix):
            for prov, p in pats:
                if p in ln:
                    bad.append(f"{rel}:{i}: names '{p}' - {prov} was removed from the platform; "
                               f"route through the chain instead")
    return bad


def _live_code_files():
    globs = [("supabase/functions", "**/*.ts"), ("tools", "**/*.py"), ("tools", "*.mjs"), (".", "*.py")]
    seen = set()
    for base, pat in globs:
        for p in (ROOT / base).glob(pat):
            if "__pycache__" in p.parts or "node_modules" in p.parts or p in seen:
                continue
            seen.add(p)
            try:
                yield p.relative_to(ROOT).as_posix(), p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue


def collect() -> tuple[list[tuple[str, list]], list[str]]:
    """[(source, entries)], plus parse failures."""
    import validate_ai_chain_mirror as M  # its own parsers: one reading of the mirrors, not two
    out, errs = [], []
    srcs = [
        ("_shared/ai-chain.ts", lambda: parse_ts_chain(TS_CHAIN.read_text(encoding="utf-8"))),
        ("tools/ai_chain.py", lambda: [(p, m) for p, m, _ in (M._parse_py_chain((ROOT / M.PY_CHAIN_PATH).read_text(encoding="utf-8")) or [])]),
        ("tools/lib/ai_chain.py", lambda: [(p, m) for p, m, _ in (M._parse_lib_chain((ROOT / M.LIB_CHAIN_PATH).read_text(encoding="utf-8")) or [])]),
        ("voice-model-call/index.ts", lambda: parse_voice_chain(VOICE_FN.read_text(encoding="utf-8"))),
    ]
    for name, fn in srcs:
        try:
            entries = fn()
        except Exception as e:  # noqa: BLE001 - a file that cannot be read is a FAIL, never a skip
            errs.append(f"{name}: could not be read ({type(e).__name__}: {e})")
            continue
        if not entries:
            errs.append(f"{name}: parsed 0 chain entries - the parser no longer sees the chain, so a clean result would be vacuous")
            continue
        out.append((name, entries))
    return out, errs


def selftest() -> int:
    snap = {"providers": {"groq": ["openai/gpt-oss-20b", "qwen/qwen3.8-27b"], "cerebras": ["gpt-oss-120b"],
                          "openrouter": ["google/gemma-4-31b-it:free"]},
            "unavailable_on_key": {"groq/qwen/qwen3.8-27b": {"reason": "402 payment required"}},
            "removed_providers": {"cerebras": {"removed": "2026-10-08", "reason": "402 on every call"}},
            "rejected_for_chain": {}}
    fake = ('const PROVIDER_CHAIN: ProviderEntry[] = [\n'
            '  { provider: "groq", baseUrl: "https://api.groq.com/openai/v1", model: "openai/gpt-oss-20b", envKey: "GROQ_API_KEY", extraBody: { reasoning_effort: "low" } },\n'
            '  { provider: "groq", baseUrl: "https://api.groq.com/openai/v1", model: "llama-3.3-70b-versatile", envKey: "GROQ_API_KEY" },\n'
            '  { provider: "cerebras", baseUrl: "https://api.cerebras.ai/v1", model: "gpt-oss-120b", envKey: "CEREBRAS_API_KEY" },\n'
            '  { provider: "sambanova", baseUrl: "https://api.sambanova.ai/v1", model: "x", envKey: "SAMBANOVA_API_KEY" },\n'
            '  { provider: "openrouter", baseUrl: "https://openrouter.ai/api/v1", model: "openai/gpt-oss-120b", envKey: "OPENROUTER_API_KEY" },\n'
            '  // { provider: "groq", baseUrl: "https://api.groq.com/openai/v1", model: "gemma2-9b-it", envKey: "GROQ_API_KEY" },\n'
            '];\n')
    entries = parse_ts_chain(fake)
    bad = check(entries, snap, "fake")
    flagged = {b.split(" - ")[0].split(": ", 1)[1] for b in bad}
    flagged_extra = {b.split(" - ")[0].split(": ", 1)[1]
                     for b in check([("groq", "qwen/qwen3.8-27b")], snap, "fake")}
    cases = [
        ("parser sees the 5 live entries and skips the commented one", len(entries) == 5),
        ("a live name passes", "groq/openai/gpt-oss-20b" not in flagged),
        ("a LISTED but key-refused name is caught (unavailable_on_key)", "groq/qwen/qwen3.8-27b" in flagged_extra),
        ("a RETIRED name is caught (llama-3.3-70b-versatile, retired from Groq 2026-09-10)", "groq/llama-3.3-70b-versatile" in flagged),
        ("a REMOVED provider's entry is caught (Cerebras)", "cerebras/gpt-oss-120b" in flagged),
        ("a provider with no models list is caught", "sambanova/x" in flagged),
        ("an OpenRouter slug that is not zero-priced is caught", "openrouter/openai/gpt-oss-120b" in flagged),
        ("a commented-out entry is not read as a chain entry", "groq/gemma2-9b-it" not in flagged),
    ]
    voice = 'model: "qwen-3.8-27b",\n        api_url: "https://api.cerebras.ai/v1/chat/completions",'
    cases.append(("voice-model-call's private chain is parsed by host", parse_voice_chain(voice) == [("cerebras", "qwen-3.8-27b")]))
    side_door = [("tools/x.py", 'import os\nKEY = os.getenv("CEREBRAS_API_KEY")\n# CEREBRAS_API_KEY in a comment is fine\n'),
                 ("supabase/functions/y/index.ts", 'const u = "https://api.cerebras.ai/v1/chat/completions";\n// api.cerebras.ai in a comment\n')]
    hits = scan_for_removed(side_door, {"cerebras": {}})
    cases.append(("a removed provider's key read / URL in live code is caught, comments are not",
                  len(hits) == 2 and "tools/x.py:2" in hits[0] and "index.ts:1" in hits[1]))
    # teeth on the REAL chain: the checked-in chain passes, and the same chain with one entry renamed to a retired id fails
    real_snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    real = TS_CHAIN.read_text(encoding="utf-8")
    cases.append(("the real chain parses to >= 6 entries", len(parse_ts_chain(real)) >= 6))
    mutated = real.replace('model: "openai/gpt-oss-20b"', 'model: "llama-3.1-8b-instant"', 1)
    cases.append(("the real chain with gpt-oss-20b swapped for a retired id FAILS",
                  mutated != real and any("llama-3.1-8b-instant" in b for b in check(parse_ts_chain(mutated), real_snap, "mut"))))
    ok = True
    for label, passed in cases:
        print(f"  {'PASS' if passed else 'FAIL'}  {label}")
        ok &= passed
    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if "--selftest" in sys.argv:
        return selftest()
    if not SNAPSHOT.exists():
        print(f"FAIL: {SNAPSHOT.relative_to(ROOT)} is missing - run tools/snapshot_ai_provider_models.py --write")
        return 1
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    sources, errs = collect()
    bad = list(errs)
    removed = snap.get("removed_providers") or {}
    side = scan_for_removed(_live_code_files(), removed) if removed else []
    bad += side
    total = 0
    for name, entries in sources:
        total += len(entries)
        bad += check(entries, snap, name)
    cap = snap.get("captured_at", "")
    age = ""
    try:
        days = (_dt.datetime.now(_dt.timezone.utc) - _dt.datetime.strptime(cap, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)).days
        age = f"{days} d old"
        if days > STALE_DAYS:
            age += f" - older than {STALE_DAYS} d, refresh it with tools/snapshot_ai_provider_models.py --write (not a failure)"
    except ValueError:
        age = "captured_at unreadable"
    print(f"AI chain models vs provider snapshot ({cap}, {age})")
    print(f"  {total} entries across {len(sources)} chain copies; "
          f"{len(snap.get('unavailable_on_key') or {})} listed-but-refused, {len(snap.get('rejected_for_chain') or {})} rejected-for-chain; "
          f"removed providers {sorted(removed) or 'none'} scanned for in live code ({len(side)} hit(s))")
    for b in bad:
        print("  FAIL", b)
    print("PASS" if not bad else f"FAIL ({len(bad)})")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())

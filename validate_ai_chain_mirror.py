"""
AI Chain Mirror Validator — WorkHive Platform
==============================================
Enforces [[feedback-python-ai-chain-mirror]]: tools/ai_chain.py PROVIDER_CHAIN
must mirror supabase/functions/_shared/ai-chain.ts PROVIDER_CHAIN. When the
TS chain adds a new free provider/model and Python doesn't get updated,
Python tools (Platform Pack, video idea generator) end up with thinner
fallback than edge functions — leading to "All providers failed" errors
under load even though edge functions are fine.

This validator catches drift between the two chains.

Layer 1: Both files exist and parse
Layer 2: Same set of (provider, model) entries appear in both chains
Layer 3: Same env_key per provider in both chains
Layer 4: Order roughly matches (same provider grouping: Groq -> Cerebras ->
         OpenRouter). Strict-order isn't required because Python and TS
         may legitimately reorder within a provider tier, but the
         provider tier order must match.

Usage:  python validate_ai_chain_mirror.py
Output: ai_chain_mirror_report.json
"""
import re, json, sys, os
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from validator_utils import read_file, format_result

PY_CHAIN_PATH = "tools/ai_chain.py"
TS_CHAIN_PATH = "supabase/functions/_shared/ai-chain.ts"


def _parse_py_chain(content: str):
    """Extract list of dicts from `PROVIDER_CHAIN = [...]` in Python.
    Returns list of (provider, model, env_key)."""
    m = re.search(r"PROVIDER_CHAIN\s*=\s*\[(.*?)\n\]", content, re.DOTALL)
    if not m:
        return None
    body = m.group(1)
    entries = []
    # Each entry is a dict like {"provider": "...", "model": "...", "env_key": "..."}
    for line in body.splitlines():
        provider_m = re.search(r'"provider"\s*:\s*"([^"]+)"', line)
        model_m    = re.search(r'"model"\s*:\s*"([^"]+)"',    line)
        envkey_m   = re.search(r'"env_key"\s*:\s*"([^"]+)"',  line)
        if provider_m and model_m and envkey_m:
            entries.append((provider_m.group(1), model_m.group(1), envkey_m.group(1)))
    return entries


def _parse_ts_chain(content: str):
    """Extract entries from the TS PROVIDER_CHAIN array. Returns list of
    (provider, model, envKey)."""
    m = re.search(r"PROVIDER_CHAIN\s*:\s*ProviderEntry\[\]\s*=\s*\[(.*?)\n\]\s*;",
                  content, re.DOTALL)
    if not m:
        return None
    body = m.group(1)
    entries = []
    for line in body.splitlines():
        provider_m = re.search(r'provider\s*:\s*"([^"]+)"', line)
        model_m    = re.search(r'model\s*:\s*"([^"]+)"',    line)
        envkey_m   = re.search(r'envKey\s*:\s*"([^"]+)"',   line)
        if provider_m and model_m and envkey_m:
            entries.append((provider_m.group(1), model_m.group(1), envkey_m.group(1)))
    return entries


def check_files_parse():
    issues = []
    for path, parser in [(PY_CHAIN_PATH, _parse_py_chain),
                          (TS_CHAIN_PATH, _parse_ts_chain)]:
        content = read_file(path)
        if content is None:
            issues.append({"check": "files_parse", "page": path,
                           "reason": f"{path} not found"})
            continue
        entries = parser(content)
        if entries is None:
            issues.append({"check": "files_parse", "page": path,
                           "reason": (f"{path} found but PROVIDER_CHAIN "
                                      f"array could not be parsed.")})
        elif not entries:
            issues.append({"check": "files_parse", "page": path,
                           "reason": (f"{path} PROVIDER_CHAIN parsed but is "
                                      f"empty.")})
    return issues


def check_models_match():
    """The (provider, model) pairs must match across the two chains."""
    issues = []
    py_content = read_file(PY_CHAIN_PATH)
    ts_content = read_file(TS_CHAIN_PATH)
    if not (py_content and ts_content):
        return []   # files_parse already flagged
    py_entries = _parse_py_chain(py_content) or []
    ts_entries = _parse_ts_chain(ts_content) or []

    py_models = {(p, m) for p, m, _ in py_entries}
    ts_models = {(p, m) for p, m, _ in ts_entries}

    only_py = py_models - ts_models
    only_ts = ts_models - py_models

    for p, m in sorted(only_py):
        issues.append({"check": "models_match", "page": PY_CHAIN_PATH,
                       "reason": (f"Python chain has {p}/{m} but TS chain "
                                  f"does not. Either remove from Python or "
                                  f"add to TS.")})
    for p, m in sorted(only_ts):
        issues.append({"check": "models_match", "page": TS_CHAIN_PATH,
                       "reason": (f"TS chain has {p}/{m} but Python chain "
                                  f"does not. Add to tools/ai_chain.py "
                                  f"PROVIDER_CHAIN — otherwise Python tools "
                                  f"miss a fallback that edge functions have.")})
    return issues


def check_env_keys_match():
    """Same provider must use same env_key in both chains."""
    issues = []
    py_content = read_file(PY_CHAIN_PATH)
    ts_content = read_file(TS_CHAIN_PATH)
    if not (py_content and ts_content):
        return []
    py_entries = _parse_py_chain(py_content) or []
    ts_entries = _parse_ts_chain(ts_content) or []

    # Map provider -> set of env keys observed
    py_envs, ts_envs = {}, {}
    for p, _, k in py_entries:
        py_envs.setdefault(p, set()).add(k)
    for p, _, k in ts_entries:
        ts_envs.setdefault(p, set()).add(k)

    for provider in set(py_envs) | set(ts_envs):
        py_keys = py_envs.get(provider, set())
        ts_keys = ts_envs.get(provider, set())
        if py_keys != ts_keys:
            issues.append({"check": "env_keys_match",
                           "page": f"{PY_CHAIN_PATH} vs {TS_CHAIN_PATH}",
                           "reason": (f"Provider '{provider}' env keys differ: "
                                      f"Python uses {sorted(py_keys)}, "
                                      f"TS uses {sorted(ts_keys)}. They MUST "
                                      f"match.")})
    return issues


def check_provider_tier_order():
    """The provider TIER ORDER (groq -> cerebras -> openrouter) must match
    so fallback semantics align between Python and TS callers."""
    issues = []
    py_content = read_file(PY_CHAIN_PATH)
    ts_content = read_file(TS_CHAIN_PATH)
    if not (py_content and ts_content):
        return []
    py_entries = _parse_py_chain(py_content) or []
    ts_entries = _parse_ts_chain(ts_content) or []

    # Walk each list, capturing the first time each provider appears
    def tier_order(entries):
        seen = []
        for p, _, _ in entries:
            if p not in seen:
                seen.append(p)
        return seen

    py_tier = tier_order(py_entries)
    ts_tier = tier_order(ts_entries)
    if py_tier != ts_tier:
        issues.append({"check": "provider_tier_order",
                       "page": f"{PY_CHAIN_PATH} vs {TS_CHAIN_PATH}",
                       "reason": (f"Provider tier order differs: Python "
                                  f"orders {py_tier}, TS orders {ts_tier}. "
                                  f"Edge fns and Python tools then prefer "
                                  f"different fallbacks under load — "
                                  f"unpredictable behaviour.")})
    return issues


CHECK_NAMES  = ["files_parse", "models_match", "env_keys_match",
                "provider_tier_order"]
CHECK_LABELS = {
    "files_parse":         "L1  Both ai_chain.py and ai-chain.ts exist and parse",
    "models_match":        "L2  (provider, model) pairs match across Python and TS chains",
    "env_keys_match":      "L3  Same provider uses same env_key in both chains",
    "provider_tier_order": "L4  Provider tier order (groq -> cerebras -> openrouter) matches",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nAI Chain Mirror Validator (4-layer)"))
    print("=" * 55)

    all_issues = []
    all_issues += check_files_parse()
    all_issues += check_models_match()
    all_issues += check_env_keys_match()
    all_issues += check_provider_tier_order()

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    # Surface chain depth for visibility
    py_content = read_file(PY_CHAIN_PATH)
    ts_content = read_file(TS_CHAIN_PATH)
    py_count = len(_parse_py_chain(py_content) or []) if py_content else 0
    ts_count = len(_parse_ts_chain(ts_content) or []) if ts_content else 0
    print(f"\n  Python chain depth: {py_count} models")
    print(f"  TS chain depth:     {ts_count} models")
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m  All {len(CHECK_NAMES)} checks passed.\033[0m")
    else:
        color = "91" if n_fail else "93"
        print(f"\033[{color}m  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":      "ai_chain_mirror",
        "total_checks":   len(CHECK_NAMES),
        "py_chain_depth": py_count,
        "ts_chain_depth": ts_count,
        "passed":         n_pass,
        "warned":         n_warn,
        "failed":         n_fail,
        "issues":         [i for i in all_issues if not i.get("skip")],
        "warnings":       [i for i in all_issues if i.get("skip")],
    }
    with open("ai_chain_mirror_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()

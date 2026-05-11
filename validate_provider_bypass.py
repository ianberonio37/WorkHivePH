"""
Direct Provider Bypass Detector -- WorkHive Platform
=====================================================
Catches code paths that bypass the centralised `_shared/callAI` chain
and talk to AI providers directly. This matters in three distinct
ways:

  1. **Browser-side AI calls leak the API key.** Any client HTML/JS
     that fetches OpenAI/Anthropic/etc directly must include an API
     key in the request, and the key sits in the browser bundle for
     anyone with DevTools to harvest. Hard FAIL.

  2. **Edge function bypass fragments the multi-provider chain.**
     The `_shared/callAI` helper rotates across providers, applies
     rate-limit gates, and logs cost. A direct fetch() in an edge fn
     skips all three; the rate-limit + cost gate becomes opt-in.
     Sister gate to `validate_ai_pattern_compliance` L2 with a
     broader provider list.

  3. **SDK imports outside the shared layer** are the same shape
     as #2 but easier to spot statically -- once an `import OpenAI
     from 'openai'` lands anywhere except `_shared/`, the next
     refactor will copy that pattern instead of using callAI.

Layer 1 -- Provider hostname or SDK in client HTML/JS                   [FAIL]
  Catastrophic: API key would have to live in browser code.

Layer 2 -- Provider hostname in edge fn outside _shared                 [WARN]
  Bypass of the rate-limit + multi-provider chain.

Layer 3 -- SDK import outside _shared (any layer)                       [WARN]
  `import OpenAI from 'openai'` etc. should appear ONLY in `_shared/`.
  Found elsewhere = fragmentation risk.

Layer 4 -- Provider-routing distribution (informational)                [INFO]
  Per-file count of which providers/SDKs are referenced. Helps spot
  if one provider is dominant (cost concentration) or if multiple
  shared layers exist.

Skills consulted: ai-engineer (callAI multi-provider chain, rate
limit + cost observability), security (browser key leak is OWASP
top-10), architect (centralisation discipline -- one helper per
cross-cutting concern).
"""
from __future__ import annotations

import re
import json
import sys
import os
import glob
from collections import defaultdict

if sys.platform == "win32" and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result


FUNCTIONS_DIR = os.path.join("supabase", "functions")
SHARED_DIR    = os.path.join("supabase", "functions", "_shared")
PYTHON_API_DIR = "python-api"

EXCLUDED_HTML_PATTERNS = ("-test.html", ".backup.html", "_backup.html", ".backup")

PROVIDER_HOSTS = [
    r"api\.openai\.com",
    r"api\.anthropic\.com",
    r"api\.groq\.com",
    r"api\.cerebras\.ai",
    r"api\.deepseek\.com",
    r"openrouter\.ai/api",
    r"generativelanguage\.googleapis\.com",
    r"api\.together\.xyz",
    r"api\.mistral\.ai",
    r"api\.cohere\.ai",
]
HOST_RE = re.compile("|".join(PROVIDER_HOSTS), re.IGNORECASE)

# Common SDK import patterns. Each: (sdk_name, regex).
SDK_IMPORTS = [
    ("OpenAI",       re.compile(r"""(?:from|import)\s+['"]openai['"]|from\s+\S*openai\s+import""", re.IGNORECASE)),
    ("Anthropic",    re.compile(r"""(?:from|import)\s+['"]@anthropic-ai|from\s+\S*anthropic\s+import""", re.IGNORECASE)),
    ("Groq",         re.compile(r"""(?:from|import)\s+['"]groq-sdk['"]|from\s+\S*groq\s+import""", re.IGNORECASE)),
    ("Cerebras",     re.compile(r"""(?:from|import)\s+['"]@cerebras""", re.IGNORECASE)),
    ("Cohere",       re.compile(r"""(?:from|import)\s+['"]cohere-ai['"]|from\s+\S*cohere\s+import""", re.IGNORECASE)),
    ("Mistral",      re.compile(r"""(?:from|import)\s+['"]@mistralai""", re.IGNORECASE)),
    ("Google AI",    re.compile(r"""(?:from|import)\s+['"]@google/generative-ai""", re.IGNORECASE)),
]

# Per-file exemptions. Each entry needs a one-line justification.
PROVIDER_BYPASS_OK = {
    "supabase/functions/_shared":       "shared callAI chain; lives here BY DESIGN",
    "supabase/functions/voice-transcribe/index.ts":
        "OpenAI Whisper isn't part of the multi-provider chain; documented exception in _shared/callAI",
}


def _strip_comments(src: str) -> str:
    src = re.sub(r"<!--[\s\S]*?-->", "", src)
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    src = re.sub(r"//[^\n]*", "", src)
    return src


def _is_exempt(path: str) -> bool:
    np = path.replace("\\", "/")
    for ex in PROVIDER_BYPASS_OK:
        if np.startswith(ex) or np == ex:
            return True
    return False


def list_client_files() -> list[str]:
    out: list[str] = []
    for path in sorted(glob.glob("*.html")):
        if any(p in path.lower() for p in EXCLUDED_HTML_PATTERNS):
            continue
        out.append(path)
    for path in sorted(glob.glob("*.js")):
        if path.endswith(".min.js"):
            continue
        out.append(path)
    return out


def list_edge_files() -> list[str]:
    out: list[str] = []
    if os.path.isdir(FUNCTIONS_DIR):
        for d in sorted(os.listdir(FUNCTIONS_DIR)):
            idx = os.path.join(FUNCTIONS_DIR, d, "index.ts")
            if os.path.isfile(idx):
                out.append(idx)
        # Also include shared lib files (the `_shared/callAI` is exempt
        # but its peers might bypass the chain too).
        for path in sorted(glob.glob(os.path.join(SHARED_DIR, "*.ts"))):
            out.append(path)
    return out


def list_python_files() -> list[str]:
    out: list[str] = []
    for path in sorted(glob.glob(os.path.join(PYTHON_API_DIR, "**", "*.py"), recursive=True)):
        if "__init__" in path:
            continue
        out.append(path)
    return out


# -- Layer 1: Provider in client HTML/JS ------------------------------------

def check_client_provider(files: list[str]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for path in files:
        if _is_exempt(path):
            continue
        src = _strip_comments(read_file(path) or "")
        host_hits = HOST_RE.findall(src)
        sdk_hits = []
        for sdk, rx in SDK_IMPORTS:
            if rx.search(src):
                sdk_hits.append(sdk)
        if not host_hits and not sdk_hits:
            continue
        report.append({
            "path":  path,
            "hosts": sorted(set(host_hits))[:3],
            "sdks":  sdk_hits,
        })
        issues.append({
            "check": "client_provider", "skip": False,
            "reason": (
                f"{path}: client {('HTML' if path.endswith('.html') else 'JS')} "
                f"references AI provider host(s) {sorted(set(host_hits))[:3]} "
                f"or SDK(s) {sdk_hits}. Browser code that calls a provider "
                f"directly leaks the API key. Move the call to an edge "
                f"function and invoke it from the browser via "
                f"`db.functions.invoke('fn-name', ...)`."
            ),
        })
    return issues, report


# -- Layer 2: Provider hostname in edge fn outside _shared -----------------

def check_edge_bypass(files: list[str]) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for path in files:
        if _is_exempt(path):
            continue
        src = _strip_comments(read_file(path) or "")
        host_hits = HOST_RE.findall(src)
        if not host_hits:
            continue
        report.append({
            "path":  path,
            "hosts": sorted(set(host_hits)),
        })
        issues.append({
            "check": "edge_bypass", "skip": True,
            "reason": (
                f"{path}: edge code references AI provider host(s) "
                f"{sorted(set(host_hits))} directly instead of routing "
                f"through `_shared/callAI`. The shared chain handles "
                f"multi-provider rotation, rate-limit gating, and cost "
                f"logging -- bypassing it makes those features opt-in. "
                f"Add to PROVIDER_BYPASS_OK if the bypass is intentional."
            ),
        })
    return issues, report


# -- Layer 3: SDK import outside _shared -----------------------------------

def check_sdk_import_drift(
    edge_files: list[str],
    python_files: list[str],
) -> tuple[list[dict], list[dict]]:
    issues: list[dict] = []
    report: list[dict] = []
    for path in edge_files + python_files:
        if _is_exempt(path):
            continue
        src = _strip_comments(read_file(path) or "")
        for sdk, rx in SDK_IMPORTS:
            if not rx.search(src):
                continue
            report.append({"path": path, "sdk": sdk})
            issues.append({
                "check": "sdk_import_drift", "skip": True,
                "reason": (
                    f"{path}: imports the {sdk} SDK directly. SDK imports "
                    f"belong in `_shared/` so all providers route through "
                    f"one chain. Move the import + usage there, or add "
                    f"the file to PROVIDER_BYPASS_OK with a justification."
                ),
            })
    return issues, report


# -- Layer 4: Provider-routing distribution (informational) ---------------

def check_distribution(
    client_files: list[str],
    edge_files: list[str],
) -> tuple[list[dict], list[dict]]:
    counter: dict[str, int] = defaultdict(int)
    for path in client_files + edge_files:
        src = _strip_comments(read_file(path) or "")
        for host in HOST_RE.findall(src):
            counter[host] += 1
        for sdk, rx in SDK_IMPORTS:
            if rx.search(src):
                counter[f"SDK:{sdk}"] += 1
    rows = [
        {"target": k, "count": v}
        for k, v in sorted(counter.items(), key=lambda kv: -kv[1])
    ]
    return [], rows


# -- Runner ---------------------------------------------------------------

CHECK_NAMES = [
    "client_provider",
    "edge_bypass",
    "sdk_import_drift",
    "distribution",
]
CHECK_LABELS = {
    "client_provider":   "L1  No AI provider hostname or SDK in client HTML/JS              [FAIL]",
    "edge_bypass":       "L2  No edge fn fetches an AI provider outside _shared/callAI      [WARN]",
    "sdk_import_drift":  "L3  AI SDK imports live ONLY in _shared/                          [WARN]",
    "distribution":      "L4  Provider/SDK reference distribution (informational)           [INFO]",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"

    print(bold("\nDirect Provider Bypass Detector (4-layer)"))
    print("=" * 60)

    client_files = list_client_files()
    edge_files   = list_edge_files()
    python_files = list_python_files()
    print(f"  {len(client_files)} client + {len(edge_files)} edge + {len(python_files)} python files scanned "
          f"(PROVIDER_BYPASS_OK={len(PROVIDER_BYPASS_OK)}).\n")

    l1_issues, l1_report = check_client_provider(client_files)
    l2_issues, l2_report = check_edge_bypass(edge_files)
    l3_issues, l3_report = check_sdk_import_drift(edge_files, python_files)
    l4_issues, l4_report = check_distribution(client_files, edge_files)

    all_issues = l1_issues + l2_issues + l3_issues + l4_issues
    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, all_issues)

    if l4_report:
        print(f"\n{bold('PROVIDER REFERENCE DISTRIBUTION (informational)')}")
        print("  " + "-" * 56)
        for r in l4_report[:8]:
            print(f"  {r['target']:<32}  count={r['count']}")

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_warn == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_warn} WARN  0 FAIL\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":         "provider_bypass",
        "total_checks":      total,
        "passed":            n_pass,
        "warned":            n_warn,
        "failed":            n_fail,
        "n_client":          len(client_files),
        "n_edge":            len(edge_files),
        "n_python":          len(python_files),
        "client_provider":   l1_report,
        "edge_bypass":       l2_report,
        "sdk_import_drift":  l3_report,
        "distribution":      l4_report,
        "issues":            [i for i in all_issues if not i.get("skip")],
        "warnings":          [i for i in all_issues if i.get("skip")],
    }
    with open("provider_bypass_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()

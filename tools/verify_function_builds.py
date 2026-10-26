#!/usr/bin/env python3
"""verify_function_builds.py - is every RUNNING edge function the tree's code? (OWN AI failure-mode lens, "stale deploy
cache", 2026-10-26)

Asks each function's /health for the `build` stamp it carries (_shared/health.ts, from _shared/build_stamps.ts) and
compares it with the tree's stamp (tools/stamp_functions.py). A function answering no stamp runs code from before stamps
existed; one answering a different stamp runs other code than the tree's - a stale runtime cache locally (the compiled
module survived restarts), or in production a function not redeployed after its own edit or a _shared change.

    python tools/verify_function_builds.py                 the local stack (127.0.0.1:54321)
    python tools/verify_function_builds.py --target prod   production (after a deploy: the post-deploy check)
    python tools/verify_function_builds.py --only ai-gateway,embed-entry
Exit 1 when any asked function is not the tree's code.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from stamp_functions import stamps  # noqa: E402

TARGETS = {
    # publishable keys are public by design (they ship in every page); /health answers before any auth check
    "local": ("http://127.0.0.1:54321", "sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH"),
    "prod": ("https://hzyvnjtisfgbksicrouu.supabase.co", "sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ"),
}


def health_functions() -> list[str]:
    fn = ROOT / "supabase" / "functions"
    return sorted(d.name for d in fn.iterdir() if (d / "index.ts").exists() and "handleHealth" in (d / "index.ts").read_text(encoding="utf-8", errors="replace"))


def ask(base: str, key: str, name: str) -> tuple[str, str | None, str]:
    req = urllib.request.Request(f"{base}/functions/v1/{name}/health", headers={"apikey": key, "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            body = r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        if e.code not in (200, 503):
            return name, None, f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        return name, None, str(e)[:80]
    try:
        return name, (json.loads(body) or {}).get("build"), ""
    except ValueError:
        return name, None, "not JSON: " + body[:60]


def main() -> int:
    target = "prod" if "--target" in sys.argv and sys.argv[sys.argv.index("--target") + 1] == "prod" else "local"
    base, key = TARGETS[target]
    tree = stamps()
    names = health_functions()
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
        names = [n for n in names if n in only]
    # one at a time locally: a cold local runtime boots each worker, and six at once took the 8 GB host's Docker engine down
    with ThreadPoolExecutor(max_workers=1 if target == "local" else 4) as pool:
        got = list(pool.map(lambda n: ask(base, key, n), names))
    stale, unreachable, fresh = [], [], []
    for name, build, err in got:
        if err:
            unreachable.append((name, err))
        elif build != tree.get(name):
            stale.append((name, build))
        else:
            fresh.append(name)
    print(f"function-builds ({target}): {len(fresh)}/{len(names)} running functions are the tree's code")
    for name, build in stale:
        print(f"  - {name}: runs {build or 'code from before build stamps'}, the tree is {tree.get(name)}")
    for name, err in unreachable:
        print(f"  ? {name}: {err}")
    ok = not stale and not unreachable
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

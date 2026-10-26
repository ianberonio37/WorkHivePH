"""edge_remote_deps_lock.py - pin what the edge functions fetch at DEPLOY, by content, not only by version (2026-10-27).

OWN74-77 (esm.sh down / slow / 429 / changed API). Every esm.sh import in supabase/functions is pinned to an exact version,
and production runs the eszip the deploy built - so esm.sh is a deploy-time dependency and a person mid-task never meets
it. What was open: nothing pinned the CONTENT. esm.sh rebuilds a package at the same version (a new build target, a
fixed transform), so "supabase-js@2.110.0" on the next deploy is not proven to be the bytes the last deploy shipped, and
a changed API would reach production unseen. This is the lock and its gate:

  python tools/edge_remote_deps_lock.py            static gate (offline): the lock agrees with the source - every
                                                    esm.sh module a deploy bundles is locked, and nothing locked is
                                                    gone. Registered on the board. (Exact pins and one supabase-js
                                                    version are validate_edge_imports_pinned.py's R1/R2 - not repeated
                                                    here; this is the half it names as "not covered": the transitive
                                                    content esm.sh serves for a pinned version.)
  python tools/edge_remote_deps_lock.py --online   the pre-deploy check: re-fetch every locked esm.sh module as the
                                                    bundler does (Deno user agent, every transitive /-path it imports)
                                                    and compare digests. A different digest = same version, new
                                                    content: review before deploying. A refused / slow / 429 fetch is
                                                    named for what it means: a deploy now would fail at its bundle
                                                    step, and production keeps serving its last bundle.
  python tools/edge_remote_deps_lock.py --write    (re)build the lock from esm.sh - only after reviewing a change.
  python tools/edge_remote_deps_lock.py --self-test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FN = ROOT / "supabase" / "functions"
LOCK = ROOT / "edge_remote_deps.lock.json"
UA = "Deno/1.45.2"            # the module loader's agent: esm.sh picks the build target (denonext) from it
MAX_FILES = 400               # a bound on the transitive walk of one package
SLOW_S = 10.0

SPEC_RX = re.compile(r"""["'](https://esm\.sh/[^"'\s]+|https://deno\.land/[^"'\s]+|npm:[^"'\s]+|jsr:[^"'\s]+)["']""")
INNER_RX = re.compile(r"""(?:from|import)\s*["'](/[^"']+)["']""")


def scan() -> dict:
    """{specifier: [files]} for every remote import under supabase/functions."""
    out: dict = {}
    for f in sorted([*FN.rglob("*.ts"), *FN.rglob("deno.json"), *FN.rglob("import_map.json")]):
        src = f.read_text(encoding="utf-8", errors="replace")
        for m in SPEC_RX.finditer(src):
            out.setdefault(m.group(1), []).append(f.relative_to(ROOT).as_posix())
    return out


def shipped(files: list) -> list:
    """The importing files a deploy bundles: a *.test.ts runs under `deno test` locally and never ships."""
    return [f for f in files if not f.endswith(".test.ts")]


def static_problems(specs: dict, lock: dict) -> list:
    probs = []
    for spec, files in specs.items():
        if not shipped(files):
            continue   # test-only: never part of a deploy
        if spec.startswith("https://esm.sh/") and spec not in lock.get("modules", {}):
            probs.append(f"not in the lock: {spec} ({files[0]}) - run --online to review it, then --write")
    for spec in lock.get("modules", {}):
        if not shipped(specs.get(spec, [])):
            probs.append(f"locked but no longer imported: {spec} - --write drops it")
    return probs


def _get(url: str, timeout: float = 30.0) -> tuple:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    t = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode(), r.read(), time.monotonic() - t
    except urllib.error.HTTPError as e:
        return e.code, b"", time.monotonic() - t
    except Exception as e:   # noqa: BLE001 - refused / DNS / timeout: reported as what a deploy would meet
        return 0, str(e).encode()[:200], time.monotonic() - t


def fetch_tree(spec: str) -> dict:
    """The module and every /-path it imports, as the bundler would fetch them: {path: sha256}, plus the worst fetch."""
    base = "https://esm.sh"
    files, queue, worst = {}, [spec], {"code": 200, "secs": 0.0, "url": ""}
    while queue and len(files) < MAX_FILES:
        url = queue.pop(0)
        key = url[len(base):] if url.startswith(base) else url
        if key in files:
            continue
        code, body, secs = _get(url)
        if code != 200:
            return {"error": {"code": code, "url": key, "detail": body.decode(errors="replace")[:160], "secs": round(secs, 1)}}
        if secs > worst["secs"]:
            worst = {"code": code, "secs": round(secs, 2), "url": key}
        files[key] = hashlib.sha256(body).hexdigest()
        for m in INNER_RX.finditer(body.decode("utf-8", errors="replace")):
            queue.append(base + m.group(1))
    digest = hashlib.sha256("\n".join(f"{k} {v}" for k, v in sorted(files.items())).encode()).hexdigest()
    return {"digest": digest, "files": len(files), "worst": worst, "tree": files}


def online(lock: dict) -> int:
    bad = 0
    for spec, rec in sorted(lock.get("modules", {}).items()):
        got = fetch_tree(spec)
        if "error" in got:
            e = got["error"]
            what = ("refused or unreachable" if e["code"] == 0 else "rate-limited (429)" if e["code"] == 429
                    else f"answered {e['code']}")
            print(f"  DOWN  {spec}: {e['url']} {what} after {e['secs']}s - a deploy now would fail at its bundle step; "
                  f"production keeps serving its last bundle ({e['detail'][:80]})")
            bad += 1
            continue
        slow = got["worst"]["secs"] > SLOW_S
        if got["digest"] != rec["digest"]:
            changed = sorted(k for k in set(got["tree"]) | set(rec.get("tree", {}))
                             if got["tree"].get(k) != rec.get("tree", {}).get(k))
            print(f"  CHANGED {spec}: same version, different content in {len(changed)} of {got['files']} files "
                  f"(e.g. {changed[0] if changed else '-'}) - review before deploying, then --write")
            bad += 1
        else:
            w = got["worst"]
            note = f"  SLOW: {w['url']} took {w['secs']}s - the deploy will be slow, and past its timeout it fails" if slow else ""
            print(f"  same  {spec}: {got['files']} files, digest {got['digest'][:12]}{note}")
    return bad


def write(specs: dict) -> int:
    mods = {}
    for spec in sorted(s for s in specs if s.startswith("https://esm.sh/") and shipped(specs[s])):
        got = fetch_tree(spec)
        if "error" in got:
            print(f"refusing to write: {spec} -> {got['error']}")
            return 1
        mods[spec] = {"digest": got["digest"], "files": got["files"], "tree": got["tree"], "used_by": len(specs[spec])}
        print(f"  {spec}: {got['files']} files, digest {got['digest'][:12]}")
    LOCK.write_text(json.dumps({"_doc": __doc__.split("\n\n")[0].strip(), "user_agent": UA,
                                "written": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "modules": mods},
                               indent=1) + "\n", encoding="utf-8")
    print(f"wrote {LOCK.name}: {len(mods)} esm.sh modules")
    return 0


def self_test() -> int:
    ok = True

    def ck(c, m):
        nonlocal ok
        print(("  ok   " if c else "  FAIL ") + m)
        ok = ok and bool(c)
    ck(any("no longer imported" in p for p in static_problems({}, {"modules": {"https://esm.sh/z@1.0.0": {}}})),
       "a locked module nothing imports is a problem")
    ck(any("not in the lock" in p for p in static_problems({"https://esm.sh/y@1.0.0": ["c.ts"]}, {"modules": {}})),
       "an unlocked esm.sh import is a problem")
    ck(not static_problems({"https://esm.sh/t@1.0.0": ["y.test.ts"]}, {"modules": {}}),
       "a test-only esm.sh import is not part of a deploy and needs no lock")
    ck(INNER_RX.findall('import "/a@1/denonext/a.mjs";export*from"/b@2/x.mjs"') == ["/a@1/denonext/a.mjs", "/b@2/x.mjs"],
       "the transitive walk reads both minified and spaced imports")
    print("SELF-TEST " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--online", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--lock", help="read this lock instead (the teeth: a tampered copy must read CHANGED)")
    a = ap.parse_args()
    global LOCK
    if a.lock:
        LOCK = Path(a.lock)
    if a.self_test:
        return self_test()
    specs = scan()
    if a.write:
        return write(specs)
    lock = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.exists() else {"modules": {}}
    probs = static_problems(specs, lock)
    n_esm = sum(1 for s in specs if s.startswith("https://esm.sh/"))
    for p in probs:
        print("  " + p)
    if a.online:
        bad = online(lock)
        print(("FAIL" if bad or probs else "PASS") + f" edge-remote-deps online - {len(lock.get('modules', {}))} locked esm.sh modules "
              f"re-fetched as the bundler does; {bad} changed or unreachable")
        return 1 if (bad or probs) else 0
    print(("FAIL" if probs else "PASS") + f" edge-remote-deps - the {n_esm} esm.sh modules a deploy bundles are content-locked in "
          f"{LOCK.name} and the lock names nothing the source no longer imports (--online re-fetches and compares)")
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())

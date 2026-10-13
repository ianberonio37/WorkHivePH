#!/usr/bin/env python3
"""validate_edge_imports_pinned.py - every remote import in supabase/functions/** names an EXACT version.

THE INCIDENT (2026-10-07 ~12:38-12:47 UTC, local): after a deno cache clear EVERY edge function failed to boot
(BOOT_ERROR "Module not found https://esm.sh/@supabase/supabase-js@2.117.3/dist/index.d.mts", then an auth-js
404). 74 imports used the FLOATING specifier `https://esm.sh/@supabase/supabase-js@2`. supabase-js 2.117.3 had
been published to npm at 12:34:46 UTC - four minutes earlier - and esm.sh had not finished building it, so `@2`
resolved to a release that did not exist yet on the CDN. A production `supabase functions deploy` bundles at
deploy time and would float the same way: what a function runs depended on the minute it was built, not on the
source. Three imports were pinned, but to three different old versions (2.38.4 x2, 2.39.7 x1) while the browser
client is vendor/supabase-js-2.110.0.min.js.

WHY URL PINS AND NOT AN IMPORT MAP (verified against Supabase CLI 2.90.0 + edge-runtime v1.73.3, 2026-10-08):
  - the local runtime receives each function's importMapPath in SUPABASE_INTERNAL_FUNCTIONS_CONFIG, baked into the
    container when `supabase start` creates it. 56 of 62 functions carry an EMPTY importMapPath, so a new global map
    is not seen after `docker restart`; it needs the container recreated.
  - the CLI's global fallback `supabase/functions/import_map.json` is DEPRECATED ("Functions using fallback import
    map ... Please use recommended per function dependency declaration"), and 6 functions already have their own
    deno.json, which takes precedence over the fallback, so a global map would never reach them.
  - a map that rewrites the URL keeps the floating string in the source; anything that reads the file without the
    map (deno test, a node harness, another bundler) floats again silently.
  An exact version in the URL is honoured the same way by the local runtime, the deploy bundler and `deno test`.
  This gate is the single source of truth that keeps the pins exact and agreeing.

CHECKS (exit 1 on any):
  R1  no FLOATING remote specifier anywhere in supabase/functions/**: code imports (static, multi-line, side
      effect, `export ... from`, dynamic import(), `/// <reference types|path>`, `@deno-types`) and every import
      map (deno.json / deno.jsonc / import_map.json "imports" + "scopes", package.json dependencies, and any
      file config.toml points at with `import_map =`). A specifier is PINNED only when it names an exact
      version: x.y.z (a prerelease or build suffix is still exact), or a 40-hex commit for a git source.
      Floating: no version, `@2`, `@2.1`, `@^2`, `@~2.1.0`, `@latest`, `@*`, a range, a computed template
      import, an esm.sh `?deps=` entry that floats, or a URL on an unrecognised host with no exact version.
  R2  ONE @supabase/supabase-js version across the tree (two versions in one module graph is two clients, and
      drift is how three different pins accumulated).
  INFO the browser vendor client version (vendor/supabase-js-<v>.min.js), so a mismatch is visible.

Not covered (reported, not enforced): transitive dependencies. esm.sh resolves a package's own dependency ranges
when it first builds it, and `npm:` resolves them at install. supabase-js >= 2.7x pins its sub-packages exactly,
so `@supabase/supabase-js@<exact>` is fully determined; ajv / web-push / hyparquet still carry caret ranges inside.

USAGE: python tools/validate_edge_imports_pinned.py [--self-test] [--verbose]
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import tempfile

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parent.parent
FUNCS = ROOT / "supabase" / "functions"
CONFIG = ROOT / "supabase" / "config.toml"
VENDOR = ROOT / "vendor"
GREEN, RED, YEL, RST = "\033[92m", "\033[91m", "\033[93m", "\033[0m"

CODE_EXT = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")
MAP_NAMES = ("deno.json", "deno.jsonc", "import_map.json")
SUPABASE_JS = "@supabase/supabase-js"

EXACT = re.compile(r"^v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
REMOTE = re.compile(r"^(?:https?://|jsr:|npm:)", re.I)

# Hosts that serve npm packages as <host>/<prefix><pkg>@<version>/<path>
NPM_CDNS = {
    "esm.sh": "", "cdn.esm.sh": "", "esm.run": "", "cdn.skypack.dev": "", "unpkg.com": "",
    "cdn.jsdelivr.net": "npm/", "ga.jspm.io": "npm:", "jspm.dev": "",
}

# ---- import extraction -------------------------------------------------------------------------------------
# Reference / @deno-types directives live inside comments, so they are read before comment lines are skipped.
DIRECTIVE_RES = [
    re.compile(r"""///\s*<reference\s+(?:types|path)\s*=\s*(["'])([^"'\n]+)\1"""),
    re.compile(r"""@deno-types\s*=\s*(["'])([^"'\n]+)\1"""),
]
CODE_RES = [
    re.compile(r"""\bfrom\s*(["'])([^"'\n]+)\1"""),                  # import/export ... from "x" (incl. the
                                                                      # closing line of a multi-line import)
    re.compile(r"""^\s*import\s*(["'])([^"'\n]+)\1"""),               # side-effect import "x"
    re.compile(r"""\bimport\s*\(\s*(["'])([^"'\n]+)\1"""),            # dynamic import("x")
]
TEMPLATE_IMPORT = re.compile(r"""\bimport\s*\(\s*`([^`\n]*)`""")     # dynamic import(`...`)


def _is_comment_line(stripped: str) -> bool:
    return stripped.startswith(("//", "*", "/*"))


def extract_code_specifiers(text: str) -> list[tuple[int, str]]:
    """(line number, specifier) for every import-context specifier in a JS/TS source."""
    out: list[tuple[int, str]] = []
    for n, line in enumerate(text.splitlines(), 1):
        for rx in DIRECTIVE_RES:
            for m in rx.finditer(line):
                out.append((n, m.group(2)))
        stripped = line.strip()
        if _is_comment_line(stripped):
            continue
        for rx in CODE_RES:
            for m in rx.finditer(line):
                out.append((n, m.group(2)))
        for m in TEMPLATE_IMPORT.finditer(line):
            out.append((n, "`" + m.group(1) + "`"))
    # de-duplicate (a side-effect import also matches nothing else, but `import("x")` must not double count)
    seen, uniq = set(), []
    for item in out:
        if item not in seen:
            seen.add(item)
            uniq.append(item)
    return uniq


def _strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments outside strings (URLs contain //, so a regex strip is wrong)."""
    out, i, n, in_str, esc = [], 0, len(text), False, False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j == -1 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _line_of(text: str, needle: str) -> int:
    for n, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return n
    return 0


def extract_map_specifiers(name: str, text: str) -> tuple[list[tuple[int, str]], str | None]:
    """(line, specifier) for every value in an import map / deno.json / package.json. Returns (items, error)."""
    try:
        data = json.loads(_strip_jsonc(text))
    except ValueError as e:
        return [], f"unparseable JSON: {e}"
    items: list[tuple[int, str]] = []
    if not isinstance(data, dict):
        return items, None
    if name == "package.json":
        for sect in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
            for pkg, rng in (data.get(sect) or {}).items():
                if isinstance(rng, str):
                    items.append((_line_of(text, f'"{pkg}"'), f"npm:{pkg}@{rng}"))
        return items, None
    imports = dict(data.get("imports") or {})
    for scope in (data.get("scopes") or {}).values():
        if isinstance(scope, dict):
            imports.update({f"{k}#scoped": v for k, v in scope.items()})
    for _key, val in imports.items():
        if isinstance(val, str):
            items.append((_line_of(text, val), val))
    return items, None


# ---- classification ----------------------------------------------------------------------------------------
def _split_pkg(path: str) -> tuple[str, str | None]:
    """'@scope/name@1.2.3/sub' -> ('@scope/name', '1.2.3'); 'name' -> ('name', None)."""
    path = path.lstrip("/")
    if path.startswith("@"):
        m = re.match(r"(@[^/@]+/[^/@?#]+)(?:@([^/?#]*))?", path)
    else:
        m = re.match(r"([^/@?#]+)(?:@([^/?#]*))?", path)
    if not m:
        return path, None
    return m.group(1), m.group(2)


def _ver_verdict(ver: str | None) -> str | None:
    """None when the version is exact, else the reason it floats."""
    if ver is None or ver == "":
        return "no version"
    if EXACT.match(ver):
        return None
    return f"range/tag '{ver}'"


def classify(spec: str) -> dict:
    """{status: pinned|floating|local, reason, pkg, version}."""
    s = spec.strip()
    if s.startswith("`"):
        body = s.strip("`")
        # remote, or wholly computed (`${x}` could be anything); a computed LOCAL path (`./${x}.ts`) is local
        if REMOTE.match(body) or body.startswith("${"):
            return {"status": "floating", "reason": "computed (template) import specifier", "pkg": None, "version": None}
        return {"status": "local", "reason": "", "pkg": None, "version": None}
    if not REMOTE.match(s):
        return {"status": "local", "reason": "", "pkg": None, "version": None}

    low = s.lower()
    if low.startswith(("jsr:", "npm:")):
        pkg, ver = _split_pkg(s[4:])
        why = _ver_verdict(ver)
        return {"status": "floating" if why else "pinned", "reason": why or "", "pkg": pkg, "version": ver}

    m = re.match(r"https?://([^/]+)(/[^?#]*)?(\?[^#]*)?", s, re.I)
    host = (m.group(1) if m else "").lower()
    path = (m.group(2) or "/") if m else "/"
    query = (m.group(3) or "") if m else ""
    rel = path.lstrip("/")

    def with_deps(result: dict) -> dict:
        dm = re.search(r"[?&]deps=([^&#]+)", query)
        if dm and result["status"] == "pinned":
            for dep in dm.group(1).split(","):
                dpkg, dver = _split_pkg(dep)
                why = _ver_verdict(dver)
                if why:
                    return {**result, "status": "floating", "reason": f"?deps={dpkg} {why}"}
        return result

    if host in ("deno.land", "www.deno.land"):
        dm = re.match(r"(std|x/[^/@]+)(?:@([^/]*))?", rel)
        if not dm:
            return {"status": "floating", "reason": "deno.land path without a module version", "pkg": rel, "version": None}
        pkg, ver = dm.group(1), dm.group(2)
        why = _ver_verdict(ver)
        return {"status": "floating" if why else "pinned", "reason": why or "", "pkg": f"deno.land/{pkg}", "version": ver}

    if host == "raw.githubusercontent.com":
        parts = rel.split("/")
        ref = parts[2] if len(parts) > 2 else None
        ok = bool(ref) and (SHA40.match(ref) or EXACT.match(ref))
        return {"status": "pinned" if ok else "floating",
                "reason": "" if ok else f"git ref '{ref}' is not a commit sha or exact tag",
                "pkg": "/".join(parts[:2]), "version": ref}

    if host == "cdn.jsdelivr.net" and rel.startswith("gh/"):
        parts = rel[3:].split("/")
        repo, _, ref = (parts[1] if len(parts) > 1 else "").partition("@")
        ok = bool(ref) and (SHA40.match(ref) or EXACT.match(ref))
        return {"status": "pinned" if ok else "floating",
                "reason": "" if ok else f"git ref '{ref or '(none)'}' is not a commit sha or exact tag",
                "pkg": f"{parts[0]}/{repo}", "version": ref or None}

    if host in NPM_CDNS:
        prefix = NPM_CDNS[host]
        r = rel
        if prefix and r.startswith(prefix):
            r = r[len(prefix):]
        r = re.sub(r"^(?:v\d+/|stable/|jsr/|pr/)+", "", r)          # esm.sh build/channel prefixes
        if r.startswith("gh/"):
            parts = r[3:].split("/")
            repo, _, ref = (parts[1] if len(parts) > 1 else "").partition("@")
            ok = bool(ref) and (SHA40.match(ref) or EXACT.match(ref))
            return {"status": "pinned" if ok else "floating",
                    "reason": "" if ok else f"git ref '{ref or '(none)'}' is not a commit sha or exact tag",
                    "pkg": f"{parts[0]}/{repo}", "version": ref or None}
        pkg, ver = _split_pkg(r)
        why = _ver_verdict(ver)
        return with_deps({"status": "floating" if why else "pinned", "reason": why or "", "pkg": pkg, "version": ver})

    # Unrecognised host: pinned only if the URL carries an exact version or a commit sha somewhere.
    if re.search(r"@v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?(?:/|$)", path) or re.search(r"/[0-9a-f]{40}(?:/|$)", path):
        return {"status": "pinned", "reason": "", "pkg": host, "version": None}
    return {"status": "floating", "reason": f"unrecognised host '{host}' with no exact version in the URL",
            "pkg": host, "version": None}


# ---- scanning ----------------------------------------------------------------------------------------------
def scan_file(rel: str, text: str, is_map: bool = False) -> tuple[list[dict], list[str]]:
    """All REMOTE specifiers in one file, classified. Returns (findings, errors).
    is_map: the file is an import map whatever its name (config.toml `import_map =` can name any file)."""
    name = rel.replace("\\", "/").rsplit("/", 1)[-1]
    errors: list[str] = []
    if is_map or name in MAP_NAMES or name == "package.json" or name.endswith(".importmap.json"):
        items, err = extract_map_specifiers(name, text)
        if err:
            errors.append(f"{rel}: {err}")
    elif name.endswith(CODE_EXT):
        items = extract_code_specifiers(text)
    else:
        items = []
    out = []
    for line, spec in items:
        c = classify(spec)
        if c["status"] == "local":
            continue
        out.append({"file": rel, "line": line, "spec": spec, **c})
    return out, errors


def _config_import_maps(config_text: str) -> list[str]:
    """Paths (relative to supabase/) of every import map config.toml names."""
    return re.findall(r'^\s*import_map\s*=\s*"([^"]+)"', config_text, re.M)


def collect_files(funcs: pathlib.Path, config: pathlib.Path | None) -> list[tuple[str, str, bool]]:
    """(path relative to the repo root, text, is_map) for every file the gate reads."""
    files: dict[pathlib.Path, list] = {}
    for p in sorted(funcs.rglob("*")):
        if not p.is_file():
            continue
        if p.name.endswith(CODE_EXT) or p.name in MAP_NAMES or p.name == "package.json" \
                or p.name.endswith(".importmap.json"):
            try:
                files[p.resolve()] = [p.read_text(encoding="utf-8", errors="replace"), False]
            except OSError:
                continue
    if config and config.exists():
        for rel in _config_import_maps(config.read_text(encoding="utf-8", errors="replace")):
            p = (config.parent / rel).resolve()
            if p in files:
                files[p][1] = True
            elif p.is_file():
                files[p] = [p.read_text(encoding="utf-8", errors="replace"), True]
    root = funcs.parent.parent.resolve()
    out = []
    for path, (text, is_map) in files.items():
        try:
            rel = str(path.relative_to(root)).replace("\\", "/")
        except ValueError:
            rel = str(path)
        out.append((rel, text, is_map))
    return out


def evaluate(files: list[tuple]) -> dict:
    """files: (rel, text) or (rel, text, is_map) tuples."""
    findings, errors = [], []
    for item in files:
        rel, text = item[0], item[1]
        f, e = scan_file(rel, text, bool(item[2]) if len(item) > 2 else False)
        findings.extend(f)
        errors.extend(e)
    floating = [f for f in findings if f["status"] == "floating"]
    sb_versions: dict[str, list[str]] = {}
    for f in findings:
        if f["pkg"] == SUPABASE_JS and f["status"] == "pinned":
            sb_versions.setdefault(f["version"], []).append(f"{f['file']}:{f['line']}")
    return {"findings": findings, "floating": floating, "errors": errors, "sb_versions": sb_versions,
            "files": len(files)}


def vendor_version(vendor: pathlib.Path) -> str | None:
    if not vendor.is_dir():
        return None
    for p in vendor.iterdir():
        m = re.match(r"supabase-js-(\d+\.\d+\.\d+)\.min\.js$", p.name)
        if m:
            return m.group(1)
    return None


def report(res: dict, verbose: bool = False) -> int:
    findings, floating, sbv = res["findings"], res["floating"], res["sb_versions"]
    pinned = [f for f in findings if f["status"] == "pinned"]
    print(f"edge imports: {res['files']} files scanned, {len(findings)} remote specifiers "
          f"({len(pinned)} pinned, {len(floating)} floating)")
    by_spec: dict[str, int] = {}
    for f in findings:
        by_spec[f["spec"]] = by_spec.get(f["spec"], 0) + 1
    if verbose or floating:
        for spec, n in sorted(by_spec.items(), key=lambda kv: (-kv[1], kv[0])):
            st = classify(spec)["status"]
            print(f"  {n:4d}  {'FLOAT ' if st == 'floating' else 'pinned'}  {spec}")
    fails = 0
    for e in res["errors"]:
        print(f"{RED}ERROR{RST} {e}")
        fails += 1
    if floating:
        print(f"{RED}R1 FAIL{RST} {len(floating)} floating remote specifier(s):")
        for f in floating[:200]:
            print(f"  {f['file']}:{f['line']}  {f['spec']}  -> {f['reason']}")
        if len(floating) > 200:
            print(f"  ... and {len(floating) - 200} more")
        fails += 1
    else:
        print(f"{GREEN}R1 PASS{RST} every remote specifier names an exact version")
    if len(sbv) > 1:
        print(f"{RED}R2 FAIL{RST} {SUPABASE_JS} is pinned to {len(sbv)} different versions:")
        for v, where in sorted(sbv.items()):
            print(f"  {v}: {len(where)}  e.g. {', '.join(where[:3])}")
        fails += 1
    elif sbv:
        print(f"{GREEN}R2 PASS{RST} one {SUPABASE_JS} version: {next(iter(sbv))} ({sum(len(w) for w in sbv.values())} imports)")
    else:
        print(f"R2 n/a  no pinned {SUPABASE_JS} import found")
    vv = vendor_version(VENDOR)
    if vv:
        same = sbv and list(sbv) == [vv]
        print(f"INFO  browser vendor client {vv} - edge {'matches' if same else 'differs: ' + ', '.join(sorted(sbv)) if sbv else 'n/a'}")
    return 1 if fails else 0


# ---- self-test ---------------------------------------------------------------------------------------------
def self_test() -> int:
    bad = 0

    def expect(cond: bool, label: str) -> None:
        nonlocal bad
        print(f"  {'ok  ' if cond else 'FAIL'}  {label}")
        if not cond:
            bad += 1

    print("classification:")
    floating = [
        "https://esm.sh/@supabase/supabase-js@2",                     # the incident specifier
        "https://esm.sh/@supabase/supabase-js",
        "https://esm.sh/@supabase/supabase-js@^2.39.0",
        "https://esm.sh/@supabase/supabase-js@latest",
        "https://esm.sh/@supabase/supabase-js@2.110",
        "https://esm.sh/v135/hyparquet@1",
        "https://esm.sh/hyparquet@1.26.0?deps=foo@^2",
        "https://deno.land/std/http/server.ts",
        "https://deno.land/std@0.168/http/server.ts",
        "https://deno.land/x/oak/mod.ts",
        "jsr:@supabase/functions-js@^2",
        "jsr:@std/assert",
        "npm:web-push",
        "npm:web-push@^3.6.7",
        "npm:@scope/pkg@~1.2.3",
        "https://cdn.jsdelivr.net/npm/ajv@8/dist/ajv.js",
        "https://cdn.jsdelivr.net/gh/o/r@main/mod.ts",
        "https://raw.githubusercontent.com/o/r/main/mod.ts",
        "https://example.com/mod.ts",
        "`https://esm.sh/${pkg}`",
    ]
    pinned = [
        "https://esm.sh/@supabase/supabase-js@2.110.0",
        "https://esm.sh/v135/@supabase/supabase-js@2.110.0/dist/module/index.js",
        "https://esm.sh/hyparquet@1.26.0",
        "https://esm.sh/hyparquet@1.26.0?deps=foo@2.0.1&target=deno",
        "https://deno.land/std@0.168.0/http/server.ts",
        "https://deno.land/x/oak@v12.6.1/mod.ts",
        "jsr:@supabase/functions-js@2.110.0",
        "jsr:@std/assert@1.0.13/equals",
        "npm:web-push@3.6.7",
        "npm:@scope/pkg@1.2.3-beta.1",
        "https://raw.githubusercontent.com/o/r/0123456789abcdef0123456789abcdef01234567/mod.ts",
    ]
    local = ["../_shared/cors.ts", "./x.ts", "node:crypto", "@supabase/functions-js"]
    for s in floating:
        expect(classify(s)["status"] == "floating", f"floating  {s}")
    for s in pinned:
        expect(classify(s)["status"] == "pinned", f"pinned    {s}")
    for s in local:
        expect(classify(s)["status"] == "local", f"local     {s}")
    c = classify("https://esm.sh/@supabase/supabase-js@2.110.0")
    expect(c["pkg"] == SUPABASE_JS and c["version"] == "2.110.0", "supabase-js package/version parsed")

    print("extraction (synthetic tree, CRLF):")
    src = "\r\n".join([
        '/// <reference types="https://esm.sh/@types/x/index.d.ts" />',
        'import { createClient } from "https://esm.sh/@supabase/supabase-js@2";',
        "import {",
        "  a,",
        "  b,",
        "} from 'https://esm.sh/multi@1';",
        'import "https://deno.land/std/dotenv/load.ts";',
        'export * from "jsr:@std/assert";',
        'const m = await import("npm:left-pad");',
        "const t = await import(`https://esm.sh/${name}`);",
        '// import { old } from "https://esm.sh/commented@2";',
        ' * import { doc } from "https://esm.sh/doc@2";',
        'import { ok } from "../_shared/envelope.ts";',
        'import { pinned } from "https://esm.sh/pinned@1.2.3";',
        "const s = Array.from(\"abc\");",
    ]) + "\r\n"
    deno_json = '{\n  // a jsonc comment with a url https://x\n  "imports": {"a": "jsr:@a/b@^1", "c": "npm:c@1.0.0"},\n' \
                '  "scopes": {"https://x/": {"d": "https://esm.sh/d@2"}}\n}\n'
    res = evaluate([("supabase/functions/fn/index.ts", src), ("supabase/functions/fn/deno.json", deno_json)])
    got = sorted(f["spec"] for f in res["floating"])
    want = sorted([
        "https://esm.sh/@types/x/index.d.ts", "https://esm.sh/@supabase/supabase-js@2", "https://esm.sh/multi@1",
        "https://deno.land/std/dotenv/load.ts", "jsr:@std/assert", "npm:left-pad", "`https://esm.sh/${name}`",
        "jsr:@a/b@^1", "https://esm.sh/d@2",
    ])
    expect(got == want, f"9 floating found across every import form + map ({len(got)} found)")
    if got != want:
        print("     got: ", got)
        print("     want:", want)
    expect(not any("commented" in f["spec"] or "doc@2" in f["spec"] for f in res["findings"]),
           "commented-out imports are not imports")
    expect(any(f["spec"] == "https://esm.sh/pinned@1.2.3" and f["status"] == "pinned" for f in res["findings"]),
           "a pinned import is pinned")
    ml = [f for f in res["floating"] if f["spec"] == "https://esm.sh/multi@1"]
    expect(bool(ml) and ml[0]["line"] == 6, "a multi-line import is reported at its `from` line")

    print("R2 version drift:")
    drift = evaluate([
        ("supabase/functions/a/index.ts", 'import { createClient } from "https://esm.sh/@supabase/supabase-js@2.110.0";\n'),
        ("supabase/functions/b/index.ts", 'import { createClient } from "https://esm.sh/@supabase/supabase-js@2.38.4";\n'),
    ])
    expect(len(drift["sb_versions"]) == 2 and not drift["floating"], "two exact supabase-js versions are DRIFT")
    one = evaluate([
        ("supabase/functions/a/index.ts", 'import { createClient } from "https://esm.sh/@supabase/supabase-js@2.110.0";\n'),
        ("supabase/functions/b/index.ts", "import { SupabaseClient } from 'https://esm.sh/@supabase/supabase-js@2.110.0';\n"),
    ])
    expect(len(one["sb_versions"]) == 1 and not one["floating"], "one version across files passes")

    print("teeth on the REAL tree (in memory, nothing written):")
    real = collect_files(FUNCS, CONFIG)
    expect(len(real) > 50, f"real tree collected ({len(real)} files)")
    base = evaluate(real)
    pinned_sb = [f for f in base["findings"] if f["pkg"] == SUPABASE_JS and f["status"] == "pinned"]
    def mutated(target: dict, new_spec: str) -> list[tuple]:
        return [(rel, text.replace(target["spec"], new_spec, 1) if rel == target["file"] else text, is_map)
                for rel, text, is_map in real]

    if pinned_sb:
        target = pinned_sb[0]
        r2 = evaluate(mutated(target, "https://esm.sh/@supabase/supabase-js@2"))
        expect(any(f["file"] == target["file"] and f["spec"].endswith("supabase-js@2") for f in r2["floating"]),
               f"reverting {target['file']} to the incident specifier is caught")
        other = "9.9.9" if "9.9.9" not in base["sb_versions"] else "9.9.8"
        r3 = evaluate(mutated(target, target["spec"].replace(f"@{target['version']}", f"@{other}", 1)))
        expect(len(r3["sb_versions"]) >= 2, f"pinning {target['file']} to a second version is caught as drift")
    else:
        expect(any(f["spec"].endswith("supabase-js@2") for f in base["floating"]),
               "the unpinned tree is caught (the incident specifier is floating)")
    map_pins = [f for f in base["findings"] if f["status"] == "pinned" and f["spec"].startswith(("jsr:", "npm:"))
                and any(rel == f["file"] and is_map for rel, _t, is_map in real)]
    if map_pins:
        t = map_pins[0]
        r5 = evaluate(mutated(t, t["spec"].replace(f"@{t['version']}", "@^2", 1)))
        expect(any(f["file"] == t["file"] for f in r5["floating"]),
               f"a caret range written back into {t['file']} is caught")

    with tempfile.TemporaryDirectory() as td:
        tdp = pathlib.Path(td)
        (tdp / "supabase" / "functions" / "fn").mkdir(parents=True)
        (tdp / "supabase" / "maps").mkdir(parents=True)
        (tdp / "supabase" / "functions" / "fn" / "index.ts").write_bytes(
            b'import { x } from "npm:y@1.0.0";\r\n')
        (tdp / "supabase" / "maps" / "outside.json").write_text('{"imports": {"y": "npm:y@^1"}}', encoding="utf-8")
        (tdp / "supabase" / "config.toml").write_text('[functions.fn]\r\nimport_map = "./maps/outside.json"\r\n',
                                                      encoding="utf-8")
        r4 = evaluate(collect_files(tdp / "supabase" / "functions", tdp / "supabase" / "config.toml"))
        expect(any(f["spec"] == "npm:y@^1" for f in r4["floating"]),
               "an import map config.toml points at OUTSIDE supabase/functions is scanned")

    print(f"self-test: {'PASS' if bad == 0 else f'FAIL ({bad})'}")
    return 1 if bad else 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    res = evaluate(collect_files(FUNCS, CONFIG))
    return report(res, verbose="--verbose" in argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

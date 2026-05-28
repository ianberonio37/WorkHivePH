"""
Edge Function Import/Export Resolution Validator (L0, ratcheted).
==================================================================
Every NAMED import from a RELATIVE module under supabase/functions/** must
resolve to a real export in the target module.

Catches the class of bug that boot-breaks the edge layer at runtime but passes
every static gate: a `_shared/` export is renamed/dropped, but importers still
reference the old name. Deno throws
  `Uncaught SyntaxError: module './X.ts' does not provide an export named 'Y'`
only when `supabase functions serve` boots the worker — by which point CI is
green and the break is invisible. Since every edge fn imports
`_shared/envelope.ts`, one bad shared export 503s the whole platform.

Concrete origin (2026-05-28): `_shared/cors.ts` refactored to `getCorsHeaders`
and dropped the static `corsHeaders` const, but `envelope.ts` + `health.ts`
still `import { corsHeaders }`. This validator would have failed at L0.

Scope: only relative imports (`./`, `../`) are resolved — remote (https/npm/jsr/
node:) modules can't be parsed statically and are skipped. Modules that
`export *` from another module are treated as providing any name (no false
positives), at the cost of not checking names sourced through them.

Output: edge_import_exports_report.json. Exit 1 on regression.
Allow with `// import-export-allow: <reason>` within 200 chars of the import.
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
EDGE_DIR = ROOT / "supabase" / "functions"
REPORT_PATH = ROOT / "edge_import_exports_report.json"
BASELINE_PATH = ROOT / "edge_import_exports_baseline.json"

LINE_COMMENT = re.compile(r"//[^\n]*")
BLOCK_COMMENT = re.compile(r"/\*[\s\S]*?\*/")

# import [type] { a, b as c } from "<spec>";   (multiline-tolerant)
# Type-only imports are erased at runtime — a missing type export is a tsc
# error, NOT a boot SyntaxError — so this gate (boot safety) skips them.
IMPORT_RE = re.compile(
    r"""import\s+(?P<typekw>type\s+)?\{(?P<names>[^}]*)\}\s+from\s+['"](?P<spec>[^'"]+)['"]""",
    re.MULTILINE,
)
INLINE_TYPE_RE = re.compile(r"^type\s+")
ALLOW_RE = re.compile(r"import-export-allow", re.IGNORECASE)

# Export forms in a target module.
EXPORT_DECL_RE = re.compile(
    r"""export\s+(?:async\s+)?(?:function|class|const|let|var|interface|type|enum)\s+(?P<name>[A-Za-z_$][\w$]*)"""
)
EXPORT_LIST_RE = re.compile(r"""export\s*\{(?P<names>[^}]*)\}""")     # export { a, b as c } [from ...]
EXPORT_DEFAULT_RE = re.compile(r"""export\s+default\b""")
EXPORT_STAR_RE = re.compile(r"""export\s*\*\s*from""")


def _strip(code: str) -> str:
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub("", code))


def _module_exports(path: Path, cache: dict) -> tuple[set[str], bool]:
    """Return (exported_names, has_star_reexport). Cached by resolved path."""
    key = str(path)
    if key in cache:
        return cache[key]
    if not path.exists():
        cache[key] = (set(), False)
        return cache[key]
    code = _strip(path.read_text(encoding="utf-8", errors="replace"))
    names: set[str] = set()
    for m in EXPORT_DECL_RE.finditer(code):
        names.add(m.group("name"))
    for m in EXPORT_LIST_RE.finditer(code):
        for tok in m.group("names").split(","):
            tok = tok.strip()
            if not tok:
                continue
            # `internal as public` -> exported name is the public (last) token
            exported = re.split(r"\s+as\s+", tok)[-1].strip()
            if exported:
                names.add(exported)
    if EXPORT_DEFAULT_RE.search(code):
        names.add("default")
    has_star = bool(EXPORT_STAR_RE.search(code))
    cache[key] = (names, has_star)
    return cache[key]


def _resolve(spec: str, from_dir: Path) -> Path | None:
    """Resolve a relative import spec to a file. Deno uses explicit extensions."""
    if not spec.startswith("."):
        return None  # remote / npm / jsr / node — not statically resolvable
    target = (from_dir / spec).resolve()
    if target.suffix:  # has extension (Deno style: ./cors.ts)
        return target
    for cand in (target.with_suffix(".ts"), target / "index.ts", target.with_suffix(".js")):
        if cand.exists():
            return cand
    return target.with_suffix(".ts")


def main() -> int:
    if not EDGE_DIR.exists():
        print("No supabase/functions dir — skipping.")
        return 0

    export_cache: dict = {}
    files = sorted(EDGE_DIR.rglob("*.ts"))
    per_file = []
    total_imports = 0
    total_drift = 0
    seen: set = set()

    for f in files:
        raw = f.read_text(encoding="utf-8", errors="replace")
        code = _strip(raw)
        issues = []
        for m in IMPORT_RE.finditer(code):
            if m.group("typekw"):
                continue  # `import type { ... }` — erased at runtime
            spec = m.group("spec")
            target = _resolve(spec, f.parent)
            if target is None:
                continue  # remote import
            total_imports += 1
            if ALLOW_RE.search(raw[max(0, m.start() - 200): m.start() + 200]):
                continue
            exports, has_star = _module_exports(target, export_cache)
            if has_star:
                continue  # target re-exports * — can't be sure; don't flag
            if not target.exists():
                # missing target file is its own (worse) problem; report it once
                key = (f.name, spec, "<missing-module>")
                if key not in seen:
                    seen.add(key)
                    issues.append({"spec": spec, "name": "<module not found>"})
                    total_drift += 1
                continue
            for tok in m.group("names").split(","):
                tok = tok.strip()
                if not tok:
                    continue
                if INLINE_TYPE_RE.match(tok):
                    continue  # inline `type X` — erased at runtime
                # `exportName as localName` -> we check exportName (the source)
                src = re.split(r"\s+as\s+", tok)[0].strip()
                if not src or src == "*":
                    continue
                if src in exports:
                    continue
                key = (f.relative_to(ROOT).as_posix(), spec, src)
                if key in seen:
                    continue
                seen.add(key)
                issues.append({"spec": spec, "name": src})
                total_drift += 1
        if issues:
            per_file.append({"file": f.relative_to(ROOT).as_posix(), "issues": issues})

    baseline = 0
    if BASELINE_PATH.exists():
        try:
            baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("drift", 0)
        except Exception:
            baseline = total_drift
    else:
        baseline = total_drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "established": True}, indent=2), encoding="utf-8")
    if total_drift < baseline:
        baseline = total_drift
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"files_scanned": len(files), "named_relative_imports": total_imports,
                    "total_drift": total_drift, "baseline": baseline},
        "per_file": per_file,
    }, indent=2), encoding="utf-8")

    print("\nEdge Function Import/Export Resolution Validator (L0)")
    print("=" * 56)
    print(f"  .ts files scanned:        {len(files)}")
    print(f"  named relative imports:   {total_imports}")
    print(f"  unresolved imports:       {total_drift}  (baseline: {baseline})")
    if total_drift == 0:
        print("\n  PASS — every named relative import resolves to a real export.")
        return 0
    shown = 0
    for entry in per_file:
        print(f"  {entry['file']}")
        for i in entry["issues"]:
            print(f"    import {{ {i['name']} }} from '{i['spec']}'  — not exported by target")
            shown += 1
            if shown >= 40:
                print("    ... (more in report)"); break
        if shown >= 40:
            break
    print(f"\n  {'PASS (at baseline)' if total_drift <= baseline else 'FAIL (regression)'}")
    return 1 if total_drift > baseline else 0


# Sentinel binding: name the L2 test `test('edge_import_exports: ...')`.
CHECK_NAMES = ["edge_import_exports"]

if __name__ == "__main__":
    sys.exit(main())

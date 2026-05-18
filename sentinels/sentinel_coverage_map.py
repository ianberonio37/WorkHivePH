"""sentinel_coverage_map.py - Layer 0 -> Layer 2 coverage sentinel (v0).

Maps each Layer 0 validator (validate_*.py at project root) to the Playwright
specs (tests/*.spec.ts) that exercise it behaviorally. Emits a coverage report
+ gap list.

This is v0 of the Sentinel Architecture. Pure deterministic - no LLM.
Coverage matching is filename-token overlap (high signal, no false positives).
Per-check granularity is left to v1 (gap proposer with LLM).

Output:
  sentinel_coverage_report.json - full per-validator map + gap list
  Console summary             - single coverage percentage + top gaps

See SENTINEL_ARCHITECTURE.md for the full roadmap.
"""

import sys
import re
import json
import datetime
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = ROOT / "tests"
REPORT_FILE = ROOT / "sentinel_coverage_report.json"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

STOP_TOKENS = {
    "validate", "validator", "check", "checks", "spec", "ts", "py",
    "journey", "test", "tests", "consistency", "coverage",
}


def tokenize(name: str) -> set:
    """Extract topic tokens from a filename or identifier."""
    for ext in (".spec.ts", ".py", ".ts", ".js"):
        if name.endswith(ext):
            name = name[: -len(ext)]
    for prefix in ("validate_", "journey-", "journey_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
    parts = re.split(r"[_\-]", name.lower())
    return {p for p in parts if p and p not in STOP_TOKENS}


def _appears_only_in_comments(src: str, html_ref: str) -> bool:
    """Return True if every occurrence of html_ref in src sits on a line
    that starts (after whitespace) with `#`, or inside a triple-quoted block.

    This catches the case where a validator mentions a page in its docstring
    or a `# Layer 1 -- foo.html` comment but never actually scans it in code.
    Such a reference should not contribute to per-page classification."""
    in_docstring = False
    found_code_line = False
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith('"""') or stripped.endswith('"""'):
            in_docstring = not in_docstring if stripped.count('"""') == 1 else in_docstring
            if html_ref in line:
                continue
            continue
        if html_ref not in line:
            continue
        if in_docstring:
            continue
        if stripped.startswith("#"):
            continue
        found_code_line = True
        break
    return not found_code_line


def discover_validators(root: Path) -> list:
    """Find every validate_*.py at project root (skip venv + site-packages)."""
    out = []
    for path in sorted(root.glob("validate_*.py")):
        if "venv" in path.parts or "site-packages" in path.parts:
            continue
        try:
            src = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        checks = sorted(set(re.findall(
            r'["\']check["\']\s*:\s*["\']([^"\']+)["\']', src
        )))
        doc_match = re.search(r'^"""([^\n]+)', src)
        label = doc_match.group(1).strip() if doc_match else path.stem
        all_html_matches = re.findall(
            r'''["\']([A-Za-z][\w\-]*\.html)["\']''', src
        )
        non_comment_html_refs = sorted(set(
            re.findall(
                r'''(?<!#)["\']([A-Za-z][\w\-]*\.html)["\']''', src
            )
        ))
        non_comment_html_refs = [
            ref for ref in non_comment_html_refs
            if not _appears_only_in_comments(src, ref)
        ]
        html_refs = sorted(set(all_html_matches))
        scope = "per-page"
        live_pages_match = re.search(r"LIVE_PAGES\s*=\s*\[(.*?)\]", src, re.DOTALL)
        if live_pages_match:
            n_pages_in_list = len(re.findall(r"\.html", live_pages_match.group(1)))
            if n_pages_in_list >= 5:
                scope = "platform-wide"
        if scope == "per-page" and re.search(
            r'''\.glob\s*\(\s*["\'][^"\']*\.html''', src
        ):
            scope = "platform-wide"
        if scope == "per-page" and len(non_comment_html_refs) >= 5:
            scope = "platform-wide"
        if scope == "per-page" and re.search(
            r"LIVE_TOOL_PAGES|nav-hub\.js|TOOLS\s*=\s*\[", src
        ):
            scope = "platform-wide"
        out.append({
            "file": path.name,
            "label": label,
            "tokens": sorted(tokenize(path.name)),
            "checks": checks,
            "html_refs": html_refs,
            "active_html_refs": non_comment_html_refs,
            "scope": scope,
            "_src": src,
        })
    return out


def discover_specs(tests_dir: Path) -> list:
    """Find every *.spec.ts in tests/ and pull out test() / describe() names."""
    out = []
    if not tests_dir.exists():
        return out
    for path in sorted(tests_dir.glob("*.spec.ts")):
        try:
            src = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        names = re.findall(
            r"""test(?:\.describe)?\(\s*['"`]([^'"`]+)['"`]""", src
        )
        out.append({
            "file": path.name,
            "tokens": sorted(tokenize(path.name)),
            "test_names": names,
        })
    return out


CONTENT_MATCH_STOP_WORDS = {
    "a", "an", "the", "to", "of", "on", "in", "is", "are", "and", "or",
    "for", "from", "with", "without", "by", "at", "as", "be", "this", "that",
    "test", "tests", "page", "pages", "load", "loads", "render", "renders",
    "save", "saves", "shows", "show", "visible", "hidden", "appear", "appears",
    "click", "fill", "form", "submit", "button", "link", "modal", "dialog",
    "card", "panel", "regression", "happy", "path", "validation", "error",
    "errors", "console", "states", "state", "html", "json", "field", "fields",
    "main", "all", "any", "only", "log", "logs", "present", "missing",
    "active", "inactive", "open", "closed", "true", "false", "null", "none",
    "auto", "edit", "list", "view", "row", "rows", "value", "values",
    "data", "type", "types", "name", "names", "id", "key", "keys", "set",
    "exist", "exists", "via", "after", "before", "not", "yes", "no",
    "live", "real", "time",
}


STRUCTURAL_CHECK_SIGNALS = {
    "table", "tables", "rpc", "rpcs", "view", "views", "column", "columns",
    "schema", "migration", "migrations", "fk", "foreign", "index", "indexes",
    "endpoint", "endpoints", "fn", "function", "functions", "edge",
    "registered", "registry", "present", "missing", "exists",
    "cron", "trigger", "triggers", "rls", "policy", "policies",
    "channel", "channels", "subscription", "publication",
    "config", "secret", "env",
    "module", "import", "imports", "export", "exports",
    "feature", "cols", "artifacts", "gitignore", "gitkeep",
}

BEHAVIORAL_CHECK_SIGNALS = {
    "render", "renders", "rendered", "visible", "hidden",
    "click", "clicks", "clicked", "tap", "tapped",
    "toast", "toasts", "notification", "alert", "alerts",
    "submit", "submits", "save", "saves", "saved",
    "fill", "fills", "filled", "input", "inputs",
    "close", "closed", "open", "opens",
    "select", "selected", "filter", "filtered",
    "navigate", "redirect", "redirects",
    "drawer", "modal", "sheet", "panel",
    "gate", "gated", "blocked", "denied",
    "show", "shown", "hide", "hidden",
    "valid", "invalid", "value", "values",
    "card", "tile", "row", "list",
    "loader", "loading", "empty", "ready",
}


CHECK_KIND_OVERRIDES_FILE = Path(__file__).resolve().parent / "check_kind_overrides.json"


def _load_check_kind_overrides() -> dict:
    """Load the manual override file. Returns dict keyed by (validator, check)."""
    if not CHECK_KIND_OVERRIDES_FILE.exists():
        return {}
    try:
        data = json.loads(CHECK_KIND_OVERRIDES_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out = {}
    for entry in data.get("overrides", []):
        v = entry.get("validator")
        c = entry.get("check")
        k = entry.get("kind")
        if v and c and k in ("behavioral", "structural"):
            out[(v, c)] = k
    return out


_CHECK_KIND_OVERRIDES = _load_check_kind_overrides()


def classify_check(check_name: str, validator_file: str | None = None) -> str:
    """Return 'behavioral' or 'structural' for a single check name.

    Order: manual override file -> heuristic on tokens.

    Heuristic:
    - structural-only signals (table, rpc, view, schema, fn, etc.) -> structural
    - behavioral signals (render, click, toast, gate, etc.) -> behavioral
    - mixed: prefer behavioral if any behavioral signal present
    - neither: default 'behavioral' (conservative)
    """
    if validator_file:
        override = _CHECK_KIND_OVERRIDES.get((validator_file, check_name))
        if override:
            return override

    raw = check_name.lower().replace("-", "_")
    parts = re.split(r"[_\s]+", raw)
    parts = [p for p in parts if p]

    structural_hits = sum(1 for p in parts if p in STRUCTURAL_CHECK_SIGNALS)
    behavioral_hits = sum(1 for p in parts if p in BEHAVIORAL_CHECK_SIGNALS)

    if behavioral_hits >= 1:
        return "behavioral"
    if structural_hits >= 1:
        return "structural"
    return "behavioral"


def _stem(tok: str) -> str:
    """Tiny stem so 'notifications' matches 'notification', 'channels' matches
    'channel'. Strip trailing 's' for words of length >= 5 that don't end in
    'ss' or 'us' (avoid mangling 'access', 'bus', 'status' etc)."""
    if len(tok) >= 5 and tok.endswith("s") and not tok.endswith(("ss", "us", "is")):
        return tok[:-1]
    return tok


def _content_tokens(text: str) -> set:
    """Lowercase alphabetic tokens of length >= 3, stop words removed.
    Splits on snake_case AND camelCase so 'buildNotifications_called'
    decomposes into {build, notifications, called}. Stem-normalized."""
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    words = re.findall(r"[A-Za-z]{3,}", spaced)
    out = set()
    for word in words:
        wl = word.lower()
        for piece in wl.split("_"):
            if len(piece) >= 3 and piece not in CONTENT_MATCH_STOP_WORDS:
                out.add(_stem(piece))
    return out


def _check_phrase_tokens(check: str) -> set:
    """Significant tokens from a single check name, e.g.
    'parts_txn_parity' -> {'parts', 'txn', 'parity'}. Stem-normalized."""
    parts = check.lower().split("_")
    return {_stem(p) for p in parts
            if len(p) >= 3 and p not in CONTENT_MATCH_STOP_WORDS}


def _is_check_covered(check_toks: set, validator_tokens: set,
                      check: str, specs: list) -> tuple:
    """v0.5 honest check-level coverage.

    Returns (covered: bool, by_spec: str | None).

    Rules in priority order:
      0. Path A (strongest): the literal check name (with `_` -> ` `) appears
         as a substring of any spec's test name. This catches the documented
         convention `test('check_name: description', ...)`.
      1. >=2 significant tokens in check: all must subset some spec's content
      2. 1 token: must subset a TOPIC-anchored spec (filename overlap)
      3. 0 tokens (all stops / short): already covered by Path A
    """
    check_norm = check.lower().replace("_", " ").strip()
    if check_norm:
        for spec in specs:
            blob = " ".join(spec.get("test_names", [])).lower().replace("_", " ")
            if check_norm in blob:
                return True, spec["file"]

    if not check_toks:
        return False, None
    if len(check_toks) == 1:
        single = next(iter(check_toks))
        for spec in specs:
            if not (validator_tokens & set(spec["tokens"])):
                continue
            spec_content = _content_tokens(" ".join(spec.get("test_names", [])))
            if single in spec_content:
                return True, spec["file"]
        return False, None
    for spec in specs:
        spec_content = _content_tokens(" ".join(spec.get("test_names", [])))
        if check_toks.issubset(spec_content):
            return True, spec["file"]
    return False, None


def compute_check_level_coverage(validator: dict, specs: list) -> dict:
    """For each check in the validator, determine if it's covered.
    Returns a dict with covered_checks, uncovered_checks, by_spec mapping."""
    v_tokens = set(validator["tokens"])
    checks = validator.get("checks", [])

    if not checks:
        filename_phrase = {t for t in v_tokens
                           if len(t) >= 3 and t not in CONTENT_MATCH_STOP_WORDS}
        if len(filename_phrase) >= 2:
            for spec in specs:
                spec_content = _content_tokens(" ".join(spec.get("test_names", [])))
                if filename_phrase.issubset(spec_content):
                    return {
                        "covered_checks": ["(structural - no declared checks, topic exercised)"],
                        "uncovered_checks": [],
                        "by_spec": {"(structural)": spec["file"]},
                    }
        for spec in specs:
            if v_tokens & set(spec["tokens"]):
                return {
                    "covered_checks": ["(structural - filename match only)"],
                    "uncovered_checks": [],
                    "by_spec": {"(structural)": spec["file"]},
                }
        return {
            "covered_checks": [],
            "uncovered_checks": ["(structural - no behavioral test)"],
            "by_spec": {},
        }

    covered, uncovered, by_spec = [], [], {}
    for check in checks:
        check_toks = _check_phrase_tokens(check)
        is_covered, spec_file = _is_check_covered(check_toks, v_tokens, check, specs)
        if is_covered:
            covered.append(check)
            by_spec[check] = spec_file
        else:
            uncovered.append(check)
    return {
        "covered_checks": covered,
        "uncovered_checks": uncovered,
        "by_spec": by_spec,
    }


def match_validator_to_specs(validator: dict, specs: list) -> list:
    """Match validator to specs via filename overlap OR strict check-name match.

    A content match requires every significant token from a check name to
    appear in the spec's test text. This avoids the false positives where
    a single shared word ('signal', 'log', 'audit') triggers a match."""
    matches = []
    v_tokens = set(validator["tokens"])
    check_phrases = []
    for check in validator.get("checks", []):
        toks = _check_phrase_tokens(check)
        if len(toks) >= 1:
            check_phrases.append((check, toks))
    filename_phrase = {tok for tok in v_tokens
                       if len(tok) >= 3 and tok not in CONTENT_MATCH_STOP_WORDS}
    if len(filename_phrase) >= 2:
        check_phrases.append(("(filename topic)", filename_phrase))

    for spec in specs:
        s_tokens = set(spec["tokens"])
        filename_overlap = v_tokens & s_tokens

        spec_test_text = " ".join(spec.get("test_names", []))
        spec_content_tokens = _content_tokens(spec_test_text)

        content_hits = []
        for check, toks in check_phrases:
            if len(toks) >= 2 and toks.issubset(spec_content_tokens):
                content_hits.append(check)

        if filename_overlap or content_hits:
            score = 5 * len(filename_overlap) + len(content_hits)
            matches.append({
                "file": spec["file"],
                "matched_tokens": sorted(filename_overlap),
                "matched_checks": content_hits[:5],
                "match_strength": score,
                "via": "filename" if filename_overlap else "check-name",
            })
    matches.sort(key=lambda m: -m["match_strength"])
    return matches


def collect_html_surfaces(root: Path) -> dict:
    """Map every <token>.html at project root to its filename.
    Used to classify validators as behavioral (has UI surface) or
    infrastructure (no UI surface) automatically."""
    surfaces = {}
    for path in root.glob("*.html"):
        surfaces[path.stem.lower()] = path.name
        normalized = path.stem.lower().replace("-", "_")
        surfaces[normalized] = path.name
    return surfaces


def classify_validator(tokens: list, html_refs: list, html_surfaces: dict) -> tuple:
    """Return (is_infrastructure: bool, matched_html: str | None).

    A validator is BEHAVIORAL if either:
      - one of its tokens matches a <token>.html file at project root, OR
      - its source code references one or more .html files at project root
        (e.g. LIVE_PAGES = [...], HIVE_HTML = ..., reads of hive.html)

    Otherwise it is INFRASTRUCTURE (backend code rule, schema check, edge
    fn contract, etc.) and Layer 2 is not the right enforcement layer."""
    for tok in tokens:
        if tok in html_surfaces:
            return False, html_surfaces[tok]
    joined = "_".join(tokens) if tokens else ""
    if joined and joined in html_surfaces:
        return False, html_surfaces[joined]
    hyphenated = "-".join(tokens) if tokens else ""
    if hyphenated and hyphenated in html_surfaces:
        return False, html_surfaces[hyphenated]

    if html_refs:
        for ref in html_refs:
            stem = ref[:-5].lower()
            normalized = stem.replace("-", "_")
            if stem in html_surfaces or normalized in html_surfaces:
                return False, ref

    return True, None


_CONTENT_SYNC_IMPORT_RE = re.compile(
    r"from\s+wh_pages\s+import\s+("
    r"all_public_surfaces|learn_slugs|sitemap_urls|public_surfaces"
    r")"
)


def is_content_sync_validator(src: str) -> bool:
    """v0.5 — Detect file-consistency scanners that target text artifacts
    (llms.txt, sitemap.xml, robots.txt, static HTML for stale string refs).

    Signal: validator imports a page-list helper from wh_pages. These
    scan files at rest — the failure mode is file drift, not user-observable
    behavior. A Playwright test would just re-do the static scan.

    Any True here forces the validator to category=infrastructure with
    subtype=content-sync, regardless of token/HTML matching. Drops these
    out of the per-page gap list."""
    return bool(_CONTENT_SYNC_IMPORT_RE.search(src or ""))


def classify_validator_strict(tokens: list, active_html_refs: list,
                              html_refs_all: list, html_surfaces: dict,
                              src: str = "") -> tuple:
    """Stricter classifier - only treats HTML refs as behavioral signal if
    they appear in actual scanning code (not docstrings / comments).

    v0.3 additional overrides (return INFRA even if HTML ref present):
      - Validator scans supabase/functions/ - edge fn contract = backend
      - Validator scans supabase/migrations/ - schema = backend
      - The only matched HTML is a *-test.html test fixture page
    """
    src_lower = src.lower()
    scans_edge_fns = bool(re.search(
        r'supabase[/\\\\]+functions|FUNCTIONS_DIR|EDGE_FN', src
    ))
    scans_migrations = bool(re.search(
        r'supabase[/\\\\]+migrations|MIGRATIONS_DIR|\.glob\(\s*["\']\*\.sql', src
    ))
    if scans_edge_fns or scans_migrations:
        if not any(tok in html_surfaces for tok in tokens):
            return True, None

    for tok in tokens:
        if tok in html_surfaces:
            return False, html_surfaces[tok]
    joined = "_".join(tokens) if tokens else ""
    if joined and joined in html_surfaces:
        return False, html_surfaces[joined]
    hyphenated = "-".join(tokens) if tokens else ""
    if hyphenated and hyphenated in html_surfaces:
        return False, html_surfaces[hyphenated]

    refs_to_use = active_html_refs if active_html_refs else []
    non_test_refs = [r for r in refs_to_use if not r.endswith("-test.html")]
    pool = non_test_refs if non_test_refs else refs_to_use
    for ref in pool:
        if ref.endswith("-test.html") and non_test_refs:
            continue
        stem = ref[:-5].lower()
        normalized = stem.replace("-", "_")
        if stem in html_surfaces or normalized in html_surfaces:
            if ref.endswith("-test.html") and not non_test_refs:
                return True, None
            return False, ref
    return True, None


def main():
    print()
    print(f"{BOLD}SENTINEL - COVERAGE MAP (v0){RESET}")
    print("─" * 60)

    validators = discover_validators(ROOT)
    specs = discover_specs(TESTS_DIR)
    html_surfaces = collect_html_surfaces(ROOT)
    print(f"  Discovered {len(validators)} validators, {len(specs)} specs, "
          f"{len(set(html_surfaces.values()))} HTML surfaces")
    print()

    coverage = []
    covered_validators = 0
    per_page_count = 0
    platform_wide_count = 0
    infra_count = 0
    per_page_covered = 0
    total_per_page_checks = 0
    covered_per_page_checks = 0
    total_per_page_behavioral_checks = 0
    covered_per_page_behavioral_checks = 0

    content_sync_count = 0
    for v in validators:
        matches = match_validator_to_specs(v, specs)
        is_infra, matched_html = classify_validator_strict(
            v["tokens"],
            v.get("active_html_refs", []),
            v.get("html_refs", []),
            html_surfaces,
            v.get("_src", ""),
        )
        is_content_sync = is_content_sync_validator(v.get("_src", ""))
        if is_content_sync:
            is_infra = True
            matched_html = None
            content_sync_count += 1
        scope = v.get("scope", "per-page")
        if is_infra:
            category = "infrastructure"
            infra_count += 1
        elif scope == "platform-wide":
            category = "platform-wide"
            platform_wide_count += 1
        else:
            category = "per-page"
            per_page_count += 1
        if matches:
            covered_validators += 1
            if category == "per-page":
                per_page_covered += 1

        check_cov = compute_check_level_coverage(v, specs)
        all_checks = check_cov["covered_checks"] + check_cov["uncovered_checks"]
        check_kinds = {c: classify_check(c, v["file"]) for c in all_checks
                       if not c.startswith("(structural")}
        behavioral_covered = [c for c in check_cov["covered_checks"]
                              if check_kinds.get(c) == "behavioral"]
        behavioral_uncovered = [c for c in check_cov["uncovered_checks"]
                                if check_kinds.get(c) == "behavioral"]
        structural_covered = [c for c in check_cov["covered_checks"]
                              if check_kinds.get(c) == "structural"]
        structural_uncovered = [c for c in check_cov["uncovered_checks"]
                                if check_kinds.get(c) == "structural"]

        if category == "per-page":
            n_checks = len(all_checks)
            total_per_page_checks += n_checks
            covered_per_page_checks += len(check_cov["covered_checks"])
            total_per_page_behavioral_checks += len(behavioral_covered) + len(behavioral_uncovered)
            covered_per_page_behavioral_checks += len(behavioral_covered)

        has_check_names = bool(v.get("checks"))
        coverage.append({
            "file": v["file"],
            "label": v["label"],
            "tokens": v["tokens"],
            "checks": v["checks"],
            "html_refs": v.get("html_refs", []),
            "active_html_refs": v.get("active_html_refs", []),
            "scope": v.get("scope", "per-page"),
            "matched_specs": matches,
            "category": category,
            "subtype": "content-sync" if is_content_sync else None,
            "actionable": has_check_names,
            "is_infrastructure": is_infra,
            "matched_html": matched_html,
            "status": "COVERED" if matches else "GAP",
            "covered_checks": check_cov["covered_checks"],
            "uncovered_checks": check_cov["uncovered_checks"],
            "check_kinds": check_kinds,
            "behavioral_covered": behavioral_covered,
            "behavioral_uncovered": behavioral_uncovered,
            "structural_covered": structural_covered,
            "structural_uncovered": structural_uncovered,
            "check_coverage_by_spec": check_cov["by_spec"],
        })

    gaps = [c for c in coverage if c["status"] == "GAP"]
    per_page_gaps_all = [c for c in gaps if c["category"] == "per-page"]
    per_page_gaps = [c for c in per_page_gaps_all if c.get("actionable")]
    needs_refactor_gaps = [c for c in per_page_gaps_all if not c.get("actionable")]
    platform_wide_gaps = [c for c in gaps if c["category"] == "platform-wide"]
    infra_gaps = [c for c in gaps if c["category"] == "infrastructure"]
    raw_pct = round(100 * covered_validators / len(validators), 1) if validators else 0.0
    eff_pct = round(100 * per_page_covered / per_page_count, 1) if per_page_count else 0.0
    check_pct = round(
        100 * covered_per_page_checks / total_per_page_checks, 1
    ) if total_per_page_checks else 0.0
    behavioral_pct = round(
        100 * covered_per_page_behavioral_checks / total_per_page_behavioral_checks, 1
    ) if total_per_page_behavioral_checks else 0.0

    def color_for(pct):
        if pct >= 80:
            return GREEN
        if pct >= 60:
            return YELLOW
        return RED

    print(f"  {BOLD}Raw coverage:{RESET}       {covered_validators} / {len(validators)} = "
          f"{color_for(raw_pct)}{raw_pct}%{RESET}  (all validators, validator-level)")
    print(f"  {BOLD}Effective coverage:{RESET} {per_page_covered} / {per_page_count} = "
          f"{color_for(eff_pct)}{eff_pct}%{RESET}  (per-page validators, validator-level)")
    print(f"  {BOLD}Check coverage:{RESET}    {covered_per_page_checks} / {total_per_page_checks} = "
          f"{color_for(check_pct)}{check_pct}%{RESET}  (per-page checks, all kinds)")
    print(f"  {BOLD}Behavioral coverage:{RESET} {covered_per_page_behavioral_checks} / {total_per_page_behavioral_checks} = "
          f"{color_for(behavioral_pct)}{behavioral_pct}%{RESET}  (BEHAVIORAL checks only - the 100% target)")
    print(f"  {BOLD}Per-page gaps:{RESET}      {len(per_page_gaps)} validators "
          f"({total_per_page_behavioral_checks - covered_per_page_behavioral_checks} uncovered behavioral checks)")
    print(f"  {BOLD}Needs refactor:{RESET}     {len(needs_refactor_gaps)} validators "
          f"(no CHECK_NAMES list - sentinel matcher cannot bind tests)")
    print(f"  {BOLD}Content-sync (infra):{RESET} {content_sync_count} validators "
          f"(wh_pages-driven file scans, auto-tagged as infra)")
    print(f"  {BOLD}Platform-wide gaps:{RESET} {len(platform_wide_gaps)} (Layer 0 owns these)")
    print(f"  {BOLD}Infra gaps:{RESET}         {len(infra_gaps)} (Layer 0 owns these)")
    print()

    if per_page_gaps:
        print(f"  {BOLD}Per-page behavioral gaps (the actionable list):{RESET}")
        for g in per_page_gaps[:30]:
            label_short = g["label"][:40] + ("..." if len(g["label"]) > 40 else "")
            html = g.get("matched_html") or "?"
            print(f"    {RED}GAP{RESET}  {g['file']:<42}  ->  {html:<25}  {label_short}")
        if len(per_page_gaps) > 30:
            print(f"    ... and {len(per_page_gaps) - 30} more (see {REPORT_FILE.name})")
        print()

    if needs_refactor_gaps:
        print(f"  {BOLD}Needs refactor (no CHECK_NAMES - not actionable):{RESET}")
        for g in needs_refactor_gaps[:10]:
            label_short = g["label"][:40] + ("..." if len(g["label"]) > 40 else "")
            html = g.get("matched_html") or "?"
            print(f"    {YELLOW}REFACTOR{RESET}  {g['file']:<38}  ->  {html:<25}  {label_short}")
        if len(needs_refactor_gaps) > 10:
            print(f"    ... and {len(needs_refactor_gaps) - 10} more (see {REPORT_FILE.name})")
        print()

    report = {
        "timestamp": datetime.datetime.now().isoformat(),
        "sentinel": "sentinel_coverage_map",
        "version": "v0.5",
        "summary": {
            "total_validators": len(validators),
            "covered_validators": covered_validators,
            "validator_coverage_pct": raw_pct,
            "per_page_validators": per_page_count,
            "per_page_covered": per_page_covered,
            "effective_coverage_pct": eff_pct,
            "total_per_page_checks": total_per_page_checks,
            "covered_per_page_checks": covered_per_page_checks,
            "check_coverage_pct": check_pct,
            "total_per_page_behavioral_checks": total_per_page_behavioral_checks,
            "covered_per_page_behavioral_checks": covered_per_page_behavioral_checks,
            "behavioral_coverage_pct": behavioral_pct,
            "platform_wide_validators": platform_wide_count,
            "infrastructure_validators": infra_count,
            "content_sync_validators": content_sync_count,
            "total_specs": len(specs),
            "gap_count": len(gaps),
            "per_page_gap_count": len(per_page_gaps),
            "needs_refactor_gap_count": len(needs_refactor_gaps),
            "platform_wide_gap_count": len(platform_wide_gaps),
            "infra_gap_count": len(infra_gaps),
        },
        "coverage": coverage,
        "gaps": [
            {"file": g["file"], "label": g["label"], "checks": g["checks"],
             "tokens": g["tokens"], "category": g["category"],
             "subtype": g.get("subtype"),
             "actionable": g.get("actionable"),
             "is_infrastructure": g["is_infrastructure"],
             "matched_html": g.get("matched_html")}
            for g in gaps
        ],
        "needs_refactor": [
            {"file": g["file"], "label": g["label"], "tokens": g["tokens"],
             "matched_html": g.get("matched_html"),
             "reason": "no CHECK_NAMES list — sentinel matcher cannot bind tests"}
            for g in needs_refactor_gaps
        ],
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"  Report -> {REPORT_FILE.name}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())

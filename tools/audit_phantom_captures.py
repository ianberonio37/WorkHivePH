"""
Phantom Capture Auditor (Layer -1.5 reverse-lineage check).
============================================================

For every HTML capture field on the platform (input / select / textarea /
button data-*), scans the rest of the codebase for any downstream consumer.
A capture with ZERO consumers is a "phantom" — dead data weight, ready for
deletion or explicit justification.

Why this exists:
  Today's validators only catch FORWARD drift (tile reads raw table).
  Nothing catches the reverse case: forms collect data nobody reads. The
  platform has accumulated 2+ years of speculative fields, vestigial
  columns, and removed-feature stragglers. This auditor turns that decay
  into a continuous gate so new dead fields can't accrete silently.

Definition of "downstream consumer" for a capture name X:
  - any `.select(...)` clause that mentions `X` (data load)
  - any `.eq('X', ...)` / `.gte('X', ...)` filter (query predicate)
  - any RPC argument or column reference of `X`
  - any AI prompt template injecting `X`
  - any sensor/ingestion path keyed on `X`

If a capture field needs to exist despite having no in-platform consumer
(external CMMS push, regulatory archival, future-planned feature), add an
inline `phantom-allow: <reason>` HTML comment near the capture site; the
auditor skips those.

Output:
  - phantom_captures_report.json
  - phantom_captures_report.md  (deletion-candidates punch list)

Exit code:
  0 = no phantoms beyond the allowlist
  1 = at least one unjustified phantom

Designed to slot into Mega Gate L0 + the platform Hardening Loop.
"""
from __future__ import annotations

import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Capture-site detectors. Look for HTML form fields with a name attr.
# ---------------------------------------------------------------------------

CAPTURE_RE = re.compile(
    r"""<(?:input|select|textarea)\b[^>]*\bname=["']([a-zA-Z_][\w\-]*)["']""",
    re.IGNORECASE,
)
# data-capture="X" attributes also count as capture markers
CAPTURE_DATA_RE = re.compile(r"""data-capture=["']([a-zA-Z_][\w\-]*)["']""", re.IGNORECASE)
# id-as-capture: forms in this codebase often use id="logbook-status" for
# the canonical capture key when no name attribute is set
CAPTURE_ID_RE = re.compile(
    r"""<(?:input|select|textarea)\b[^>]*\bid=["']([a-zA-Z_][\w\-]*)["'][^>]*>""",
    re.IGNORECASE,
)

# `phantom-allow: <reason>` either inline near the capture or anywhere on
# the page suppresses phantom flagging for that capture key.
PHANTOM_ALLOW_RE = re.compile(
    r"""phantom-allow\s*:\s*([a-zA-Z_][\w\-]*)?\s*([^>\n]+)?""",
    re.IGNORECASE,
)

# Field names we always treat as "framework / form scaffolding" and
# never flag as phantom. Plain UI plumbing that's part of every form.
NEVER_PHANTOM = {
    "submit", "cancel", "close", "search", "query", "q", "filter",
    "csrf", "_csrf", "token", "g-recaptcha-response",
    "username", "password", "email", "remember",
    "name", "title", "description", "notes",  # too generic to safely flag
    "file", "image", "photo",
    "from", "to", "start", "end", "date",
    "tab", "view", "sort", "order",
    "all", "select-all",
    "next", "prev", "page", "limit", "offset",
}

# Stop-words inside the capture-name itself — purely cosmetic suffixes
# we should ignore in the no-consumer check (they decorate, not identify).
CAPTURE_NAME_NORMALIZERS = [
    (re.compile(r"-\d+$"), ""),  # trailing index e.g. "asset-12"
]

# Source files scanned for downstream consumers.
HTML_GLOB = "*.html"
JS_GLOB = "*.js"
SUPABASE_DIR = ROOT / "supabase"

# Pages excluded — backups + test fixtures.
EXCLUDED_HTML = [re.compile(r"\.backup\d*\.html$"), re.compile(r"-test\.html$")]


# ---------------------------------------------------------------------------
# Phase 1: discover every capture site.
# ---------------------------------------------------------------------------

def _strip_html_comments(text: str) -> str:
    return re.sub(r"<!--[\s\S]*?-->", "", text)


def _collect_captures() -> tuple[dict[str, list[dict]], set[str]]:
    """Return (captures_by_name, allowlisted_names)."""
    captures: dict[str, list[dict]] = defaultdict(list)
    allowlisted: set[str] = set()

    for p in sorted(ROOT.glob(HTML_GLOB)):
        if any(rx.search(p.name) for rx in EXCLUDED_HTML):
            continue
        raw = p.read_text(encoding="utf-8", errors="replace")

        # Phantom-allow comments (inside <!-- ... -->) are extracted BEFORE
        # stripping. Each match contributes its first token (the key) to
        # the allowlist set.
        for m in PHANTOM_ALLOW_RE.finditer(raw):
            tok = (m.group(1) or "").strip()
            if tok:
                allowlisted.add(tok)

        stripped = _strip_html_comments(raw)

        for m in CAPTURE_RE.finditer(stripped):
            captures[m.group(1)].append({"file": p.name, "kind": "name"})
        for m in CAPTURE_DATA_RE.finditer(stripped):
            captures[m.group(1)].append({"file": p.name, "kind": "data-capture"})
        # ID-as-capture only fires if there's NO name attribute (avoid
        # double-counting). Crude check by looking for name= in the same tag.
        for m in CAPTURE_ID_RE.finditer(stripped):
            tag_text = m.group(0)
            if 'name=' in tag_text.lower():
                continue
            captures[m.group(1)].append({"file": p.name, "kind": "id"})

    return captures, allowlisted


# ---------------------------------------------------------------------------
# Phase 2: build a consumer index.
# ---------------------------------------------------------------------------

def _normalize(name: str) -> str:
    base = name
    for rx, repl in CAPTURE_NAME_NORMALIZERS:
        base = rx.sub(repl, base)
    return base


def _strip_sql_comments(text: str) -> str:
    out = re.sub(r"/\*[\s\S]*?\*/", "", text)
    out = re.sub(r"--[^\n]*", "", out)
    return out


def _strip_js_comments(text: str) -> str:
    out = re.sub(r"/\*[\s\S]*?\*/", "", text)
    out = re.sub(r"^[ \t]*//[^\n]*$", "", out, flags=re.MULTILINE)
    return out


def _strip_py_comments(text: str) -> str:
    return re.sub(r"^[ \t]*#[^\n]*$", "", text, flags=re.MULTILINE)


def _gather_consumer_text() -> tuple[str, dict[str, str]]:
    """Concatenate everything that could consume a capture: HTML pages,
    JS modules, edge fn TS files, migrations, Python tool sources. Each
    blob has its language-specific comments stripped first — commented
    references aren't real consumers.

    Returns (big_blob, per_file_blobs).
    """
    blobs: dict[str, str] = {}

    for p in sorted(ROOT.glob(HTML_GLOB)):
        if any(rx.search(p.name) for rx in EXCLUDED_HTML):
            continue
        blobs[p.name] = _strip_html_comments(p.read_text(encoding="utf-8", errors="replace"))

    # Subdirectory HTML (feedback/, learn/, etc.) — consumer surfaces outside root.
    for subdir in sorted(ROOT.iterdir()):
        if not subdir.is_dir() or subdir.name.startswith(".") or subdir.name in {
            "node_modules", "test-results", "playwright-report", ".tmp",
            "supabase", "tools", "python-api", "tests",
        }:
            continue
        for p in sorted(subdir.rglob("*.html")):
            if any(rx.search(p.name) for rx in EXCLUDED_HTML):
                continue
            rel = p.relative_to(ROOT).as_posix()
            blobs[rel] = _strip_html_comments(p.read_text(encoding="utf-8", errors="replace"))

    for p in sorted(ROOT.glob(JS_GLOB)):
        if p.name == "sw.js":
            continue
        blobs[p.name] = _strip_js_comments(p.read_text(encoding="utf-8", errors="replace"))

    if SUPABASE_DIR.exists():
        for fn_dir in sorted((SUPABASE_DIR / "functions").glob("*")):
            if not fn_dir.is_dir():
                continue
            idx = fn_dir / "index.ts"
            if idx.exists():
                blobs[f"edge:{fn_dir.name}"] = _strip_js_comments(idx.read_text(encoding="utf-8", errors="replace"))
        # Shared TS modules (memory.ts, rate-limit.ts, embedding-chain.ts ...) — imported
        # by edge fns and frequently the actual consumer of a capture.
        shared_dir = SUPABASE_DIR / "functions" / "_shared"
        if shared_dir.exists():
            for p in sorted(shared_dir.rglob("*.ts")):
                rel = p.relative_to(ROOT).as_posix()
                blobs[f"shared:{rel}"] = _strip_js_comments(
                    p.read_text(encoding="utf-8", errors="replace")
                )
        for m in sorted((SUPABASE_DIR / "migrations").glob("*.sql")):
            blobs[f"migration:{m.name}"] = _strip_sql_comments(m.read_text(encoding="utf-8", errors="replace"))

    for p in sorted(ROOT.glob("tools/*.py")):
        if p.name.startswith("audit_") or p.name == "mine_skill_rules.py":
            continue
        blobs[f"tools:{p.name}"] = _strip_py_comments(p.read_text(encoding="utf-8", errors="replace"))
    for p in sorted(ROOT.glob("python-api/**/*.py")):
        blobs[f"python-api:{p.relative_to(ROOT).as_posix()}"] = _strip_py_comments(
            p.read_text(encoding="utf-8", errors="replace")
        )

    big_blob = "\n".join(blobs.values())
    return big_blob, blobs


# ---------------------------------------------------------------------------
# Phase 3: classify each capture as alive, phantom, or allowlisted.
# ---------------------------------------------------------------------------

def _count_consumers(name: str, blobs: dict[str, str], origin_files: set[str]) -> tuple[int, list[str]]:
    """Count downstream-consumer SITES for the capture key.

    The key insight: a form field is usually consumed by JS in the SAME file
    that declares it (`getElementById('X').value`, `formData.get('X')`, etc).
    We therefore include origin files but EXCLUDE the literal capture-markup
    site from the count.

    For each file, total mentions of `X` are counted (word-boundary). We
    subtract the number of capture-markup occurrences in that file (input/
    select/textarea/label/button name= or id=). What remains is consumer
    references (JS reads, DB queries, AI prompt templates).

    A capture is alive if AT LEAST ONE consumer reference exists anywhere.
    """
    word_pat = re.compile(r"""(?<![A-Za-z0-9_-])""" + re.escape(name) + r"""(?![A-Za-z0-9_])""")
    # Patterns that ARE the capture markup itself — these don't count as
    # consumers, only as the declaration site.
    markup_pats = [
        re.compile(r"""<(?:input|select|textarea|button)\b[^>]*\b(?:name|id)=["']""" + re.escape(name) + r"""["']""", re.IGNORECASE),
        re.compile(r"""<label\b[^>]*\bfor=["']""" + re.escape(name) + r"""["']""", re.IGNORECASE),
        re.compile(r"""data-capture=["']""" + re.escape(name) + r"""["']""", re.IGNORECASE),
    ]

    consumer_files: list[str] = []
    total_mentions = 0
    total_markup = 0
    for fname, blob in blobs.items():
        mentions = len(word_pat.findall(blob))
        if mentions == 0:
            continue
        markup_here = sum(len(p.findall(blob)) for p in markup_pats)
        consumer_mentions = mentions - markup_here
        if consumer_mentions > 0:
            consumer_files.append(fname)
        total_mentions += mentions
        total_markup += markup_here

    n_consumers = total_mentions - total_markup
    return max(n_consumers, 0), consumer_files[:8]


def main() -> int:
    captures, allowlisted = _collect_captures()
    _, blobs = _gather_consumer_text()

    by_name: dict[str, dict] = {}
    phantom_count = 0
    alive_count = 0
    allowlisted_count = 0
    skipped_framework = 0

    for name, sites in sorted(captures.items()):
        norm = _normalize(name)
        if norm.lower() in NEVER_PHANTOM:
            skipped_framework += 1
            continue
        origin_files = {s["file"] for s in sites}
        n_consumers, consumer_files = _count_consumers(name, blobs, origin_files)
        # Strip origin from displayed consumer list when it carries no
        # *additional* consumer beyond its own markup (cleaner report).
        consumer_files = [f for f in consumer_files if f not in origin_files] or consumer_files

        status = "alive"
        if n_consumers == 0:
            status = "phantom"
        if name in allowlisted:
            status = "allowlisted"

        by_name[name] = {
            "name":            name,
            "status":          status,
            "capture_sites":   sites,
            "consumer_count":  n_consumers,
            "consumer_files":  consumer_files[:8],  # truncate for report sanity
        }
        if status == "phantom":
            phantom_count += 1
        elif status == "alive":
            alive_count += 1
        elif status == "allowlisted":
            allowlisted_count += 1

    report = {
        "summary": {
            "total_captures_discovered": len(captures),
            "framework_skipped":         skipped_framework,
            "alive":                     alive_count,
            "phantom":                   phantom_count,
            "allowlisted":               allowlisted_count,
        },
        "by_name": by_name,
    }

    (ROOT / "phantom_captures_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    # ── Markdown ──────────────────────────────────────────────────────
    md = []
    md.append("# Phantom Capture Audit (Layer -1.5 reverse-lineage)\n")
    md.append("Every HTML form field that no engine, brain, or dashboard reads.")
    md.append("Run by `tools/audit_phantom_captures.py`. Output is a deletion")
    md.append("candidates punch list. To keep a field, add `phantom-allow: <key> <reason>`")
    md.append("as an HTML comment on the capture page.\n")

    s = report["summary"]
    md.append("## Summary\n")
    md.append(f"- Capture fields discovered:  **{s['total_captures_discovered']}**")
    md.append(f"- Framework names skipped:    **{s['framework_skipped']}** (submit, search, csrf, ...)")
    md.append(f"- Alive (≥1 consumer):        **{s['alive']}** ✅")
    md.append(f"- Phantom (0 consumers):      **{s['phantom']}** ❌")
    md.append(f"- Allowlisted (justified):    **{s['allowlisted']}**")
    md.append("")

    phantoms = [v for v in by_name.values() if v["status"] == "phantom"]
    phantoms.sort(key=lambda v: v["name"])

    # Low-usage candidates: alive but consumer_count == 1 means the field
    # is read in exactly one place. Worth a human eyeball — could be a
    # legitimate single-purpose field, could be a vestigial half-wired one.
    low_usage = sorted(
        [v for v in by_name.values() if v["status"] == "alive" and v["consumer_count"] == 1],
        key=lambda v: v["name"],
    )

    md.append(f"## Deletion candidates ({len(phantoms)})\n")
    if not phantoms:
        md.append("_None — every capture has at least one downstream consumer. Schema discipline is currently good; the gate locks this in against future drift._\n")
    else:
        md.append("| Capture name | Captured on | Consumer count |")
        md.append("|---|---|---:|")
        for v in phantoms:
            sites_str = ", ".join(sorted({s["file"] for s in v["capture_sites"]}))
            md.append(f"| `{v['name']}` | {sites_str} | {v['consumer_count']} |")
    md.append("")

    md.append(f"## Low-usage candidates — `consumer_count == 1` ({len(low_usage)})\n")
    md.append("Fields read in exactly one place. Likely fine (single-purpose),")
    md.append("but worth a scan for vestigial half-wired fields.\n")
    if low_usage:
        md.append("| Capture name | Captured on |")
        md.append("|---|---|")
        for v in low_usage[:60]:
            sites_str = ", ".join(sorted({s["file"] for s in v["capture_sites"]}))
            md.append(f"| `{v['name']}` | {sites_str} |")
        if len(low_usage) > 60:
            md.append(f"| ... | ... ({len(low_usage) - 60} more) |")
        md.append("")

    allow = [v for v in by_name.values() if v["status"] == "allowlisted"]
    if allow:
        md.append(f"## Allowlisted phantoms ({len(allow)})\n")
        md.append("| Capture name | Captured on | Reason |")
        md.append("|---|---|---|")
        for v in allow:
            sites_str = ", ".join(sorted({s["file"] for s in v["capture_sites"]}))
            md.append(f"| `{v['name']}` | {sites_str} | (see page comment) |")
        md.append("")

    md.append("## What to do with a phantom\n")
    md.append("1. **Delete it** — if no business reason exists, remove the form field, the column,")
    md.append("   and any migration that adds it. This is the default and safe move.")
    md.append("2. **Justify it** — add an HTML comment on the capture page:")
    md.append("   `<!-- phantom-allow: <field-name> reason here -->`")
    md.append("   Use sparingly: each allowlist line is a maintenance promise.")
    md.append("3. **Wire a consumer** — if the field SHOULD power a dashboard tile or AI input,")
    md.append("   add the read site downstream. The auditor flips the field to alive on next run.")

    (ROOT / "phantom_captures_report.md").write_text("\n".join(md), encoding="utf-8")

    # ── stdout banner ─────────────────────────────────────────────────
    print("Phantom Capture Audit (Layer -1.5 reverse-lineage)")
    print(f"  total captures:    {s['total_captures_discovered']}")
    print(f"  framework skipped: {s['framework_skipped']}")
    print(f"  alive:             {s['alive']}")
    print(f"  phantom:           {s['phantom']}")
    print(f"  allowlisted:       {s['allowlisted']}")
    print()
    if phantoms:
        print("Top deletion candidates:")
        for v in phantoms[:12]:
            origins = ", ".join(sorted({s["file"] for s in v["capture_sites"]}))
            print(f"  {v['name']:<32} captured on: {origins[:60]}")

    return 1 if phantoms else 0


if __name__ == "__main__":
    sys.exit(main())

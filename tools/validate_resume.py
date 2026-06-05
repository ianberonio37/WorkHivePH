#!/usr/bin/env python3
"""
Validator: Resume / CV Builder wiring contract (L0).

Asserts the resume.html feature is wired the way the platform requires, so a
future edit that breaks a registration point is caught by the Mega Gate rather
than by a user. Static-only (no DB): scans the source files.

Checks:
  1. resume.html boilerplate: Supabase CDN, utils.js, <main> landmark,
     viewport-fit=cover, manifest, toast a11y, escHtml usage.
  2. resume.html calls both edge functions (resume-extract, resume-polish).
  3. Two-registry rule: nav-hub.js TOOLS + index.html stageData.
  4. config.toml registers both edge functions with verify_jwt = false.
  5. Migration present with OWNER-ONLY RLS (auth.uid() = auth_uid) for
     resume_documents AND resume_versions (personal doc, NOT hive-scoped).
  6. Edge functions exist and contain NO em dash (U+2014) in prompt strings
     (they garble as a 3-char sequence under Windows-1252 misdecode).
  7. Smoke spec exists and surface-coverage lists resume.html.
  8. Lever A (summary reduce-pass): resume-polish has the synthesize_summary
     mode; resume.html has buildResumeFacts + runSummarize + the btn-summary.
  9. Lever B (heavy-file map-reduce): resume-extract has splitResumeText +
     mergePartials and the 12K hard-truncation is GONE (MAX_TEXT_TOTAL/CHUNK_CHARS).
 10. Lever C (vendored taxonomy): _shared/resume-taxonomy.ts exists with its
     exports, resume-extract imports it, and the offline _JD_DICT in resume.html
     stays in sync with MAINTENANCE_SKILLS (a sentinel subset is in both).

Exit 0 if all PASS, 1 if any FAIL. Prints one line per check.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []
PASSES = 0


def read(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def check(name, ok, detail=""):
    global PASSES
    if ok:
        PASSES += 1
        print(f"  [PASS] {name}")
    else:
        FAILS.append(name)
        print(f"  [FAIL] {name}{(' - ' + detail) if detail else ''}")


def validate_resume():
    print("\n[Resume / CV Builder] wiring contract")

    html = read("resume.html")
    check("resume.html exists", html is not None)
    if html:
        m_sb = re.search(r'<script\s+src="[^"]*supabase-js[^"]*"', html)
        m_ut = re.search(r'<script\s+src="utils\.js"', html)
        check("loads Supabase JS CDN before utils.js",
              bool(m_sb) and bool(m_ut) and m_sb.start() < m_ut.start())
        check("has <main> landmark (surface-coverage requires it)", re.search(r"<main\b", html) is not None)
        check("declares viewport-fit=cover", "viewport-fit=cover" in html)
        check("links a manifest", re.search(r'rel=["\']manifest["\']', html) is not None)
        check("toast container has aria-live (a11y)", re.search(r'role="alert"\s+aria-live="polite"', html) is not None)
        check("uses escHtml() for dynamic content", "escHtml(" in html)
        check("calls resume-extract edge fn", "functions/v1/resume-extract" in html)
        check("calls resume-polish edge fn", "functions/v1/resume-polish" in html)
        check("editable-checklist review sheet present (internal control)", "review-sheet" in html and "openReview" in html)
        # Lever A (summary reduce-pass): the whole-resume facts builder + runner + button.
        check("summary reduce-pass: buildResumeFacts + runSummarize present",
              "buildResumeFacts" in html and "runSummarize" in html and "synthesize_summary" in html,
              "the opening summary must synthesize the WHOLE resume from computed facts, not transcribe the old doc")
        check("summary reduce-pass: btn-summary wired",
              'id="btn-summary"' in html and "getElementById('btn-summary')" in html)

    nav = read("nav-hub.js")
    check("registered in nav-hub.js TOOLS", bool(nav) and "href: 'resume.html'" in nav)

    index = read("index.html")
    check("registered in index.html stageData", bool(index) and "link: 'resume.html'" in index)

    cfg = read("supabase/config.toml")
    if cfg:
        ex = re.search(r"\[functions\.resume-extract\][^\[]*verify_jwt\s*=\s*false", cfg, re.S)
        po = re.search(r"\[functions\.resume-polish\][^\[]*verify_jwt\s*=\s*false", cfg, re.S)
        check("config.toml registers resume-extract (verify_jwt=false)", ex is not None)
        check("config.toml registers resume-polish (verify_jwt=false)", po is not None)
    else:
        check("supabase/config.toml exists", False)

    mig = read("supabase/migrations/20260603000000_resume_builder.sql")
    check("migration exists", mig is not None)
    if mig:
        for tbl in ("resume_documents", "resume_versions"):
            check(f"{tbl}: RLS enabled", bool(re.search(rf"ALTER TABLE public\.{tbl}\s+ENABLE ROW LEVEL SECURITY", mig)))
            check(f"{tbl}: owner-only RLS (auth.uid() = auth_uid)",
                  bool(re.search(r"auth\.uid\(\)\s*=\s*auth_uid", mig)))
        check("hive_id documented as context, not an access key",
              "context" in mig.lower() and "auth_uid" in mig)

    # Edge functions present + no em dash (U+2014) anywhere.
    for fn in ("resume-extract", "resume-polish"):
        src = read(f"supabase/functions/{fn}/index.ts")
        check(f"{fn} edge function exists", src is not None)
        if src:
            check(f"{fn}: no em dash (U+2014) in source", "—" not in src,
                  "em dashes garble as 3 chars under Windows-1252")
            if fn == "resume-extract":
                check("resume-extract: deterministic project-miner present (mineProjectsFromWork)",
                      "mineProjectsFromWork" in src and "PROJECT_VERB" in src,
                      "free-tier model under-extracts projects embedded in bullets; code miner is the recall safety net (measured 0/4 -> 4/4)")
                # Lever B: heavy-file map-reduce, and the silent 12K truncation must be GONE.
                check("resume-extract: heavy-file map-reduce present (splitResumeText + mergePartials)",
                      "splitResumeText" in src and "mergePartials" in src,
                      "a single 12K slice silently dropped trailing pages; chunk + merge keeps the tail")
                check("resume-extract: no silent 12K truncation (MAX_TEXT_CHARS removed)",
                      "MAX_TEXT_CHARS" not in src and "MAX_TEXT_TOTAL" in src and "CHUNK_CHARS" in src,
                      "the old hard slice must not come back")
                # Lever C: the vendored taxonomy is imported (canonicalization + verbs).
                check("resume-extract: imports vendored resume-taxonomy",
                      "resume-taxonomy.ts" in src and "canonicalizeSkill" in src)
            if fn == "resume-polish":
                check("resume-polish: synthesize_summary mode present (summary reduce-pass)",
                      "synthesize_summary" in src and "SUMMARIZE_SYSTEM" in src,
                      "the whole-resume summary is a server mode fed a deterministic fact sheet")

    # Lever C: the vendored taxonomy file + the offline JD-dict mirror stay in sync.
    tax = read("supabase/functions/_shared/resume-taxonomy.ts")
    check("resume-taxonomy.ts exists", tax is not None)
    if tax:
        for sym in ("MAINTENANCE_SKILLS", "PROJECT_ACTION_VERBS", "SECTION_HEADERS",
                    "SKILL_CANON", "canonicalizeSkill", "isSectionHeaderLine"):
            check(f"resume-taxonomy exports {sym}", sym in tax)
        check("resume-taxonomy: no em dash (U+2014)", "—" not in tax)
        if html:
            # Drift guard: a sentinel subset must appear in BOTH the taxonomy and the
            # client _JD_DICT mirror (no build step, so the mirror is hand-kept).
            sentinel = ["preventive maintenance", "vibration analysis", "root cause analysis",
                        "condition monitoring", "reliability-centered maintenance"]
            both = [t for t in sentinel if t in tax and t in html]
            check("offline _JD_DICT mirrors MAINTENANCE_SKILLS (sentinel subset in both)",
                  len(both) == len(sentinel),
                  f"missing from one side: {[t for t in sentinel if t not in both]}")

    spec = read("tests/resume.spec.ts")
    check("smoke spec tests/resume.spec.ts exists", spec is not None)

    sc = read("tests/surface-coverage.spec.ts")
    check("surface-coverage ALL_PAGES includes resume.html", bool(sc) and "'resume.html'" in sc)

    total = PASSES + len(FAILS)
    print(f"\n[Resume / CV Builder] {PASSES}/{total} checks passed.")
    if FAILS:
        print("  FAILED: " + ", ".join(FAILS))
        return False
    return True


if __name__ == "__main__":
    sys.exit(0 if validate_resume() else 1)

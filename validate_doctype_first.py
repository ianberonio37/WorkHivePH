#!/usr/bin/env python3
"""
validate_doctype_first — nothing may precede <!DOCTYPE html>.

WHY THIS GATE EXISTS (PJ18, 2026-07-28)
---------------------------------------
A four-line JS comment block of mine ended up at the TOP OF THE FILE in
project-manager.html, above the doctype, instead of beside the code it described:

    // PJ8: distinguish "computed, nothing critical" from "could not compute" ...
    // PJ9: explicit columns, NOT select('*') ...
    <!DOCTYPE html>

Two consequences, and the second is the one that matters:

  1. The comment RENDERED as visible text at the top of the page, above the
     "Project Manager" heading. Internal notes about revoked columns and 42501
     errors, on a user-facing page.

  2. Content before the doctype makes the browser DISCARD it. Measured live:
     document.compatMode === 'BackCompat' — the entire page was in QUIRKS MODE.
     Different box model, different percentage-height resolution, different
     inline baseline handling. Every layout rule on the page was being applied
     under 1990s semantics.

WHY NOTHING ELSE CAUGHT IT. `node --check` only parses <script> bodies. The
render-budget gates count bytes. The XSS gate reads JS. The HTML still *parsed*,
so no validator complained — a browser recovers from this silently, which is
exactly what makes it dangerous. It took a full-page screenshot at 390px to see
it, which is the Whole-Artifact Discipline working as intended, but a gate is
cheaper than a screenshot.

A leading UTF-8 BOM is tolerated (browsers strip it). HTML comments before the
doctype are tolerated (they are invisible and do not trigger quirks mode in any
current engine) but are reported as a warning, because they are almost always
a mistake too.
"""
import glob
import os
import re
import sys

BOM = "﻿"


def scan():
    files = sorted(set(glob.glob("*.html") + glob.glob("workhive/*.html")))
    fails, warns = [], []
    for path in files:
        try:
            text = open(path, encoding="utf-8").read()
        except Exception as exc:                      # unreadable is its own problem
            fails.append((path, "unreadable: %s" % exc, ""))
            continue

        idx = text.lower().find("<!doctype")
        if idx < 0:
            fails.append((path, "no <!DOCTYPE> anywhere", ""))
            continue

        pre = text[:idx]
        if pre.startswith(BOM):
            pre = pre[1:]
        pre = pre.strip()
        if not pre:
            continue

        # Comments are invisible; anything else is rendered content.
        rendered = re.sub(r"<!--.*?-->", "", pre, flags=re.S).strip()
        if rendered:
            fails.append((path, "%d chars of content before the doctype (quirks mode)"
                          % len(rendered), rendered[:90].replace("\n", " ")))
        else:
            warns.append((path, "HTML comment before the doctype", pre[:70].replace("\n", " ")))

    return files, fails, warns


def main():
    files, fails, warns = scan()

    for path, why, sample in warns:
        print("  WARN  %s — %s" % (path, why))
        if sample:
            print("          %s" % sample)

    if fails:
        print("\n  FAIL — %d page(s) do not begin at <!DOCTYPE html>:" % len(fails))
        for path, why, sample in fails:
            print("    %s" % path)
            print("      %s" % why)
            if sample:
                print("      starts: %s" % sample)
        print("\n  A browser DISCARDS a doctype that is not first and renders the page in")
        print("  quirks mode (document.compatMode === 'BackCompat'), changing the box model")
        print("  and percentage heights for every rule on the page. The stray text also")
        print("  renders. Move the content into the <head>/<body> or into a <script>.")
        return 1

    print("  PASS — all %d pages begin at <!DOCTYPE html> (standards mode)." % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())

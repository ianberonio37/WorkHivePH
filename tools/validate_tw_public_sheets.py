"""validate_tw_public_sheets.py - the public pages' compiled Tailwind sheets stay complete, last, and the only source.

2026-10-13. tools/tw_public_build.mjs moved the public pages (learn articles, the 60 calculators and their staging
copies, the learn hub, about / privacy / terms and the public roadmap) off the Tailwind Play CDN onto four compiled
sheets, /wh-tw-pub-<family>.css, one per tailwind.config family. The CDN was a ~400 KB script that blocked render and
built the CSS on the reader's phone; a compiled sheet is 7-9 KB. But a compiled sheet only holds the classes that were
on the pages when it was built, so it can rot, silently - a missing CSS rule raises no error anywhere. This gate fails:

  1. a production page that loads the Play CDN again (a new page from an old template, a paste from an old article);
  2. a class a page can carry that its sheet never compiled, unless the build recorded it as the page's own
     (non-Tailwind) class. Read from class attributes (also inside template literals), className assignments and
     classList.add/remove/toggle/replace arguments, in the page and in the local scripts it loads - the same reading
     the build uses. The fix is always the same: node tools/tw_public_build.mjs build --family <family>;
  3. anything AFTER the sheet's link in <head>. The CDN appended its <style> at the end of <head>, so Tailwind won its
     ties with the page's own rules; a block placed below the link would start winning them instead;
  4. a leftover `tailwind.config = ...` script (a ReferenceError once the CDN is gone), a link to a sheet that is not
     built, a family missing from tools/tw_pub_families.json, or a sheet built from a different config than the
     manifest now records (rebuild it).

  python tools/validate_tw_public_sheets.py              the gate
  python tools/validate_tw_public_sheets.py --self-test  each failure mode on a synthetic page, plus a clean control
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "tools" / "tw_pub_families.json"
SKIP_DIRS = {"node_modules", "_fixtures", "test-data-seeder", "video_marketing_app", "promo_posters", "test-runs"}

CDN_SCRIPT = re.compile(r"""<script[^>]*\bsrc\s*=\s*["']https?://cdn\.tailwindcss\.com""", re.I)
LINK = re.compile(r'^<link rel="stylesheet" href="/wh-tw-pub-([\w-]+)\.css">', re.M)
ANY_PUB_LINK = re.compile(r"/wh-tw-pub-([\w-]+)\.css")
CONFIG = re.compile(r"\btailwind\.config\s*=")
# The same reading tools/tw_public_build.mjs uses (classUse) - keep the two in step.
P_ATTR = re.compile(r"""\bclass\s*=\s*(?:"([^"]*)"|'([^']*)')""")
P_CLASSNAME = re.compile(r"""\bclassName\s*\+?=\s*(?:"([^"]*)"|'([^']*)'|`([^`]*)`)""")
P_CLASSLIST = re.compile(r"""classList\.(?:add|remove|toggle|replace)\s*\(([^)]*)\)""")
P_STR = re.compile(r"""["'`]([^"'`]*)["'`]""")
TOKEN = re.compile(r"^[!-]?[A-Za-z0-9@\[*][A-Za-z0-9_\-:/.\[\]%#&>*(),]*$")
INTERP = re.compile(r"\$\{[^}]*\}?")
SCRIPT_SRC = re.compile(r"""<script\b[^>]*\bsrc\s*=\s*["']([^"']+)["']""", re.I)


def class_use(text: str) -> set[str]:
    vals = []
    for m in P_ATTR.finditer(text):
        vals.append(m.group(1) if m.group(1) is not None else m.group(2))
    for m in P_CLASSNAME.finditer(text):
        vals.append(next(g for g in m.groups() if g is not None))
    for m in P_CLASSLIST.finditer(text):
        vals.extend(s.group(1) for s in P_STR.finditer(m.group(1)))
    out = set()
    for v in vals:
        for t in INTERP.sub(" ", v).split():
            if TOKEN.match(t):
                out.add(t)
    return out


def css_class_names(css: str) -> set[str]:
    css = re.sub(r"/\*[\s\S]*?\*/", "", css)
    css = re.sub(r"\{[^{}]*\}", "{}", css)
    out = set()
    for m in re.finditer(r"\.((?:\\[0-9a-fA-F]{1,6} ?|\\[^\n0-9a-fA-F]|[A-Za-z0-9_-]|[^\x00-\x7F])+)", css):
        s = re.sub(r"\\([0-9a-fA-F]{1,6}) ?", lambda h: chr(int(h.group(1), 16)), m.group(1))
        out.add(re.sub(r"\\(.)", r"\1", s))
    return out


def html_pages():
    for p in sorted(ROOT.rglob("*.html")):
        rel = p.relative_to(ROOT)
        if any(part.startswith(".") or part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        yield p


_sheet_cache: dict[str, tuple[set[str], dict | None]] = {}
_script_cache: dict[str, set[str]] = {}


def sheet_info(name: str):
    if name not in _sheet_cache:
        f = ROOT / f"wh-tw-pub-{name}.css"
        if not f.exists():
            _sheet_cache[name] = (set(), None)
        else:
            css = f.read_text(encoding="utf-8")
            m = re.search(r"\n   config: (\{.*\}) \*/\n", css[:4000])
            cfg = json.loads(m.group(1)) if m else None
            _sheet_cache[name] = (css_class_names(css), cfg)
    return _sheet_cache[name]


def local_script_classes(page: Path, html: str) -> set[str]:
    out = set()
    for src in SCRIPT_SRC.findall(html):
        if re.match(r"^(https?:)?//", src, re.I):
            continue
        path = (ROOT / src.lstrip("/")) if src.startswith("/") else (page.parent / src)
        key = str(path.resolve()).split("?")[0]
        if key not in _script_cache:
            try:
                _script_cache[key] = class_use(Path(key).read_text(encoding="utf-8"))
            except OSError:
                _script_cache[key] = set()
        out |= _script_cache[key]
    return out


def check_page(page: Path, html: str, manifest: dict) -> list[str]:
    probs = []
    if CDN_SCRIPT.search(html):
        probs.append("loads the Tailwind Play CDN - move it to its family's compiled sheet "
                     "(node tools/tw_public_build.mjs plan / build / verify / apply)")
    names = ANY_PUB_LINK.findall(html)
    if not names:
        return probs
    if len(names) > 1:
        probs.append(f"links {len(names)} compiled Tailwind sheets")
    m = LINK.search(html)
    if not m:
        return probs + ["the sheet's <link> is not the standard line `<link rel=\"stylesheet\" href=\"/wh-tw-pub-<family>.css\">` at column 0"]
    name = m.group(1)
    fam = manifest.get("families", {}).get(name)
    if fam is None:
        probs.append(f"family '{name}' is not in tools/tw_pub_families.json")
    classes, cfg = sheet_info(name)
    if cfg is None and not (ROOT / f"wh-tw-pub-{name}.css").exists():
        return probs + [f"/wh-tw-pub-{name}.css is not built"]
    if fam is not None and cfg is not None and cfg != fam.get("config"):
        probs.append(f"wh-tw-pub-{name}.css was built from a different config than the manifest records - rebuild it")
    if CONFIG.search(html):
        probs.append("still carries a tailwind.config script (a ReferenceError without the CDN)")
    end = html.find("</head>")
    if end == -1 or m.start() > end:
        probs.append("the sheet's link is not inside <head>")
    else:
        rest = html[m.end():end]
        rest = rest.split("\n", 1)[1] if "\n" in rest else ""
        if rest.strip():
            probs.append("something follows the sheet's link in <head> (it must stay last, where the CDN's style landed): "
                         + re.sub(r"\s+", " ", rest.strip())[:90])
    own = set(fam.get("non_utility_classes", [])) if fam else set()
    used = class_use(html) | local_script_classes(page, html)
    missing = sorted(t for t in used if t not in classes and t not in own)
    if missing:
        probs.append(f"{len(missing)} class(es) not compiled into wh-tw-pub-{name}.css: {' '.join(missing[:12])}"
                     f"{' ...' if len(missing) > 12 else ''} -> node tools/tw_public_build.mjs build --family {name}")
    return probs


def main() -> int:
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"FAIL tw-public-sheets: cannot read {MANIFEST.relative_to(ROOT)}: {e}")
        return 1
    fails, per_family, cdn_pages = [], {}, 0
    for page in html_pages():
        html = page.read_text(encoding="utf-8", errors="replace")
        if "tailwindcss" not in html and "wh-tw-pub-" not in html:
            continue
        probs = check_page(page, html, manifest)
        lm = LINK.search(html)
        if lm:
            per_family[lm.group(1)] = per_family.get(lm.group(1), 0) + 1
        cdn_pages += bool(CDN_SCRIPT.search(html))
        rel = page.relative_to(ROOT).as_posix()
        fails += [f"{rel}: {p}" for p in probs]
    summary = ", ".join(f"{k} {v}" for k, v in sorted(per_family.items())) or "none"
    if fails:
        print(f"FAIL tw-public-sheets - {len(fails)} problem(s); pages on compiled sheets: {summary}; on the Play CDN: {cdn_pages}")
        for f in fails[:40]:
            print("  " + f)
        return 1
    print(f"PASS tw-public-sheets - pages on compiled sheets: {summary}; on the Play CDN: 0; "
          "every class compiled or recorded as the page's own, every link last in <head>")
    return 0


def self_test() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    name = sorted(manifest["families"])[0]
    good = next(iter(sorted(sheet_info(name)[0] - {""})))
    link = f'<link rel="stylesheet" href="/wh-tw-pub-{name}.css"><!-- x -->'
    page = ROOT / "learn" / "x" / "index.html"
    cases = {
        "clean control": (f'<html><head>\n<style>p{{}}</style>\n{link}\n</head><body class="{good}"></body></html>', 0),
        "Play CDN": ('<html><head>\n<script src="https://cdn.tailwindcss.com"></script>\n</head><body></body></html>', 1),
        "uncompiled class": (f'<html><head>\n{link}\n</head><body class="{good} text-[13.37px]"></body></html>', 1),
        "uncompiled class via classList": (f'<html><head>\n{link}\n</head><body><script>el.classList.add("mt-[7.77px]")</script></body></html>', 1),
        "style after the link": (f'<html><head>\n{link}\n<style>p{{}}</style>\n</head><body></body></html>', 1),
        "leftover config": (f'<html><head>\n<script>tailwind.config = {{}};</script>\n{link}\n</head><body></body></html>', 1),
        "sheet not built": ('<html><head>\n<link rel="stylesheet" href="/wh-tw-pub-nosuchfamily.css">\n</head><body></body></html>', 1),
    }
    bad = 0
    for label, (html, want_fail) in cases.items():
        probs = check_page(page, html, manifest)
        ok = bool(probs) == bool(want_fail)
        bad += not ok
        print(f"  {'ok ' if ok else 'BAD'} {label}: {'; '.join(probs)[:110] if probs else 'passes'}")
    print(f"self-test: {len(cases) - bad}/{len(cases)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else main())

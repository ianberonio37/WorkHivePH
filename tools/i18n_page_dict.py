#!/usr/bin/env python3
"""i18n_page_dict.py — a per-page Filipino dictionary for the text a person actually reads (EX-TL, 2026-09-07).

WHY. The live Tagalog-first walk (prove_tagalog_first.mjs L1) switches a signed-in page to wh_lang=fil and
counts the visible text that changed. After every failure sentence and control label was made bilingual,
achievements.html still moved 8 of 110 visible strings (7%) - because a healthy page shows neither its
failure copy nor most of its buttons. What it shows is headings, labels, paragraphs, table heads, options.
The platform's mechanism for those is `data-i="<key>"` on the element plus a dictionary whI18nApply reads
(WH_FIL_COMMON shared, WH_FIL_PAGE per page). This tool builds the per-page half:

  --extract   walk the page's static markup (never <script>/<style>), collect every element whose content
              is plain text (no child tag, no ${} slot, no ' + ' splice), and write i18n/<page>.json as
              {"English text": "Filipino or empty"}; existing translations are kept, new strings arrive empty
  --apply     for every extracted string that HAS a translation: tag the element with data-i="<key>" (a
              key derived from the text, unique per page) and emit/replace ONE
              dictionary to i18n/pages/<stem>.fil.json (fetched by utils.js under FIL; no inline block), so
              the dictionary exists before whI18nApply's DOMContentLoaded pass. Idempotent. Its own global,
              because pages that declare window.WH_FIL_PAGE themselves reassign that name AFTER this block
              (achievements kept 6 keys of 39 until the applier learned to merge both).

The Filipino in i18n/*.json is AUTHORED (natural Taglish - engineering nouns stay English, the way a
Philippine plant says them), never machine-derived: this tool only moves what a person wrote into place.

  python tools/i18n_page_dict.py --extract achievements.html   # or --all for the EX-TL roster
  python tools/i18n_page_dict.py --apply achievements.html     # or --all
  python tools/i18n_page_dict.py --status                      # per page: strings, translated, applied
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DICT_DIR = ROOT / "i18n"
PAGES_DIR = DICT_DIR / "pages"   # the emitted per-page dictionaries the browser fetches under FIL
TAGS = "h1|h2|h3|h4|h5|h6|p|label|th|td|li|a|span|button|summary|legend|option|small|strong|em|b|dt|dd|figcaption|div|caption"
# an element whose whole content is text: an opening tag (attrs may not contain > inside a quoted value we
# cannot see, so attrs are kept simple), the text, the matching closing tag
ELEMENT = re.compile(rf"<({TAGS})\b((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>([^<>{{}}]{{3,220}})</\1>", re.I)
SCRIPT_OR_STYLE = re.compile(r"<(script|style)\b[^>]*>[\s\S]*?</\1>", re.I)
NOSCRIPT_TEMPLATE = re.compile(r"<(template|noscript|svg|pre|code|kbd)\b[^>]*>[\s\S]*?</\1>", re.I)


def roster() -> list[str]:
    reg = json.loads((ROOT / "trajectory_registry.json").read_text(encoding="utf-8"))
    return sorted({p for t in reg["trajectories"] if t.get("wave") == "EX-TL" for p in t.get("pages", [])})


def translatable(text: str) -> bool:
    t = html.unescape(text).strip()
    if len(t) < 3:
        return False
    if "${" in t or " + " in t or "' +" in t or '" +' in t or t.startswith("{{"):
        return False
    letters = sum(ch.isalpha() for ch in t)
    if letters < 3 or letters < len(t) * 0.4:          # numbers, units, glyph-only, "OK"
        return False
    if re.fullmatch(r"[A-Z0-9_\-./: ]+", t) and len(t) <= 12:   # an acronym or a code (MTBF, OEE, P-F)
        return False
    if re.fullmatch(r"[a-z0-9_./:-]+", t):                       # an identifier (wh_last_worker, closed_at, simple_recency)
        return False
    if re.search(r"https?://|@|\.html\b|\.js\b", t):
        return False
    return True


def key_of(text: str) -> str:
    base = re.sub(r"[^a-z]", "", html.unescape(text).lower())[:28]
    return f"p_{base}_{hashlib.sha1(html.unescape(text).strip().encode('utf-8')).hexdigest()[:4]}"


def masked(src: str) -> str:
    """Scripts, styles, templates blanked to spaces of equal length, so offsets map 1:1 to the real file."""
    def sp(m: re.Match) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))
    return NOSCRIPT_TEMPLATE.sub(sp, SCRIPT_OR_STYLE.sub(sp, src))


def strings_of(src: str) -> list[tuple[str, int, int, str, str]]:
    """(text, start, end, tag, attrs) for every plain-text element in the visible markup, in page order."""
    out = []
    for m in ELEMENT.finditer(masked(src)):
        tag, attrs, text = m.group(1), m.group(2), m.group(3)
        if not translatable(text) or "data-i=" in attrs:
            continue
        out.append((text.strip(), m.start(), m.end(), tag, attrs))
    return out


def dict_path(page: str) -> Path:
    return DICT_DIR / (page.replace(".html", "") + ".json")


def extract(page: str) -> tuple[int, int]:
    src = (ROOT / page).read_text(encoding="utf-8")
    DICT_DIR.mkdir(exist_ok=True)
    path = dict_path(page)
    have = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    have = {k: v for k, v in have.items() if not k.startswith("_")}
    # strings already tagged by an earlier --apply keep their translation under the ORIGINAL text
    seen: dict[str, str] = {}
    for text, *_ in strings_of(src):
        t = html.unescape(text)
        if t not in seen:
            seen[t] = have.get(t, "")
    for k, v in have.items():                 # keep what was translated even if the element is tagged now
        if v and k not in seen:
            seen[k] = v
    out = {"_doc": f"{page}: English visible text -> Filipino, authored. Empty = not yet translated. "
                   "tools/i18n_page_dict.py --apply tags the element and emits WH_FIL_PAGE."}
    out.update(seen)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="")
    return len(seen), sum(1 for v in seen.values() if v)


def apply(page: str) -> tuple[int, int]:
    src = (ROOT / page).read_text(encoding="utf-8")
    path = dict_path(page)
    if not path.exists():
        return 0, 0
    table = {k: v for k, v in json.loads(path.read_text(encoding="utf-8")).items() if not k.startswith("_") and v}
    if not table:
        return 0, 0
    # tag, from the end backwards so offsets stay valid
    tagged = 0
    keys: dict[str, str] = {}
    for text, start, end, tag, attrs in reversed(strings_of(src)):
        t = html.unescape(text)
        if t not in table:
            continue
        k = key_of(t)
        keys[k] = table[t]
        seg = src[start:end]
        seg = re.sub(rf"^<{tag}\b", f'<{tag} data-i="{k}"', seg, count=1, flags=re.I)
        src = src[:start] + seg + src[end:]
        tagged += 1
    # strings tagged by an earlier apply still need their entry in the dictionary
    for m in re.finditer(r'data-i="(p_[a-z]*_[0-9a-f]{4})"', src):
        k = m.group(1)
        if k not in keys:
            for t, v in table.items():
                if key_of(t) == k:
                    keys[k] = v
    # EMITTED AS A FILE, NOT INLINE (2026-09-07): the inline <script id="wh-fil-page"> block counted against every
    # page's inline-script render budget for EVERY reader, and tipped assistant + platform-actions over it. The
    # dictionary now lives in i18n/pages/<stem>.fil.json and is fetched ONCE, only under FIL, only when the page
    # carries p_ keys (utils.js whI18nApply) - an English reader pays zero bytes for the Filipino a worker chose.
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    stem = page.replace(".html", "")
    (PAGES_DIR / f"{stem}.fil.json").write_text(
        json.dumps(keys, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    has_utils = re.search(r"<script[^>]*\butils\.js[^>]*>", src) is not None
    if has_utils:
        block = ""   # utils.js fetches + applies; nothing inline
    else:
        # a page that loads no utils.js (architecture.html, a static reference) gets the same contract inline: fetch
        # the same file under the same wh_lang key, apply at DOMContentLoaded/load and on every DOM change (debounced)
        # - architecture re-renders its map from data AFTER DOMContentLoaded, so a one-shot swap read 1 of 47 live.
        block = ('<script id="wh-fil-page">(function(){try{if(localStorage.getItem(\'wh_lang\')!==\'fil\')return;}catch(e){return;}'
                 'fetch(\'i18n/pages/' + stem + '.fil.json\').then(function(r){return r.ok?r.json():{};}).catch(function(){return {};})'
                 '.then(function(d){window.WH_FIL_PAGE_VISIBLE=d||{};'
                 "function ap(){document.querySelectorAll('[data-i]').forEach(function(el){"
                 "var v=window.WH_FIL_PAGE_VISIBLE[el.getAttribute('data-i')];if(v!=null&&el.textContent!==v)el.textContent=v;});}"
                 "function arm(){ap();var t=null;if(typeof MutationObserver==='function')new MutationObserver(function(){clearTimeout(t);t=setTimeout(ap,200);})"
                 ".observe(document.body,{childList:true,subtree:true});window.addEventListener('load',ap);}"
                 "if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',arm);else arm();});})();</script>\n")
    if 'id="wh-fil-page"' in src:
        def _swap(m):
            indent = re.match(r"[ \t]*", m.group(0)).group(0)
            return (indent + block) if block else ""
        src = re.sub(r'[ \t]*<script id="wh-fil-page">[\s\S]*?</script>\n?', _swap, src, count=1)
    elif block:
        m = re.search(r"[ \t]*</head>", src)
        if not m:
            print(f"  {page}: no utils.js and no </head> - loader NOT emitted")
            return tagged, 0
        indent = re.match(r"[ \t]*", m.group(0)).group(0)
        src = src[:m.start()] + indent + block + src[m.start():]
    (ROOT / page).write_text(src, encoding="utf-8", newline="")
    return tagged, len(keys)


def status() -> None:
    tot = [0, 0]
    for page in roster():
        path = dict_path(page)
        d = {k: v for k, v in json.loads(path.read_text(encoding="utf-8")).items() if not k.startswith("_")} if path.exists() else {}
        src = (ROOT / page).read_text(encoding="utf-8")
        applied = len(re.findall(r'data-i="p_', src))
        n, t = len(d), sum(1 for v in d.values() if v)
        tot[0] += n; tot[1] += t
        print(f"  {page:<34} strings {n:>4} · translated {t:>4} · tagged {applied:>4}")
    print(f"  roster: {tot[1]}/{tot[0]} translated")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract", nargs="?", const="", metavar="PAGE")
    ap.add_argument("--apply", nargs="?", const="", metavar="PAGE")
    ap.add_argument("--all", action="store_true", help="with --extract/--apply: the whole EX-TL roster")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.status:
        status(); return 0
    pages = roster() if a.all else [a.extract or a.apply]
    if a.extract is not None:
        for p in pages:
            n, t = extract(p); print(f"  {p:<34} {n:>4} visible string(s) · {t:>4} translated")
    if a.apply is not None:
        for p in pages:
            n, k = apply(p); print(f"  {p:<34} tagged {n:>4} · WH_FIL_PAGE {k:>4} key(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

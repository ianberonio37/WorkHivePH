"""
build_md_twins.py — clean markdown twin for every public page (llms.txt convention).
====================================================================================
The llms.txt specification asks a site to serve a clean markdown version of each page
at the SAME URL with `.md` appended — and for a URL with no filename, `index.html.md`
[substrate/external/external-llms-txt-specification-github-official-format-h1].

WHY THIS IS NOT COSMETIC: an agent that fetches a page today gets ~25KB of HTML —
Tailwind CDN script, inline <style>, the local-dev URL bridge, GA4, nav chrome, footer —
wrapped around ~4KB of actual answer. Every one of those bytes competes for the model's
context, and the parse is lossy: our own harvest of OpenAI's bots page came back as
navigation because a crawler could not find the content. A markdown twin removes the
guesswork. This is the agentic-web layer, which is where llms.txt does real work even
though Google says it is not needed for AI Overviews
[external-llms-txt-google-2026-guidance-agentic-web-value-].

DRIFT IS THE RISK, so each twin records the sha256 of the HTML it came from and
`tools/validate_md_twins.py` fails when a page changed without its twin being rebuilt —
the same source_sha discipline the knowledge substrate uses. A stale twin is worse than
no twin: it feeds an agent a confidently wrong version of the page.

RUN:  python tools/build_md_twins.py            # build/refresh every twin
      python tools/build_md_twins.py --check    # report only, write nothing
"""
from __future__ import annotations

import re
import sys
import hashlib
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
SITE = "https://workhiveph.com"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# chrome that must never reach the markdown
DROP_SELECTORS = [
    "script", "style", "noscript", "header", "footer",
    ".toc", ".author-card", ".breadcrumb", "nav",
]
# Bump when the CONVERTER changes shape. The twin fingerprint is source-sha + this
# version, because keying on the page alone means an improved converter never
# regenerates anything — which is exactly how 54 twins silently kept a missing
# answer-first block after the bug was fixed.
GENERATOR_VERSION = 2
SHA_MARK = "<!-- md-twin source-sha:"


def _clean_text(s: str) -> str:
    return re.sub(r"[ \t]+", " ", s.replace("\xa0", " ")).strip()


def _inline(node) -> str:
    """Render inline content, preserving links/emphasis/code."""
    out = []
    for c in node.children:
        if isinstance(c, NavigableString):
            out.append(str(c))
        elif isinstance(c, Tag):
            if c.name == "a":
                href = c.get("href", "")
                txt = _inline(c).strip()
                if href.startswith("/"):
                    href = SITE + href
                out.append(f"[{txt}]({href})" if txt else "")
            elif c.name in ("strong", "b"):
                out.append(f"**{_inline(c).strip()}**")
            elif c.name in ("em", "i"):
                out.append(f"*{_inline(c).strip()}*")
            elif c.name == "code":
                out.append(f"`{_inline(c).strip()}`")
            elif c.name == "br":
                out.append("\n")
            else:
                out.append(_inline(c))
    return _clean_text("".join(out))


def _table(tag: Tag) -> str:
    rows = []
    for tr in tag.find_all("tr"):
        cells = [_inline(td) for td in tr.find_all(["th", "td"])]
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |",
           "|" + "|".join([" --- "] * width) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(out)


def _block(tag: Tag, depth: int = 0) -> list[str]:
    n = tag.name
    if n in ("h1", "h2", "h3", "h4"):
        lvl = {"h1": "#", "h2": "##", "h3": "###", "h4": "####"}[n]
        return [f"{lvl} {_inline(tag)}"]
    if n == "p":
        t = _inline(tag)
        return [t] if t else []
    if n == "table":
        t = _table(tag)
        return [t] if t else []
    if n in ("ul", "ol"):
        # the whole list is ONE block: items joined by single newlines, so markdown
        # renders a tight list instead of a paragraph per bullet
        lines: list[str] = []
        for i, li in enumerate(tag.find_all("li", recursive=False), 1):
            bullet = f"{i}." if n == "ol" else "-"
            nested = [c for c in li.find_all(["ul", "ol"], recursive=False)]
            for x in nested:
                x.extract()
            txt = _inline(li)
            if txt:
                lines.append(f"{'  ' * depth}{bullet} {txt}")
            for x in nested:
                lines.extend(_block(x, depth + 1))
        return ["\n".join(lines)] if lines else []
    if n == "blockquote":
        return ["> " + _inline(tag)]
    if n == "details":                       # FAQ accordions
        summ = tag.find("summary")
        body = tag.find(class_="faq-answer") or tag.find("p")
        q = _inline(summ) if summ else ""
        a = _inline(body) if body else ""
        return [f"### {q}", a] if q else ([a] if a else [])
    if n in ("div", "section", "article", "main"):
        # A container whose content is bare text + inline tags (no p/h/ul/table/details)
        # carries real prose that would otherwise be dropped on the floor. The
        # `.answer-first` block is exactly this shape — raw text and <strong>, no <p> —
        # and it is the most citable paragraph on the page, so losing it silently
        # gutted every twin until this branch existed.
        BLOCKISH = ("p", "h1", "h2", "h3", "h4", "ul", "ol", "table",
                    "details", "blockquote", "div", "section")
        if not tag.find(BLOCKISH, recursive=False):
            txt = _inline(tag)
            return [txt] if txt else []
        out = []
        for c in tag.children:
            if isinstance(c, Tag):
                out.extend(_block(c, depth))
        return out
    return []


def html_to_md(html: str, url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for sel in DROP_SELECTORS:
        for el in soup.select(sel):
            el.decompose()
    root = soup.find("article") or soup.find("main") or soup.body
    if root is None:
        return ""
    title = soup.find("h1")
    title_txt = _clean_text(title.get_text()) if title else ""
    desc = soup.find("meta", attrs={"name": "description"})
    parts: list[str] = []
    if title_txt:
        parts.append(f"# {title_txt}")
    if desc and desc.get("content"):
        parts.append(f"> {_clean_text(desc['content'])}")
    parts.append(f"Source: {url}")
    seen_h1 = False
    for c in root.children:
        if isinstance(c, Tag):
            for blk in _block(c):
                if blk.startswith("# "):
                    if seen_h1:
                        continue
                    seen_h1 = True
                    continue            # title already emitted
                if blk.strip():
                    parts.append(blk)
    md = "\n\n".join(parts).strip()
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md + "\n"


def _twin_path(page: Path) -> Path:
    """`/learn/x/index.html` -> `/learn/x/index.html.md` (spec: append .md)."""
    return page.with_suffix(page.suffix + ".md")


def _pages() -> list[tuple[Path, str]]:
    """Every page listed in sitemap.xml, resolved to a file."""
    sm = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    out = []
    for loc in re.findall(r"<loc>([^<]+)</loc>", sm):
        rel = loc.replace(SITE, "").strip("/")
        p = ROOT / rel if rel else ROOT / "index.html"
        if p.is_dir():
            p = p / "index.html"
        if "." not in p.name:
            p = p.with_suffix(".html")
        if p.exists():
            out.append((p, loc))
    return out


def main() -> int:
    check = "--check" in sys.argv[1:]
    built = stale = ok = 0
    for page, url in _pages():
        html = page.read_text(encoding="utf-8", errors="replace")
        sha = hashlib.sha256((html + f"|gen{GENERATOR_VERSION}").encode("utf-8")).hexdigest()[:16]
        twin = _twin_path(page)
        want_mark = f"{SHA_MARK} {sha} -->"
        if twin.exists() and want_mark in twin.read_text(encoding="utf-8", errors="replace"):
            ok += 1
            continue
        stale += 1
        if check:
            continue
        md = html_to_md(html, url)
        if not md.strip():
            print(f"  SKIP (no content extracted): {page.relative_to(ROOT)}")
            continue
        twin.write_text(md + "\n" + want_mark + "\n", encoding="utf-8")
        built += 1
    verb = "would rebuild" if check else "rebuilt"
    print(f"md twins: {ok} current, {stale} {verb}" + (f", {built} written" if not check else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

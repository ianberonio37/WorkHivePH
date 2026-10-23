#!/usr/bin/env python3
"""render_skew_heal.py - BRH-D (2026-10-14): a page that relies on a shared function heals an older utils.js instead of
silently skipping it.

WHY. Ian's missing hive assets, 2026-10-14: vercel.json let a phone keep utils.js for an hour after a deploy while the
page itself was fetched fresh, so the new logbook ran on yesterday's utils.js. The function it needed was not there, and
the page's `typeof whX === 'function'` guard turned that into silence - personal mode, "No assets registered yet." The
cache lifetime is fixed (scripts revalidate on every load), but a page can still meet an older copy: the service worker
serves utils.js network-first and falls back to its kept copy when the request drops, which on a plant floor's
connection is not rare. 31 production pages guard 51 utils.js functions this way (bug_hunt_inventory class D).

utils.js cannot detect that it is old - an old copy predates any check it could carry - so the check lives in the PAGE,
the one artifact that is current by construction (app pages are never served from a cache while the network answers).
Right after the page's <script src="utils.js"> this tool writes one block naming every utils.js function the page
guards (bug_hunt_inventory.skew_needs, the inventory's own class-D measurement). When one is missing the block stops the
page before it runs on the old script, fetches utils.js past the HTTP cache (which also refreshes the worker's kept
copy) and reloads. A sessionStorage guard - the one logbook's own heal uses - makes a second miss a logged degrade,
never a loop; a clean load clears it, so a later deploy can heal again. No utils.js at all (getDb missing) is not skew:
the page's own did-not-load notice answers that, and a reload while offline would only replace it with an error page.

    python tools/render_skew_heal.py              # report pages whose block is missing, stale, misplaced or edited
    python tools/render_skew_heal.py --apply      # write the blocks
    python tools/render_skew_heal.py --check      # the gate (skew-heal): exit 1 on any drift
    python tools/render_skew_heal.py --self-test
    python tools/render_skew_heal.py --needs-json # {page: functions} - the roster tools/prove_skew_heal.mjs walks
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from bug_hunt_inventory import DEFINED, production_pages, skew_needs  # noqa: E402


SCRIPT_SRC = re.compile(r'<script\b[^>]*\bsrc="([^"/:?#]+\.js)"', re.I)


def own_scripts_text(page: str) -> str:
    """The text of the local scripts ONLY this page loads - its own code, kept in a file. ★A PAGE'S OWN SCRIPT IS THE
    PAGE (OPC, 2026-10-22): the operator console runs its action queues from operator-actions.js, and engineering-design
    keeps its logic in engineering-design.js. A function guarded there is guarded on that page, and an older utils.js
    silences it the same way - the block measured the HTML alone and named none of them (the console's queues guard 11,
    engineering-design.js 3). A script more than one page loads is shared, and stays out: it is no one page's code."""
    loads = {}
    for f in ROOT.glob("*.html"):
        loads[f.name] = set(SCRIPT_SRC.findall(f.read_text(encoding="utf-8", errors="replace")))
    mine = [s for s in sorted(loads.get(page, ())) if s != "utils.js" and (ROOT / s).exists()
            and sum(1 for ss in loads.values() if s in ss) == 1]
    return "".join("\n" + (ROOT / s).read_text(encoding="utf-8", errors="replace") for s in mine)


def heal_pages() -> list[str]:
    """Every page that must heal: the LX production pages AND every root page of the SL program's roster (SL CA3,
    2026-10-16). The roster started as LX's production list, which leaves out design-system, status, voice-journal and
    the retired observability pages - each of which guards utils.js functions and, on an older copy, skipped them in
    silence: the exact defect the block exists for. A page the SL walk measures is a page that must heal."""
    import json
    sl = set()
    try:
        reg = json.loads((ROOT / "trajectory_registry.json").read_text(encoding="utf-8"))
        sl = {(t.get("sl") or {}).get("page") for t in reg.get("trajectories", [])}
    except (OSError, ValueError):
        pass
    sl = {x for x in sl if x and "/" not in x and x.endswith(".html") and (ROOT / x).exists()}
    return sorted(set(production_pages()) | sl)

UTILS_TAG = re.compile(r'<script src="utils\.js"></script>')
BLOCK_RX = re.compile(r'<script data-wh-skew-heal="([^"]*)">(.*?)</script>', re.S)

# The jscpd markers: this block is identical on every page BY DESIGN (one source, this file), and the clone-debt
# ratchet read it as 205 lines of new copy-paste across 6 page pairs (2026-10-23). The markers keep generated code
# out of a measure that is about hand-written copies; a hand edit to a block still fails --check below.
BODY = [
    "/* jscpd:ignore-start */",
    "/* BRH-D skew heal (2026-10-14), written by tools/render_skew_heal.py - change the generator, never this block.",
    "   The page relies on the utils.js functions named above. An older utils.js (a copy kept from before a deploy) lacks",
    "   some of them, and every call behind a typeof guard would then silently do nothing. So: stop this page before it",
    "   runs on the old script, fetch utils.js past the cache and reload - once per tab. A second miss is logged and the",
    "   page carries on; a clean load clears the guard so a later deploy can heal again. No utils.js at all (getDb",
    "   missing) is not skew: the page's own did-not-load notice answers that. */",
    "(function (s) {",
    "  if (typeof window.getDb !== 'function') return;",
    "  var need = ((s && s.getAttribute('data-wh-skew-heal')) || '').split(' '), missing = [], tried = true, i;",
    "  for (i = 0; i < need.length; i++) if (need[i] && typeof window[need[i]] !== 'function') missing.push(need[i]);",
    "  try { tried = sessionStorage.getItem('wh_utils_refetched') === '1'; } catch (e) { void e; }",
    "  if (!missing.length) { if (tried) { try { sessionStorage.removeItem('wh_utils_refetched'); } catch (e) { void e; } } return; }",
    "  if (tried) { try { console.error('[skew] utils.js still lacks ' + missing.join(', ') + ' after one refetch'); } catch (e) { void e; } return; }",
    "  try { sessionStorage.setItem('wh_utils_refetched', '1'); } catch (e) { return; }",
    "  try { window.stop(); } catch (e) { void e; }",
    "  fetch('utils.js', { cache: 'reload' }).catch(function () { return null; }).then(function () { location.reload(); });",
    "})(document.currentScript);",
    "/* jscpd:ignore-end */",
]


def block(names: list[str], nl: str = "\n") -> str:
    return f'<script data-wh-skew-heal="{" ".join(names)}">' + nl + nl.join(BODY) + nl + "</script>"


def _nl(src: str) -> str:
    return "\r\n" if "\r\n" in src else "\n"


def defined_in(utils_src: str) -> set:
    return {a or b for a, b in DEFINED.findall(utils_src)}


def render(src: str, defined: set, own: str = "") -> str:
    """The page with its heal block present, current and in place (or absent, when it guards nothing). `own` is the
    text of the scripts only this page loads (own_scripts_text)."""
    names, nl = skew_needs(_strip_block(src) + own, defined), _nl(src)
    out = _strip_block(src)
    if not names:
        return out
    m = UTILS_TAG.search(out)
    if not m:
        return out          # a page that does not load utils.js cannot meet an older one (problems() says so)
    return out[:m.end()] + nl + block(names, nl) + out[m.end():]


def _strip_block(src: str) -> str:
    """The page without its heal block (and the one newline the block was written after)."""
    return re.sub(r'(?:\r?\n)?<script data-wh-skew-heal="[^"]*">.*?</script>', "", src, count=1, flags=re.S)


def problems(page: str, src: str, defined: set, own: str = "") -> list[str]:
    names = skew_needs(_strip_block(src) + own, defined)
    blocks = BLOCK_RX.findall(src)
    if not names:
        return [f"{page}: a heal block, but the page guards no utils.js function - remove it (--apply)"] if blocks else []
    if not UTILS_TAG.search(src):
        return [f"{page}: guards {len(names)} utils.js functions but has no plain <script src=\"utils.js\"> tag to heal after"]
    if not blocks:
        return [f"{page}: guards {len(names)} utils.js functions ({', '.join(names[:4])}{' ...' if len(names) > 4 else ''}) "
                f"with no heal block - an older utils.js silences every one of them (--apply)"]
    out = []
    if len(blocks) > 1:
        out.append(f"{page}: {len(blocks)} heal blocks - one per page")
    listed = blocks[0][0].split()
    if listed != names:
        miss, extra = sorted(set(names) - set(listed)), sorted(set(listed) - set(names))
        out.append(f"{page}: the heal block's list is stale - not named: {miss}; named but no longer guarded: {extra} "
                   f"(--apply)")
    if blocks[0][1].replace("\r\n", "\n").strip() != "\n".join(BODY):
        out.append(f"{page}: the heal block's body was edited by hand - it must equal the generator's (--apply)")
    tag, blk = UTILS_TAG.search(src), src.find("<script data-wh-skew-heal=")
    # after the tag AND nothing but whitespace between (a block above the tag slices to "" and would pass alone)
    if not (tag and blk >= tag.end() and src[tag.end():blk].strip() == ""):
        out.append(f"{page}: the heal block is not directly after the utils.js tag - it must run as soon as utils.js has, "
                   f"before the page's own scripts")
    return out


def main(apply: bool, check: bool) -> int:
    defined = defined_in((ROOT / "utils.js").read_text(encoding="utf-8", errors="replace"))
    found, written = [], []
    for page in heal_pages():
        path = ROOT / page
        src = path.read_bytes().decode("utf-8", errors="replace")
        own = own_scripts_text(page)
        probs = problems(page, src, defined, own)
        if not probs:
            continue
        if apply:
            new = render(src, defined, own)
            if new != src:
                path.write_bytes(new.encode("utf-8"))
                written.append(page)
            probs = problems(page, new, defined, own)
        found += probs
    if apply:
        print(f"wrote {len(written)} page(s): {', '.join(written) or '-'}")
    for p in found:
        print("  FAIL " + p)
    healed = sum(1 for page in heal_pages()
                 if BLOCK_RX.search((ROOT / page).read_text(encoding="utf-8", errors="replace")))
    if found:
        print(f"FAIL skew-heal - {len(found)} problem(s)")
        return 1
    print(f"PASS skew-heal - {healed} page(s) that guard utils.js functions each heal an older utils.js (one block per "
          f"page, directly after its utils.js tag, naming every function it guards, the generator's body unedited)")
    return 0


def self_test() -> int:
    utils = "function whHiveId(){}\nfunction whFmtAgo(){}\nwindow.whListError = function(){};\n"
    d = defined_in(utils)
    page = ("<html>\r\n<script src=\"utils.js\"></script>\r\n<script>if (typeof whHiveId === 'function') {} "
            "if (typeof whListError === 'function') {} if (typeof whNope === 'function') {}</script>\r\n</html>")
    ok = True
    ok &= bool(problems("p.html", page, d))                                   # no block: red
    fixed = render(page, d)
    ok &= problems("p.html", fixed, d) == []                                  # rendered: green
    ok &= '<script data-wh-skew-heal="whHiveId whListError">\r\n' in fixed    # names sorted, the page's CRLF kept
    ok &= render(fixed, d) == fixed                                           # idempotent
    ok &= bool(problems("p.html", fixed.replace("whHiveId whListError", "whHiveId"), d))          # a name dropped: red
    ok &= bool(problems("p.html", fixed.replace("location.reload();", "void 0;"), d))             # body edited: red
    moved = _strip_block(fixed).replace("<html>", "<html>" + block(["whHiveId", "whListError"], "\r\n"))
    ok &= bool(problems("p.html", moved, d))                                  # before utils.js: red
    plain = "<script src=\"utils.js\"></script><script>go()</script>"
    ok &= problems("q.html", plain, d) == [] and render(plain, d) == plain    # guards nothing: no block
    ok &= bool(problems("q.html", plain.replace("</script><script>", "</script>" + block(["whHiveId"]) + "<script>"), d))
    ok &= skew_needs(fixed, d) == ["whHiveId", "whListError"]                 # the block does not count as a guard
    own = "if (typeof whFmtAgo === 'function') {}"                               # a guard in a script only this page loads
    ok &= bool(problems("p.html", fixed, d, own))                             # its own script guards one more: red
    ok &= '"whFmtAgo whHiveId whListError"' in render(fixed, d, own) and problems("p.html", render(fixed, d, own), d, own) == []
    print(("PASS" if ok else "FAIL") + " skew-heal self-test - a missing, stale, edited or misplaced block reddens; a "
          "rendered page is green and idempotent; a page that guards nothing carries no block; a guard in a script only the page "
          "loads counts as the page's")
    return 0 if ok else 1


def needs_map() -> dict:
    """{page: the utils.js functions it guards} for every production page that guards any - the roster
    tools/prove_skew_heal.mjs walks, from the same measurement as the blocks."""
    defined = defined_in((ROOT / "utils.js").read_text(encoding="utf-8", errors="replace"))
    out = {}
    for page in heal_pages():
        names = skew_needs(_strip_block((ROOT / page).read_text(encoding="utf-8", errors="replace"))
                           + own_scripts_text(page), defined)
        if names:
            out[page] = names
    return out


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    if "--needs-json" in sys.argv:
        import json
        print(json.dumps(needs_map()))
        sys.exit(0)
    sys.exit(main(apply="--apply" in sys.argv, check="--check" in sys.argv))

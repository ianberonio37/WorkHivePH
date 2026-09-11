#!/usr/bin/env python3
"""validate_shared_component_i18n.py — shared JS chrome must speak the platform's two languages.

WHY THIS EXISTS (W3-SC, 2026-09-09). `validate_i18n_coverage.py` scans PAGES. Nothing scanned the
shared JS components, so five of them shipped user-facing English on up to 35 pages each while the
pages around them were bilingual:

  session-timeout.js   33 pages  the idle prompt on a shared plant tablet -- a file whose OWN header
                                 says "on a shared Filipino plant tablet"
  offline-banner.js    35 pages  "You are offline. Some actions may not work."
  connectivity-widget  33 pages  the sentence that tells a person whether their offline work is SAFE
  qr-scanner.js         4 pages  every camera-failure line, each ending "type tag manually below"
  worker-drawer.js      1 page   a supervisor's view of one of their own workers
  wh-feedback-fab.js    3 pages  the panel that asks a person what is broken

They were inside the contract the whole time: `utils.js` installs `window._t(en, fil)` as a
platform-wide locale FLOOR (whLocaleFloor) precisely so shared chrome can translate without owning a
dictionary, and `nav-hub.js` + `maturity-gate.js` + `companion-launcher.js` already used it. The gap
was silent because no gate looked. This is the gate.

WHAT IT CHECKS (deliberately FILE-level, not string-level). For each shared root .js file that is
loaded by at least one page: if the file writes user-facing text into the DOM, it must reference the
platform translator (`_t(` / `_tt(` / `T(` / `whT(` / `window._t`) at least once.

File-level is the honest granularity here, and the choice is load-bearing rather than lazy. A
string-level rule would demand `_t('Online', 'Online')` around true loanwords -- Filipino industrial
speech says "online", "offline", "Network" -- and a gate that forces no-op translations teaches
people to satisfy it with noise. File-level asks the one question that actually distinguishes the
defect from the design: has this component joined the contract at all? Three separate hand-rolled
greps got the per-string picture WRONG in the session that produced this file (`grep "_t("` cannot
see `_tt(`; a case-sensitive class cannot see `T(`), which is its own argument for asking a coarse
question accurately instead of a fine one approximately.

EXEMPTION. A component that genuinely must not call the translator carries a marker comment:

    // i18n-shared-allow: <reason>

`browser-floor.js` is the real case: it runs on a pre-2020 engine, where the `_tt` arrow-function
helper every other component uses would not even parse -- so it inlines both languages literally.
That is the correct design for that file, and the marker records why rather than hiding it.

FORWARD-ONLY RATCHET. The ceiling lives in `.i18n_shared_ceiling`. The gate FAILS if the count of
untranslated components rises above it, and rewrites the ceiling downward when it falls. Registered
in run_platform_checks.py; `--selftest` runs deterministic cases with no filesystem scan.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CEILING_FILE = REPO / ".i18n_shared_ceiling"

# A translator reference in any of the shapes the platform actually uses. `T(` is matched with a
# leading non-identifier char so it cannot fire on `escapeHTML(` or `printT(`.
TRANSLATOR_RE = re.compile(r"(?:^|[^A-Za-z0-9_$.])(?:_t|_tt|T|whT)\s*\(|window\._t\b")

# A deliberate opt-out, with its reason on the same line.
ALLOW_RE = re.compile(r"i18n-shared-allow:\s*(\S.*)")

# What a person actually reads, and -- the load-bearing part -- only when the value is a LITERAL the
# component owns. `btn.textContent = original` (button-lock restoring a caller's label) and
# `pop.innerHTML = content` (wh-help rendering a string the PAGE passed in) are not this component's
# words to translate; both were false positives in the first draft of this gate, and a gate whose
# false positives are silenced with exemption markers stops meaning anything.
#
# So every pattern below requires a quoted literal holding at least two letter-words: an English UI
# string. An already-translated call reads `aria-label="${_tt('Close', 'Isara')}"` or
# `.textContent = _tt('Reload', 'I-reload')` -- no bare literal after the sink, and the translator
# check passes the file anyway.
# A capitalised word followed by at least one more word. The trailing class is wide on purpose:
# with it narrow, browser-floor.js's real banner -- "This browser is too old to run WorkHive (it
# needs a 2020-or-newer browser engine)." -- slipped through on its PARENTHESES alone, which would
# have let the next component with a parenthetical sentence past the gate too. CSS survives this
# because a declaration starts lowercase (background:rgba(...)), and <style> blocks are stripped
# before any of these patterns run. The space class holds a plain space and a NBSP.
_WORDS = r"""[A-Z][A-Za-z'’]*(?:[  ][A-Za-z0-9(][A-Za-z0-9'’.,:!?()/&%-]*)+"""
PROSE_PATTERNS = [
    # el.textContent = 'Two or more words'   /  el.innerHTML = "..."
    ("assignment", re.compile(
        r"""(?<![.\w])\w+\s*\.\s*(?:textContent|innerHTML|title)\s*=\s*(['"])(""" + _WORDS + r""")\s*\1""")),
    # el.setAttribute('aria-label', 'Two or more words')
    ("setAttribute", re.compile(
        r"""\.\s*setAttribute\s*\(\s*['"](?:aria-label|title|placeholder|alt)['"]\s*,\s*"""
        r"""(['"])(""" + _WORDS + r""")\s*\1""")),
    # markup inside a template literal: aria-label="Two or more words"
    ("attribute", re.compile(
        r"""(?:aria-label|placeholder|title|alt)\s*=\s*(["'])(""" + _WORDS + r""")\s*\1""")),
    # a text node in generated markup: >Two or more words<   (group 1 is a placeholder so every
    # pattern in this list yields the words in group 2)
    ("text node", re.compile(r"""(>)\s*(""" + _WORDS + r""")\s*<""")),
]
# String concatenation builds a label from a literal plus a value:
#   'aria-label="Companion ' + name + '"'      /      'Could not load worker profile: ' + err
CONCAT_RE = re.compile(r"""(['"])(""" + _WORDS + r"""|[A-Z][a-z]+:)\s*\1\s*\+""")


SCRIPT_SRC_RE = re.compile(
    # (?:\./)? -- the whole "./" prefix is optional. Written `\./?` it silently REQUIRED the dot and
    # matched nothing at all, which is why this gate's first run reported zero shared components.
    r"""<script[^>]+src\s*=\s*["'](?:\./)?([A-Za-z0-9._-]+\.js)(?:\?[^"']*)?["']""",
    re.I,
)


def _script_srcs(html: str) -> set[str]:
    return set(SCRIPT_SRC_RE.findall(html))


def shared_components(repo: Path) -> dict[str, int]:
    """Root .js files loaded by at least one root .html page -> how many pages load them."""
    hosts: dict[str, int] = {}
    for page in sorted(repo.glob("*.html")):
        try:
            srcs = _script_srcs(page.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        for s in srcs:
            if (repo / s).is_file():
                hosts[s] = hosts.get(s, 0) + 1
    return hosts


# The repo's established comment-strip idiom (api_adoption_census.py and a dozen siblings). Line
# comments only when `//` OPENS the line, so a `https://` inside real code is never eaten.
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT_RE = re.compile(r"^\s*//.*$", re.M)


def _strip_css(source: str) -> str:
    """Drop what is not this component's live UI text: comments first, then injected <style> blocks.

    Comments matter more than they look. Four of the first seven files this gate flagged were flagged
    on a DOC COMMENT -- wh-capture-validate.js and oc-helper.js both show `showToast('Cannot save: ')`
    as a USAGE EXAMPLE, and browser-floor.js was flagged on its own wiring note. A gate that reports a
    comment as a defect is the "quoting a comment is not reading the code" error wearing a ratchet.
    """
    body = LINE_COMMENT_RE.sub("", BLOCK_COMMENT_RE.sub(" ", source))
    return re.sub(r"<style>.*?</style>", " ", body, flags=re.S | re.I)


def prose_evidence(source: str) -> list[tuple[str, str]]:
    """Every English UI literal this component owns, as (how it was found, the words)."""
    body = _strip_css(source)
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for kind, pat in PROSE_PATTERNS:
        for m in pat.finditer(body):
            words = m.group(2).strip()
            if words not in seen:
                seen.add(words)
                found.append((kind, words))
    for m in CONCAT_RE.finditer(body):
        words = m.group(2).strip()
        if words not in seen:
            seen.add(words)
            found.append(("concatenation", words))
    return found


def classify(source: str) -> tuple[bool, bool, str | None, str | None]:
    """-> (writes_prose, has_translator, allow_reason, sample_of_untranslated_prose).

    Both halves read COMMENT-STRIPPED source. The translator half has to, and learning that cost a
    real false reading: the exemption comment written onto browser-floor.js said "utils.js (which
    installs window._t)" -- prose explaining why the file does NOT translate -- and the gate read
    those two words as proof that it DOES, quietly dropping the file out of its own report. A comment
    is never evidence about what the code does, in either direction.

    ALLOW_RE is the one deliberate exception: the exemption marker IS a comment, so it reads the raw
    source.
    """
    allow = ALLOW_RE.search(source)
    body = _strip_css(source)
    evidence = prose_evidence(source)
    has_t = bool(TRANSLATOR_RE.search(body))
    sample = evidence[0][1] if evidence else None
    return bool(evidence), has_t, (allow.group(1).strip() if allow else None), sample


def read_ceiling() -> int | None:
    try:
        return int(CEILING_FILE.read_text(encoding="utf-8").split("#", 1)[0].strip())
    except (OSError, ValueError):
        return None


def write_ceiling(n: int) -> None:
    CEILING_FILE.write_text(
        f"{n}  # validate_shared_component_i18n.py forward-only ratchet; lower is better\n",
        encoding="utf-8",
    )


def run(repo: Path) -> int:
    hosts = shared_components(repo)
    if not hosts:
        print("shared-component-i18n: no shared components found -- is this the site root?")
        return 1

    offenders: list[tuple[str, int, str | None]] = []
    exempt: list[tuple[str, str]] = []
    ok = 0
    for name, n_hosts in sorted(hosts.items(), key=lambda kv: -kv[1]):
        try:
            src = (repo / name).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        writes, has_t, allow, sample = classify(src)
        if not writes:
            continue
        if has_t:
            ok += 1
        elif allow:
            exempt.append((name, allow))
        else:
            offenders.append((name, n_hosts, sample))

    ceiling = read_ceiling()
    count = len(offenders)

    print(f"shared-component-i18n: {ok} translated · {len(exempt)} exempt · {count} untranslated")
    for name, reason in exempt:
        print(f"  EXEMPT  {name} -- {reason}")
    for name, n_hosts, sample in offenders:
        tail = f' e.g. "{sample}"' if sample else ""
        print(f"  UNTRANSLATED  {name} ({n_hosts} pages){tail}")

    if ceiling is None:
        write_ceiling(count)
        print(f"shared-component-i18n: ceiling initialised at {count}")
        return 0
    if count > ceiling:
        print(
            f"FAIL shared-component-i18n: {count} untranslated shared components, ceiling {ceiling}.\n"
            "  A shared component that writes text a person reads must call the platform translator\n"
            "  window._t(en, fil) -- utils.js installs it on every page, so the idiom is one line:\n"
            "    const _tt = (en, fil) => (typeof window._t === 'function') ? window._t(en, fil) : en;\n"
            "  Resolve it at CALL time, not bind time: a page with its own engine defines _t later in\n"
            "  the body, and shared chrome usually paints long after load.\n"
            "  If the file genuinely must not (an ES5-only surface, say), add a line comment:\n"
            "    // i18n-shared-allow: <reason>"
        )
        return 1
    if count < ceiling:
        write_ceiling(count)
        print(f"shared-component-i18n: ratchet lowered {ceiling} -> {count}")
    return 0


def selftest() -> int:
    # (writes_prose, has_translator). A file FAILS only on (True, False) with no allow marker.
    cases = [
        # -- the defect this gate exists for ------------------------------------------------
        ("untranslated textContent",
         "el.textContent = 'You are offline. Some actions may not work.';", (True, False)),
        ("aria-label literal via setAttribute",
         "btn.setAttribute('aria-label', 'Close scanner');", (True, False)),
        ("aria-label literal inside generated markup",
         'w.innerHTML = `<button aria-label="Open companion"></button>`;', (True, False)),
        ("element .title assignment",
         "btn.title = 'Send feedback to WorkHive';", (True, False)),
        ("a text node in generated markup",
         "d.innerHTML = `<h3>Are you still here</h3>`;", (True, False)),
        ("a label built by concatenation",
         "e.textContent = 'Could not load worker profile: ' + err.message;", (True, False)),
        # -- already translated: no bare literal left for the gate to see -------------------
        ("translated via _tt",
         "const _tt=(a,b)=>a; el.textContent = _tt('Back online.', 'Online ka na ulit.');", (False, True)),
        ("translated via bare _t",
         "el.textContent = _t('Reload', 'I-reload');", (False, True)),
        ("translated via uppercase T (maturity-gate idiom)",
         "el.innerHTML = `<b>${T('Locked','Naka-lock')}</b>`;", (False, True)),
        ("translated aria-label in generated markup",
         'w.innerHTML = `<button aria-label="${_tt(\'Close\',\'Isara\')}"></button>`;', (False, True)),
        # -- the false positives that made the first draft of this gate wrong ---------------
        ("restoring a caller's own label is not this file's prose (button-lock.js)",
         "if (btn.textContent !== original) { btn.textContent = original; }", (False, False)),
        ("rendering a string the PAGE passed in is not this file's prose (wh-help.js)",
         "function _renderPop(anchor, content) { pop.innerHTML = content; }", (False, False)),
        ("injected CSS is not prose",
         "var s=document.createElement('style'); s.textContent = STYLE;", (False, False)),
        ("CSS inside generated markup is not prose",
         "w.innerHTML = `<style>#x { background: rgba(11,15,26,0.78); font-family: Poppins, sans-serif; }</style>`;",
         (False, False)),
        ("escapeHTML must not read as a translator",
         "el.innerHTML = escapeHTML(name);", (False, False)),
        ("no DOM text at all",
         "function hash(s){ return s.length; }", (False, False)),
        # -- comments are not shipped text ---------------------------------------------------
        ("a usage example in a doc comment (wh-capture-validate.js, oc-helper.js)",
         "/**\n *   showToast('Cannot save: ' + result.errors[0].message);\n */\nfunction v(){}",
         (False, False)),
        ("a wiring note in a line comment (browser-floor.js)",
         '// Wiring: <script src="browser-floor.js"></script> EARLY in <head>\nvar x = 1;',
         (False, False)),
        ("a comment ABOUT the translator is not a translator (browser-floor.js exemption)",
         "// i18n-shared-allow: ES5 only; utils.js (which installs window._t) may not have run\n"
         "d.innerHTML = 'This browser is too old to run WorkHive.';", (True, False)),
        ("a URL inside real code survives the line-comment strip",
         "el.textContent = 'Open the guide now'; var u='https://example.com/a';", (True, False)),
    ]
    bad = 0
    for label, src, (want_w, want_t) in cases:
        got_w, got_t, _, _ = classify(src)
        if (got_w, got_t) != (want_w, want_t):
            print(f"  FAIL {label}: writes={got_w} (want {want_w}) translator={got_t} (want {want_t})")
            bad += 1
        else:
            print(f"  ok   {label}")

    allow_w, allow_t, reason, _ = classify(
        "// i18n-shared-allow: ES5-only engine, cannot use the arrow helper\n"
        "d.innerHTML = 'This browser is too old. Masyadong luma ang browser na ito.';"
    )
    if not reason or not allow_w or allow_t:
        print("  FAIL exemption marker not honoured")
        bad += 1
    else:
        print("  ok   exemption marker read with its reason")

    print("selftest:", "PASS" if not bad else f"{bad} FAILED")
    return 1 if bad else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(run(REPO))

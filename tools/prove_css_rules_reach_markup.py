"""prove_css_rules_reach_markup.py - a page's own CSS rules must be able to reach something it renders.

THE GAP THIS FILLS. `validate_css_class_existence.py` already proves the other direction: every class the
JavaScript adds with classList.add() is defined somewhere in CSS (792 calls, 0 missing). Nothing proved
that a rule the stylesheet WRITES ever reaches markup - and that is where this drive kept finding real,
shipped defects:

  * report-sender.html declared `.chip-check { opacity: 0 }` and `.chip.selected .chip-check { opacity: 1 }`.
    The rendered element carried `class="ic ic-check"`. Neither rule had ever matched anything, so EVERY
    UNSELECTED CHIP PAINTED A CHECKMARK on a page whose entire job is choosing - past three design lenses,
    a static detector, and a release commit. (2026-09-17, W46027)

  * marketplace-seller.html declared `.empty-state h3 { font-size: 0.95rem }` and every empty state emitted
    an <h2>, so those headings rendered at the UA's 24px - louder than the section heading above them, and
    chosen by nobody. Fixing the heading level for a STRUCTURAL reason made a dormant rule start working
    and moved the page's type ramp. (2026-09-18, W45964)

A rule that matches nothing is not harmless. It reads as a decision that has been made, so the next editor
trusts it; and the day the markup drifts toward it, styling nobody has ever seen goes live.

THE TEST, and why it is nearly free of false positives. Markup on this platform is written two ways: in the
HTML, and in JavaScript template strings inside the same file. Both are TEXT IN THE SAME FILE. So:

    a selector token (a class name, or a heading tag) that appears ONLY inside the page's <style> blocks,
    and nowhere else in the file, cannot match anything that file renders.

That is a much weaker claim than "this selector matches the DOM right now" - it does not need a browser, it
does not care which state is rendered, and it cannot be fooled by markup built at runtime, because the
string still has to exist somewhere. It catches exactly the case where the stylesheet and the renderer have
drifted apart.

Descendant rules keyed on a heading tag (`.container h3`) are checked too: if the file contains no `<h3` at
all, the rule is dead no matter what the container does.

★A TAG RULE IS A WEAKER SIGNAL THAN A DEAD CLASS, AND THIS TOOL FOUND ITS OWN FALSE-POSITIVE CLASS ON ITS
SECOND OUTING (2026-09-18). It flagged `.prose-wh h3` on about/, privacy-policy/ and terms-of-service/. All
three are genuinely dead THERE - each page emits only h1 and h2. But `.prose-wh` is a shared prose block
copied byte-identically into 57 pages (the three root copies share one md5), and NINE of the 54 learn pages
DO emit an <h3> - so the rule is alive on the set and merely unused on these three. Deleting it from the
three would fragment a block that is identical everywhere, which is precisely the drift the .wh-help
three-copy lesson is about.

No mechanical test separates that from the REAL case this tool was built for. On marketplace-seller,
`.empty-state h3` was flagged while `.empty-state` itself WAS emitted - structurally identical to about/,
and yet a true defect, because a component's heading level is a fixed contract while a prose page may
legitimately have no h3. The discriminator is judgement, not a predicate.

So this gate is a RATCHET, not a verdict. Its baseline is a list of things to LOOK at; a RISE is the
failure. A dead CLASS token is close to conclusive - nothing in the file renders that name. A dead TAG
token means only "this rule does not reach this page", which may be drift or may be a shared block doing
its job elsewhere: check whether the same selector is alive on a sibling page before touching it.

RUN:  python tools/prove_css_rules_reach_markup.py --check
      python tools/prove_css_rules_reach_markup.py --rebase   (only ever lowers)
      python tools/prove_css_rules_reach_markup.py --self-test
"""
import argparse
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "css_rules_reach_markup_baseline.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SKIP_DIRS = ("test-data-seeder", "seo_assets", "_fixtures", "node_modules", ".tmp", "clonebase")

# Classes that belong to shared chrome or to a state another file adds. A page may legitimately style a
# class it never writes itself - nav-hub.js, utils.js and components.css all inject markup into it.
SHARED_PREFIXES = ("wh-", "ic-", "ic ", "nav-", "hub-", "companion-", "sr-only", "skip-")

STYLE_BLOCK = re.compile(r"<style[^>]*>([\s\S]*?)</style>", re.I)
# a rule head: everything before the { of a declaration block, excluding at-rules
RULE_HEAD = re.compile(r"(^|[}\n])\s*([^{}@/][^{}]*?)\s*\{", re.M)
CLASS_TOKEN = re.compile(r"\.(-?[_a-zA-Z][\w-]*)")
HEADING_TOKEN = re.compile(r"(?:^|[\s>+~])(h[1-6])(?=[\s>+~.:\[]|$)")


# ★Reachability for a class the renderer BUILDS rather than writes. See the note at the call site.
_INTERP_OPENERS = ("${", "' +", '" +', "'+", '"+')


def _prefix_is_interpolated(cls: str, rest: str) -> bool:
    """True when some dash-prefix of `cls` is immediately followed by an interpolation in `rest`."""
    parts = cls.split("-")
    # longest prefix first: `a-b-` before `a-`; a single-segment class has no prefix to test
    for n in range(len(parts) - 1, 0, -1):
        prefix = "-".join(parts[:n]) + "-"
        for opener in _INTERP_OPENERS:
            if prefix + opener in rest:
                return True
    return False


def _strip_css_comments(css: str) -> str:
    return re.sub(r"/\*[\s\S]*?\*/", " ", css)


def _pages():
    out = []
    for pat in ("*.html", "*/index.html"):
        for p in sorted(ROOT.glob(pat)):
            rel = p.relative_to(ROOT).as_posix()
            if any(s in rel for s in SKIP_DIRS):
                continue
            out.append(p)
    return out


def scan_page(path: Path):
    """[(selector, token, kind)] for every rule token that appears only inside this page's <style>."""
    try:
        src = io.open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return []

    styles = STYLE_BLOCK.findall(src)
    if not styles:
        return []
    css = _strip_css_comments("\n".join(styles))

    # everything in the file that is NOT inside a <style> block: markup, JS template strings, attributes
    rest = STYLE_BLOCK.sub(" ", src)

    dead = []
    seen = set()
    for m in RULE_HEAD.finditer(css):
        head = m.group(2).strip()
        if not head or head.startswith(("@", "/*", "-")):
            continue
        # one rule head can carry several comma-separated selectors
        for sel in head.split(","):
            sel = sel.strip()
            if not sel or len(sel) > 200:
                continue

            for cm in CLASS_TOKEN.finditer(sel):
                cls = cm.group(1)
                if cls.startswith(SHARED_PREFIXES) or len(cls) < 3:
                    continue
                key = ("class", cls)
                if key in seen:
                    continue
                seen.add(key)
                # does the name occur anywhere outside the stylesheet?
                if re.search(r"\b" + re.escape(cls) + r"\b", rest):
                    continue
                # ★A COMPUTED CLASS NAME NEVER APPEARS AS A LITERAL (2026-09-28). The test above rests on
                # "the string still has to exist somewhere", which holds for markup and for template
                # strings - but not when the renderer BUILDS the name from data:
                #     <span class="kind-chip kind-${escHtml(r.kind)}">
                # feedback/index.html emits exactly that, so .kind-bug / .kind-idea / .kind-question /
                # .kind-review / .kind-praise / .kind-other were all reported dead while every one of them
                # matches at runtime. A token is reachable if any of its dash-prefixes is interpolated: for
                # `kind-bug`, the file containing `kind-${` proves the renderer can produce it. Narrow on
                # purpose - it needs the prefix to sit immediately before an interpolation, so a genuinely
                # dead `.kind-bug` on a page that never builds a kind- class still fails.
                if _prefix_is_interpolated(cls, rest):
                    continue
                dead.append((sel[:70], cls, "class"))

            # a descendant rule keyed on a heading tag the file never emits
            for hm in HEADING_TOKEN.finditer(" " + sel):
                tag = hm.group(1)
                key = ("tag", sel[:70], tag)
                if key in seen:
                    continue
                seen.add(key)
                if re.search(r"<" + tag + r"\b", rest, re.I):
                    continue
                dead.append((sel[:70], tag, "tag"))
    return dead


def collect():
    per_page = {}
    for p in _pages():
        d = scan_page(p)
        if d:
            per_page[p.relative_to(ROOT).as_posix()] = d
    return per_page


def _counts(per_page):
    return {k: len(v) for k, v in sorted(per_page.items())}


def _delta(base, counts):
    """(pages that ROSE, total that FELL) - pure, so the self-test can reach the improvement branch."""
    rose = {k: (base.get(k, 0), v) for k, v in counts.items() if v > base.get(k, 0)}
    fell = sum(max(0, base.get(k, 0) - counts.get(k, 0)) for k in set(base) | set(counts))
    return rose, fell


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--rebase", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        import tempfile
        good = ("<style>.alive { color: red } .empty-state h3 { font-size: 1rem }</style>"
                "<div class='alive'><div class='empty-state'><h3>x</h3></div></div>")
        bad = ("<style>.alive { color: red } .never-emitted { color: blue }"
               " .empty-state h3 { font-size: 1rem }</style>"
               "<div class='alive'><div class='empty-state'><h2>x</h2></div></div>")
        with tempfile.TemporaryDirectory() as td:
            gp = Path(td) / "good.html"
            bp = Path(td) / "bad.html"
            gp.write_text(good, encoding="utf-8")
            bp.write_text(bad, encoding="utf-8")
            g = scan_page(gp)
            b = scan_page(bp)
        if g:
            print(f"SELF-TEST FAIL: a page whose rules all reach markup reported {len(g)}: {g}")
            return 2
        kinds = {k for _, _, k in b}
        if not ({"class", "tag"} <= kinds):
            print(f"SELF-TEST FAIL: planted a dead CLASS rule and a dead TAG rule; caught {b}")
            return 2
        # ★AND THE BRANCH THAT ONLY RUNS WHEN SOMEBODY FIXES SOMETHING (2026-09-18). The comparison read
        # `base.get(k, 0) - v` with `v` left over from the comprehension above it: a NameError that could
        # not fire on the baseline run, nor on any run where nothing moved, only on the FIRST run where a
        # count went DOWN - the run a ratchet exists to celebrate. A gate whose failure mode is "someone
        # repaired a page" is worse than no gate, because it teaches the next person to ignore it. The
        # self-test planted defects and had never planted a REPAIR, so the branch shipped unexecuted.
        rose_up, _ = _delta({"a.html": 2}, {"a.html": 5})
        rose_dn, fell_dn = _delta({"a.html": 5, "b.html": 3}, {"a.html": 2})
        if not rose_up or rose_dn or fell_dn != 6:
            print(f"SELF-TEST FAIL: delta on a rise/fall pair read {rose_up} / {rose_dn},{fell_dn}")
            return 2
        print("PASS self-test: a page whose rules all reach markup is clean, a planted dead class rule")
        print(f"   AND a planted dead heading-tag rule are both caught - {b}")
        print("   - and the comparison reports a rise as a rise and a REPAIR as 6 fallen, which is the")
        print("     branch that only ever runs after somebody fixes a page.")
        return 0

    per_page = collect()
    counts = _counts(per_page)
    total = sum(counts.values())

    base = {}
    if BASELINE.exists():
        try:
            base = json.loads(BASELINE.read_text(encoding="utf-8")).get("per_page", {})
        except (OSError, ValueError):
            base = {}

    if a.rebase or not BASELINE.exists():
        merged = {k: min(v, base.get(k, v)) for k, v in counts.items()}
        BASELINE.write_text(json.dumps({"total": sum(merged.values()), "per_page": merged},
                                       indent=1, sort_keys=True), encoding="utf-8")
        print(f"rebased: {sum(base.values()) or total} -> {sum(merged.values())} rule(s) that reach no markup")
        return 0

    rose, fell = _delta(base, counts)
    if rose:
        print("FAIL css-rules-reach-markup: a page gained a CSS rule that can reach nothing it renders.")
        print("   A rule that matches nothing reads as a decision already made, so the next editor trusts")
        print("   it - and the day the markup drifts toward it, styling nobody has seen goes live.")
        # For a TAG token, say whether the same selector is ALIVE on a sibling page. A shared prose block
        # copied into many pages is alive on the set and merely unused here - deleting it there would
        # fragment the block. See the docstring's false-positive note; this line is what saves the reader
        # the ten minutes it cost to find that out the first time.
        alive_elsewhere = {}
        for other, rows in per_page.items():
            for sel, tok, kind in rows:
                alive_elsewhere.setdefault((sel, tok), set()).add(other)
        for page, (was, now) in sorted(rose.items()):
            print(f"   - {page}: {was} -> {now}")
            for sel, tok, kind in per_page[page][:6]:
                shared = len(alive_elsewhere.get((sel, tok), ())) - 1
                where = f"  (the same rule is dead on {shared} other page(s) too - likely a shared block)" \
                        if kind == "tag" and shared else ""
                print(f"       {kind:5s} '{tok}' in  {sel}{where}")
        return 1

    extra = f" ({fell} fell - run --rebase to lower the floor)" if fell else ""
    print(f"PASS css-rules-reach-markup: {total} rule(s) reach no markup across {len(counts)} page(s), "
          f"none rose against the baseline of {sum(base.values())}{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

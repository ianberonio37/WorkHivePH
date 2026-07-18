"""
Deep-Link Param Contract Validator -- WorkHive Platform Guardian (forward-only ratchet)
=======================================================================================
Catches the DEAD-PARAM bug class (2026-06-10 Phase-6b edge walk): page A emits a link
carrying a query param that page B never reads -> the link silently no-ops. Two real
instances shipped broken for weeks: index.html emitted `asset-hub.html?tag=` from BOTH
the QR-scan quick action and the Top-At-Risk tiles while asset-hub only read `?node_id=`
(the entire scan->asset-360 loop dead, zero errors); asset-hub emitted
`marketplace.html?listing=` while marketplace's only URL parsing was the payments-gated
onboard/checkout block. Neither `validate_link_target_existence` (file exists) nor
`validate_cross_page` (INSERT payloads) can see this -- the page loads fine, the param
just does nothing.

For every emitter in HTML / JS (`href="dest.html?p=..."`, template literals,
`location.href = 'dest.html?p=' + x`), it extracts (dest, param) pairs for INTERNAL
bare-name destinations that exist on disk, then asserts the destination file contains a
reader: `.get('<param>')` / `.get("<param>")` (the platform's URLSearchParams
convention -- a quoted-string-anywhere check is too weak because column names like
'tag' appear in every `.select()`).

FORWARD-ONLY RATCHET (Mega Gate Rule B): baseline the current dead-param count; FAIL
only when it RISES (a NEW dead param). Auto-tightens as the backlog is paid down.

Self-test:  python validate_deeplink_param_contracts.py --self-test   (synthetic fixtures, never live-drift)
Baseline:   deeplink_param_contracts_baseline.json
Output:     deeplink_param_contracts_report.json
Sentinel binding: name the L2 test "test('deeplink_param_contracts: ...')".
"""
import re, json, sys
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import format_result  # noqa: E402

ROOT = Path(__file__).resolve().parent
BASELINE = ROOT / "deeplink_param_contracts_baseline.json"
REPORT = ROOT / "deeplink_param_contracts_report.json"

CHECK_NAMES = ["deeplink_params_have_readers"]
CHECK_LABELS = {
    "deeplink_params_have_readers":
        "L0  No NEW emitted deep-link param lacks a reader in its destination page "
        "(forward-only; catches the dead-?param class from the Phase-6b edge walk)",
}

# dest.html?<query> where dest is a bare internal page name (no path, no protocol).
# The char before the match must not be alphanumeric, '/', or '.' (rejects
# https://x.com/page.html?... and learn/page.html?...).
RE_EMITTER = re.compile(
    r"(?<![\w/.])([a-z0-9-]+\.html)\?([A-Za-z0-9_]+=[^\s'\"`<>]*(?:&(?:amp;)?[A-Za-z0-9_]+=[^\s'\"`<>]*)*)"
)
RE_PARAM_NAME = re.compile(r"(?:^|&(?:amp;)?)([A-Za-z_][A-Za-z0-9_]*)=")
RE_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
RE_JS_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
# Line comments: '//' not preceded by ':' (protects http:// URLs in real code).
RE_JS_LINE_COMMENT = re.compile(r"(?<!:)//[^\n]*")

# Params consumed by infrastructure, not the destination page itself.
# sw-precache cache-busters, GA/UTM tags, etc. Keep this list SHORT and justified.
INFRA_PARAMS = {
    "v", "ts", "cache", "utm_source", "utm_medium", "utm_campaign",
}


def scan_emitters(root: Path):
    """[(emitter_file, dest, param)] for internal bare-name dests that exist on disk."""
    pairs = []
    pages = {p.name for p in root.glob("*.html")}
    for f in sorted(list(root.glob("*.html")) + list(root.glob("*.js"))):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if f.suffix == ".html":
            text = RE_HTML_COMMENT.sub("", text)
        # JS comments describe URLs without emitting them (voice-handler narrates
        # "...opens from asset-hub.html?asset=P-203" in a comment) -> strip both
        # comment kinds in .js AND inside <script> bodies before scanning.
        text = RE_JS_BLOCK_COMMENT.sub("", text)
        text = RE_JS_LINE_COMMENT.sub("", text)
        for m in RE_EMITTER.finditer(text):
            dest, query = m.group(1), m.group(2)
            if dest not in pages:
                continue  # link-target-existence owns missing files
            if dest == f.name:
                continue  # self-link (history.replaceState round-trips)
            for pm in RE_PARAM_NAME.finditer(query):
                param = pm.group(1)
                if param in INFRA_PARAMS:
                    continue
                pairs.append((f.name, dest, param))
    return sorted(set(pairs))


def dest_has_reader(root: Path, dest: str, param: str) -> bool:
    """Destination reads the param via the URLSearchParams .get() convention."""
    try:
        text = (root / dest).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return True  # unreadable -> don't false-flag; existence validator owns it
    return bool(re.search(r"\.get\(\s*['\"]" + re.escape(param) + r"['\"]\s*\)", text))


def find_dead_params(root: Path):
    return sorted({
        f"{emitter} -> {dest}?{param}"
        for emitter, dest, param in scan_emitters(root)
        if not dest_has_reader(root, dest, param)
    })


def run():
    dead = find_dead_params(ROOT)
    baseline = {"count": 0, "mismatches": []}
    if BASELINE.exists():
        try:
            baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass

    if not BASELINE.exists():
        BASELINE.write_text(json.dumps({"count": len(dead), "mismatches": dead}, indent=2),
                            encoding="utf-8")
        print(f"  baseline seeded at {len(dead)} known dead param(s)")
        baseline = {"count": len(dead), "mismatches": dead}

    passed = len(dead) <= baseline.get("count", 0)
    new_items = [d for d in dead if d not in set(baseline.get("mismatches", []))]

    if passed and len(dead) < baseline.get("count", 0):
        BASELINE.write_text(json.dumps({"count": len(dead), "mismatches": dead}, indent=2),
                            encoding="utf-8")
        print(f"  baseline auto-tightened {baseline['count']} -> {len(dead)}")

    if dead:
        print(f"  current backlog ({len(dead)}): {', '.join(dead[:10])}{' ...' if len(dead) > 10 else ''}")

    issues = []
    if not passed:
        issues.append({
            "check": CHECK_NAMES[0],
            "reason": f"{len(dead)} dead param(s) vs baseline {baseline.get('count', 0)}; "
                      f"NEW: {', '.join(new_items[:5])}",
        })
    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)
    REPORT.write_text(json.dumps({"count": len(dead), "baseline": baseline.get("count", 0),
                                  "mismatches": dead, "n_fail": n_fail}, indent=2),
                      encoding="utf-8")
    print(f"\nDeep-link param contracts: {n_pass} PASS, {n_fail} FAIL, {n_skip} SKIP")
    return 1 if n_fail else 0


def self_test():
    """Synthetic fixtures (never live-drift): teeth + FP guards."""
    import tempfile
    ok = True
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # dest WITH reader; dest WITHOUT reader; self-link; external link; infra param
        (root / "dest-good.html").write_text(
            "<script>const p=new URLSearchParams(location.search);p.get('tag');</script>",
            encoding="utf-8")
        (root / "dest-dead.html").write_text(
            "<script>document.querySelector('.tag');// mentions 'tag' but never reads the param</script>",
            encoding="utf-8")
        (root / "emitter.html").write_text(
            "<a href='dest-good.html?tag=M-001'>ok</a>"
            "<a href='dest-dead.html?tag=M-001'>dead</a>"
            "<a href='emitter.html?self=1'>self</a>"
            "<a href='https://x.com/other.html?ext=1'>ext</a>"
            "<a href='dest-dead.html?utm_source=email'>infra</a>"
            "<!-- <a href='dest-dead.html?commented=1'>stripped</a> -->",
            encoding="utf-8")
        dead = find_dead_params(root)
        t1 = dead == ["emitter.html -> dest-dead.html?tag"]
        print(("PASS" if t1 else "FAIL") +
              "  teeth: dead param flagged, good/self/external/infra/commented skipped "
              f"(got {dead})")
        ok &= t1

        # template-literal + location.href emitters
        (root / "emit2.js").write_text(
            "location.href = `dest-dead.html?node=${id}`;\n"
            "window.location.href = 'dest-good.html?tag=' + encodeURIComponent(t);\n",
            encoding="utf-8")
        dead2 = find_dead_params(root)
        t2 = "emit2.js -> dest-dead.html?node" in dead2 and \
             "emit2.js -> dest-good.html?tag" not in dead2
        print(("PASS" if t2 else "FAIL") + f"  JS emitters: template+concat extracted (got {dead2})")
        ok &= t2

        # JS comments narrate URLs without emitting them -> must NOT flag
        (root / "emit3.js").write_text(
            "// When voice-journal opens from dest-dead.html?narrated=P-203 we seed it\n"
            "/* block: dest-dead.html?blocked=1 */\n"
            "const real = 'http://x.test/y'; // keep http:// intact\n",
            encoding="utf-8")
        dead2b = find_dead_params(root)
        t2b = not any("narrated" in d or "blocked" in d for d in dead2b)
        print(("PASS" if t2b else "FAIL") + f"  JS comment URLs not treated as emitters (got {dead2b})")
        ok &= t2b

        # regression guard: the REAL pre-fix bug shape (reader for another param only)
        (root / "asset-hub-sim.html").write_text(
            "<script>const params=new URLSearchParams(location.search);"
            "const n=params.get('node_id');db.select('tag,name');</script>",
            encoding="utf-8")
        (root / "index-sim.html").write_text(
            "<script>window.location.href='asset-hub-sim.html?tag='+encodeURIComponent(text);</script>",
            encoding="utf-8")
        dead3 = find_dead_params(root)
        t3 = "index-sim.html -> asset-hub-sim.html?tag" in dead3
        print(("PASS" if t3 else "FAIL") +
              f"  real-bug regression: quoted column 'tag' in select does NOT count as a reader")
        ok &= t3
    print("Self-test:", "ALL GREEN" if ok else "FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else run())

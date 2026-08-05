"""
localStorage / sessionStorage Key Consistency Validator (L0, ratcheted).
========================================================================
Catches the class where a key is `setItem`'d under one name but
`getItem`'d under a different name — cache reads return null forever
because the writer and reader disagree on the key.

Detection
  Build {key} sets per (file, action) for setItem / getItem. A key
  that appears as setItem in ANY file should also appear as getItem
  in some file (and vice versa). Orphan setItem → cache never read.
  Orphan getItem → cache never written.

Output: localstorage_key_consistency_report.json. Exit 1 on regression.
Allow with `// storage-key-allow: <reason>` near the call.
"""
from __future__ import annotations
import io, json, re, sys
from collections import defaultdict
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_PATH   = ROOT / "localstorage_key_consistency_report.json"
BASELINE_PATH = ROOT / "localstorage_key_consistency_baseline.json"

PAGES = [
    "index.html", "hive.html", "logbook.html", "inventory.html",
    "pm-scheduler.html", "analytics.html", "analytics-report.html",
    "skillmatrix.html", "community.html", "public-feed.html",
    "marketplace.html", "marketplace-seller.html", "dayplanner.html",
    "engineering-design.html", "engineering-design.js", "assistant.html", "report-sender.html",
    "platform-health.html", "project-manager.html", "integrations.html",
    "ph-intelligence.html", "project-report.html", "predictive.html",
    "ai-quality.html", "plant-connections.html", "achievements.html",
    "asset-hub.html", "shift-brain.html", "alert-hub.html",
    "audit-log.html", "voice-journal.html",
]

# (localStorage|sessionStorage).<action>('<key>'
STORAGE_RE = re.compile(
    r"""\b(?:local|session)Storage\.(?P<action>setItem|getItem|removeItem)\(\s*['"`](?P<key>[^'"`]+)['"`]""",
)

# A KEY BUILT BY A HELPER IS STILL THAT KEY. The literal-only match above reported
# `wh_draft_listing_desc_` as write-only in marketplace-seller.html and blocked a commit — but the
# draft IS read, three lines away, via `getItem(_editDraftKey(item.id))`. The write happens to inline
# its literal (`setItem('wh_draft_listing_desc_' + id, ...)`) while the read goes through the helper,
# so the detector saw a set and no get and called a working feature a bug. A false write-only report
# is worse than none: it invites someone to "fix" a draft-restore path that already works.
#
# So resolve one-line key helpers — `function _editDraftKey(id) { return 'wh_...' + id; }` — and count
# `getItem(_editDraftKey(...))` as a read of that literal. Deliberately narrow: only a helper whose
# body is a single `return '<literal>'...` qualifies, because anything more can branch between keys
# and guessing which one it returns would trade a false positive for a false negative.
KEY_HELPER_RE = re.compile(
    r"""\bfunction\s+(?P<fn>[A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{\s*return\s+['"`](?P<key>[^'"`]+)['"`]""",
)

ALLOW_RE = re.compile(r"storage-key-allow", re.IGNORECASE)
HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


# Sentinel binding: name the L2 test `test('localstorage_key_consistency: ...')` for coverage credit.
CHECK_NAMES = ["localstorage_key_consistency"]


def main() -> int:
    files: list[tuple[str, Path]] = [(n, ROOT / n) for n in PAGES]
    for js in sorted(ROOT.glob("*.js")):
        if js.name == "sw.js": continue
        files.append((js.name, js))

    # key → {action → set of files}
    key_actions: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    for name, path in files:
        if not path.exists(): continue
        body = HTML_COMMENT_RE.sub("", path.read_text(encoding="utf-8", errors="replace"))
        for m in STORAGE_RE.finditer(body):
            key = m.group("key")
            action = m.group("action")
            win = body[max(0, m.start() - 200):m.end() + 200]
            if ALLOW_RE.search(win): continue
            key_actions[key][action].add(name)

        # Second pass: keys reached through a one-line helper, in the SAME file that defines it.
        helpers = {h.group("fn"): h.group("key") for h in KEY_HELPER_RE.finditer(body)}
        if helpers:
            alt = "|".join(re.escape(f) for f in sorted(helpers))
            # (a) called inline: localStorage.getItem(_editDraftKey(item.id))
            via = re.compile(
                r"""\b(?:local|session)Storage\.(?P<action>setItem|getItem|removeItem)\(\s*"""
                r"""(?P<fn>%s)\s*\(""" % alt)
            for m in via.finditer(body):
                win = body[max(0, m.start() - 200):m.end() + 200]
                if ALLOW_RE.search(win): continue
                key_actions[helpers[m.group("fn")]][m.group("action")].add(name)

            # (b) parked in a local first — `const k = _errorKey(hiveId); ... setItem(k, ...)`.
            # Resolving only (a) is worse than resolving neither: voice-handler READS the key through
            # a direct call and WRITES it through the local, so (a) alone turned a working
            # read-and-write pair into a fresh "get-without-set". A binding is honoured only when the
            # variable name resolves to exactly ONE helper in this file; a name reused for two
            # different keys is skipped rather than guessed, since merging two keys could hide a
            # genuinely write-only one and cost the gate its teeth.
            bind: dict[str, set[str]] = defaultdict(set)
            for b in re.finditer(r"""\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(%s)\s*\(""" % alt,
                                 body):
                bind[b.group(1)].add(helpers[b.group(2)])
            unique = {v: next(iter(ks)) for v, ks in bind.items() if len(ks) == 1}
            if unique:
                vre = re.compile(
                    r"""\b(?:local|session)Storage\.(?P<action>setItem|getItem|removeItem)\(\s*"""
                    r"""(?P<var>%s)\s*[,)]""" % "|".join(re.escape(v) for v in sorted(unique)))
                for m in vre.finditer(body):
                    win = body[max(0, m.start() - 200):m.end() + 200]
                    if ALLOW_RE.search(win): continue
                    key_actions[unique[m.group("var")]][m.group("action")].add(name)

    # Drift cases:
    #   1. set with no get anywhere = write-only orphan (probably real bug)
    #   2. get with no set anywhere = read-only orphan (cache key never written)
    drift: list[dict] = []
    for key, actions in sorted(key_actions.items()):
        set_files = actions.get("setItem", set())
        get_files = actions.get("getItem", set())
        if set_files and not get_files:
            drift.append({"key": key, "kind": "set-without-get", "files": sorted(set_files)})
        elif get_files and not set_files:
            drift.append({"key": key, "kind": "get-without-set", "files": sorted(get_files)})

    baseline = 0
    if BASELINE_PATH.exists():
        try: baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("drift", 0)
        except Exception: baseline = 0
    else:
        baseline = len(drift)
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "established": True}, indent=2), encoding="utf-8")
    if len(drift) < baseline:
        baseline = len(drift)
        BASELINE_PATH.write_text(json.dumps({"drift": baseline, "tightened": True}, indent=2), encoding="utf-8")

    REPORT_PATH.write_text(json.dumps({
        "summary": {"files_scanned": len(files), "total_keys": len(key_actions),
                    "drift": len(drift), "baseline": baseline},
        "drift": drift,
    }, indent=2), encoding="utf-8")

    print(f"\nlocalStorage Key Consistency Validator (L0)")
    print("=" * 56)
    print(f"  files scanned:    {len(files)}")
    print(f"  total keys:       {len(key_actions)}")
    print(f"  drift keys:       {len(drift)}  (baseline: {baseline})")
    if not drift:
        print("\n  PASS — every storage key is set AND read somewhere.")
        return 0
    shown = 0
    for d in drift[:25]:
        print(f"  '{d['key']}'  [{d['kind']}]  → {', '.join(d['files'][:4])}{'...' if len(d['files'])>4 else ''}")
        shown += 1
    return 1 if len(drift) > baseline else 0


if __name__ == "__main__":
    sys.exit(main())

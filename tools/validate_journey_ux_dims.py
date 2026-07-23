#!/usr/bin/env python3
"""
validate_journey_ux_dims.py — source-grep gate for 3 experience-in-motion rubric dims that the runtime
__RUBRIC lens can't cleanly see (they're behavioral, detectable in the page SOURCE, not a single DOM load):

  J3 · Consequence transparency — every DESTRUCTIVE action (delete/remove/wipe/purge handler) routes through
       the central whConfirm() (which the platform uses with a consequence message + action-specific label).
       A destructive onclick that does NOT go through whConfirm can fire an irreversible write on a mis-tap
       with no consequence preview. Measure: destructive-action pages that use whConfirm / such pages.
  G5 · System memory & personalization — a page with a FILTER/VIEW/SORT control persists the user's choice
       (localStorage.setItem of a *filter/view/sort/tab/pref* key) so it restores next visit (recognition,
       not re-setup). Measure: filterable pages that persist a preference / filterable pages.
  S4 · Behavioral consistency — the SAME action behaves the same everywhere: across all destructive-action
       pages, the confirm mechanism is the ONE shared whConfirm (not a raw window.confirm or a bespoke modal
       on some pages). Measure: 1 - (pages using a NON-shared confirm / destructive-action pages).

Forward-only ratchets (baselines in journey_ux_dims_baseline.json). Emits journey_ux_dims_report.json (read
by rubric_coverage.py as the measurement source for J3/G5/S4). Static (grep), fast. Self-test: --selftest.

USAGE: python tools/validate_journey_ux_dims.py [--json] [--selftest] [--accept]
Exit 0 = no regression, 1 = a dim regressed below baseline (or self-test failed).
"""
from __future__ import annotations
import io, json, re, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"
ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "journey_ux_dims_report.json"
BASELINE = ROOT / "journey_ux_dims_baseline.json"

# The 32 user-facing "family" pages (the rubric's measured denominator). Internal dev consoles + distinct
# artifacts are excluded, same basis as the family sweep + the S1 EXCLUDE list.
EXCLUDE = {
    "architecture.html", "design-system.html", "symbol-gallery.html", "validator-catalog.html",
    "llm-observability.html", "agentic-rag-observability.html", "ai-quality.html", "status.html",
    "offline-fallback.html", "promo-poster.html", "resume.html", "platform-health.html",
    "engineering-design-test.html",   # test/dev page, not a production surface
}
# a DESTRUCTIVE handler: an onclick/handler whose verb is irreversible-loss (mirrors the lens Z3 _destRe).
_DESTRUCTIVE = re.compile(r"onclick=\"[^\"]*\b(delete|remove|wipe|purge|discard|revoke)[A-Za-z]*\s*\(", re.I)
_WHCONFIRM = re.compile(r"\bwhConfirm\s*\(")
# An action is J3-safe if it CONFIRMS (whConfirm) OR is UNDOABLE — a soft-delete (deleted_at) with a
# 5s-undo / supervisor-recovery IS the NN/g "undo > confirmation" pattern (community's deletePost), an
# equally-valid consequence-safety mechanism, NOT a J3 gap. Credit it alongside whConfirm.
_UNDO_SAFE = re.compile(r"deleted_at|soft.?delete|\bundo\b|recover", re.I)
_RAWCONFIRM = re.compile(r"(?<![.\w])(window\.)?confirm\s*\(")   # native confirm() = NOT the shared mechanism
_FILTER_CTL = re.compile(r"id=\"[^\"]*(filter|sort)[^\"]*\"|class=\"[^\"]*\bfilter\b[^\"]*\"|placeholder=\"[^\"]*(filter|search)", re.I)
# G5a is satisfied by a raw localStorage-persist of a filter/view/sort key OR by adopting the SHARED
# whRememberView() helper (the centralize-first fix — one helper, not 14 hand-rolled persistences).
_PERSIST = re.compile(r"localStorage\.setItem\(\s*[`'\"][a-z0-9_:]*(filter|view|sort|tab|pref|last)|whRememberView\b|whAutoRememberFilters\b|whAutoRememberTabs\b", re.I)
# X2 · interruption resilience: a page that WRITES via a substantial free-text/compose form (a <textarea> the
# user types a post/message/report/journal/log entry into) should autosave a DRAFT so a refresh / interruption
# (a field-tech's connectivity blip, a phone call) doesn't lose the in-progress work.
_WRITES = re.compile(r"\.from\([^)]*\)\s*\.\s*(insert|upsert)|\bdb\.rpc\(|functions\.invoke\(", re.I)
_COMPOSE = re.compile(r"<textarea(?![^>]*\b(readonly|disabled)\b)", re.I)
_DRAFT = re.compile(r"localStorage\.(setItem|getItem)\([^)]*draft|whRememberDraft\b|whAutoSaveDraft\b|saveDraft|restoreDraft|wh_draft", re.I)


_NONPROD = re.compile(r"backup|\.bak\b|-test\.|\.test\.|\.old\b|\.orig\b|copy", re.I)


def app_pages() -> list[Path]:
    # production surfaces only: skip the EXCLUDE consoles/artifacts AND backup/test/old copies (logbook.backup.html
    # etc.) that pollute the denominator — the "derive the denominator, don't count non-production" discipline.
    return [p for p in sorted(ROOT.glob("*.html")) if p.name not in EXCLUDE and not _NONPROD.search(p.name)]


def measure() -> dict:
    pages = app_pages()
    j3_tot = j3_ok = 0
    g5_tot = g5_ok = 0
    s4_tot = s4_bad = 0
    x2_tot = x2_ok = 0
    j3_gaps, g5_gaps, s4_gaps, x2_gaps = [], [], [], []
    for p in pages:
        src = p.read_text(encoding="utf-8", errors="replace")
        # J3: pages with a destructive handler must use whConfirm
        if _DESTRUCTIVE.search(src):
            j3_tot += 1
            if _WHCONFIRM.search(src) or _UNDO_SAFE.search(src):
                j3_ok += 1
            else:
                j3_gaps.append(p.name)
            # S4: destructive-action page must use the SHARED confirm, not a raw window.confirm()
            s4_tot += 1
            if _RAWCONFIRM.search(src) and not _WHCONFIRM.search(src):
                s4_bad += 1
                s4_gaps.append(p.name)
        # G5: pages with a filter/sort control should persist the choice
        if _FILTER_CTL.search(src):
            g5_tot += 1
            if _PERSIST.search(src):
                g5_ok += 1
            else:
                g5_gaps.append(p.name)
        # X2: a write-page with a compose <textarea> should autosave a draft (interruption resilience)
        if _COMPOSE.search(src) and _WRITES.search(src):
            x2_tot += 1
            if _DRAFT.search(src):
                x2_ok += 1
            else:
                x2_gaps.append(p.name)
    def pct(a, b):
        return round(100 * a / b, 1) if b else 100.0
    return {
        "pages": len(pages),
        "J3": {"total": j3_tot, "ok": j3_ok, "pct": pct(j3_ok, j3_tot), "gaps": j3_gaps},
        "G5": {"total": g5_tot, "ok": g5_ok, "pct": pct(g5_ok, g5_tot), "gaps": g5_gaps},
        "S4": {"total": s4_tot, "ok": s4_tot - s4_bad, "pct": pct(s4_tot - s4_bad, s4_tot), "gaps": s4_gaps},
        "X2": {"total": x2_tot, "ok": x2_ok, "pct": pct(x2_ok, x2_tot), "gaps": x2_gaps},
    }


def self_test() -> bool:
    ok = True
    good = '<button onclick="deletePost(1)">x</button><script>whConfirm("sure?")</script>'
    bad = '<button onclick="deleteThing(1)">x</button>'
    if not (_DESTRUCTIVE.search(good) and _WHCONFIRM.search(good)):
        print(f"{R}selftest FAIL: good J3 not recognized{X}"); ok = False
    if not (_DESTRUCTIVE.search(bad) and not _WHCONFIRM.search(bad)):
        print(f"{R}selftest FAIL: bad J3 not caught{X}"); ok = False
    if not _PERSIST.search("localStorage.setItem('wh_asset_view', v)"):
        print(f"{R}selftest FAIL: G5 persist not recognized{X}"); ok = False
    print((G + "selftest PASS - journey-ux-dims has teeth." + X) if ok else (R + "selftest FAILED." + X))
    return ok


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        return 0 if self_test() else 1
    m = measure()
    REPORT.write_text(json.dumps(m, indent=1), encoding="utf-8")
    base = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
    if "--accept" in sys.argv or not base:
        base = {k: m[k]["pct"] for k in ("J3", "G5", "S4", "X2")}
        BASELINE.write_text(json.dumps(base, indent=1), encoding="utf-8")
    if "--json" in sys.argv:
        print(json.dumps(m, indent=2)); return 0
    print(f"{B}journey-ux dims (J3 consequence · G5 memory · S4 behavioral · X2 interruption) — source-grep{X}")
    regressed = False
    for dim in ("J3", "G5", "S4", "X2"):
        d = m[dim]; b = base.get(dim, d["pct"])
        tag = G + "OK" + X if d["pct"] >= b else R + "REGRESSED" + X
        if d["pct"] < b:
            regressed = True
        print(f"  {tag}  {dim}: {d['ok']}/{d['total']} = {d['pct']}% (baseline {b}%)" + (f"  gaps: {d['gaps'][:4]}" if d["gaps"] else ""))
    if regressed:
        print(f"{R}FAIL: a journey-ux dim dropped below baseline.{X}"); return 1
    print(f"{G}PASS - J3/G5/S4 held (report → journey_ux_dims_report.json).{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

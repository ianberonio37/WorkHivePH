"""
page_evidence.py — Content Grounding Gate, capability-grounding SUBSTRATE.
=========================================================================
The page is the only ground truth for what a feature can DO. This extracts, per
feature page, the page's REAL affordances from the authored HTML — headings,
button/CTA/data-action labels, form fields, tabs, and the features it actually
links to (the TRUE connects_to). That evidence block is what a product claim in
a learn article / landing / video script must trace to, or it is invented.

Deterministic + offline (parses the .html on disk). Playwright augments only for
end-to-end verification, never as a gate runtime dependency. This — not
platform_intel.loop_role (itself hand-written copy) — is the capability source.

Output: page_evidence.json  { feature_id: {route, title, headings, actions,
fields, tabs, links_to, vocab} }. `vocab` is the normalized token set used by
the capability_drift grounding check.

CLI:
    python tools/page_evidence.py            # build page_evidence.json
    python tools/page_evidence.py --print FEATURE_ID
    python tools/page_evidence.py --self-test
"""
from __future__ import annotations

import re
import sys
import json
import html
from pathlib import Path
from datetime import datetime, timezone

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import platform_catalog as pc  # noqa: E402

EVIDENCE_PATH = ROOT / "page_evidence.json"

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_STOP = pc._STOPWORDS | {
    "click", "here", "page", "view", "see", "all", "back", "close", "open", "new",
    "add", "save", "cancel", "ok", "yes", "no", "loading", "this", "that", "with",
    "from", "into", "more", "less", "show", "hide", "menu", "home",
}


def _text(s: str) -> str:
    return _WS.sub(" ", html.unescape(_TAG.sub(" ", s or ""))).strip()


def _toks(s: str) -> set:
    return {t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if len(t) > 2 and t not in _STOP}


def _dedup_keep_order(items, limit):
    seen, out = set(), []
    for it in items:
        k = it.lower().strip()
        if k and k not in seen:
            seen.add(k)
            out.append(it.strip())
        if len(out) >= limit:
            break
    return out


def extract_page(html_text: str, catalog_routes: set, feature_id: str | None = None) -> dict:
    """Pull the real affordance vocabulary from one page's authored HTML."""
    title_m = re.search(r"<title>(.*?)</title>", html_text, re.DOTALL | re.I)
    title = re.sub(r"\s*\|\s*WorkHive.*$", "", _text(title_m.group(1)) if title_m else "").strip()

    headings = _dedup_keep_order(
        [_text(m) for m in re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html_text, re.DOTALL | re.I)], 40)

    # Actions = button text + CTA-ish anchors + data-action verbs + aria/title on buttons.
    btn_text = [_text(m) for m in re.findall(r"<button[^>]*>(.*?)</button>", html_text, re.DOTALL | re.I)]
    data_actions = re.findall(r'data-action=["\']([^"\']+)["\']', html_text)
    aria = re.findall(r'aria-label=["\']([^"\']+)["\']', html_text)
    title_attrs = re.findall(r'<button[^>]*\stitle=["\']([^"\']+)["\']', html_text)
    actions = _dedup_keep_order(
        [a for a in (btn_text + [d.replace("-", " ") for d in data_actions] + aria + title_attrs)
         if a and len(a) <= 60], 60)

    fields = _dedup_keep_order(
        [_text(m) for m in re.findall(r"<label[^>]*>(.*?)</label>", html_text, re.DOTALL | re.I)]
        + re.findall(r'placeholder=["\']([^"\']+)["\']', html_text), 40)

    tabs = _dedup_keep_order(
        re.findall(r'data-tab=["\']([^"\']+)["\']', html_text)
        + [_text(m) for m in re.findall(r'role=["\']tab["\'][^>]*>(.*?)<', html_text, re.I)], 24)

    # Real outbound links to OTHER feature pages = the true connects_to.
    linked = {h.lstrip("/") for h in re.findall(r'href=["\']/?([a-z0-9-]+\.html)["\']', html_text)}
    links_to = sorted({pc._href_stem(h) for h in linked
                       if h in catalog_routes and (feature_id is None or pc._href_stem(h) != feature_id)})

    vocab = set()
    for bucket in (headings, actions, fields, tabs, [title]):
        for item in bucket:
            vocab |= _toks(item)

    return {
        "title":    title,
        "headings": headings,
        "actions":  actions,
        "fields":   fields,
        "tabs":     tabs,
        "links_to": links_to,
        "vocab":    sorted(vocab),
    }


def build_evidence(catalog: dict | None = None) -> dict:
    cat = catalog or pc.build_catalog()
    routes = {f["route"] for f in cat["features"] if f["route"]}
    evidence = {}
    for f in cat["features"]:
        if not f["route"]:
            continue
        page = ROOT / f["route"]
        if not page.exists():
            continue
        ev = extract_page(pc._read(page), routes, feature_id=f["id"])
        ev["route"] = f["route"]
        ev["feature"] = f["name"]
        evidence[f["id"]] = ev
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator":    "page_evidence.py",
        "evidence":     evidence,
    }


def write_evidence(path: Path = EVIDENCE_PATH) -> dict:
    out = build_evidence()
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def load_evidence() -> dict:
    if EVIDENCE_PATH.exists():
        try:
            return json.loads(EVIDENCE_PATH.read_text(encoding="utf-8")).get("evidence", {})
        except Exception:
            return {}
    return build_evidence()["evidence"]


# ── Self-test ─────────────────────────────────────────────────────────────────

def self_test() -> int:
    def ok(label):  print(f"  \033[92mPASS\033[0m  {label}")
    def bad(label): print(f"  \033[91mFAIL\033[0m  {label}")
    print("\n\033[1mpage_evidence.py --self-test\033[0m")
    print("=" * 55)
    fails = 0

    def check(cond, label):
        nonlocal fails
        (ok if cond else bad)(label)
        if not cond:
            fails += 1

    out = build_evidence()
    ev = out["evidence"]
    check(len(ev) >= 18, f"evidence extracted for the routed features ({len(ev)})")
    check(all(set(("route", "headings", "actions", "vocab", "links_to")) <= set(v) for v in ev.values()),
          "every evidence block has route/headings/actions/vocab/links_to")

    lb = ev.get("logbook", {})
    check(bool(lb) and len(lb.get("vocab", [])) >= 10,
          f"logbook page yields a real affordance vocabulary ({len(lb.get('vocab', []))} tokens)")
    check("logbook" in (lb.get("vocab", []) or []) or "log" in (lb.get("vocab", []) or [])
          or any("log" in a.lower() for a in lb.get("actions", [])),
          "logbook evidence actually mentions logging affordances")

    # Discriminating: a real affordance grounds; an invented one does not.
    vocab = set(lb.get("vocab", []))
    check("teleport" not in vocab and "blockchain" not in vocab,
          "evidence does NOT contain invented affordances (teleport/blockchain)")

    # links_to should surface real interconnections (the true connects_to).
    any_links = any(v.get("links_to") for v in ev.values())
    check(any_links, "at least one page exposes real outbound feature links (true connects_to)")

    print("=" * 55)
    if fails == 0:
        print("\033[92m  self-test PASS\033[0m\n")
    else:
        print(f"\033[91m  self-test FAIL — {fails} check(s)\033[0m\n")
    return 1 if fails else 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    if "--print" in argv:
        i = argv.index("--print")
        fid = argv[i + 1] if i + 1 < len(argv) else "logbook"
        ev = load_evidence().get(fid)
        print(json.dumps(ev, indent=2, ensure_ascii=False) if ev else f"no evidence for {fid!r}")
        return 0
    out = write_evidence()
    n = len(out["evidence"])
    tot_actions = sum(len(v["actions"]) for v in out["evidence"].values())
    print(f"\nPage evidence: {n} feature pages, {tot_actions} affordances extracted.")
    print(f"  → {EVIDENCE_PATH.name}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

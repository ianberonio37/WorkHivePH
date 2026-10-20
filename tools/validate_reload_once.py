#!/usr/bin/env python3
"""reload-once - SL AV4 (2026-10-20): the platform recovers a page with AT MOST ONE automatic reload, and never a loop -
not under a fault the reload cannot fix, and not under a network that keeps flapping.

WHAT THE AV4 WALK FOUND (receipts SL1621-SL1644: 24 pages, phone-390 and desktop-1280, each as its row's cast, every
probe in a FRESH tab - every reload guard lives in sessionStorage, per tab - under five conditions: clean; the skew heal
stuck (every utils.js, the refetch too, is yesterday's); the stored hive lost at every document start; a worker change
after every load; the database unreachable while the network flapped offline/online every 3 s):
  * the skew heal, the hive recovery and the worker handoff each held: one reload, then the guard (2 loads at most).
  * the FLAP looped. public-feed and logbook reloaded on EVERY reconnect - 12 loads in 35 s, for as long as it lasted -
    because a failed read's Retry is very often location.reload() (the settle pass's own and a dozen pages'), and the
    unattended-screen auto-retry (T126) re-ran it on each 'online'. llm-observability's "could not check your access"
    card reloaded on every reconnect too (every ~10 s: the client's 7 s back-off, then the next flap), and so did four
    more admin pages and the offline fallback. 'online' is about the Wi-Fi, not the database.

WHAT THIS HOLDS (static; the walk is the live floor, auto-read-retry its behavioural test):
  1. A reconnect round asks the database first - whServerAnswers: one HEAD on a public view, its own 5 s budget, one in
     flight at a time, any answer under 500 - and re-runs nothing if it does not answer.
  2. A retry that reloads is an automatic reload: at most once until the page has loaded clean (whAutoReloadAllowed and
     the 20 s clean-load reset). A person's own Retry press is never limited.
  3. A page that closed itself for want of the server reloads through whReloadWhenBack (ask first, once) - no bare
     "reload on every 'online'" is left on any page; the offline fallback asks the site first and reloads once a minute.
  4. The three guards that already held stay in place: the skew heal's wh_utils_refetched, the hive recovery's
     wh_hive_recovered, the worker handoff's 60 s wh_one_build_reload.

    python tools/validate_reload_once.py
    python tools/validate_reload_once.py --self-test
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

ANCHORS = [
    ("utils.js", r"function whServerAnswers\(timeoutMs\) \{\s*if \(_whProbeBusy\) return _whProbeBusy;",
     "a reconnect no longer asks the database before re-running failed reads (or probes pile up, one per flap)"),
    ("utils.js", r"method: 'HEAD', cache: 'no-store', headers: \{ apikey: window\.WH_SUPABASE_ANON_KEY \|\| '' \}",
     "the database probe is no longer one cheap HEAD"),
    ("utils.js", r"\}, timeoutMs \|\| 5000\);", "the database probe lost its own 5 s budget"),
    ("utils.js", r"\.then\(function \(r\) \{ return !!r && r\.status < 500; \}, function \(\) \{ return false; \}\)",
     "the probe no longer counts any answer under 500 as an answer (or a network failure as none)"),
    ("utils.js", r"whServerAnswers\(\)\.then\(function \(ok\) \{\s*if \(!ok\) \{[^}]*return; \}\s*_whRunAutoRetriesNow\(reason\);",
     "the reconnect auto-retry re-runs failed reads (and their reloads) while the database does not answer"),
    ("utils.js", r"if \(_whRetryReloads\(rec\.fn\) && !whAutoReloadAllowed\('auto-retry ' \+ reason\)\) return true;",
     "a retry that reloads the page runs on every reconnect - the flap loop"),
    ("utils.js", r"return /\\blocation\\\.reload\\s\*\\\(/\.test\(Function\.prototype\.toString\.call\(fn\)\);",
     "the auto-retry can no longer tell a retry that reloads from one that re-reads"),
    ("utils.js", r"if \(last && last\.href === location\.href\) return false;\s*sessionStorage\.setItem\(WH_AUTO_RELOAD_KEY",
     "an automatic reload is allowed more than once before the page has loaded clean"),
    ("utils.js", r"why: String\(why \|\| ''\) \}\)\);\s*return true;\s*\} catch \(_\) \{ return false; \}",
     "with storage blocked an automatic reload has no guard and still runs"),
    ("utils.js", r"if \(document\.querySelector\('\.wh-list-error'\)\) return;\s*if \(window\._whConnFailedSvcs && Object\.keys\(window\._whConnFailedSvcs\)\.length\) return;\s*sessionStorage\.removeItem\(WH_AUTO_RELOAD_KEY\);",
     "the clean-load reset clears the guard on a page that is still failing (or never clears it)"),
    ("utils.js", r"function whReloadWhenBack\(\) \{", "the shared reconnect reload is gone"),
    ("utils.js", r"if \(ok && whAutoReloadAllowed\('reconnect'\)\) \{ location\.reload\(\); return; \}",
     "whReloadWhenBack reloads without asking the database, or more than once"),
    # the three guards that already held
    ("utils.js", r"if \(sessionStorage\.getItem\('wh_hive_recovered'\)\) return;", "the hive recovery can reload on every load"),
    ("utils.js", r"try \{ sessionStorage\.setItem\('wh_hive_recovered', seated \? '1' : 'none'\); \} catch \(_\) \{ return;\s*\}\s*if \(seated\) location\.reload\(\);",
     "the hive recovery reloads without its guard"),
    ("utils.js", r"var key = 'wh_one_build_reload';[\s\S]{0,200}if \(last && last\.href === location\.href && Date\.now\(\) - last\.at < 60000\) return;",
     "the worker handoff's reload lost its loop guard"),
    ("tools/render_skew_heal.py", r"wh_utils_refetched", "the skew heal's once-per-tab guard is gone from its generator"),
    # the pages that closed themselves for want of the server
    ("llm-observability.html", r"if \(typeof whReloadWhenBack === 'function'\) whReloadWhenBack\(\);", "llm-observability reloads on every reconnect"),
    ("platform-actions.html", r"if \(typeof whReloadWhenBack === 'function'\) whReloadWhenBack\(\);", "platform-actions reloads on every reconnect"),
    ("founder-console.html", r"if \(typeof whReloadWhenBack === 'function'\) whReloadWhenBack\(\);", "founder-console reloads on every reconnect"),
    ("agentic-rag-observability.html", r"if \(typeof whReloadWhenBack === 'function'\) whReloadWhenBack\(\);", "agentic-rag-observability reloads on every reconnect"),
    ("marketplace-admin.html", r"if \(typeof whReloadWhenBack === 'function'\) whReloadWhenBack\(\);", "marketplace-admin reloads on every reconnect"),
    ("offline-fallback.html", r"fetch\(location\.href, \{ method: 'HEAD', cache: 'no-store'",
     "the offline fallback reloads without asking whether the site answers"),
    ("offline-fallback.html", r"if \(last && last\.href === location\.href && Date\.now\(\) - last\.at < 60000\) return;",
     "the offline fallback reloads on every flap"),
]


def _code(src: str) -> str:
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    src = re.sub(r"<!--[\s\S]*?-->", "", src)
    return re.sub(r"(?m)(?<![:\"'`\\/])//[^\n]*$", "", src)


# a reload on 'online' with nothing between them is the loop; the only allowed form is the fallback after whReloadWhenBack
BARE_ONLINE_RELOAD = re.compile(r"addEventListener\(\s*['\"]online['\"]\s*,\s*(?:\(\)\s*=>|function\s*\(\)\s*\{)\s*(?:window\.)?location\.reload\(\)")


def bare_online_reloads(name: str, src: str) -> list[str]:
    out = []
    code = _code(src)
    for m in BARE_ONLINE_RELOAD.finditer(code):
        before = code[max(0, m.start() - 200):m.start()]
        if re.search(r"if \(typeof whReloadWhenBack === 'function'\) whReloadWhenBack\(\);\s*else window\.$", before):
            continue
        out.append(f"{name}: a bare reload on every 'online' - it loops while the server is still out of reach")
    return out


def problems(files: dict[str, str]) -> list[str]:
    bad = []
    for f, rx, why in ANCHORS:
        if not re.search(rx, _code(files.get(f, "")) if f.endswith((".js", ".html")) else files.get(f, "")):
            bad.append(f"{f}: {why}")
    for f, src in files.items():
        if f.endswith((".html", ".js")):
            bad.extend(bare_online_reloads(f, src))
    return bad


def load() -> dict[str, str]:
    names = {a[0] for a in ANCHORS}
    for p in list(ROOT.glob("*.html")) + list(ROOT.glob("*.js")):
        t = p.read_text(encoding="utf-8", errors="replace")
        if "'online'" in t or '"online"' in t:
            names.add(p.name)
    return {f: (ROOT / f).read_text(encoding="utf-8") for f in sorted(names)}


def run() -> int:
    bad = problems(load())
    if bad:
        for b in bad:
            print("  FAIL " + b)
        print(f"FAIL reload-once - {len(bad)} problem(s)")
        return 1
    print(f"PASS reload-once - a reconnect asks the database before re-running anything, a retry that reloads runs once "
          f"until the page loads clean, every reconnect reload goes through whReloadWhenBack, and the skew heal, hive "
          f"recovery and worker handoff keep their guards; {len(ANCHORS)} anchors hold, no bare reload-on-online")
    return 0


def self_test() -> int:
    ok = True

    def expect(name, cond):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + name)
        ok = ok and cond
    files = load()
    expect("the real tree passes", not problems(files))

    def mut(f, a, b):
        m = dict(files)
        assert a in m[f], (f, a[:60])
        m[f] = m[f].replace(a, b, 1)
        return bool([x for x in problems(m) if x.startswith(f + ":")])
    expect("the reconnect round without the database question fails", mut("utils.js",
        "    if (!ok) { if (typeof console !== 'undefined' && console.info) console.info('[wh] reconnect: the database did not answer, so no failed read was re-run'); return; }\n",
        ""))
    expect("a reload retry without its guard fails", mut("utils.js",
        "    if (_whRetryReloads(rec.fn) && !whAutoReloadAllowed('auto-retry ' + reason)) return true;   // reloaded once already\n", ""))
    expect("an automatic reload allowed every time fails", mut("utils.js",
        "if (last && last.href === location.href) return false;   // once until a clean load clears it: never a loop", "if (false) return false;"))
    expect("a reset that ignores a failing page fails", mut("utils.js",
        "        if (document.querySelector('.wh-list-error')) return;\n", ""))
    expect("whReloadWhenBack reloading without asking fails", mut("utils.js",
        "if (ok && whAutoReloadAllowed('reconnect')) { location.reload(); return; }", "location.reload(); return;"))
    expect("the hive recovery without its guard fails", mut("utils.js",
        "if (sessionStorage.getItem('wh_hive_recovered')) return;", ""))
    expect("an admin page back to a bare reload fails", mut("llm-observability.html",
        "if (typeof whReloadWhenBack === 'function') whReloadWhenBack();", "if (false) whReloadWhenBack();"))
    expect("a NEW bare reload-on-online anywhere fails", bool(bare_online_reloads("new.html", "window.addEventListener('online', () => location.reload());")))
    expect("the function form is caught too", bool(bare_online_reloads("new.html", "window.addEventListener('online', function () { location.reload(); }, { once: true });")))
    expect("the guarded fallback stays allowed", not bare_online_reloads("x.html",
        "if (typeof whReloadWhenBack === 'function') whReloadWhenBack();\n        else window.addEventListener('online', () => location.reload(), { once: true });"))
    expect("the offline fallback reloading on every flap fails", mut("offline-fallback.html",
        "if (last && last.href === location.href && Date.now() - last.at < 60000) return;", ""))
    print("PASS self-test" if ok else "FAIL self-test")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else run())

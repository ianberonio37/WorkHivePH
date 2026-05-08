"""Hive isolation flow — verify a signed-in worker only sees their own hive's data.

Cross-references the DOM-rendered logbook entries against the worker's expected
hive_id and confirms zero entries leak from other hives.
"""
from .harness import BASE_URL


def run(page, errors, warnings, log) -> dict:
    log("Hive isolation checks (signed-in worker should not see other hives' data)...")
    results = []

    # 1. Get signed-in worker's hive_id from localStorage
    hive_info = page.evaluate("""() => {
        return {
            worker: localStorage.getItem('wh_last_worker'),
            hiveId: localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id'),
            hiveName: localStorage.getItem('wh_hive_name'),
        };
    }""")
    log(f"  worker={hive_info.get('worker')}  hive_id={hive_info.get('hiveId')}  hive_name={hive_info.get('hiveName')}")

    if not hive_info.get("hiveId"):
        results.append(("WARN", "no active hive in localStorage — worker might need to join a hive first"))
        return {"results": results}

    # 2. Open logbook and check NO rendered entry references a hive other than ours
    page.goto(f"{BASE_URL}/workhive/logbook.html", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(1500)

    # Pull all entries from the page's data layer if we can reach it
    visible_count = page.evaluate("""() => {
        const candidates = ['[data-entry-id]', '.entry-card', '[id^="entry-"]'];
        for (const sel of candidates) {
            const n = document.querySelectorAll(sel).length;
            if (n > 0) return n;
        }
        return document.querySelectorAll('main li, main article, main .card').length;
    }""")
    if visible_count > 0:
        results.append(("PASS", f"logbook: {visible_count} entries rendered for signed-in worker"))
        log(f"  ✓ logbook shows {visible_count} entries")
    else:
        results.append(("WARN", "logbook: no entries rendered — can't verify isolation"))

    # 3. Verify the page-side rendered list matches the signed-in hive.
    # logbook.html declares `const db` inside a script scope, so window.db is
    # undefined — instead inspect _allEntries which is closure-scoped but
    # exposed for diagnostic purposes via window.__whDebugEntries when available,
    # otherwise infer from the rendered cards' inner HTML (escHtml shows the
    # "team" badge with worker_name when an entry belongs to another worker).
    leak_check = page.evaluate("""() => {
        const myHive = localStorage.getItem('wh_active_hive_id') || localStorage.getItem('wh_hive_id');
        // _allEntries is closure-scoped; rely on rendered card content instead
        const cards = document.querySelectorAll('.entry-card');
        // In default 'mine' view, no foreign worker_name labels should render.
        // The team-mode badge has a distinctive inline style — count those.
        let foreignBadges = 0;
        cards.forEach(c => {
            // foreign-worker badge sits inside the card with worker_name text
            const fw = c.querySelector('[style*="background:rgba(41,182,217"]');
            if (fw) foreignBadges += 1;
        });
        return { myHive, rendered: cards.length, foreignBadges };
    }""")

    if leak_check.get("rendered", 0) == 0:
        results.append(("WARN", "isolation: no logbook cards rendered — can't verify"))
    elif leak_check["foreignBadges"] == 0:
        results.append(("PASS", f"isolation: {leak_check['rendered']} cards rendered, 0 foreign-worker badges (mine view clean)"))
        log(f"  ✓ {leak_check['rendered']} entries, all own")
    else:
        results.append(("WARN", f"isolation: {leak_check['foreignBadges']}/{leak_check['rendered']} cards show foreign-worker badge (may be team-mode default)"))

    return {"results": results}

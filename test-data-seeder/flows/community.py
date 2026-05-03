"""Community page UI checks after sign-in."""
from .harness import BASE_URL, screenshot


def run(page, errors, warnings, log) -> dict:
    log("Community UI checks...")
    results = []

    page.goto(f"{BASE_URL}/workhive/community.html", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(1500)

    # Check 1: posts visible
    try:
        post_count = page.evaluate("""() => {
            const candidates = ['[data-post-id]', '.community-post', '.post-card', '[id^="post-"]'];
            for (const sel of candidates) {
                const n = document.querySelectorAll(sel).length;
                if (n > 0) return n;
            }
            return document.querySelectorAll('main article, main .card').length;
        }""")
        if post_count > 0:
            results.append(("PASS", f"community posts rendered: {post_count}"))
            log(f"  ✓ {post_count} posts rendered")
        else:
            results.append(("FAIL", "no community posts rendered"))
            log(f"  ✗ 0 posts rendered (expected ~30 in this hive)")
    except Exception as e:
        results.append(("FAIL", f"post-count crashed: {e}"))

    # Check 2: category labels visible
    try:
        page_text = page.locator("body").inner_text()
        cats = ["general", "safety", "technical", "announcement", "General", "Safety", "Technical", "Announcement"]
        found = [c for c in cats if c in page_text]
        if found:
            results.append(("PASS", f"category labels found: {found[:4]}"))
            log(f"  ✓ category labels visible")
        else:
            results.append(("WARN", "no community category labels visible"))
    except Exception as e:
        results.append(("FAIL", f"category check crashed: {e}"))

    screenshot(page, "community_feed")
    return {"results": results}

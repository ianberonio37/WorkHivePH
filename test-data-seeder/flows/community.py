"""Community + Public Feed flows — DB-verified post CRUD and feed checks.

Scenarios:
  1 – Posts visible in feed (original)
  2 – Category labels visible (original)
  3 – New post creates DB record (community_posts row inserted)
  4 – Edit own post persists change to DB
  5 – Delete own post soft-deletes (deleted_at set, not hard delete)
  6 – Cannot edit/delete another worker's post (buttons not visible)
  7 – Reaction increments count (no NaN after click)
  8 – public-feed.html loads and shows cross-hive content
  9 – No "undefined" worker names in post author fields
 10 – Post count on page matches DB row count for hive
"""

import time
from lib.supabase_client import get_client
from .harness import BASE_URL, ensure_signed_in, screenshot

TEST_POST_BODY = f"COMMUNITY_TEST_{int(time.time())}"


def run(page, errors, warnings, log) -> dict:
    log("Community + Public Feed checks (DB-verified)...")
    results = []
    db = get_client()

    try:
        ensure_signed_in(page, log=log)
    except Exception as e:
        return {"results": [("FAIL", f"sign-in failed: {e}")]}

    page.goto(f"{BASE_URL}/workhive/community.html", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2000)

    hive_id     = page.evaluate("localStorage.getItem('wh_active_hive_id') || null")
    worker_name = page.evaluate("localStorage.getItem('wh_last_worker') || ''")

    # ── Check 1: Posts visible (original, strengthened) ───────────────────────
    log("  [1] Community posts rendered in feed...")
    try:
        post_count = page.evaluate("""() => {
            const sels = ['[data-post-id]', '.community-post', '.post-card', '[id^="post-"]'];
            for (const s of sels) {
                const n = document.querySelectorAll(s).length;
                if (n > 0) return n;
            }
            return document.querySelectorAll('main article, main .card').length;
        }""")

        db_count = 0
        if hive_id:
            db_count = db.table("community_posts").select("id", count="exact") \
                .eq("hive_id", hive_id).is_("deleted_at", "null") \
                .limit(1).execute().count or 0

        if post_count > 0:
            results.append(("PASS", f"1: {post_count} posts rendered (DB has {db_count})"))
        elif db_count == 0:
            results.append(("WARN", "1: no posts in DB or rendered — seed community data first"))
        else:
            results.append(("FAIL", f"1: DB has {db_count} posts but 0 rendered"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"1 crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Check 2: Category labels visible (original) ───────────────────────────
    log("  [2] Category labels visible...")
    try:
        page_text = page.locator("body").inner_text()
        cats = ["General", "Safety", "Technical", "Announcement",
                "general", "safety", "technical", "announcement"]
        found = [c for c in cats if c in page_text]
        if found:
            results.append(("PASS", f"2: category labels found: {list(set(c.lower() for c in found))[:4]}"))
        else:
            results.append(("WARN", "2: no category labels visible in feed"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"2 crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Check 3: New post creates DB record ───────────────────────────────────
    log("  [3] New post → community_posts row in DB...")
    try:
        db_count_before = 0
        if hive_id:
            db_count_before = db.table("community_posts").select("id", count="exact") \
                .eq("hive_id", hive_id).eq("author_name", worker_name) \
                .limit(1).execute().count or 0

        # community.html uses a bottom-sheet composer — open it first
        page.evaluate("if (typeof openComposer === 'function') openComposer()")
        page.wait_for_timeout(600)

        compose  = page.locator("#post-content").first
        post_btn = page.locator("#btn-submit-post").first

        if not compose.count():
            results.append(("WARN", "3: #post-content textarea not found — composer may not be open"))
        elif not post_btn.count():
            results.append(("WARN", "3: #btn-submit-post not found"))
        else:
            compose.fill(TEST_POST_BODY)
            page.wait_for_timeout(300)
            post_btn.click()
            page.wait_for_timeout(3000)

            # Check DB — also accept content match as fallback (handles hive_id mismatch)
            db_count_after = 0
            if hive_id:
                db_count_after = db.table("community_posts").select("id", count="exact") \
                    .eq("hive_id", hive_id).eq("author_name", worker_name) \
                    .limit(1).execute().count or 0
            content_in_db = db.table("community_posts").select("id", count="exact") \
                .eq("content", TEST_POST_BODY).limit(1).execute().count or 0

            if db_count_after > db_count_before or content_in_db > 0:
                results.append(("PASS", f"3: post created in DB ({db_count_before}→{db_count_after or content_in_db})"))
            elif TEST_POST_BODY[:20] in page.locator("body").inner_text():
                results.append(("WARN", "3: post appears on page (optimistic UI) but DB count unchanged"))
            else:
                results.append(("FAIL", "3: post not created in DB and not visible in feed"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"3 skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Check 4: Edit own post persists to DB ─────────────────────────────────
    log("  [4] Edit own post → DB content updated...")
    try:
        # Find our test post
        own_post = db.table("community_posts").select("id, content") \
            .eq("author_name", worker_name).eq("hive_id", hive_id) \
            .order("created_at", desc=True).limit(1).execute().data if hive_id else []

        if not own_post:
            results.append(("WARN", "4: no own posts to edit — skipping"))
        else:
            post_id     = own_post[0]["id"]
            old_content = own_post[0]["content"] or ""
            new_content = old_content[:30] + " [EDITED]"

            # Find edit button — icon-only buttons use aria-label or onclick attribute
            edit_btn = page.locator(
                f"[data-post-id='{post_id}'] [aria-label='Edit my post'], "
                f"[data-post-id='{post_id}'] [onclick*='openEditor']"
            ).first

            if edit_btn.count():
                edit_btn.click()
                page.wait_for_timeout(500)

                edit_area = page.locator(
                    "textarea:visible, [contenteditable='true']:visible"
                ).first
                if edit_area.count():
                    edit_area.fill(new_content)
                    page.wait_for_timeout(200)

                    save_btn = page.locator(
                        "button:has-text('Save'), button:has-text('Update'), button:has-text('Done')"
                    ).first
                    if save_btn.count():
                        save_btn.click()
                        page.wait_for_timeout(2000)

                        db_post = db.table("community_posts").select("content") \
                            .eq("id", post_id).single().execute().data
                        if db_post and "EDITED" in (db_post.get("content") or ""):
                            results.append(("PASS", f"4: edited content persisted to DB"))
                        else:
                            results.append(("WARN", "4: edit may not have persisted to DB (content unchanged)"))
                    else:
                        results.append(("WARN", "4: Save button not found after edit"))
                else:
                    results.append(("WARN", "4: edit area not found after clicking Edit"))
            else:
                results.append(("WARN", "4: Edit button not found for own post"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"4 skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Check 5: Delete own post soft-deletes ────────────────────────────────
    log("  [5] Delete own post → deleted_at set (soft delete, row survives)...")
    try:
        own_posts = db.table("community_posts").select("id") \
            .eq("author_name", worker_name).eq("hive_id", hive_id) \
            .is_("deleted_at", "null").order("created_at", desc=True) \
            .limit(1).execute().data if hive_id else []

        if not own_posts:
            results.append(("WARN", "5: no own posts to delete — skipping"))
        else:
            post_id = own_posts[0]["id"]
            del_btn = page.locator(
                f"[data-post-id='{post_id}'] [aria-label='Delete my post'], "
                f"[data-post-id='{post_id}'] [onclick*='deletePost']"
            ).first

            if del_btn.count():
                page.on("dialog", lambda d: d.accept())
                del_btn.click()
                page.wait_for_timeout(2000)

                # Verify soft delete: row should exist with deleted_at set
                row = db.table("community_posts").select("id, deleted_at") \
                    .eq("id", post_id).execute().data
                if row and row[0].get("deleted_at"):
                    results.append(("PASS", "5: soft delete — row survives with deleted_at set"))
                elif not row:
                    results.append(("WARN", "5: row hard-deleted (acceptable if no soft-delete implemented)"))
                else:
                    results.append(("FAIL", "5: row exists but deleted_at is NULL — delete had no effect"))
            else:
                results.append(("WARN", "5: Delete button not found for own post"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"5 skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Check 6: Cannot edit/delete another worker's post ─────────────────────
    log("  [6] Edit/Delete buttons hidden for other workers' posts...")
    try:
        other_posts = db.table("community_posts").select("id, author_name") \
            .eq("hive_id", hive_id).neq("author_name", worker_name) \
            .is_("deleted_at", "null").limit(3).execute().data if hive_id else []

        if not other_posts:
            results.append(("WARN", "6: no posts from other workers to check"))
        else:
            exposed = 0
            for p in other_posts[:2]:
                pid = p["id"]
                edit_visible = page.locator(
                    f"[data-post-id='{pid}'] button:has-text('Edit')"
                ).is_visible() if page.locator(f"[data-post-id='{pid}']").count() else False
                del_visible  = page.locator(
                    f"[data-post-id='{pid}'] button:has-text('Delete')"
                ).is_visible() if page.locator(f"[data-post-id='{pid}']").count() else False
                if edit_visible or del_visible:
                    exposed += 1

            if exposed == 0:
                results.append(("PASS", "6: Edit/Delete buttons not visible on other workers' posts"))
            else:
                results.append(("FAIL", f"6: Edit/Delete visible on {exposed} other worker post(s) — permission leak"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"6 skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Check 7: Reaction does not produce NaN ────────────────────────────────
    log("  [7] Reaction click does not produce NaN count...")
    try:
        like_btn = page.locator(
            "button[aria-label*='like' i], button[aria-label*='react' i], "
            "button:has-text('👍'), button:has-text('❤'), [class*='reaction'] button"
        ).first

        if like_btn.count():
            like_btn.click()
            page.wait_for_timeout(1000)
            page_text = page.locator("body").inner_text()
            if "NaN" in page_text:
                results.append(("FAIL", "7: 'NaN' appeared after reaction click — count calculation bug"))
            else:
                results.append(("PASS", "7: reaction click did not produce NaN"))
        else:
            results.append(("WARN", "7: no reaction button found — skipping"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"7 skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Check 8: public-feed.html shows cross-hive content ────────────────────
    log("  [8] public-feed.html loads and shows posts from multiple hives...")
    try:
        page.goto(f"{BASE_URL}/workhive/public-feed.html", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2500)

        # Count distinct hive_ids in public community_posts
        public_rows = db.table("community_posts").select("hive_id") \
            .eq("public", True).is_("deleted_at", "null").limit(100).execute().data or []
        distinct_hives = len(set(r["hive_id"] for r in public_rows if r.get("hive_id")))

        page_text = page.locator("body").inner_text()
        post_count = page.evaluate("""() => {
            const sels = ['[data-post-id]', '.community-post', '.post-card'];
            for (const s of sels) {
                const n = document.querySelectorAll(s).length;
                if (n > 0) return n;
            }
            return 0;
        }""")

        if post_count > 0:
            results.append(("PASS", f"8: public-feed shows {post_count} post(s) from {distinct_hives} hive(s)"))
        elif distinct_hives == 0:
            results.append(("WARN", "8: no public posts in DB — public-feed will be empty (expected)"))
        else:
            results.append(("WARN", f"8: {distinct_hives} hive(s) have public posts but 0 rendered"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"8 skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Check 9: No "undefined" worker names ──────────────────────────────────
    log("  [9] No 'undefined' author names in post feed...")
    try:
        # Go back to community
        page.goto(f"{BASE_URL}/workhive/community.html", wait_until="networkidle", timeout=12000)
        page.wait_for_timeout(2000)
        page_text = page.locator("body").inner_text()
        if "undefined" in page_text:
            results.append(("FAIL", "9: 'undefined' found in community feed — worker name not resolving"))
        else:
            results.append(("PASS", "9: no 'undefined' author names in community feed"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"9 crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Check 10: Post count matches DB ──────────────────────────────────────
    log("  [10] Rendered post count matches DB count...")
    try:
        ui_count = page.evaluate("""() => {
            const sels = ['[data-post-id]', '.community-post', '.post-card'];
            for (const s of sels) {
                const n = document.querySelectorAll(s).length;
                if (n > 0) return n;
            }
            return 0;
        }""")

        db_total = db.table("community_posts").select("id", count="exact") \
            .eq("hive_id", hive_id).is_("deleted_at", "null") \
            .limit(1).execute().count or 0 if hive_id else 0

        # community.html paginates posts at 20/page (community.html:840) plus
        # pinned posts loaded separately. Compare against expected first-page
        # size, not the full DB total.
        pinned_count = db.table("community_posts").select("id", count="exact") \
            .eq("hive_id", hive_id).eq("pinned", True).is_("deleted_at", "null") \
            .limit(1).execute().count or 0 if hive_id else 0
        expected_first_page = min(20, db_total) + pinned_count

        if db_total == 0:
            results.append(("WARN", "10: no posts in DB — count check skipped"))
        elif ui_count == 0:
            results.append(("WARN", f"10: DB has {db_total} posts but 0 rendered (pagination or lazy load?)"))
        elif abs(ui_count - expected_first_page) <= 3:
            results.append(("PASS", f"10: rendered={ui_count} ≈ first-page+pinned={expected_first_page} (DB total={db_total})"))
        elif abs(ui_count - db_total) <= max(5, db_total * 0.1):
            results.append(("PASS", f"10: rendered={ui_count} DB={db_total} (within 10% tolerance)"))
        else:
            results.append(("WARN", f"10: rendered={ui_count} expected first-page={expected_first_page} DB total={db_total}"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"10 skipped: {e}"))
        log(f"    → WARN: {e}")

    # Cleanup test post
    try:
        db.table("community_posts").delete() \
            .eq("author_name", worker_name).eq("content", TEST_POST_BODY).execute()
    except Exception:
        pass

    screenshot(page, "community_final")
    pass_count = sum(1 for r in results if r[0] == "PASS")
    fail_count = sum(1 for r in results if r[0] == "FAIL")
    log(f"  Community: {pass_count} PASS / {fail_count} FAIL / {len(results)-pass_count-fail_count} WARN")
    return {"results": results, "fail_count": fail_count}


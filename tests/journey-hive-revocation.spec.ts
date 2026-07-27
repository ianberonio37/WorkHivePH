/**
 * journey-hive-revocation.spec.ts — HK1 live assertions: what a REVOKED membership leaves behind.
 *
 * The hive deepwalk's H8 journey (remove a member, then walk as them) found three defects that no
 * static check could see, because all three are about client state AFTER a server-side row is gone:
 *
 *   1. `html.is-supervisor` survived the removal. It is painted early from the CACHED role, on
 *      purpose, so supervisor chrome does not flash in after the async membership check — and
 *      nothing cleared it. A role marker outliving the role.
 *   2. Removal from your ACTIVE hive dumped you to the create/join screen even while you were still
 *      a member of another hive.
 *   3. The first fix for (2) asked a localStorage CACHE whether any memberships remained, letting a
 *      stale cache answer on the server's behalf.
 *
 * The static gate `tools/validate_role_marker_revocation.py` covers (1)'s SHAPE — a root role marker
 * must be removable. It cannot prove the removal actually runs on the revocation path. That is what
 * this spec is for, and it is the reason HK1 needs both a static detector and a live probe.
 *
 * FIXTURE DISCIPLINE (HK2, learned the hard way): this spec CREATES AND DESTROYS ITS OWN HIVE. The
 * H8 walk itself deleted the platform's only multi-hive membership and silently made the switcher
 * journey unwalkable again, so a revocation test that revoked a SEEDED membership would be the same
 * mistake automated. Nothing here touches seeded rows; the throwaway hive is torn down in `finally`
 * even when an assertion fails.
 */
import { test, expect } from './_fixtures';
import { waitForPageReady } from './_helpers';
import { adminClient } from './_db-cleanup';

const PAGE = '/workhive/hive.html';
const TMP_HIVE_NAME = 'ZZ Revocation Probe (test)';

/** Resolve the signed-in identity from the page the fixture already authenticated. */
async function currentIdentity(page): Promise<{ workerName: string; authUid: string | null }> {
  return await page.evaluate(async () => {
    const name = localStorage.getItem('wh_last_worker') || localStorage.getItem('wh_worker_name') || '';
    let uid: string | null = null;
    try {
      // @ts-ignore — window.db is the page's own signed-in client
      const { data } = await window.db.auth.getSession();
      uid = data?.session?.user?.id || null;
    } catch { /* empty-catch-allow: probe falls back to a null uid */ }
    return { workerName: name, authUid: uid };
  });
}

test.describe('hive.html — revocation leaves nothing behind (HK1)', () => {

  test('removal clears the supervisor marker and lands the member in a hive they still belong to',
    async ({ whPage }) => {
      const db = adminClient();
      await whPage.goto(PAGE);
      await waitForPageReady(whPage);

      const { workerName, authUid } = await currentIdentity(whPage);
      test.skip(!workerName, 'no signed-in worker resolved from the page');

      // The hive this worker really belongs to. Revocation must land them back here, never on onboard.
      const { data: home } = await db.from('hive_members')
        .select('hive_id, role').eq('worker_name', workerName).eq('status', 'active').limit(1).maybeSingle();
      test.skip(!home?.hive_id, 'signed-in worker has no seeded hive membership');
      const homeHiveId = home!.hive_id as string;
      const homeRole = (home!.role || 'worker') as string;

      let tmpHiveId = '';
      try {
        // ── Build a throwaway second hive and make this worker its SUPERVISOR ──────────────
        // hives.invite_code is character(6) — exactly six, or the insert fails on length.
        const code = ('P' + Math.floor(Math.random() * 1e5).toString().padStart(5, '0')).slice(0, 6);
        const { data: hive, error: hiveErr } = await db.from('hives')
          .insert({ name: TMP_HIVE_NAME, invite_code: code, created_by: workerName })
          .select('id').single();
        expect(hiveErr, `throwaway hive insert failed: ${hiveErr?.message}`).toBeFalsy();
        tmpHiveId = hive!.id as string;

        const { error: memErr } = await db.from('hive_members').insert({
          hive_id: tmpHiveId, worker_name: workerName, auth_uid: authUid,
          role: 'supervisor', status: 'active',
        });
        expect(memErr, `throwaway membership insert failed: ${memErr?.message}`).toBeFalsy();

        // Make it the ACTIVE hive, exactly as switching to it would.
        await whPage.evaluate(([id, name]) => {
          localStorage.setItem('wh_active_hive_id', id);
          localStorage.setItem('wh_hive_id', id);
          localStorage.setItem('wh_hive_name', name);
          localStorage.setItem('wh_hive_role', 'supervisor');
        }, [tmpHiveId, TMP_HIVE_NAME]);

        await whPage.goto(PAGE);
        await waitForPageReady(whPage);

        // Precondition: the marker is actually painted, otherwise the assertion below proves nothing
        // (a test that passes because the thing never appeared is the classic false green).
        const markedBefore = await whPage.evaluate(() =>
          document.documentElement.classList.contains('is-supervisor'));
        expect(markedBefore, 'precondition: supervisor marker should be present while the role holds')
          .toBeTruthy();

        // ── Revoke, server-side, while the browser still holds supervisor state ───────────
        await db.from('hive_members').delete().eq('hive_id', tmpHiveId).eq('worker_name', workerName);

        await whPage.goto(PAGE);
        await waitForPageReady(whPage);
        // The kicked branch reloads into recovery; give that second load room to settle.
        await whPage.waitForFunction(
          () => !!document.getElementById('view-board') || !!document.getElementById('view-onboard'),
          { timeout: 20000 }).catch(() => {});
        await whPage.waitForTimeout(4000);

        const after = await whPage.evaluate(() => ({
          marker: document.documentElement.classList.contains('is-supervisor'),
          activeHive: localStorage.getItem('wh_hive_id'),
          role: localStorage.getItem('wh_hive_role'),
          onboardVisible: (() => {
            const el = document.getElementById('view-onboard');
            return !!el && getComputedStyle(el).display !== 'none';
          })(),
        }));

        // (2) still a member elsewhere => must land there, not on the create/join screen
        expect(after.activeHive, 'revoked member should be recovered into the hive they still belong to')
          .toBe(homeHiveId);
        expect(after.onboardVisible,
          'a worker who still belongs to a hive must not be shown the create/join screen').toBeFalsy();

        // (1) the role marker must not outlive the role. Note the invariant is NOT "the marker is
        // gone" — after recovery the worker holds whatever role the RECOVERED hive gives them, and
        // if that is supervisor the marker is correctly repainted. Asserting absence would encode
        // one persona's seeded role into the test and fail for the next. What must hold is that the
        // marker tracks the CURRENT role rather than the revoked one.
        expect(after.role, 'role must be re-derived for the recovered hive').toBe(homeRole);
        expect(after.marker,
          `is-supervisor must match the recovered hive's role (home role is "${homeRole}")`)
          .toBe(homeRole === 'supervisor');

      } finally {
        // Tear down unconditionally: a failed assertion must not leave a probe hive behind.
        if (tmpHiveId) {
          await db.from('hive_members').delete().eq('hive_id', tmpHiveId);
          await db.from('hives').delete().eq('id', tmpHiveId);
        }
        await whPage.evaluate((id) => {
          localStorage.setItem('wh_active_hive_id', id);
          localStorage.setItem('wh_hive_id', id);
        }, homeHiveId).catch(() => {});
      }
    });

  /**
   * The DEMOTION case, and the one with real teeth.
   *
   * The revocation test above can only assert that the marker MATCHES the recovered hive's role —
   * if the seeded identity happens to be a supervisor at home, the marker is correctly repainted and
   * the assertion proves nothing about clearing. This test removes that dependency by creating a
   * throwaway hive it controls the role in, so the expected outcome is fixed regardless of seed data.
   *
   * It also covers the more damaging half of the defect. On revocation the board never renders, so a
   * stale marker is inert. On DEMOTION the board renders normally, and the supervisor rules are not
   * cosmetic: html.is-supervisor sets `#my-work-card{display:none}` and hides `#pm-overdue-alert` and
   * `#stock-alert`. A demoted worker therefore lost their own work card and their overdue-PM and
   * stock alerts while the page otherwise looked fine.
   */
  test('demotion clears the supervisor marker and restores the worker layout', async ({ whPage }) => {
    const db = adminClient();
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);

    const { workerName, authUid } = await currentIdentity(whPage);
    test.skip(!workerName, 'no signed-in worker resolved from the page');

    let tmpHiveId = '';
    try {
      const code = ('D' + Math.floor(Math.random() * 1e5).toString().padStart(5, '0')).slice(0, 6);
      const { data: hive, error: hiveErr } = await db.from('hives')
        .insert({ name: 'ZZ Demotion Probe (test)', invite_code: code, created_by: workerName })
        .select('id').single();
      expect(hiveErr, `probe hive insert failed: ${hiveErr?.message}`).toBeFalsy();
      tmpHiveId = hive!.id as string;

      await db.from('hive_members').insert({
        hive_id: tmpHiveId, worker_name: workerName, auth_uid: authUid,
        role: 'supervisor', status: 'active',
      });

      await whPage.evaluate((id) => {
        localStorage.setItem('wh_active_hive_id', id);
        localStorage.setItem('wh_hive_id', id);
        localStorage.setItem('wh_hive_name', 'ZZ Demotion Probe (test)');
        localStorage.setItem('wh_hive_role', 'supervisor');
      }, tmpHiveId);

      await whPage.goto(PAGE);
      await waitForPageReady(whPage);
      const before = await whPage.evaluate(() =>
        document.documentElement.classList.contains('is-supervisor'));
      expect(before, 'precondition: marker present while the supervisor role holds').toBeTruthy();

      // Demote server-side while the browser still holds the supervisor role.
      await db.from('hive_members').update({ role: 'worker' })
        .eq('hive_id', tmpHiveId).eq('worker_name', workerName);

      await whPage.goto(PAGE);
      await waitForPageReady(whPage);
      await whPage.waitForTimeout(4000);

      const after = await whPage.evaluate(() => {
        const disp = (id: string) => {
          const el = document.getElementById(id);
          return el ? getComputedStyle(el).display : 'absent';
        };
        return {
          role: localStorage.getItem('wh_hive_role'),
          marker: document.documentElement.classList.contains('is-supervisor'),
          myWorkCard: disp('my-work-card'),
        };
      });

      expect(after.role, 'role should sync down to worker').toBe('worker');
      expect(after.marker, 'is-supervisor must not outlive the supervisor role').toBeFalsy();
      expect(after.myWorkCard,
        'a demoted worker must get their own work card back (it is hidden by the supervisor rule)')
        .not.toBe('none');

    } finally {
      if (tmpHiveId) {
        await db.from('hive_members').delete().eq('hive_id', tmpHiveId);
        await db.from('hives').delete().eq('id', tmpHiveId);
      }
    }
  });

  test('a hidden supervisor panel contains no filled data for a non-supervisor', async ({ whPage }) => {
    await whPage.goto(PAGE);
    await waitForPageReady(whPage);

    // HK1's first assertion: hiding with CSS is only safe if there is nothing behind the CSS.
    // Read the panel's state without caring which role this run happens to have — if it is visible
    // the check does not apply, and saying so is more honest than skipping silently.
    const state = await whPage.evaluate(() => {
      const el = document.getElementById('supervisor-summary');
      if (!el) return { present: false, hidden: false, filled: [] as string[] };
      const hidden = getComputedStyle(el).display === 'none' || el.classList.contains('hidden');
      // A "filled" node is one carrying real content: a number, or text beyond a placeholder dash.
      const filled = Array.from(el.querySelectorAll('*'))
        .filter(n => !n.children.length)
        .map(n => (n.textContent || '').trim())
        .filter(t => t && t !== '—' && t !== '--' && t !== '·' && !/^loading/i.test(t))
        .filter(t => /\d/.test(t));
      return { present: true, hidden, filled: filled.slice(0, 12) };
    });

    test.skip(!state.present, '#supervisor-summary not rendered on this page state');
    if (!state.hidden) {
      // Visible panel => this run holds the role, so there is nothing to hide. Not a failure.
      expect(state.hidden, 'panel visible: role is held, hidden-emptiness does not apply').toBeFalsy();
      return;
    }
    expect(state.filled,
      `#supervisor-summary is hidden but carries filled values (${state.filled.join(' | ')}). ` +
      `CSS is then the only thing standing between a non-supervisor and supervisor data.`)
      .toEqual([]);
  });
});

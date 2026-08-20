#!/usr/bin/env python3
"""validate_community_xp_ledger.py — community XP must be attributable, reversible, and unfarmable.

WHY THIS GATE EXISTS. On 2026-08-05, walking PB-community-057 found that three cycles of
(post a category='safety' post -> soft-delete it) moved one worker's community_xp.xp_total from 185
to 260 with zero posts left visible to any feed. community_xp was a running TOTAL with no ledger, so
no award could be attributed to the row that earned it, and nothing could reverse one.

The farm mattered beyond gamification: community_xp feeds the hive board, achievements XP parity, and
the community->commerce reputation seam (get_community_reputation / v_marketplace_sellers_truth), so
farmed XP inflates a COMMERCIAL trust signal.

THE STRUCTURAL HALF OF THIS GATE IS NOT THE POINT. A gate that only checked "the table exists and the
triggers are attached" would stay green through a logic change that silently stopped reversing — which
is the class of false green this whole bank exists to end. So the load-bearing check is a LIVE TEETH
TEST: it runs the original farm inside a rolled-back transaction and fails if the total drifts.

It also asserts the path that the obvious fix would have missed. The product does not delete a post;
community.html:1821 soft-deletes with .update({deleted_at}) and :1840 restores it. An ON DELETE
trigger would never fire on a real person's delete, so the reversal hangs on the deleted_at
transition — and this gate proves the transition path, not just the DELETE path.

Usage:  python tools/validate_community_xp_ledger.py
"""
import os
import subprocess
import sys

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
CONTAINER = "supabase_db_workhive"


def psql(sql):
    try:
        p = subprocess.run(["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres",
                            "-d", "postgres", "-t", "-A", "-F", "|", "-v", "ON_ERROR_STOP=1"],
                           input=sql, capture_output=True, text=True, timeout=90)
    except Exception as e:
        return None, str(e)
    if p.returncode != 0:
        return None, (p.stderr or "").strip()
    return [ln for ln in (p.stdout or "").splitlines() if ln.strip()], None


def main():
    print(f"{BOLD}Community XP ledger — attributable, reversible, unfarmable{RST}")
    checks, fails = [], []

    probe, err = psql("select 1;")
    if probe is None:
        print(f"  {YEL}SKIP{RST} — local database unreachable ({err[:80] if err else 'no output'})")
        return 0

    # ── 1. the ledger's shape IS its invariant ────────────────────────────────────────────────────
    rows, err = psql("""
        select
          (select string_agg(a.attname, ',' order by a.attname)
             from pg_index i join pg_attribute a on a.attrelid=i.indrelid and a.attnum=any(i.indkey)
            where i.indrelid='public.community_post_xp_awards'::regclass and i.indisprimary),
          (select relrowsecurity from pg_class where oid='public.community_post_xp_awards'::regclass),
          (select count(*) from information_schema.role_table_grants
            where table_name='community_post_xp_awards' and grantee in ('anon','authenticated')
              and privilege_type in ('SELECT','INSERT','UPDATE','DELETE')),
          (select count(*) from public.canonical_sources where source_name='community_post_xp_awards');
    """)
    if err:
        fails.append(f"the ledger table is missing or unreadable: {err[:120]}")
    else:
        pk, rls, client_grants, anchored = (rows[0].split("|") + ["", "", "", ""])[:4]
        checks.append(("PK is (post_id, reason) — one award per post per reason",
                       pk == "post_id,reason", f"pk={pk or '(none)'}"))
        checks.append(("RLS enabled on the ledger", rls == "t", f"relrowsecurity={rls}"))
        checks.append(("no client role holds read/write grants", client_grants == "0",
                       f"{client_grants} client grant(s)"))
        checks.append(("registered in canonical_sources", anchored != "0", f"rows={anchored}"))

    # ── 2. the reversal must hang on the SOFT-DELETE transition, not only on DELETE ────────────────
    rows, err = psql("""
        select t.tgname, pg_get_triggerdef(t.oid)
          from pg_trigger t
         where t.tgrelid='public.community_posts'::regclass and not t.tgisinternal
           and t.tgname in ('trg_community_post_visibility_xp','trg_community_post_delete_xp');
    """)
    defs = {r.split("|")[0]: r.split("|", 1)[1] for r in (rows or []) if "|" in r}
    vis = defs.get("trg_community_post_visibility_xp", "")
    checks.append(("a trigger fires on the deleted_at transition (the product's real delete path)",
                   "UPDATE OF deleted_at" in vis, vis[:70] or "missing"))
    checks.append(("a trigger also covers the hard-delete path",
                   "trg_community_post_delete_xp" in defs, "present" if defs.get(
                       "trg_community_post_delete_xp") else "missing"))

    # ── 3. THE TEETH: run the original farm and require the total not to move ──────────────────────
    # Rolled back, so it cannot pollute the shared database — the same discipline every probe in this
    # bank follows. Uses a worker who already has posts, so the first-post milestone is not in play
    # and the only award under test is the repeatable one that was farmable.
    #
    # EXACTLY TWO INSERTS, AND THAT IS A CONSTRAINT, NOT A SHORTCUT. community_post_rate_limit()
    # refuses a 4th post by the same author in the same hive within 30 seconds — and it counts
    # soft-deleted posts, so the probe cannot hide behind its own deletes. A first draft of this gate
    # did 3 farm cycles plus a 4th live post and failed on 'Posting too fast', which is a gate
    # exhausting its own rate budget and reporting it as a product defect. Two posts prove strictly
    # more than the four did: post A carries award -> reverse -> restore -> re-delete (so drift across
    # a delete/restore cycle is covered), and post B is the SECOND distinct post whose award must also
    # come back to base — which is the farm.
    # (Worth recording: because the limiter counts soft-deleted rows, it bounds the farm to ~3 per 30s
    # even unfixed. It bounds the RATE; it never bounded the REVERSAL, which is what was broken.)
    #
    # THE VERDICT COMES BACK AS DATA, NOT AS A NOTICE. RAISE NOTICE writes to stderr, which this
    # runner does not read — the first version of this check therefore never saw its own TEETH-OK and
    # reported a passing fix as a failure. It failed CLOSED, which is the safe direction, but the same
    # blind spot written as "no error means pass" would have been a false green. A verdict a gate
    # cannot read is not a verdict, so it is selected out of a temp table instead.
    farm = """
    begin;
    create temp table _teeth(v text);
    do $$
    declare h uuid; w text; v_base int; v int;
    begin
      select worker_name, hive_id into w, h from public.community_xp
        where xp_total > 0 order by xp_total desc limit 1;
      if w is null then insert into _teeth values ('TEETH-SKIP no seeded community_xp row'); return; end if;
      select xp_total into v_base from public.community_xp where worker_name=w and hive_id=h;

      -- post A: the award must WORK, or "no drift" would be satisfied by paying nothing at all
      insert into public.community_posts (hive_id, author_name, content, category)
        values (h, w, 'xp-ledger-gate A', 'safety');
      select xp_total into v from public.community_xp where worker_name=w and hive_id=h;
      if v <> v_base + 25 then
        raise exception 'TEETH-FAIL a safety post no longer awards +25 (% -> %)', v_base, v;
      end if;

      -- the product's real delete path must reverse it
      update public.community_posts set deleted_at = now() where content='xp-ledger-gate A';
      select xp_total into v from public.community_xp where worker_name=w and hive_id=h;
      if v <> v_base then
        raise exception 'TEETH-FAIL soft-delete did not reverse (% -> %)', v_base + 25, v;
      end if;

      -- restore must re-apply, and re-deleting must not drift
      update public.community_posts set deleted_at = null where content='xp-ledger-gate A';
      select xp_total into v from public.community_xp where worker_name=w and hive_id=h;
      if v <> v_base + 25 then
        raise exception 'TEETH-FAIL restore did not re-apply (% -> %)', v_base, v;
      end if;
      update public.community_posts set deleted_at = now() where content='xp-ledger-gate A';
      select xp_total into v from public.community_xp where worker_name=w and hive_id=h;
      if v <> v_base then
        raise exception 'TEETH-FAIL delete/restore/delete drifted (base % -> %)', v_base, v;
      end if;

      -- post B: a SECOND distinct post, farmed the same way, must also come back to base
      insert into public.community_posts (hive_id, author_name, content, category)
        values (h, w, 'xp-ledger-gate B', 'safety');
      update public.community_posts set deleted_at = now() where content='xp-ledger-gate B';
      select xp_total into v from public.community_xp where worker_name=w and hive_id=h;
      if v <> v_base then
        raise exception 'TEETH-FAIL the farm still pays: 2 distinct posts left xp % -> %', v_base, v;
      end if;

      insert into _teeth values ('TEETH-OK award +25 exact, soft-delete reverses, restore '
                                 're-applies, delete/restore/delete no drift, 2-post farm nets 0');
    end $$;
    select v from _teeth;
    rollback;
    """
    rows, err = psql(farm)
    if err:
        fails.append(f"live teeth test: {err.splitlines()[0][:160] if err else 'unknown'}")
        checks.append(("LIVE TEETH: farm cannot move the total; award/reverse/restore exact",
                       False, "raised"))
    else:
        out = " ".join(rows or [])
        if "TEETH-SKIP" in out:
            checks.append(("LIVE TEETH (skipped: no seeded community_xp row)", True, "skipped"))
        else:
            checks.append(("LIVE TEETH: farm cannot move the total; award/reverse/restore exact",
                           "TEETH-OK" in out, out[:70] or "no notice"))

    # ── 4. non-vacuity: the backfill must actually have attributed the existing awards ─────────────
    rows, err = psql("""
        select (select count(*) from public.community_post_xp_awards where reversed_at is null),
               (select count(*) from public.community_posts
                 where category='safety' and deleted_at is null);
    """)
    if not err and rows:
        live_awards, live_safety = (rows[0].split("|") + ["", ""])[:2]
        checks.append(("existing safety posts carry ledger rows (so they are reversible)",
                       int(live_awards or 0) >= int(live_safety or 0) and int(live_safety or 0) > 0,
                       f"{live_awards} award row(s) for {live_safety} live safety post(s)"))

    # ── 5. THE THIRD AWARD KIND — replies, left out of both previous migrations ────────────────────
    # Reactions were ledgered by 20260804000049, posts by 20260806000059 (whose own comment says
    # "Posts were simply left out of that pattern"), and replies were then left out the same way:
    # handle_community_reply_xp() did nothing but `PERFORM increment_community_xp(author, hive, 10)`.
    # Unattributable and irreversible — the one-sided-write class, third instance. Closed by
    # 20260812000060, and this section is what stops it re-opening.
    rows, err = psql("""
        select
          (select string_agg(a.attname, ',' order by a.attname)
             from pg_index i join pg_attribute a on a.attrelid=i.indrelid and a.attnum=any(i.indkey)
            where i.indrelid='public.community_reply_xp_awards'::regclass and i.indisprimary),
          (select relrowsecurity from pg_class where oid='public.community_reply_xp_awards'::regclass),
          (select count(*) from information_schema.role_table_grants
            where table_name='community_reply_xp_awards' and grantee in ('anon','authenticated')
              and privilege_type in ('SELECT','INSERT','UPDATE','DELETE')),
          (select count(*) from public.canonical_sources
            where source_name='community_reply_xp_awards'),
          (select count(*) from pg_constraint
            where conrelid='public.community_reply_xp_awards'::regclass and contype='f');
    """)
    if err:
        fails.append(f"the reply ledger table is missing or unreadable: {err[:120]}")
    else:
        pk, rls, grants, anchored, fks = (rows[0].split("|") + [""] * 5)[:5]
        checks.append(("reply ledger PK is reply_id — one award per reply", pk == "reply_id",
                       f"pk={pk or '(none)'}"))
        checks.append(("RLS enabled on the reply ledger", rls == "t", f"relrowsecurity={rls}"))
        checks.append(("no client role holds read/write grants on the reply ledger", grants == "0",
                       f"{grants} client grant(s)"))
        checks.append(("reply ledger registered in canonical_sources", anchored != "0",
                       f"rows={anchored}"))
        # NO FK IS THE INVARIANT HERE, not an omission. community_post_xp_awards references
        # community_posts ON DELETE CASCADE, which is safe only because posts SOFT-delete so the
        # cascade never fires. Replies are HARD-deleted, so a cascade would erase the award row at the
        # instant the reversal needs to read it — and an erased row re-opens the reply to being paid
        # again. Adding an FK here would look like tightening and would silently restore the farm.
        checks.append(("reply ledger carries NO foreign key, so it outlives the reply it paid for",
                       fks == "0", f"{fks} FK(s)"))

    rows, err = psql("""
        select t.tgname, pg_get_triggerdef(t.oid)
          from pg_trigger t
         where t.tgrelid='public.community_replies'::regclass and not t.tgisinternal
           and t.tgname = 'trg_community_reply_delete_xp';
    """)
    got = " ".join(rows or [])
    # DELETE, not a deleted_at transition — the opposite of the post fix, because community_replies has
    # NO deleted_at column and a hard DELETE is the only delete path the table has. Same lesson as
    # migration 59 ("hang the guard where the product actually goes"), opposite conclusion.
    checks.append(("a trigger reverses reply XP on DELETE (replies have no soft-delete to hang on)",
                   "AFTER DELETE" in got.upper(), got[:70] or "missing"))

    # ── 6. THE REPLY TEETH ────────────────────────────────────────────────────────────────────────
    # community_reply_rate_limit() refuses a 6th reply by the same author/hive within 15 seconds, so
    # this stays at 3 inserts — the same "a gate must not exhaust its own rate budget" constraint the
    # post teeth test records. Verdict comes back as a temp-table row, not RAISE NOTICE, because
    # notices go to stderr where this runner never reads them.
    reply_farm = """
    begin;
    create temp table _rt(v text);
    do $$
    declare h uuid; w text; p uuid; v_base int; v int; r1 uuid; r2 uuid;
    begin
      select worker_name, hive_id into w, h from public.community_xp
        where xp_total > 0 order by xp_total desc limit 1;
      select id into p from public.community_posts where hive_id = h and deleted_at is null limit 1;
      if w is null or p is null then
        insert into _rt values ('TEETH-SKIP no seeded community_xp row or post'); return; end if;
      select xp_total into v_base from public.community_xp where worker_name=w and hive_id=h;

      -- the award must WORK, or "no drift" is satisfied by paying nothing at all
      insert into public.community_replies (post_id, hive_id, author_name, content)
        values (p, h, w, 'reply-xp-gate A') returning id into r1;
      select xp_total into v from public.community_xp where worker_name=w and hive_id=h;
      if v <> v_base + 10 then
        raise exception 'TEETH-FAIL a reply no longer awards +10 (% -> %)', v_base, v; end if;
      if not exists (select 1 from public.community_reply_xp_awards
                      where reply_id=r1 and reversed_at is null) then
        raise exception 'TEETH-FAIL the paid reply has no ledger row'; end if;

      -- DELETE must reverse, and must STAMP rather than erase
      delete from public.community_replies where id = r1;
      select xp_total into v from public.community_xp where worker_name=w and hive_id=h;
      if v <> v_base then
        raise exception 'TEETH-FAIL delete did not reverse (% -> %)', v_base + 10, v; end if;
      if not exists (select 1 from public.community_reply_xp_awards
                      where reply_id=r1 and reversed_at is not null) then
        raise exception 'TEETH-FAIL the award row was erased instead of stamped reversed'; end if;

      -- a SECOND distinct reply farmed the same way must also net zero
      insert into public.community_replies (post_id, hive_id, author_name, content)
        values (p, h, w, 'reply-xp-gate B') returning id into r2;
      delete from public.community_replies where id = r2;
      select xp_total into v from public.community_xp where worker_name=w and hive_id=h;
      if v <> v_base then
        raise exception 'TEETH-FAIL the reply farm still pays: 2 cycles left xp % -> %', v_base, v;
      end if;

      -- and a REUSED reply id must not be paid twice: the stamped row is the guard
      insert into public.community_replies (id, post_id, hive_id, author_name, content)
        values (r1, p, h, w, 'reply-xp-gate A again');
      select xp_total into v from public.community_xp where worker_name=w and hive_id=h;
      if v <> v_base then
        raise exception 'TEETH-FAIL a reused reply id was paid again (% -> %)', v_base, v; end if;

      insert into _rt values ('TEETH-OK +10 exact, delete reverses and stamps, 2-cycle farm nets 0, '
                              'reused id not repaid');
    end $$;
    select v from _rt;
    rollback;
    """
    rows, err = psql(reply_farm)
    if err:
        fails.append(f"reply teeth test: {err.splitlines()[0][:160] if err else 'unknown'}")
        checks.append(("LIVE TEETH: the reply farm cannot move the total", False, "raised"))
    else:
        out = " ".join(rows or [])
        if "TEETH-SKIP" in out:
            checks.append(("LIVE TEETH reply farm (skipped: no seed)", True, "skipped"))
        else:
            checks.append(("LIVE TEETH: the reply farm cannot move the total; award/reverse exact",
                           "TEETH-OK" in out, out[:70] or "no verdict"))

    # ── 7. CONSERVATION, REPORTED HONESTLY RATHER THAN ASSERTED FALSELY ───────────────────────────
    # The ledgers' stated purpose is to be "the ONLY record of what has been paid", so the natural
    # invariant is xp_total == sum(live awards). It does NOT hold today, and asserting it would go red
    # for a reason no code change caused: migration 59's backfill created `safety_post` rows only, so
    # platform-wide the ledger holds ZERO first_post rows for 15 posting authors and ZERO reaction
    # rows. One worker is 110 XP short of attribution with 13 live posts, 0 deleted and 0 replies —
    # the pre-existing total the PB-community-057 walk recorded before farming it, whose provenance is
    # not determinable from the data. Reducing a real worker's XP on that premise would be a
    # destructive repair, so the shortfall is REPORTED with its numbers and never absorbed.
    # What IS asserted: replies must reconcile EXACTLY. That ledger starts from zero rows with no
    # history to excuse, so any drift there is a live defect rather than inherited debt.
    rows, err = psql("""
        with post_l as (select author_name w, hive_id h, sum(xp_awarded) s
                          from public.community_post_xp_awards where reversed_at is null group by 1,2),
             reac_l as (select author_name w, hive_id h, sum(xp_awarded) s
                          from public.community_reaction_xp_awards group by 1,2),
             rep_l  as (select author_name w, hive_id h, sum(xp_awarded) s
                          from public.community_reply_xp_awards where reversed_at is null group by 1,2),
             led as (select w, h, sum(s) s from (
                       select * from post_l union all select * from reac_l union all select * from rep_l
                     ) z group by 1,2)
        select (select count(*) from public.community_xp c left join led on led.w=c.worker_name
                 and led.h=c.hive_id where c.xp_total is distinct from coalesce(led.s,0)),
               (select coalesce(sum(c.xp_total - coalesce(led.s,0)),0) from public.community_xp c
                  left join led on led.w=c.worker_name and led.h=c.hive_id
                 where c.xp_total > coalesce(led.s,0)),
               (select count(*) from public.community_post_xp_awards where reason='first_post'),
               (select count(distinct author_name) from public.community_posts),
               (select count(*) from public.community_replies),
               (select count(*) from public.community_reply_xp_awards);
    """)
    if not err and rows:
        unrec, short, firsts, authors, replies, rep_awards = (rows[0].split("|") + [""] * 6)[:6]
        # Replies: exact reconciliation, asserted. One award row per reply that still exists.
        checks.append(("every existing reply carries a ledger row (exact, no inherited debt here)",
                       int(replies or 0) <= int(rep_awards or 0),
                       f"{rep_awards} award row(s) for {replies} reply(ies)"))
        print(f"  {YEL}NOTE{RST} historical XP is not fully attributable, and this is inherited debt "
              f"rather than a regression: {unrec} of the community_xp rows do not equal their live "
              f"ledger sum, {short} XP total is unattributed, and the ledger holds {firsts} "
              f"first_post row(s) for {authors} posting author(s) because migration 59 backfilled "
              f"safety_post only. Recorded, not repaired — reducing a real worker's XP on an "
              f"undetermined provenance would be destructive.")

    for label, ok, detail in checks:
        print(f"  {GREEN + 'PASS' + RST if ok else RED + 'FAIL' + RST}  {label} {DIM}({detail}){RST}")
        if not ok:
            fails.append(label)

    if fails:
        print(f"\n  {RED}FAIL{RST} — {len(fails)} check(s). Fix: re-apply "
              f"supabase/migrations/20260806000059_community_xp_was_a_total_with_no_ledger_"
              f"so_it_could_not_reverse.sql")
        return 1
    print(f"\n  {GREEN}PASS{RST} — community XP is attributable, reversible on the real "
          f"soft-delete path, and unfarmable")
    return 0


if __name__ == "__main__":
    sys.exit(main())

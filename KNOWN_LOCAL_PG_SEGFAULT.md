# Local Postgres segfault — permission-denied call under a role switch (2026-07-29)

**Status: ISOLATED to the ENVIRONMENT, not our SQL. Local dev container only. No data loss.**

> **RESOLVED to a classification (2026-07-29, idle-stack test).** The isolating query below was run
> against `expire_stale_parts_recommendations()` - an unrelated, revoked function from the PARTS arc
> with no connection to service-hailing - under the same `SET LOCAL ROLE authenticated`. It segfaulted
> identically. **Therefore the fault is in this Postgres build's permission-denied path under a role
> switch, not in any function we wrote.** It reproduces for ANY revoked function, so no service-hailing
> code needs changing. Recovery was clean again (9 service tables intact).
>
> **Practical consequence, and the only thing that matters day to day:** never probe a revoke by
> *calling* the function under a role switch on this build. Assert the privilege instead - it is both
> authoritative and safe:
> ```sql
> select has_function_privilege('authenticated','public.fn()','execute');  -- expect false
> ```
> and confirm the legitimate path still runs (`docker logs … | grep 'cron job'`). That pair proves a
> revoke completely, with no crash risk.

## What happened

While proving that the `sweep_service_broadcasts()` revoke had actually closed the IDOR
(`20260729000011`), the probe that *replayed the exploit* crashed the database backend — twice.

```
2026-07-29 04:46:17 UTC [10] LOG: server process (PID 38181) was terminated by signal 11: Segmentation fault
2026-07-29 04:47:13 UTC [10] LOG: server process (PID 38321) was terminated by signal 11: Segmentation fault
```

Both crashes are **after** the `REVOKE`, never before it. The shape that triggers it:

```sql
begin;
set local role authenticated;
set local request.jwt.claims = '{"sub":"<uuid>","role":"authenticated"}';
select * from public.sweep_service_broadcasts();   -- caller now LACKS execute
rollback;
```

Both a bare `select` and a `PERFORM` inside a `DO $$ … $$` block reproduced it.

## What it is NOT

- **Not the function.** `pg_cron` runs the identical function every minute as the owner and it
  succeeds throughout, including between the two crashes:
  `cron job 32 starting: SELECT public.sweep_service_broadcasts();` → `completed: 1 row`.
- **Not data loss.** Postgres reinitialised cleanly both times (end-of-recovery checkpoint, then
  `database system is ready to accept connections`). Verified after recovery: 9 service tables,
  9 service views, and every arc gate still passing.
- **Not the security fix.** The revoke is authoritative in the catalog and needs no runtime probe:
  `has_function_privilege('authenticated','public.sweep_service_broadcasts()','execute') = false`,
  while the cron path keeps working. That pair is the complete proof.

## Working hypothesis

A permission-denied error raised for a `SECURITY DEFINER` function *while the session role has been
switched with `SET LOCAL ROLE`* appears to fault in this Supabase Postgres build. The interesting
question is whether it reproduces for **any** revoked function or only for one that also touches
`pg_cron` / PostGIS — that distinguishes an environment bug from something in our own SQL.

## The next step, and why it has not been taken yet

The isolating test is one query against an **unrelated** revoked function under the same role
switch. It was deliberately deferred because a full gate suite was mid-run: a backend crash during
a suite corrupts every in-flight gate verdict, which is exactly the edit-freeze discipline applied
to the database instead of the filesystem. Run it against an idle stack.

```sql
-- isolating test (run on an IDLE stack, expect either a clean 42501 or a repeat segfault)
begin;
set local role authenticated;
select public.expire_stale_parts_recommendations();   -- also revoked, unrelated to service-hailing
rollback;
```

If that also segfaults, it is an environment/extension bug and belongs upstream, with a note in
DevOps so nobody re-derives it. If it does *not*, the difference is inside
`sweep_service_broadcasts` and worth reading line by line.

## Why this file exists

A segfault found in passing is exactly the kind of thing that gets mentioned once in a session and
then lost. It is written down with its evidence, its non-implications, and its one next step so it
can be picked up cold.

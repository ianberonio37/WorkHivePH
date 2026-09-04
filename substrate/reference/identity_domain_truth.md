# Identity domain truth — name-as-key (T62, declared 2026-08-26)

## The statement

**A worker's display name IS their attribution key.** `worker_name` is the JOIN column across
logbook, pm_completions, achievements/XP, hive_members, inventory_transactions, community
authorship and the audit trail. There is no separate person-id that renders join on; the name a
worker signs up with is the name their history is filed under, permanently.

Consequences, all deliberate today:

1. **Worker display-name RENAME DOES NOT EXIST**, and must not be added casually: a bare
   `UPDATE ... SET worker_name` on one table dangles every other table's attributions — the
   worker's XP, completions and authorship would silently belong to a name that no longer
   signs in. (Contrast: HIVE rename exists and is safe — hives join on `hive_id`, the name is
   display-only; H11's audited rename is the receipt.)
2. **Uniqueness scope**: `UNIQUE(hive_id, worker_name)` on hive_members means the name is the
   identity WITHIN a hive. Two people with the same legal name in one hive must register
   distinguishable names — the T127 duplicate-name discipline applies to people too.
3. **What to tell a user who asks** (marriage, correction): today the honest answer is that
   the name is fixed to the account's history; a supervisor-mediated path would require the
   identity-keyed migration below. Do not hand-edit the DB.

## The recipe (the future gate)

If an identity-keyed migration ever lands (auth_uid becomes the join key and worker_name goes
display-only), THIS is the acceptance check — after any rename, dangling attributions must be 0:

```sql
-- rename-propagation check: rows still filed under a worker_name that no active
-- member of that hive carries. >0 after a rename = the rename dangled history.
SELECT t.tbl, t.n FROM (
  SELECT 'logbook' AS tbl, count(*) AS n FROM logbook l
    WHERE l.hive_id IS NOT NULL AND NOT EXISTS (
      SELECT 1 FROM hive_members m WHERE m.hive_id = l.hive_id AND m.worker_name = l.worker_name)
  UNION ALL
  SELECT 'pm_completions', count(*) FROM pm_completions c
    WHERE NOT EXISTS (
      SELECT 1 FROM hive_members m WHERE m.hive_id = c.hive_id AND m.worker_name = c.worker_name)
  UNION ALL
  SELECT 'inventory_transactions', count(*) FROM inventory_transactions it
    WHERE it.hive_id IS NOT NULL AND NOT EXISTS (
      SELECT 1 FROM hive_members m WHERE m.hive_id = it.hive_id AND m.worker_name = it.worker_name)
) t;
```

NOTE the baseline is NOT zero today: departed members (self-leave deletes the row) legitimately
leave history behind — that is T58's records-outlive-the-member design, not dangling. The gate
form is therefore a DELTA check around a rename (count before == count after), never an
absolute zero.

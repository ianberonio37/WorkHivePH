---
name: external-postgres-skip-locked-job-queue-worker-dispatch
type: reference
source: https://vladmihalcea.com/database-job-queue-skip-locked/
source_sha: 465f13f07157eca9
fetched_at: 2026-07-29T06:18:56Z
last_verified: 2026-07-29
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: postgres SKIP LOCKED job queue worker dispatch
---

## reference · Postgres SKIP LOCKED job queue worker dispatch
* Use `SKIP LOCKED` to implement a database job queue and avoid locking conflicts between concurrent workers.
* `SKIP LOCKED` is supported by most relational database systems, including Oracle 10g, PostgreSQL 9.5, SQL Server 2005, and MySQL 8.0.
* To use `SKIP LOCKED`, append the `SKIP LOCKED` option to the `FOR UPDATE` clause in your SQL query.
* In Hibernate, use the `LockMode.UPGRADE_SKIPLOCKED` lock mode to enable `SKIP LOCKED`.
* `SKIP LOCKED` allows a query to skip rows that are already locked by another transaction, reducing contention and improving concurrency.
* When using `SKIP LOCKED`, ensure that your database system supports it and that you are using the correct syntax.
* `SKIP LOCKED` is particularly useful in job queue implementations, where multiple workers may be competing for the same resources.
Sources: https://vladmihalcea.com/database-job-queue-skip-locked/

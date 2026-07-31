#!/usr/bin/env python3
"""drain_embedding_outbox.py — the relay: claim, embed, retry, dead-letter.

AUTO-EMBED P1 (AUTO_EMBED_INFRASTRUCTURE_PLAN.md §5B). The trigger writes an outbox row inside the user's
transaction and does nothing else; this drains it. The pattern is the one already in the substrate —
`external-postgres-skip-locked-job-queue-worker-dispatch.md` — so N workers can run concurrently without
coordination and without a broker.

WHY A RELAY AT ALL, rather than the trigger calling the function directly (what we had):
  * a failed HTTP call from a trigger is LOST — no retry, no backpressure, no record. 3,278 logbook rows
    are unretrievable today for exactly that reason.
  * the trigger needed a URL and a service-role key IN THE CATALOG, which is how local writes reached
    production. The outbox row carries neither.
  * a trigger's HTTP call cannot roll back with the transaction, so a rolled-back write could still index.

CLAIM SEMANTICS. `FOR UPDATE SKIP LOCKED` hands each row to exactly one worker and lets the others walk past
it rather than block — that is the whole reason this scales without a queue server. Attempts are counted at
CLAIM time, not at failure, so a worker that dies mid-batch still burns an attempt and the job cannot spin
forever.

BACKOFF AND DEAD-LETTER. Retries are exponential (30s, 2m, 8m, 32m…) so a provider outage does not become a
hot loop against a rate limit. After MAX_ATTEMPTS the job is dead-lettered — it leaves the queue but keeps
its error, because a job that silently disappears is indistinguishable from one that succeeded, which is the
failure mode this whole spine exists to end.

Usage:
  python tools/drain_embedding_outbox.py [--batch N] [--max-attempts N] [--dry-run] [--selftest]
"""
import argparse
import json
import os
import re
import subprocess
import sys

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
CONTAINER = "supabase_db_workhive"
MAX_ATTEMPTS = 5
# A claimed job is invisible this long. Long enough for a batch of embeddings to
# finish, short enough that a worker which died mid-job frees it promptly.
LEASE_SECONDS = 300
# psql emits its command tag on stdout next to RETURNING rows; single-field and fixed shape.
TAG_RE = re.compile(r"^(INSERT \d+ \d+|UPDATE \d+|DELETE \d+|SELECT \d+)$")
BACKOFF_SECONDS = "30 * power(2, greatest(attempts - 1, 0))"      # 30s, 60s, 120s, 240s, 480s

# CONFIG, not a constant. The relay must run against whatever host serves the platform — a deployed
# embedder for production users, or the local stack while developing. Hardcoding 127.0.0.1 is the same
# mistake in miniature as the trigger that hardcoded a PRODUCTION url: a destination baked into code is a
# destination nobody can change without a deploy. Defaults to local so nothing changes for development.
EMBED_FN_URL = os.environ.get("WH_EMBED_FN_URL", "http://127.0.0.1:54321/functions/v1/embed-entry")


def psql(sql, want_rows=True):
    try:
        r = subprocess.run(["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
                            "-t", "-A", "-F", "\x1f", "-v", "ON_ERROR_STOP=1", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    except Exception as e:
        return None, str(e)
    if r.returncode != 0:
        return None, (r.stderr or "")[:200]
    if not want_rows:
        return [], ""
    # psql prints the COMMAND TAG ("UPDATE 1") on stdout alongside the RETURNING tuples, even under -t -A.
    # Counting it as a row made the claim look like it returned two jobs when it returned one — the
    # self-test caught that as "two claims took two different jobs" failing, which is the whole point of
    # having one. Tags are single-field and match a fixed shape, so they are dropped precisely rather than
    # by trimming the last line (which would eat a real row whenever the tag was absent).
    out = []
    for ln in (r.stdout or "").splitlines():
        if not ln.strip():
            continue
        parts = ln.split("\x1f")
        if len(parts) == 1 and TAG_RE.match(parts[0].strip()):
            continue
        out.append(parts)
    return out, ""


def service_key():
    """Read the LOCAL service-role key from the running edge-runtime container at call time.

    Never stored, never printed, and never written into a trigger — which is precisely the failure this
    whole spine replaces: the old webhooks carried a PRODUCTION service-role bearer inside their trigger
    definitions, so the key sat in the catalog and every local write reached production. The relay holds it
    in memory for one process instead.
    """
    try:
        r = subprocess.run(["docker", "exec", "supabase_edge_runtime_workhive",
                            "printenv", "SUPABASE_SERVICE_ROLE_KEY"],
                           capture_output=True, text=True, timeout=30)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def embed_row(source_table, row_id, key):
    """POST the row to embed-entry (WH_EMBED_FN_URL) in the DB-webhook shape it was written for.

    The destination is CONFIG, never baked into the database. That distinction is the whole point of this
    spine: the triggers it replaces carried a production URL and a service-role key inside their own
    definitions, so the destination could not be changed and the key could not be rotated without touching
    the catalog. Here the outbox row carries neither — only which row needs indexing.
    """
    rows, err = psql(f"select to_jsonb(l) from public.{source_table} l "
                     f"where l.id::text = {lit(row_id)};")
    if rows is None or not rows:
        return False, err or "source row vanished before it could be embedded"
    payload = json.dumps({"type": "INSERT", "table": source_table, "record": json.loads(rows[0][0])})
    try:
        import urllib.request
        req = urllib.request.Request(
            EMBED_FN_URL,
            data=payload.encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
            method="POST")
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read().decode() or "{}")
        if body.get("skipped"):
            # The function's OWN reason for not embedding (near-empty, table not handled). Not a failure:
            # retrying would never change the answer, so the job completes rather than looping.
            return True, f"skipped by embed-entry: {body.get('reason')}"
        return True, ""
    except Exception as e:
        detail = ""
        try:
            detail = e.read().decode()[:200]          # HTTPError carries the function's own message
        except Exception:
            detail = str(e)[:200]
        return False, detail


def lit(s):
    """A SQL STRING literal — single-quoted, with internal quotes doubled.

    NOT json.dumps. json.dumps produces DOUBLE quotes, and in SQL a double-quoted token is an IDENTIFIER,
    so `last_error = "simulated outage"` asks for a column of that name and errors. That bug sat in both
    finish() and compose_and_target() and was invisible because finish() discarded psql's error — the job
    simply never updated, which looks identical to a job that was never claimed. The self-test caught it;
    nothing else would have.
    """
    return "'" + str(s).replace("'", "''") + "'"


def claim(batch):
    """Claim up to `batch` due jobs. One statement, so two workers can never take the same row.

    THE LEASE IS LOAD-BEARING, and the self-test is what proved it. `FOR UPDATE SKIP LOCKED` only excludes
    workers for the DURATION OF THE TRANSACTION — and each claim here is its own transaction, so the moment
    it commits the row is unlocked while still `done_at is null` and still due. Without a lease the second
    worker re-claims the row the first is currently embedding, and the same text gets embedded twice (paid
    for twice, against a free-tier budget). `claimed_at` acts as pgmq's visibility timeout: a claimed row is
    invisible for LEASE_SECONDS, after which it becomes claimable again so a worker that DIED mid-job cannot
    strand it forever.
    """
    sql = f"""
    with due as (
      select id from public.embedding_outbox
       where done_at is null
         and next_attempt_at <= now()
         and (claimed_at is null or claimed_at < now() - interval '{LEASE_SECONDS} seconds')
       order by id
       for update skip locked
       limit {int(batch)})
    update public.embedding_outbox o
       set claimed_at = now(), attempts = o.attempts + 1
      from due
     where o.id = due.id
    returning o.id, o.source_table, o.row_id, o.attempts;
    """
    return psql(sql)


def compose_and_target(source_table, row_id):
    """Build the embedding text from the REGISTRY, not from a hardcoded per-table branch.

    One definition of "what text represents this row" shared by the trigger, the relay and the coverage
    gate. Three copies of that rule is how a denominator and a pipeline drift apart.
    """
    sql = f"""
    select r.target_table, r.conflict_key, r.min_chars, r.embedding_model,
           (select string_agg(elem->>'label' || ': ' || (to_jsonb(l) ->> (elem->>'col')), '. '
                              order by ord)
              from jsonb_array_elements(r.text_fields) with ordinality e(elem, ord)
             where nullif(to_jsonb(l) ->> (elem->>'col'), '') is not null)
      from public.embedding_registry r
      join public.{source_table} l on l.id::text = {lit(row_id)}
     where r.source_table = {lit(source_table)} and r.active;
    """
    rows, err = psql(sql)
    if rows is None or not rows:
        return None, err or "row or registry entry not found"
    t, key, minc, model, text = rows[0][0], rows[0][1], int(rows[0][2]), rows[0][3], rows[0][4]
    return {"target": t, "conflict_key": key, "min_chars": minc, "model": model, "text": text or ""}, ""


def finish(job_id, ok, error=""):
    if ok:
        sql = f"update public.embedding_outbox set done_at = now(), last_error = null where id = {job_id};"
        _, err = psql(sql, want_rows=False)
        if err:
            print(f"  {RED}relay could not record job {job_id}{RST}: {err[:140]}")
        return
    else:
        # Dead-letter KEEPS the row and its error. A job that vanishes on failure looks exactly like one
        # that succeeded — the ambiguity this spine exists to remove.
        sql = f"""
        update public.embedding_outbox
           set done_at = case when attempts >= {MAX_ATTEMPTS} then now() else null end,
               last_error = case when attempts >= {MAX_ATTEMPTS}
                                 then 'DEAD after {MAX_ATTEMPTS} attempts: ' || {lit(error[:300])}
                                 else {lit(error[:300])} end,
               next_attempt_at = now() + ({BACKOFF_SECONDS}) * interval '1 second'
         where id = {job_id};"""
    _, err = psql(sql, want_rows=False)
    if err:
        # A relay that cannot record an outcome is worse than one that fails loudly: the job looks
        # untouched and will be re-claimed forever.
        print(f"  {RED}relay could not record job {job_id}{RST}: {err[:140]}")


def selftest():
    """Prove the CLAIM is exclusive and the backoff/dead-letter arithmetic is real — no embedding needed.

    The valuable half of a relay is its queue semantics, and those are testable deterministically. A
    self-test that needed a live model would be skipped exactly when it mattered.
    """
    print("  selftest: claim must be exclusive, and a failure must back off then dead-letter")
    psql("delete from public.embedding_outbox where source_table = 'selftest';", want_rows=False)
    psql("""insert into public.embedding_outbox(source_table, row_id) values
            ('selftest','a'),('selftest','b');""", want_rows=False)
    first, _ = claim(1)
    second, _ = claim(1)
    ids = {r[0] for r in (first or [])} | {r[0] for r in (second or [])}
    exclusive = len(first or []) == 1 and len(second or []) == 1 and len(ids) == 2
    print(f"    {'PASS' if exclusive else 'FAIL'}  two claims took two DIFFERENT jobs")

    jid = first[0][0]
    finish(jid, False, "simulated provider outage")
    rows, _ = psql(f"""select attempts, done_at is null, next_attempt_at > now(), coalesce(last_error,'')
                        from public.embedding_outbox where id = {jid};""")
    backed_off = rows and rows[0][1] == "t" and rows[0][2] == "t"
    print(f"    {'PASS' if backed_off else 'FAIL'}  a failure stays queued with a future next_attempt_at")

    psql(f"update public.embedding_outbox set attempts = {MAX_ATTEMPTS} where id = {jid};", want_rows=False)
    finish(jid, False, "still failing")
    rows, _ = psql(f"""select done_at is not null, last_error like 'DEAD%%'
                        from public.embedding_outbox where id = {jid};""")
    dead = rows and rows[0][0] == "t" and rows[0][1] == "t"
    print(f"    {'PASS' if dead else 'FAIL'}  past max attempts it dead-letters, KEEPING the error")

    psql("delete from public.embedding_outbox where source_table = 'selftest';", want_rows=False)
    ok = exclusive and backed_off and dead
    print(f"  {GREEN}PASS{RST} — queue semantics hold" if ok else f"  {RED}FAIL{RST} — queue semantics broken")
    return 0 if ok else 1


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=25)
    ap.add_argument("--max-attempts", type=int, default=MAX_ATTEMPTS)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()

    print(f"{BOLD}Embedding outbox relay{RST}")
    jobs, err = claim(a.batch)
    if jobs is None:
        print(f"  {YEL}SKIP{RST} database unavailable ({err})")
        return 0
    if not jobs:
        print(f"  {DIM}nothing due{RST}")
        return 0

    key = service_key()
    if not key and not a.dry_run:
        print(f"  {YEL}SKIP{RST} local service key unavailable (edge runtime not up) — jobs left queued")
        return 0

    embedded = skipped = failed = 0
    for jid, source_table, row_id, attempts in jobs:
        spec, err = compose_and_target(source_table, row_id)
        if spec is None:
            finish(jid, False, err)
            failed += 1
            continue
        if len(spec["text"]) < spec["min_chars"]:
            # The same near-empty rule embed-entry applies. Marked DONE, not failed: there is nothing to
            # retry, and leaving it queued would make the backlog look like breakage forever.
            finish(jid, True)
            skipped += 1
            continue
        if a.dry_run:
            print(f"  {DIM}would embed {source_table}/{row_id} -> {spec['target']} "
                  f"({len(spec['text'])} chars, {spec['model']}){RST}")
            continue
        ok, detail = embed_row(source_table, row_id, key)
        finish(jid, ok, detail)
        if ok:
            embedded += 1
            if detail:
                print(f"  {DIM}{source_table}/{row_id}: {detail}{RST}")
        else:
            failed += 1
            print(f"  {YEL}retry{RST} {source_table}/{row_id} (attempt {attempts}): {detail[:110]}")

    print(f"  claimed {len(jobs)} · embedded {embedded} · skipped-short {skipped} · deferred {failed}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

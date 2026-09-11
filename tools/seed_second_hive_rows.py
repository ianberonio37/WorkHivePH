#!/usr/bin/env python3
"""
seed_second_hive_rows — give the local DB a SECOND hive's rows in the tables the cross-hive / write-authz
recipe generators could not prove (2026-09-05: "no table with rows in >= 2 hives"). Missing data is a reseed,
never a ceiling: a refusal can only be proved against a foreign row that exists. Idempotent - each table is
seeded only while it still has rows in fewer than two hives; every seeded row carries the marker text
'seed-second-hive' so it can be found or removed.

  python tools/seed_second_hive_rows.py          # seed + report per table
"""
from __future__ import annotations
import subprocess, sys

PSQL = ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-tA", "-c"]
BAGUIO = "084c113b-99c0-45c6-a8e8-b4b8349da46d"
MANILA = "b4f7fe63-92e1-4f8d-b96e-625c3f85ba61"
MARK = "seed-second-hive"


def psql(sql: str) -> str:
    r = subprocess.run(PSQL + [sql], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip() + (("\nERROR: " + r.stderr.strip()) if r.returncode else "")


def spread(table: str) -> int:
    out = psql(f"select count(distinct hive_id) from {table} where hive_id is not null")
    return int(out) if out.isdigit() else -1


def member(hive: str) -> tuple[str, str]:
    out = psql(f"select auth_uid||'|'||worker_name from hive_members where hive_id = '{hive}' and status = 'active' and auth_uid is not null order by (role = 'supervisor') desc limit 1")
    return tuple(out.split("|", 1)) if "|" in out else ("", "")


def main() -> int:
    b_uid, b_name = member(BAGUIO); m_uid, m_name = member(MANILA)
    if not (b_uid and m_uid):
        print("FAIL no active member with an auth_uid in Baguio/Manila"); return 1
    report = []
    # 1. agentic_rag_traces — empty locally: two traces per hive (question/route required)
    if spread("agentic_rag_traces") < 2:
        for hive, who in ((BAGUIO, b_name), (MANILA, m_name)):
            for k in (1, 2):
                psql(f"insert into agentic_rag_traces (hive_id, worker_name, question, route, retries, grader_passed, checker_passed, citation_count, final_answer, total_tokens, latency_ms) values ('{hive}', '{who}', '{MARK}: why does pump P-{k}0{k} trip on start?', 'semantic', 0, true, true, 2, 'Seeded answer ({MARK}).', 850, 1200)")
        report.append(("agentic_rag_traces", spread("agentic_rag_traces")))
    # 2. integration_configs — copy one row of the seeded hive to the other hive
    if spread("integration_configs") < 2:
        src = psql("select hive_id from integration_configs where hive_id is not null limit 1")
        dst = MANILA if src == BAGUIO else BAGUIO
        psql(f"insert into integration_configs select (jsonb_populate_record(null::integration_configs, to_jsonb(r) || jsonb_build_object('id', gen_random_uuid(), 'hive_id', '{dst}', 'label', coalesce(r.label, r.system_type) || ' ({MARK})'))).* from (select * from integration_configs where hive_id = '{src}' limit 1) r")
        report.append(("integration_configs", spread("integration_configs")))
    # 3. ai_reply_feedback — copy the one row to the other hive
    if spread("ai_reply_feedback") < 2:
        src = psql("select hive_id from ai_reply_feedback where hive_id is not null limit 1")
        dst, uid, who = (MANILA, m_uid, m_name) if src == BAGUIO else (BAGUIO, b_uid, b_name)
        psql(f"insert into ai_reply_feedback select (jsonb_populate_record(null::ai_reply_feedback, to_jsonb(r) || jsonb_build_object('id', gen_random_uuid(), 'hive_id', '{dst}', 'auth_uid', '{uid}', 'worker_name', '{who}', 'question', '{MARK}: ' || r.question))).* from (select * from ai_reply_feedback where hive_id = '{src}' limit 1) r")
        report.append(("ai_reply_feedback", spread("ai_reply_feedback")))
    # 4. resume_documents — stamp the existing row's hive from its author, then a second worker's document
    if spread("resume_documents") < 2:
        psql("update resume_documents d set hive_id = m.hive_id from hive_members m where m.auth_uid = d.auth_uid and m.status = 'active' and d.hive_id is null")
        for hive, uid, who in ((BAGUIO, b_uid, b_name), (MANILA, m_uid, m_name)):
            if psql(f"select count(*) from resume_documents where hive_id = '{hive}'") == "0":
                psql(f"insert into resume_documents (auth_uid, worker_name, hive_id, title, doc, template) values ('{uid}', '{who}', '{hive}', 'Resume ({MARK})', '{{}}'::jsonb, 'classic')")
        report.append(("resume_documents", spread("resume_documents")))
    # 5. report_contacts — one contact per hive
    if spread("report_contacts") < 2:
        for hive, who in ((BAGUIO, b_name), (MANILA, m_name)):
            psql(f"insert into report_contacts (hive_id, name, email, label) values ('{hive}', 'Plant Manager ({MARK})', 'manager+{hive[:8]}@example.test', 'management')")
        report.append(("report_contacts", spread("report_contacts")))
    # 6. gateway_audit_log — a hive-less log locally: stamp the newest 20 rows to two hives
    if spread("gateway_audit_log") < 2:
        psql(f"with t as (select id, row_number() over (order by created_at desc) rn from gateway_audit_log where hive_id is null limit 20) update gateway_audit_log g set hive_id = case when t.rn % 2 = 0 then '{BAGUIO}'::uuid else '{MANILA}'::uuid end from t where t.id = g.id")
        report.append(("gateway_audit_log", spread("gateway_audit_log")))
    # 7. worker_achievements — rows exist by worker_name with NO auth_uid: stamp it from the active membership
    n_fixed = psql("with u as (update worker_achievements w set auth_uid = m.auth_uid from hive_members m where m.worker_name = w.worker_name and m.status = 'active' and m.auth_uid is not null and w.auth_uid is null returning 1) select count(*) from u")
    if n_fixed.isdigit() and int(n_fixed) > 0:
        report.append(("worker_achievements auth_uid stamped", int(n_fixed)))
    for t, n in report:
        print(f"  {t:24} hives now = {n}")
    if not report:
        print("  nothing to seed - every table already has rows in >= 2 hives")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""policy<->RLS parity — T163's "the privacy policy is a claim" gate (2026-08-26).

privacy-policy/index.html makes an enforceable promise: "We never share your hive
data with another hive without your explicit consent", and lists the classes it
covers — logbook entries, PM completions, asset records, skill matrix entries,
voice journal recordings, fault notes. RLS is what has to keep that promise.

This probe puts the two side by side. For each class, it impersonates a REAL
member of hive A (their auth uid + the authenticated role, the shape RLS actually
sees) and asks for rows belonging to hive B. The policy holds only if the answer
is zero, for every class, every time.

It also asserts the probe is not vacuous: hive B must genuinely HOLD rows of that
class (otherwise "0 returned" proves nothing — the empty-set trap), and the same
member must be able to read their OWN hive's rows (otherwise a blanket-deny would
pass while the product is broken).

Classes with no rows in either hive are reported as NOT PROVEN rather than passed.

SKIPs when psql is unreachable. Usage: python tools/validate_policy_rls_parity.py
"""
import io
import shutil
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

# (label, table, hive column, consented-predicate) — the classes the privacy policy names.
# The policy's promise is "never share your hive data with another hive WITHOUT YOUR EXPLICIT
# CONSENT", so a row the author deliberately PUBLISHED is not a leak — it is the consent clause
# working, and public-feed.html exists to show exactly those. The first run of this gate called
# 8 such posts a LEAK; they were precisely the public=true rows, and community_posts' RLS reads
# `(public AND NOT flagged) OR member-of-hive`. Subtract consented rows from the leak test rather
# than from the CLAIM: the un-consented remainder must still be invisible, and that is asserted.
CLASSES = [
    ("logbook entries",      "logbook",               "hive_id", None),
    ("PM completions",       "pm_completions",        "hive_id", None),
    ("asset records",        "asset_nodes",           "hive_id", None),
    ("skill matrix entries", "skill_profiles",        "hive_id", None),
    ("voice journal",        "voice_journal_entries", "hive_id", None),
    ("community posts",      "community_posts",       "hive_id", "public IS NOT TRUE"),
]


def psql(sql: str) -> str:
    r = subprocess.run(
        ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-F", "|", "-c", sql],
        capture_output=True, text=True, timeout=90, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip()


def main() -> int:
    if not shutil.which("docker"):
        print("SKIP policy-rls-parity — docker not available (RLS is the oracle)")
        return 0

    pair = psql(
        "SELECT a.hive_id::text, a.auth_uid::text, b.hive_id::text FROM "
        "(SELECT DISTINCT hive_id, auth_uid FROM hive_members WHERE status='active' AND auth_uid IS NOT NULL) a "
        "JOIN (SELECT DISTINCT hive_id FROM hive_members WHERE status='active') b ON b.hive_id <> a.hive_id "
        "LIMIT 1;")
    if not pair or "|" not in pair:
        print("SKIP policy-rls-parity — need two hives with an active member to test isolation")
        return 0
    hive_a, uid, hive_b = pair.split("|")[:3]

    failures, unproven = [], []
    for label, table, col, private_pred in CLASSES:
        scope = f" AND {private_pred}" if private_pred else ""
        exists = psql(f"SELECT to_regclass('public.{table}') IS NOT NULL;")
        if exists != "t":
            unproven.append(f"{label}: table {table} does not exist")
            continue
        theirs = psql(f"SELECT count(*) FROM public.{table} WHERE {col}='{hive_b}'{scope};")
        mine = psql(f"SELECT count(*) FROM public.{table} WHERE {col}='{hive_a}'{scope};")
        if theirs in ("", "0"):
            unproven.append(f"{label}: the other hive holds 0 un-consented rows, so a 0 result proves nothing")
            continue
        # impersonate the real member: authenticated role + their JWT claims
        leaked = psql(
            "BEGIN; SET LOCAL ROLE authenticated; "
            f"SELECT set_config('request.jwt.claims', json_build_object('sub','{uid}','role','authenticated')::text, true); "
            f"SELECT count(*) FROM public.{table} WHERE {col}='{hive_b}'{scope}; ROLLBACK;")
        leaked_n = [x for x in leaked.splitlines() if x.strip().isdigit()]
        got = leaked_n[-1] if leaked_n else "?"
        own = psql(
            "BEGIN; SET LOCAL ROLE authenticated; "
            f"SELECT set_config('request.jwt.claims', json_build_object('sub','{uid}','role','authenticated')::text, true); "
            f"SELECT count(*) FROM public.{table} WHERE {col}='{hive_a}'{scope}; ROLLBACK;")
        own_n = [x for x in own.splitlines() if x.strip().isdigit()]
        own_got = own_n[-1] if own_n else "?"
        status = "ok" if got == "0" else "LEAK"
        note = ""
        if got == "0" and own_got == "0" and mine not in ("", "0"):
            status, note = "not-proven", " (blanket-deny: this member cannot read their OWN hive either)"
            unproven.append(f"{label}: reads 0 of its own hive's {mine} rows{note}")
        print(f"  {status:9} {label:22} other-hive rows {theirs} -> visible {got} · own {mine} -> visible {own_got}")
        if status == "LEAK":
            failures.append(f"{label}: a member of another hive can see {got} of {theirs} rows in {table}")

    for u in unproven:
        print(f"  NOT PROVEN  {u}")
    if failures:
        print("FAIL policy-rls-parity — the privacy policy's cross-hive promise is not enforced:")
        for f in failures:
            print("    " + f)
        return 1
    print(f"PASS policy-rls-parity — every provable class is invisible across hives "
          f"({len(CLASSES) - len(unproven)}/{len(CLASSES)} classes proven).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

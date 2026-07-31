#!/usr/bin/env python3
"""validate_commission_leakage.py — is anyone declaring a price far below what they agreed?

FOUND BY ATTACKING, NOT BY TESTING (TB-FRAUD-money-economy-attacks, A3). Commission bills what was actually
PAID, which is the honest base and was a deliberate fix — a job settled at a different real price should not
be billed off a catalogue number. But it hands both parties a lever: a client and provider who agree a
PHP50,000 job and then declare PHP1 on the payment record pay **PHP0.10 commission instead of PHP2,500**. The
attack probe measured exactly that. Nothing refused it and nothing noticed.

WHY THIS DETECTS RATHER THAN REFUSES. A declared payment below the quoted price is often legitimate: a job
came in under scope, a provider gave a discount, a client paid part in materials. Refusing those would block
honest work and push people off-platform entirely, which costs more than the leak. So the platform bills
honestly on what was declared and MEASURES the gap — the same disposition the fraud model uses everywhere:
an attack is either refused or DETECTED AND NAMED, never silently absorbed.

WHAT IS MEASURED. For every settled job carrying a payment record, the ratio of what was declared to what was
agreed (the selected offer price, else the catalogue rate, else the stated budget). A ratio near 1.0 is
normal. A ratio near 0 on a large job is either a data-entry error or someone routing the fee around the
platform, and both deserve a look.

The gate FAILs on a forward-only ratchet over the count of severe cases, so an existing backlog does not
block the build while a NEW understatement pattern shows up immediately.

Usage:  python tools/validate_commission_leakage.py [--accept] [--selftest]
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "commission_leakage_baseline.json"
CONTAINER = "supabase_db_workhive"
G, R, Y, D, B, X = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

# Below this share of the agreed price, a declared payment is "severe" and reviewable. 0.5 is deliberately
# generous: a half-price job is unusual but plausible, while a 2%-of-price job is not.
SEVERE_RATIO = 0.5
# ...and only on jobs big enough for the gap to be worth anything. A PHP200 job declared at PHP80 is noise.
MATERIAL_AGREED = 1000


def psql(sql):
    try:
        r = subprocess.run(["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
                            "-t", "-A", "-F", "\x1f", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except Exception as e:
        return None, str(e)
    if r.returncode != 0:
        return None, (r.stderr or "")[:200]
    return [ln.split("\x1f") for ln in (r.stdout or "").splitlines() if ln.strip()], ""


QUERY = """
select r.id::text,
       coalesce(p.amount_paid, 0)::text,
       -- THE SHARED DEFINITION. This chain used to be written out here a THIRD time, alongside both
       -- minters; three copies of a money rule drift, and the drift would be silent. `service_agreed_base`
       -- is now the only place it lives, so the gate and the biller cannot disagree about what was agreed.
       public.service_agreed_base(r.id)::text,
       coalesce(r.segment, '?'),
       coalesce(p.variance_reason, '')
  from public.service_requests r
  join public.service_payments p on p.request_id = r.id
 where r.status in ('settled', 'disputed');
"""


def judge(rows):
    """Pure arithmetic over (paid, agreed) pairs, so the self-test needs no database."""
    severe, total_gap = [], 0.0
    for row in rows:
        rid, paid, agreed, seg = row[0], row[1], row[2], row[3]
        reason = row[4] if len(row) > 4 else ""
        paid, agreed = float(paid), float(agreed)
        if agreed < MATERIAL_AGREED:
            continue                      # too small for the gap to be worth routing around
        ratio = paid / agreed if agreed else 1.0
        if ratio < SEVERE_RATIO:
            severe.append((rid, paid, agreed, ratio, seg, reason))
            total_gap += agreed - paid
    return severe, total_gap


def selftest():
    print("  selftest: the ratio arithmetic must catch an understated job and pass an honest one")
    ok = True
    honest = [("a", "2000", "2000", "consumer", ""), ("b", "1800", "2000", "consumer", "")]
    if judge(honest)[0]:
        print(f"  {R}FAIL{X} — an honest job (and a modest discount) was flagged"); ok = False
    attack = [("c", "1", "50000", "consumer", "")]
    sev, gap = judge(attack)
    if not sev or round(gap) != 49999:
        print(f"  {R}FAIL{X} — the PHP1-on-PHP50,000 attack was not caught"); ok = False
    noise = [("d", "80", "200", "consumer", "")]
    if judge(noise)[0]:
        print(f"  {R}FAIL{X} — a tiny job was flagged; the threshold must be material"); ok = False
    if ok:
        print(f"  {G}PASS{X} — catches a severe understatement, ignores discounts and small jobs")
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print(f"{B}Commission leakage{X} — is anyone declaring far less than they agreed?")
    if selftest() != 0:
        return 1

    rows, err = psql(QUERY)
    if rows is None:
        print(f"  {Y}SKIP{X} database unavailable ({err})")
        return 0
    severe, gap = judge(rows)
    base = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
    floor = base.get("severe", 0)

    print(f"  {D}settled jobs with a payment record: {len(rows)}{X}")
    for rid, paid, agreed, ratio, seg, reason in sorted(severe, key=lambda s: s[3])[:5]:
        print(f"  {R}severe{X} {rid[:8]} {seg:<10} declared {paid:>12,.2f} of {agreed:>12,.2f} "
              f"{D}({ratio*100:.1f}% — {agreed-paid:,.2f} of fee base unbilled){X}")
        # The STATED reason is the point. Since mig ...024 a materially-understated payment cannot be
        # written without one, so every severe case here carries an attributable claim — and a pattern of
        # identical reasons across many jobs is the farming signal this gate exists to make actionable.
        print(f"           {D}reason: {reason or '(none — pre-dates the variance guard)'}{X}")

    if "--accept" in argv:
        if len(severe) > floor and BASELINE.exists():
            print(f"  {R}ACCEPT REFUSED{X} {floor} -> {len(severe)} is a RISE; the floor only moves down.")
            return 1
        BASELINE.write_text(json.dumps(
            {"severe": len(severe),
             "_doc": "Forward-only floor for severe commission understatement. A RISE FAILs the gate; "
                     "--accept only ratchets DOWN as the backlog is worked off."}, indent=2),
            encoding="utf-8")
        print(f"  {G}ACCEPTED{X} floor -> {len(severe)}")
        return 0

    if len(severe) > floor:
        print(f"\n  {R}FAIL{X} — {len(severe)} severe understatement(s), baseline {floor}. "
              f"{gap:,.2f} of fee base went unbilled. Each is either a data-entry error or a fee being "
              f"routed around the platform; both need a look.")
        return 1
    print(f"\n  {G}PASS{X} — {len(severe)} severe case(s), within the {floor} baseline"
          + (f" ({gap:,.2f} unbilled)" if severe else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

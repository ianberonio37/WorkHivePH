#!/usr/bin/env python3
"""
validate_role_vocabulary_coverage.py — the client role reader must UNDERSTAND every role the
database actually stores.

WHY THIS EXISTS (hive deepwalk H8c, 2026-07-27). wh-roles.js is the canonical client RBAC reader.
It reads the AUTH key `wh_hive_role` — which holds whatever `hive_members.role` holds — but its
capability map mirrors nav-hub's `roles` arrays, which are written in DISPLAY vocabulary
('field' | 'supervisor' | 'engineer'). Those two vocabularies were never reconciled.

`hive_members.role` stores 'worker'. 'worker' was not in the reader's ROLES list, so whRole()
returned '' for it — and an empty role is DELIBERATELY treated as permissive ("solo mode / new
install", so a lone tech is not locked out of their own tools). The two reasonable decisions
combined into an unreasonable outcome: every real worker on the platform (12 of 16 seeded
memberships) silently satisfied can('approve'), can('manage_hive') and can('audit_log').

It shipped harmless only by accident — nothing calls can() yet — while every comment in the codebase
instructs the next change to use it. A latent trap is still a defect; this gate keeps it closed.

THE ASSERTION: every DISTINCT role value present in hive_members must resolve, through the reader's
own ROLES list or its documented alias map, to a role the capability matrix knows. Anything that
resolves to '' would inherit the permissive branch.

Live rows on purpose: the failure was a mismatch between what the DB WRITES and what the client
UNDERSTANDS, so reading only the source would compare the client against itself. Skips clean when the
DB is down. Self-test: `--selftest` (pure text + set logic, no DB).
"""
from __future__ import annotations
import io, re, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
READER = ROOT / "wh-roles.js"
DB = "supabase_db_workhive"
GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"

# The permissive sentinel: a role the reader cannot place resolves to '' and whCan() then returns
# true for everything. That is the whole failure mode, so name it rather than leaving it implicit.
PERMISSIVE = ""


def parse_reader(src: str) -> tuple[list[str], dict[str, str]]:
    """Extract the ROLES vocabulary and the AUTH->DISPLAY alias map from wh-roles.js."""
    roles: list[str] = []
    m = re.search(r"var\s+ROLES\s*=\s*\[([^\]]*)\]", src)
    if m:
        roles = re.findall(r"['\"]([A-Za-z0-9_-]+)['\"]", m.group(1))
    aliases: dict[str, str] = {}
    a = re.search(r"var\s+AUTH_TO_DISPLAY\s*=\s*\{([^}]*)\}", src)
    if a:
        for k, v in re.findall(r"['\"]?([A-Za-z0-9_-]+)['\"]?\s*:\s*['\"]([A-Za-z0-9_-]+)['\"]", a.group(1)):
            aliases[k.lower()] = v.lower()
    return roles, aliases


def resolve(role: str, roles: list[str], aliases: dict[str, str]) -> str:
    """Mirror whRole(): lowercase, apply the alias, then require membership in ROLES."""
    r = (role or "").lower().strip()
    r = aliases.get(r, r)
    return r if r in roles else PERMISSIVE


def unresolved(db_roles: list[str], roles: list[str], aliases: dict[str, str]) -> list[str]:
    """DB role values the reader cannot place (they would fall into the permissive branch)."""
    return sorted({r for r in db_roles if r and resolve(r, roles, aliases) == PERMISSIVE})


def _psql(sql: str, timeout: int = 20):
    return subprocess.run(
        ["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-tA", "-c", sql],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def _db_roles() -> list[str] | None:
    try:
        r = _psql("select distinct role from public.hive_members where role is not null;")
        if r.returncode != 0:
            return None
        return [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()]
    except Exception:
        return None


def selftest() -> int:
    ok = True

    def chk(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {GREEN+'PASS'+RESET if good else RED+'FAIL'+RESET}  {label}: got {got}, want {want}")

    src_fixed = ("var ROLES = ['field', 'supervisor', 'engineer'];\n"
                 "var AUTH_TO_DISPLAY = { worker: 'field' };\n")
    roles, aliases = parse_reader(src_fixed)
    chk("parses the vocabulary", (roles, aliases), (["field", "supervisor", "engineer"], {"worker": "field"}))

    # The exact H8c defect: 'worker' stored, no alias, so it lands on the permissive branch.
    src_broken = "var ROLES = ['field', 'supervisor', 'engineer'];\n"
    rb, ab = parse_reader(src_broken)
    chk("unmapped DB role is caught", unresolved(["worker", "supervisor"], rb, ab), ["worker"])

    # With the alias in place the same data is clean.
    chk("aliased role resolves", unresolved(["worker", "supervisor"], roles, aliases), [])

    # A brand-new DB role nobody taught the client about must FAIL, not pass quietly.
    chk("a future unknown role is caught", unresolved(["worker", "contractor"], roles, aliases), ["contractor"])

    chk("case and whitespace are normalised", resolve("  Worker ", roles, aliases), "field")
    print(f"\n  SELFTEST: {GREEN+'PASS'+RESET if ok else RED+'FAIL'+RESET}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()

    print(f"{BOLD}Role vocabulary coverage (does the client understand every role the DB stores?){RESET}")
    if not READER.exists():
        print(f"  {RED}FAIL{RESET}  {READER.name} not found")
        return 1

    roles, aliases = parse_reader(READER.read_text(encoding="utf-8", errors="replace"))
    if not roles:
        print(f"  {RED}FAIL{RESET}  could not parse a ROLES vocabulary out of {READER.name}")
        return 1

    db_roles = _db_roles()
    if db_roles is None:
        print(f"  {YELLOW}SKIP{RESET}  local DB unreachable — vocabulary not compared against live roles")
        return 0

    bad = unresolved(db_roles, roles, aliases)
    print(f"  reader vocabulary : {roles}  (aliases: {aliases or 'none'})")
    print(f"  roles in the DB   : {sorted(db_roles)}")
    if bad:
        print(f"  {RED}FAIL{RESET}  {len(bad)} DB role value(s) the client cannot place: {bad}")
        print(f"  {YELLOW}Why this is dangerous:{RESET} an unplaceable role resolves to '' and whCan() treats "
              f"an empty role as PERMISSIVE (the solo-mode default), so those users satisfy EVERY capability.")
        print(f"  {YELLOW}Fix:{RESET} add the value to ROLES, or map it in AUTH_TO_DISPLAY in {READER.name}.")
        return 1
    print(f"  {GREEN}PASS{RESET}  every DB role resolves into the capability matrix")
    return 0


if __name__ == "__main__":
    sys.exit(main())

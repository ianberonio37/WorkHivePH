"""
test_identity — resolve a seeded test user's JWT + CURRENT hive at RUNTIME (reseed-proof).
=========================================================================================
Root fix for the stale-hive-fixture class (2026-07-13): live gates hard-coded a test hive
UUID (`9b4eaeac…`) that rotted across a reseed (→ 0 members → the edge fn 403s "not_a_member"
→ the gate SKIPS the surface → it VACUOUSLY PASSES, silently disabling itself). A hard-coded
UUID is the bug. This helper derives the hive from the user's LIVE `hive_members` row via
PostgREST (RLS-scoped: a user can read their own membership), so it can NEVER go stale.

Usage:
    from test_identity import resolve_test_identity
    ident = resolve_test_identity("leandromarquez@auth.workhiveph.com")   # password default test1234
    ident.jwt        # Bearer token
    ident.hive_id    # the user's current active hive (Baguio 636cf7e8…, whatever the seed minted)
    ident.user_id

Env:  WH_LOCAL_BASE (default http://127.0.0.1:54321), WH_ANON_KEY (default local publishable).
Raises TestIdentityError on any auth/lookup failure so a gate can SKIP with a real reason
(never silently pass). Zero third-party deps (urllib only).
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from dataclasses import dataclass

BASE = os.environ.get("WH_LOCAL_BASE", "http://127.0.0.1:54321").rstrip("/")
# Local publishable anon key (same one the live gates + seeder use). Overridable for CI.
ANON = os.environ.get("WH_ANON_KEY", "sb_publishable_ePj-suLMwkMRVDH6eM6S8g_R0rZVbMZ")
DEFAULT_PASSWORD = "test1234"


class TestIdentityError(RuntimeError):
    """Auth or hive-lookup failed — the caller should SKIP (with this reason), never pass vacuously."""


@dataclass
class TestIdentity:
    email: str
    jwt: str
    user_id: str
    hive_id: str
    role: str


def _post_json(url: str, payload: dict, headers: dict, timeout: int = 15) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", **headers}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def _get_json(url: str, headers: dict, timeout: int = 15):
    req = urllib.request.Request(url, headers=headers, method="GET")
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def resolve_test_identity(email: str, password: str = DEFAULT_PASSWORD,
                          *, base: str = BASE, anon: str = ANON) -> TestIdentity:
    """Sign the user in, then read their CURRENT active hive from hive_members. Reseed-proof."""
    # 1. mint the user JWT
    try:
        tok = _post_json(f"{base}/auth/v1/token?grant_type=password",
                         {"email": email, "password": password}, {"apikey": anon})
    except urllib.error.HTTPError as e:
        raise TestIdentityError(f"GoTrue {e.code} for {email}: {e.read().decode()[:120]}")
    except Exception as e:
        raise TestIdentityError(f"GoTrue unreachable for {email}: {type(e).__name__}")
    jwt = tok.get("access_token")
    user_id = (tok.get("user") or {}).get("id", "")
    if not jwt:
        raise TestIdentityError(f"no access_token for {email}")

    # 2. read the user's CURRENT active hive via PostgREST (RLS: self-membership is readable)
    auth = {"apikey": anon, "Authorization": f"Bearer {jwt}"}
    try:
        rows = _get_json(
            f"{base}/rest/v1/hive_members?auth_uid=eq.{user_id}&status=eq.active"
            f"&select=hive_id,role&limit=1", auth)
    except Exception as e:
        raise TestIdentityError(f"hive_members lookup failed for {email}: {type(e).__name__}")
    if not rows:
        raise TestIdentityError(f"{email} has no ACTIVE hive membership (reseed the DB?)")
    return TestIdentity(email=email, jwt=jwt, user_id=user_id,
                        hive_id=rows[0]["hive_id"], role=rows[0].get("role", ""))


if __name__ == "__main__":
    import sys
    who = sys.argv[1] if len(sys.argv) > 1 else "leandromarquez@auth.workhiveph.com"
    try:
        ident = resolve_test_identity(who)
        print(f"OK  {ident.email}  hive={ident.hive_id}  role={ident.role}  jwt={len(ident.jwt)}chars")
    except TestIdentityError as e:
        print(f"SKIP  {e}")
        sys.exit(2)

"""Shared-secret auth gate for the edge↔python compute routes (Arc F, B1 keystone).

THE FINDING (NEXT_LAYER_STUDY.md §3): main.py had CORSMiddleware allow_origins=["*"]
and NO Depends/API-key/Bearer check on any route. The edge called it with only
Content-Type. If the Railway deploy URL is reachable, anyone could invoke
/calculate, /ml/train, /analytics, /project/progress with no credential — an open
compute API doing real work (and /ml/train reads cross-hive data).

THE FIX: a shared secret carried edge→python in the `X-API-Key` header, checked
here in constant time. Kept in its own module (not main.py) so it is unit-testable
without importing the heavy calc stack (fluids/iapws/psychrolib/matplotlib), mirroring
the edge's _shared/tenant-context.ts separation.

CONFIGURE-TO-ENABLE: enforcement is active only when PYTHON_API_KEY is set. Unset =
warn-and-allow, so health checks and existing deploys don't break before the key is
provisioned on BOTH sides (Railway env + the edge functions' PYTHON_API_KEY). Live
enforcement is therefore attributed until that env var is set — a named external
ceiling (roadmap §5); the gate's CORRECTNESS is proven hermetically by
tools/validate_python_api_auth.py.

The key is read fresh on every check so tests (and a key rotation) take effect
without a process restart.
"""
from __future__ import annotations
import hmac
import logging
import os

from fastapi import Header, HTTPException

logger = logging.getLogger("engcalc-api.auth")

_ENV_VAR = "PYTHON_API_KEY"


def _load_key() -> str:
    return os.environ.get(_ENV_VAR, "").strip()


def api_key_configured() -> bool:
    """True when a shared secret is set, i.e. the gate is enforcing."""
    return bool(_load_key())


def check_api_key(provided: str | None) -> bool:
    """Pure authorization decision for a given X-API-Key header value.

    No FastAPI types so it is hermetically unit-testable. Returns:
      - True  when no key is configured (configure-to-enable: unset = allow), OR
              when the provided value matches the configured secret (constant-time).
      - False when a key IS configured and the provided value is missing/wrong.
    """
    key = _load_key()
    if not key:
        return True  # unset = allow (a loud startup warning is logged by main.py)
    return bool(provided) and hmac.compare_digest(provided, key)


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """FastAPI dependency: 401 a compute request when the shared secret is
    configured and the X-API-Key header is missing or wrong."""
    if not check_api_key(x_api_key):
        logger.warning("auth: rejected %s X-API-Key on compute route",
                       "missing" if not x_api_key else "invalid")
        raise HTTPException(status_code=401, detail="invalid or missing API key")

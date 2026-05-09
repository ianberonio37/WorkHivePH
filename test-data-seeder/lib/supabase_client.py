"""Cached supabase client + Windows WMI hang workaround.

WMI hang (Python 3.12 + Windows):
  supabase-py's auth client calls platform.system() AND platform.release()
  at create_client time to populate request headers. On Python 3.12 Windows,
  both route through platform.uname() -> win32_ver() -> _wmi_query, which
  hangs indefinitely (20-60+ seconds, sometimes forever) on some Windows
  setups (sluggish WMI service, locked WMI repository, sleep-state quirks).

  Reproduced 2026-05-09 with the WorkHive Tester dashboard hanging at
  "Loading..." on every request. Stack trace pinned the freeze to
  _wmi.exec_query inside platform.win32_ver inside platform.uname.

  Fix: short-circuit platform.system / release / uname before importing
  supabase. We're always on Windows in this Tester so the constants are
  correct, and supabase-py only uses these strings as request headers --
  precise version detection is not load-bearing.

Singleton client:
  Cache the supabase client as a module-level singleton instead of
  creating a fresh one per call. Without this, every request through
  the Flask dashboard fired multiple create_client() calls, multiplying
  the WMI hang as well as connection setup overhead.
"""
from typing import Optional
import platform as _platform

# Patch BEFORE supabase import so its auth client uses the safe constants.
# All three Windows entry points route through _wmi_query in Python 3.12.
_platform.system = lambda: "Windows"
_platform.release = lambda: ""
_platform.uname = lambda: _platform.uname_result(
    system="Windows", node="", release="", version="", machine="", processor=""
)

from supabase import create_client, Client  # noqa: E402
from .config import SUPABASE_URL, SUPABASE_SECRET_KEY  # noqa: E402

_client: Optional[Client] = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
    return _client

from typing import Optional
from supabase import create_client, Client
from .config import SUPABASE_URL, SUPABASE_SECRET_KEY

# Singleton client. Previously every Flask request created a fresh client,
# which compounded into 19+ create_client() calls per index page load.
# /api/status (polled every 1-2s) calls get_db_counts() = 16 sequential count
# queries. The index() route additionally calls get_test_logins() which makes
# 3 more queries. Multiplied across concurrent requests this saturated the
# single-threaded debug Flask and the dashboard hung at "Loading...".
#
# Caching the client doesn't change query semantics -- supabase-py is
# thread-safe for read-only table operations.
_client: Optional[Client] = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
    return _client

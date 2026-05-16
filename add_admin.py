#!/usr/bin/env python3
import sys
sys.path.insert(0, 'test-data-seeder')

from lib.supabase_client import get_client

db = get_client()

# Find pablo aguilar's auth_uid
print("Looking for pablo aguilar...")
workers = db.table("worker_profiles").select("auth_uid, display_name, username").execute()

# Search for matching display_name (case-insensitive)
found = None
for w in workers.data:
    if w["display_name"].lower() == "pablo aguilar" or w["username"].lower() == "pablo aguilar":
        found = w
        break

if not found:
    # Try partial match
    for w in workers.data:
        if "pablo" in w["display_name"].lower():
            found = w
            break

if not found:
    print("ERROR: pablo aguilar not found in worker_profiles")
    print("Available users:")
    for w in workers.data:
        print(f"  - {w['display_name']} (username: {w['username']})")
    sys.exit(1)

display_name = found["display_name"]
print(f"[OK] Found {display_name}")

# Check if already in admins
existing = db.table("marketplace_platform_admins").select("worker_name").eq("worker_name", display_name).execute()
if existing.data:
    print("[OK] Already in marketplace_platform_admins")
    sys.exit(0)

# Add to admins
print("Adding to marketplace_platform_admins...")
result = db.table("marketplace_platform_admins").insert({
    "worker_name": display_name,
    "granted_by": "system"
}).execute()

if result.data:
    print(f"[OK] Successfully added {display_name} as platform admin")
    print("Refresh founder-console.html in your browser")
    sys.exit(0)
else:
    print("ERROR: Failed to add to admins")
    print(result)
    sys.exit(1)

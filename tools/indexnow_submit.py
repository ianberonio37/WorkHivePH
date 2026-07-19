#!/usr/bin/env python3
"""
indexnow_submit.py -- push WorkHive's public URLs to the IndexNow network
(Bing, Microsoft Copilot, Yandex, DuckDuckGo, Seznam) in one shot.

WHY: Google/Bing discover pages by crawling on their own schedule (days-weeks).
IndexNow is a push protocol: you notify the engines the instant a URL is new or
changed, so a freshly-public page gets indexed in hours, not weeks. Microsoft
Copilot and several AI answer engines read the Bing index, so IndexNow is also
the AEO/GEO discoverability lever -- no dashboard, no account, no login.

Zero external dependencies (urllib only). The URL list is single-sourced from
sitemap.xml (the same list Google/Bing already crawl) so it can never drift.

OWNERSHIP: IndexNow proves you own the domain via a key file at the site root:
    https://workhiveph.com/<key>.txt      (file contents == <key>)
This tool auto-discovers that file in the web root next to index.html.

USAGE:
    python tools/indexnow_submit.py                 # dry-run: show what WOULD be sent
    python tools/indexnow_submit.py --verify        # check the key file is LIVE on prod
    python tools/indexnow_submit.py --submit        # verify, then POST the full URL list
    python tools/indexnow_submit.py --submit --url https://workhiveph.com/learn/new-article/
                                                    # push a single new/changed URL

Run --submit only AFTER the key file has been deployed to production. --submit
verifies the file is reachable first and refuses to send if it is not (a submit
with an unreachable key returns 403 and can get the domain rate-limited).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import urllib.error
import urllib.request

HOST = "workhiveph.com"
BASE = f"https://{HOST}"
ENDPOINT = "https://api.indexnow.org/indexnow"  # shared -> fans out to all IndexNow engines
TIMEOUT = 20

WEB_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITEMAP = os.path.join(WEB_ROOT, "sitemap.xml")

_KEY_RE = re.compile(r"^[a-f0-9]{8,128}$", re.IGNORECASE)


def find_key_file() -> tuple[str, str, str]:
    """Return (key, key_file_path, key_location_url) for the root IndexNow key file.

    The IndexNow key file is the one whose <name>.txt basename is a valid key
    AND whose contents exactly equal that basename. This avoids matching llms.txt,
    robots.txt, or any other stray .txt in the root.
    """
    for path in sorted(glob.glob(os.path.join(WEB_ROOT, "*.txt"))):
        stem = os.path.splitext(os.path.basename(path))[0]
        if not _KEY_RE.match(stem):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            body = fh.read().strip()
        if body == stem:
            return stem, path, f"{BASE}/{stem}.txt"
    sys.exit(
        "ERROR: no IndexNow key file found in the web root.\n"
        "Expected a file named <key>.txt (8-128 hex chars) whose contents equal <key>.\n"
        f"Looked in: {WEB_ROOT}"
    )


def parse_sitemap_urls() -> list[str]:
    """All <loc> URLs from sitemap.xml, in document order (single source of truth)."""
    if not os.path.exists(SITEMAP):
        sys.exit(f"ERROR: sitemap not found at {SITEMAP}")
    with open(SITEMAP, "r", encoding="utf-8") as fh:
        raw = fh.read()
    urls = [u.strip() for u in re.findall(r"<loc>\s*(.*?)\s*</loc>", raw, re.DOTALL)]
    # keep only same-host https URLs -- IndexNow rejects a payload mixing hosts
    return [u for u in urls if u.startswith(BASE)]


def verify_key_live(key: str, key_location: str) -> bool:
    """Fetch the key file from the LIVE domain and confirm it matches (proves deploy)."""
    try:
        req = urllib.request.Request(key_location, headers={"User-Agent": "WorkHive-IndexNow/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            live = resp.read().decode("utf-8").strip()
    except urllib.error.HTTPError as e:
        print(f"  key file NOT reachable: HTTP {e.code} at {key_location}")
        return False
    except Exception as e:  # noqa: BLE001 -- surface any network failure plainly
        print(f"  key file NOT reachable: {e}")
        return False
    if live == key:
        print(f"  key file LIVE and matches: {key_location}")
        return True
    print(f"  key file reachable but content mismatch (got {live!r}, want {key!r})")
    return False


def post_indexnow(urls: list[str], key: str, key_location: str) -> int:
    payload = {
        "host": HOST,
        "key": key,
        "keyLocation": key_location,
        "urlList": urls,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8",
                 "User-Agent": "WorkHive-IndexNow/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            code = resp.getcode()
    except urllib.error.HTTPError as e:
        code = e.code
    _explain(code)
    return code


def _explain(code: int) -> None:
    meaning = {
        200: "OK -- URLs accepted.",
        202: "Accepted -- URLs received, validation pending (key check async).",
        400: "Bad request -- malformed payload.",
        403: "Forbidden -- key file not found/valid on the live domain (deploy it first).",
        422: "Unprocessable -- a URL does not match the host, or the key is invalid.",
        429: "Too many requests -- back off and retry later.",
    }.get(code, "Unexpected status.")
    print(f"  IndexNow response: HTTP {code} -- {meaning}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Submit WorkHive URLs to IndexNow (Bing/Copilot/Yandex/DuckDuckGo).")
    ap.add_argument("--submit", action="store_true", help="actually POST (default is dry-run)")
    ap.add_argument("--verify", action="store_true", help="only check the key file is live on prod")
    ap.add_argument("--url", action="append", default=[], help="submit specific URL(s) instead of the whole sitemap")
    args = ap.parse_args()

    key, key_path, key_location = find_key_file()
    print(f"IndexNow key : {key}")
    print(f"key file     : {os.path.relpath(key_path, WEB_ROOT)}  (deploy this to the site root)")
    print(f"keyLocation  : {key_location}")

    urls = args.url if args.url else parse_sitemap_urls()
    print(f"URLs to push : {len(urls)} (source: {'--url args' if args.url else 'sitemap.xml'})\n")

    if args.verify:
        print("Verifying key file on the live domain...")
        sys.exit(0 if verify_key_live(key, key_location) else 1)

    if not args.submit:
        print("DRY-RUN (no request sent). URLs that WOULD be submitted:")
        for u in urls:
            print(f"  {u}")
        print("\nRe-run with --submit once the key file is deployed to production.")
        return

    print("Verifying key file is live before submitting...")
    if not verify_key_live(key, key_location):
        sys.exit(
            "REFUSING to submit: the key file is not live at the domain root yet.\n"
            f"Deploy {os.path.basename(key_path)} to https://{HOST}/ , then re-run --submit."
        )
    print(f"\nSubmitting {len(urls)} URL(s) to {ENDPOINT} ...")
    code = post_indexnow(urls, key, key_location)
    sys.exit(0 if code in (200, 202) else 2)


if __name__ == "__main__":
    main()

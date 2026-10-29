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
    python tools/indexnow_submit.py --submit --changed
                                                    # push every sitemap URL whose <lastmod> is newer than the
                                                    # last receipt (the post-deploy step; all of them if none)

Run --submit only AFTER the key file has been deployed to production. --submit
verifies the file is reachable first and refuses to send if it is not (a submit
with an unreachable key returns 403 and can get the domain rate-limited).

★A PUSH THAT LEAVES NO RECEIPT DID NOT HAPPEN, AND --verify MUST NOT SWALLOW --submit (2026-10-27, KA-B).
Two holes kept the freshness trip's `push` reading "never" through a release: `--verify` exited before the
submit branch, so the runbook's documented `--verify --submit` (and refresh_public_page.py's own call) only ever
checked the key file and POSTed nothing; and no code wrote indexnow_receipts.json, the file the trip reads. Now
`--verify` alone checks and exits, `--verify --submit` verifies then submits, and an accepted POST (200/202)
writes the receipt: when, how many, which URLs, the response.
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


RECEIPTS = os.path.join(WEB_ROOT, "indexnow_receipts.json")


def read_receipt() -> dict:
    try:
        with open(RECEIPTS, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def changed_since_receipt(src: str, last_submit_at: str | None) -> list[str]:
    """Sitemap URLs whose <lastmod> is after the last accepted push's DATE (all of them when nothing was pushed).
    A lastmod ON the push day counts as changed: lastmod carries no time, so a page stamped later that day must not
    be skipped (re-telling the index about one page is cheap; never telling it is the failure)."""
    since = (last_submit_at or "")[:10]
    out = []
    for block in re.findall(r"<url>([\s\S]*?)</url>", src):
        loc = (re.search(r"<loc>\s*(.*?)\s*</loc>", block) or [None, ""])[1]
        lm = (re.search(r"<lastmod>\s*(.*?)\s*</lastmod>", block) or [None, ""])[1][:10]
        if loc.startswith(BASE) and (not since or not lm or lm >= since):
            out.append(loc)
    return out


ACCEPTED = (200, 202)


def _write(rec: dict) -> None:
    tmp = RECEIPTS + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rec, fh, indent=1)
        fh.write("\n")
    os.replace(tmp, RECEIPTS)


def write_receipt(urls: list[str], code: int, mode: str) -> None:
    """The latest push at the top (what the trip and the header read), and `pushed`: each URL's own last accepted push.
    ★A RECEIPT THAT KEEPS ONLY THE LATEST PUSH CANNOT PROVE A URL WAS EVER TOLD (2026-10-29, KA-S). M2's push (17 URLs)
    overwrote M1's (120), so no file could show that a page outside the 17 had been pushed after its last change - the
    claim each KA-S row makes. The per-URL map keeps it; a refused push records nothing in it."""
    from datetime import datetime, timezone
    at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    pushed = dict(read_receipt().get("pushed") or {})
    if code in ACCEPTED:
        for u in urls:
            pushed[u] = {"at": at, "response": code, "mode": mode}
    _write({"last_submit_at": at, "count": len(urls), "mode": mode, "response": code, "urls": urls,
            "pushed": dict(sorted(pushed.items()))})
    print(f"  receipt written: {os.path.basename(RECEIPTS)} ({len(urls)} URL(s), HTTP {code}; {len(pushed)} URL(s) on record)")


def backfill_history() -> int:
    """Rebuild `pushed` from every committed version of the receipt (git history, oldest first) - each one a push that
    happened and was recorded at the time; only accepted pushes count and a URL keeps its newest. Idempotent."""
    import subprocess
    rel = os.path.relpath(RECEIPTS, WEB_ROOT).replace("\\", "/")
    log = subprocess.run(["git", "log", "--reverse", "--format=%H", "--", rel], cwd=WEB_ROOT, capture_output=True, text=True)
    pushed: dict = {}

    def keep(u: str, v: dict) -> None:
        if not pushed.get(u) or (v.get("at") or "") > (pushed[u].get("at") or ""):
            pushed[u] = v

    versions = 0
    for sha in log.stdout.split():
        show = subprocess.run(["git", "show", f"{sha}:{rel}"], cwd=WEB_ROOT, capture_output=True, text=True, encoding="utf-8")
        try:
            old = json.loads(show.stdout)
        except ValueError:
            continue
        versions += 1
        for u, v in (old.get("pushed") or {}).items():
            keep(u, v)
        if old.get("response") in ACCEPTED and old.get("last_submit_at"):
            for u in old.get("urls") or []:
                keep(u, {"at": old["last_submit_at"], "response": old["response"], "mode": old.get("mode"),
                         "from": f"git {sha[:8]}"})
    cur = read_receipt()
    for u, v in (cur.get("pushed") or {}).items():
        keep(u, v)
    if cur.get("response") in ACCEPTED and cur.get("last_submit_at"):
        for u in cur.get("urls") or []:
            keep(u, {"at": cur["last_submit_at"], "response": cur["response"], "mode": cur.get("mode")})
    cur["pushed"] = dict(sorted(pushed.items()))
    _write(cur)
    print(f"  backfilled from {versions} committed receipt(s) and the file on disk: {len(pushed)} URL(s) on record")
    return 0


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
    ap.add_argument("--changed", action="store_true",
                    help="only sitemap URLs whose <lastmod> is newer than the last receipt (all if no receipt)")
    ap.add_argument("--backfill-history", action="store_true",
                    help="rebuild the per-URL push record from the receipt's git history (sends nothing)")
    args = ap.parse_args()
    if args.backfill_history:
        sys.exit(backfill_history())

    key, key_path, key_location = find_key_file()
    print(f"IndexNow key : {key}")
    print(f"key file     : {os.path.relpath(key_path, WEB_ROOT)}  (deploy this to the site root)")
    print(f"keyLocation  : {key_location}")

    if args.url:
        urls, mode = args.url, "url"
    elif args.changed:
        last = read_receipt().get("last_submit_at")
        with open(SITEMAP, "r", encoding="utf-8") as fh:
            urls = changed_since_receipt(fh.read(), last)
        mode = "changed"
        print(f"last receipt : {last or 'none - every sitemap URL counts as changed'}")
    else:
        urls, mode = parse_sitemap_urls(), "sitemap"
    print(f"URLs to push : {len(urls)} (source: {'--url args' if mode == 'url' else 'sitemap.xml' + (' lastmod since the last receipt' if mode == 'changed' else '')})\n")
    if args.submit and not urls:
        print("Nothing changed since the last receipt - no request sent.")
        return

    if args.verify and not args.submit:
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
    if code in (200, 202):
        write_receipt(urls, code, mode)
    sys.exit(0 if code in (200, 202) else 2)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""move_inline_photos_to_storage.py - BRH 9 AB (2026-10-21): the one-time move of photos out of their rows.

logbook.photo and inventory_items.photo held each picture as base64 text (production, 2026-10-21: 22 logbook photos,
4.35 MB, and 5 part photos, 0.54 MB). Since migration 20261021000010 a photo lives in the private bucket entry-photos
and the row keeps its two object names; the server refuses new image data. This moves the photos already there, in
two passes, so nothing is ever shown missing:

  copy  (default)  each inline photo is uploaded as it is (the same bytes, never re-encoded) with a 160 px thumbnail,
                   read back and compared byte for byte, and only then named on its row (wh_inline_photo_moved, which
                   writes only if the photo is still the one copied). The inline text stays, so a page still running
                   the old code shows the photo until the new code is live.
  --clear          after the new pages are live: each row's object is read back again and compared with the inline
                   text; only a match clears it (wh_inline_photo_cleared). A row whose object is missing or differs is
                   reported and left as it is.

    python tools/move_inline_photos_to_storage.py --dry            # what would move, and its size
    python tools/move_inline_photos_to_storage.py                  # copy, local stack
    python tools/move_inline_photos_to_storage.py --clear          # clear, local stack
    python tools/move_inline_photos_to_storage.py --target prod    # production: the OWNER runs it (outward)

Local reads the service key from the running edge-runtime container. Production needs WH_PHOTO_MOVE_URL and
WH_PHOTO_MOVE_SERVICE_KEY in the environment; the key is held in memory for this process, never printed or stored.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import uuid

import requests

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

BUCKET = "entry-photos"
TABLES = ("logbook", "inventory_items")
DATA = re.compile(r"^data:image/(jpeg|jpg|png|webp);base64,", re.I)
THUMB_EDGE = 160


def endpoint(target: str) -> tuple[str, str]:
    if target == "prod":
        url, key = os.environ.get("WH_PHOTO_MOVE_URL", ""), os.environ.get("WH_PHOTO_MOVE_SERVICE_KEY", "")
        if not url or not key:
            sys.exit("production: set WH_PHOTO_MOVE_URL and WH_PHOTO_MOVE_SERVICE_KEY (the owner's)")
        return url.rstrip("/"), key
    r = subprocess.run(["docker", "exec", "supabase_edge_runtime_workhive", "printenv", "SUPABASE_SERVICE_ROLE_KEY"],
                       capture_output=True, text=True, timeout=30)
    key = (r.stdout or "").strip()
    if not key:
        sys.exit("local: the edge-runtime container is not running (docker start supabase_edge_runtime_workhive)")
    return "http://127.0.0.1:54321", key


class Api:
    def __init__(self, url: str, key: str):
        self.url, self.s = url, requests.Session()
        self.s.headers.update({"apikey": key, "Authorization": "Bearer " + key})

    def rpc(self, fn: str, args: dict):
        r = self.s.post(f"{self.url}/rest/v1/rpc/{fn}", json=args, timeout=60)
        if r.status_code >= 300:
            raise RuntimeError(f"{fn}: HTTP {r.status_code} {r.text[:200]}")
        return r.json()

    def put(self, name: str, body: bytes, mime: str) -> None:
        r = self.s.post(f"{self.url}/storage/v1/object/{BUCKET}/{name}", data=body, timeout=120,
                        headers={"Content-Type": mime, "x-upsert": "false", "cache-control": "max-age=31536000"})
        if r.status_code >= 300:
            raise RuntimeError(f"upload {name}: HTTP {r.status_code} {r.text[:200]}")

    def get(self, name: str) -> bytes | None:
        r = self.s.get(f"{self.url}/storage/v1/object/authenticated/{BUCKET}/{name}", timeout=120)
        return r.content if r.status_code == 200 else None

    def drop(self, names: list[str]) -> None:
        self.s.delete(f"{self.url}/storage/v1/object/{BUCKET}", json={"prefixes": names}, timeout=60)


def decode(photo: str) -> tuple[bytes, str, str]:
    m = DATA.match(photo)
    if not m:
        raise ValueError("not an inline image")
    kind = m.group(1).lower().replace("jpg", "jpeg")
    return base64.b64decode(photo[m.end():]), "image/" + kind, {"jpeg": "jpg"}.get(kind, kind)


def thumbnail(body: bytes) -> bytes:
    from PIL import Image
    im = Image.open(io.BytesIO(body))
    im.load()
    if im.mode not in ("RGB", "L"):
        bg = Image.new("RGB", im.size, (255, 255, 255))   # a transparent PNG must not turn black as a JPEG
        bg.paste(im.convert("RGBA"), mask=im.convert("RGBA").split()[-1])
        im = bg
    im.thumbnail((THUMB_EDGE, THUMB_EDGE))
    out = io.BytesIO()
    im.convert("RGB").save(out, "JPEG", quality=72)
    return out.getvalue()


def rows(api: Api, table: str):
    after = ""
    while True:
        page = api.rpc("wh_inline_photos", {"p_table": table, "p_after": after, "p_limit": 100})
        if not page:
            return
        yield from page
        after = page[-1]["id"]


def copy(api: Api, table: str, dry: bool) -> dict:
    n = moved = skipped = failed = size = 0
    for row in rows(api, table):
        n += 1
        if row.get("photo_path"):
            skipped += 1            # copied on an earlier run; --clear finishes it
            continue
        try:
            body, mime, ext = decode(row["photo"])
        except Exception as e:
            print(f"  {table} {row['id']}: unreadable inline photo, left as it is ({e})")
            failed += 1
            continue
        size += len(body)
        if dry:
            continue
        folder = row.get("auth_uid") or "legacy"
        stem = f"{folder}/{uuid.uuid4()}"
        name, thumb = f"{stem}.{ext}", f"{stem}.t.jpg"
        try:
            api.put(name, body, mime)
            api.put(thumb, thumbnail(body), "image/jpeg")
            back = api.get(name)
            if back is None or hashlib.sha256(back).digest() != hashlib.sha256(body).digest():
                raise RuntimeError("the object read back differs from the row's photo")
            if not api.rpc("wh_inline_photo_moved", {"p_table": table, "p_id": row["id"], "p_md5": row["photo_md5"],
                                                     "p_path": name, "p_thumb": thumb}):
                raise RuntimeError("the row changed while it was copied")
            moved += 1
        except Exception as e:
            api.drop([name, thumb])
            print(f"  {table} {row['id']}: not moved ({e})")
            failed += 1
    return {"table": table, "inline": n, "copied": moved, "already_copied": skipped, "failed": failed, "bytes": size}


def clear(api: Api, table: str, dry: bool) -> dict:
    n = cleared = waiting = mismatched = 0
    for row in rows(api, table):
        n += 1
        if not (row.get("photo_path") and row.get("photo_thumb_path")):
            waiting += 1            # not copied yet: run the copy pass first
            continue
        body, _, _ = decode(row["photo"])
        back = api.get(row["photo_path"])
        if back is None or back != body or api.get(row["photo_thumb_path"]) is None:
            print(f"  {table} {row['id']}: its object is missing or differs - the inline photo is kept")
            mismatched += 1
            continue
        if not dry and api.rpc("wh_inline_photo_cleared", {"p_table": table, "p_id": row["id"]}):
            cleared += 1
    return {"table": table, "inline": n, "cleared": cleared, "not_copied": waiting, "mismatched": mismatched}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=("local", "prod"), default="local")
    ap.add_argument("--clear", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    api = Api(*endpoint(a.target))
    out = [(clear if a.clear else copy)(api, t, a.dry) for t in TABLES]
    print(json.dumps({"target": a.target, "pass": "clear" if a.clear else "copy", "dry": a.dry, "tables": out}, indent=1))
    return 1 if any(t.get("failed") or t.get("mismatched") for t in out) else 0


if __name__ == "__main__":
    sys.exit(main())

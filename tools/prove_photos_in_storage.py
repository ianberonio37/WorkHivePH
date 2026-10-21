#!/usr/bin/env python3
"""prove_photos_in_storage.py - BRH 9 AB (2026-10-21): the reproduction, made to FAIL on demand, against the local stack.

The defect (production, 2026-10-21: logbook.photo 22 photos / 4.35 MB, inventory_items.photo 5 / 0.54 MB): a photo stored
inside its row as base64 text, so the free 500 MB database grew by every photo and every list read shipped every photo.
This proves, live and as the real cast (Dela Cruz Delivery Fleet: Rosa dela Cruz, supervisor; Ben Ocampo, worker; an
outsider from another hive), that each half of the defect no longer reproduces:

  R1  the old read shape still ships the picture: rows holding inline photos (made here, as production holds them) read
      with select=* carry the image text - the reproduction itself, shown on demand;
  R2  the list read the pages now send (utils.js WH_ROW_COLS) carries no image text from the same rows;
  R3  a new inline photo is refused by the server, as the signed-in worker (P0001);
  R4  an upload goes only into the uploader's own folder;
  R5  a photo is exactly as private as its row: a teammate who can read the row signs its URL, an outsider and a
      signed-out visitor cannot;
  R6  an object a row names cannot be deleted by a client; once no row names it, its owner can;
  R7  the one-time move (tools/move_inline_photos_to_storage.py) copies each inline photo, verifies it, names it on the
      row, and the clear pass empties the inline text - no row of the proof holds image data afterwards.

Every row and object it makes is its own (ids prefixed brhab-proof-) and is removed at the end, pass or fail.

    python tools/prove_photos_in_storage.py        # exit 0 = every check held; receipt in .tmp/brh_ab_proof.json
"""
from __future__ import annotations

import base64
import io
import json
import random
import re
import subprocess
import sys
import uuid
from pathlib import Path

import requests

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
URL = "http://127.0.0.1:54321"
DB = "supabase_db_workhive"
BUCKET = "entry-photos"
HIVE = "2807e679-788e-4738-a95a-a81c7abd4736"           # Dela Cruz Delivery Fleet
CAST = {"rosa": "delacruzfleet", "ben": "driverben", "outsider": "bryangarcia"}
PASSWORD = "test1234"
PREFIX = "brhab-proof-"


def psql(sql: str) -> str:
    r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-At", "-v",
                        "ON_ERROR_STOP=1", "-f", "-"], input=sql, capture_output=True, text=True, encoding="utf-8",
                       timeout=120)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[-300:])
    return r.stdout.strip()


def env(name: str) -> str:
    r = subprocess.run(["docker", "exec", "supabase_edge_runtime_workhive", "printenv", name],
                       capture_output=True, text=True, timeout=30)
    return (r.stdout or "").strip()


def photo(seed: int, kb: int) -> str:
    """A camera-like JPEG of about `kb` KB, as a data URL - the shape production's rows hold."""
    from PIL import Image
    rnd = random.Random(seed)
    # coarse noise blown up to 800 x 600: soft shapes and texture, which JPEG compresses the way it does a real scene
    im = Image.frombytes("RGB", (200, 150), bytes(rnd.randrange(256) for _ in range(200 * 150 * 3)))
    im = im.resize((800, 600), Image.BICUBIC)
    for q in (92, 85, 75, 65, 55, 45):
        out = io.BytesIO()
        im.save(out, "JPEG", quality=q)
        if out.tell() <= kb * 1024:
            break
    return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()


class Who:
    def __init__(self, anon: str, user: str | None):
        self.anon, self.token, self.uid = anon, anon, None
        if user:
            r = requests.post(f"{URL}/auth/v1/token?grant_type=password", headers={"apikey": anon}, timeout=30,
                              json={"email": f"{user}@auth.workhiveph.com", "password": PASSWORD})
            r.raise_for_status()
            j = r.json()
            self.token, self.uid = j["access_token"], j["user"]["id"]

    def h(self, extra: dict | None = None) -> dict:
        return {"apikey": self.anon, "Authorization": "Bearer " + self.token, **(extra or {})}

    def get(self, path: str) -> requests.Response:
        return requests.get(f"{URL}/rest/v1/{path}", headers=self.h(), timeout=60)

    def post(self, path: str, body) -> requests.Response:
        return requests.post(f"{URL}/rest/v1/{path}", headers=self.h({"Prefer": "return=minimal"}), json=body, timeout=60)

    def upload(self, name: str, body: bytes) -> requests.Response:
        return requests.post(f"{URL}/storage/v1/object/{BUCKET}/{name}", data=body, timeout=60,
                             headers=self.h({"Content-Type": "image/jpeg", "x-upsert": "false"}))

    def sign(self, names: list[str]) -> list[dict]:
        r = requests.post(f"{URL}/storage/v1/object/sign/{BUCKET}", headers=self.h(), timeout=60,
                          json={"paths": names, "expiresIn": 600})
        return r.json() if r.status_code == 200 else [{"path": n, "error": f"HTTP {r.status_code}"} for n in names]

    def remove(self, names: list[str]) -> list:
        r = requests.delete(f"{URL}/storage/v1/object/{BUCKET}", headers=self.h(), json={"prefixes": names}, timeout=60)
        return r.json() if r.status_code == 200 else []


def row_cols(source: str) -> str:
    src = (ROOT / "utils.js").read_text(encoding="utf-8")
    m = re.search(r"\b" + source + r":\s*((?:'[^']*'\s*\+?\s*)+)", src)
    return "".join(re.findall(r"'([^']*)'", m.group(1)))


def main() -> int:
    anon, service = env("SUPABASE_ANON_KEY"), env("SUPABASE_SERVICE_ROLE_KEY")
    if not anon or not service:
        print("SKIP prove-photos-in-storage - the local stack is not running (no unearned pass)")
        return 0
    svc = {"apikey": service, "Authorization": "Bearer " + service}
    rosa, ben, outsider, nobody = Who(anon, CAST["rosa"]), Who(anon, CAST["ben"]), Who(anon, CAST["outsider"]), Who(anon, None)
    checks, receipt = [], {"hive": "Dela Cruz Delivery Fleet", "rows": {}}

    def check(key: str, ok: bool, saw: str) -> None:
        checks.append((key, ok, saw))
        print(f"  {'PASS' if ok else 'FAIL'} {key}: {saw}")

    lb_ids = [f"{PREFIX}lb-{i}" for i in range(4)]
    inv_ids = [f"{PREFIX}inv-{i}" for i in range(2)]
    made_objects: list[str] = []
    try:
        # the production shape: rows holding their photos as text (made with triggers off - the server now refuses it)
        pics = {i: photo(i, 190) for i in lb_ids + inv_ids}
        vals_lb = ",\n".join(
            f"('{i}', 'Rosa dela Cruz', now() - interval '{n} minutes', 'FLT 9005', 'Mechanical', 'Proof: a photo kept in the row',"
            f" 'Open', 'Breakdown / Corrective', '{HIVE}', '{rosa.uid}', '{pics[i]}')" for n, i in enumerate(lb_ids))
        vals_inv = ",\n".join(
            f"('{i}', 'Rosa dela Cruz', 'BRHAB-{n}', 'Proof part {n}', 'pcs', 3, 1, 'approved', '{HIVE}', '{rosa.uid}', '{pics[i]}')"
            for n, i in enumerate(inv_ids))
        psql(f"""begin; set local session_replication_role = replica;
insert into public.logbook (id, worker_name, date, machine, category, problem, status, maintenance_type, hive_id, auth_uid, photo)
values {vals_lb};
insert into public.inventory_items (id, worker_name, part_number, part_name, unit, qty_on_hand, min_qty, status, hive_id, auth_uid, photo)
values {vals_inv};
commit;""")
        inline_bytes = sum(len(p) for p in pics.values())
        receipt["rows"] = {"logbook": lb_ids, "inventory_items": inv_ids, "inline_text_bytes": inline_bytes}

        ids = ",".join(lb_ids)
        old = rosa.get(f"v_logbook_truth?select=*&id=in.({ids})")
        new = rosa.get(f"v_logbook_truth?select={row_cols('v_logbook_truth')}&id=in.({ids})")
        check("R1 the old read shape ships the picture", old.status_code == 200 and old.text.count("data:image/") == 4,
              f"select=* over 4 rows: HTTP {old.status_code}, {len(old.content):,} bytes, {old.text.count('data:image/')} images")
        check("R2 the list read the pages send carries no picture",
              new.status_code == 200 and "data:image/" not in new.text and len(new.json()) == 4,
              f"WH_ROW_COLS: HTTP {new.status_code}, {len(new.content):,} bytes, {new.text.count('data:image/')} images "
              f"({len(old.content) / max(1, len(new.content)):.0f}x smaller)")
        iold = rosa.get(f"v_inventory_items_truth?select=*&id=in.({','.join(inv_ids)})")
        inew = rosa.get(f"v_inventory_items_truth?select={row_cols('v_inventory_items_truth')}&id=in.({','.join(inv_ids)})")
        check("R2 the inventory list read carries no picture",
              iold.text.count("data:image/") == 2 and "data:image/" not in inew.text and inew.status_code == 200,
              f"select=* {len(iold.content):,} bytes ({iold.text.count('data:image/')} images) vs "
              f"WH_ROW_COLS {len(inew.content):,} bytes ({inew.text.count('data:image/')})")
        receipt["read_bytes"] = {"logbook_star": len(old.content), "logbook_cols": len(new.content),
                                 "inventory_star": len(iold.content), "inventory_cols": len(inew.content)}

        ref = ben.post("logbook", {"id": f"{PREFIX}inline", "worker_name": "Ben Ocampo", "date": "2026-10-21T08:00:00Z",
                                   "machine": "FLT 9005", "category": "Mechanical", "problem": "inline photo attempt",
                                   "status": "Open", "maintenance_type": "Inspection", "hive_id": HIVE,
                                   "auth_uid": ben.uid, "photo": pics[lb_ids[0]]})
        landed = psql(f"select count(*) from public.logbook where id = '{PREFIX}inline';")
        check("R3 a new inline photo is refused", ref.status_code >= 400 and "saved separately" in ref.text and landed == "0",
              f"HTTP {ref.status_code} {ref.json().get('code') if ref.headers.get('content-type','').startswith('application/json') else ''}, rows written {landed}")

        own = f"{ben.uid}/{uuid.uuid4()}.jpg"
        body = base64.b64decode(pics[lb_ids[1]].split(",", 1)[1])
        up_own = ben.upload(own, body)
        if up_own.status_code < 300:
            made_objects.append(own)
        foreign = f"{rosa.uid}/{uuid.uuid4()}.jpg"
        # a SMALL body for the refused upload: the local gateway answers a refusal before reading a large body, and the
        # unread bytes then stall the next request on that connection for a minute (measured 2026-10-21; the product
        # never sends an upload its policy refuses, so this is the instrument's hazard, not the page's)
        up_foreign = ben.upload(foreign, body[:2048])
        if up_foreign.status_code < 300:
            made_objects.append(foreign)
        check("R4 an upload goes only into the uploader's own folder", up_own.status_code < 300 and up_foreign.status_code >= 400,
              f"own folder HTTP {up_own.status_code}; another person's folder HTTP {up_foreign.status_code}")

        pre = rosa.sign([own])
        # Ben's entry naming his upload (made directly: the write path itself is R3's subject, and an insert through the
        # API would pay Ben achievement XP for a proof row)
        psql(f"""begin; set local session_replication_role = replica;
insert into public.logbook (id, worker_name, date, machine, category, problem, status, maintenance_type, hive_id, auth_uid, photo_path)
values ('{PREFIX}named', 'Ben Ocampo', now(), 'FLT 9005', 'Mechanical', 'a photo named by its row', 'Open', 'Inspection',
        '{HIVE}', '{ben.uid}', '{own}');
commit;""")
        team, out, anon_s = rosa.sign([own]), outsider.sign([own]), nobody.sign([own])
        ok_team = bool(team and team[0].get("signedURL"))
        check("R5 a photo is as private as its row",
              ok_team and not (pre and pre[0].get("signedURL")) and not (out and out[0].get("signedURL"))
              and not (anon_s and anon_s[0].get("signedURL")),
              f"teammate before the row names it: {'signed' if pre and pre[0].get('signedURL') else 'refused'}; "
              f"after: {'signed' if ok_team else 'refused'}; outsider: {'signed' if out and out[0].get('signedURL') else 'refused'}; "
              f"signed out: {'signed' if anon_s and anon_s[0].get('signedURL') else 'refused'}")

        gone_while_named = ben.remove([own])
        still = psql(f"select count(*) from storage.objects where bucket_id = '{BUCKET}' and name = '{own}';")
        psql(f"begin; set local session_replication_role = replica; delete from public.logbook where id = '{PREFIX}named'; commit;")
        gone_after = ben.remove([own])
        after = psql(f"select count(*) from storage.objects where bucket_id = '{BUCKET}' and name = '{own}';")
        if after == "0":
            made_objects.remove(own)
        check("R6 a named object cannot be deleted by a client; an orphan can, by its owner",
              still == "1" and after == "0" and not gone_while_named and bool(gone_after),
              f"while named: {len(gone_while_named)} removed, object kept={still == '1'}; no row names it: "
              f"{len(gone_after)} removed, object gone={after == '0'}")

        mv = subprocess.run([sys.executable, str(ROOT / "tools" / "move_inline_photos_to_storage.py")],
                            capture_output=True, text=True, encoding="utf-8", timeout=600)
        named_now = psql(f"select count(*) from (select id from public.logbook where id like '{PREFIX}%' and photo_path is not null "
                         f"union all select id from public.inventory_items where id like '{PREFIX}%' and photo_path is not null) x;")
        signed_moved = rosa.sign([psql(f"select photo_thumb_path from public.logbook where id = '{lb_ids[0]}';")])
        cl = subprocess.run([sys.executable, str(ROOT / "tools" / "move_inline_photos_to_storage.py"), "--clear"],
                            capture_output=True, text=True, encoding="utf-8", timeout=600)
        inline_left = psql(f"select count(*) from (select id from public.logbook where id like '{PREFIX}%' and photo like 'data:%' "
                           f"union all select id from public.inventory_items where id like '{PREFIX}%' and photo like 'data:%') x;")
        check("R7 the move copies, verifies and clears every inline photo",
              mv.returncode == 0 and cl.returncode == 0 and named_now == "6" and inline_left == "0"
              and bool(signed_moved and signed_moved[0].get("signedURL")),
              f"copy exit {mv.returncode}, {named_now} of 6 rows named; teammate signs a moved thumbnail: "
              f"{'yes' if signed_moved and signed_moved[0].get('signedURL') else 'no'}; clear exit {cl.returncode}, inline left {inline_left}")
        receipt["move"] = {"copy": mv.stdout[-1200:], "clear": cl.stdout[-800:]}
    finally:
        names = psql(f"select coalesce(string_agg(n, ' '), '') from (select photo_path n from public.logbook where id like '{PREFIX}%' "
                     f"union all select photo_thumb_path from public.logbook where id like '{PREFIX}%' "
                     f"union all select photo_path from public.inventory_items where id like '{PREFIX}%' "
                     f"union all select photo_thumb_path from public.inventory_items where id like '{PREFIX}%') x where n is not null;").split()
        psql(f"""begin; set local session_replication_role = replica;
delete from public.logbook where id like '{PREFIX}%';
delete from public.inventory_items where id like '{PREFIX}%';
delete from public.embedding_outbox where row_id like '{PREFIX}%';
commit;""")
        leftovers = [n for n in names + made_objects if n]
        if leftovers:
            requests.delete(f"{URL}/storage/v1/object/{BUCKET}", headers=svc, json={"prefixes": leftovers}, timeout=60)
        receipt["cleanup"] = {"rows_removed": True, "objects_removed": len(leftovers)}

    receipt["checks"] = [{"check": k, "ok": ok, "saw": saw} for k, ok, saw in checks]
    (ROOT / ".tmp").mkdir(exist_ok=True)
    (ROOT / ".tmp" / "brh_ab_proof.json").write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    bad = [k for k, ok, _ in checks if not ok]
    print(("FAIL prove-photos-in-storage - " + "; ".join(bad)) if bad else
          f"PASS prove-photos-in-storage - {len(checks)} checks held against the local stack as the real cast")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

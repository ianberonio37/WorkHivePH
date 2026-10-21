#!/usr/bin/env python3
"""file-storage-owned - SL D4 (2026-10-19): every file a page takes is kept where the page says, under the person who
gave it, and comes back to them - or it is read and kept nowhere, and the page says so.

WHAT THE D4 WALK FOUND (receipts SL845-SL850, phone-390 and desktop-1280, each page as its row's cast):
  * marketplace.html and marketplace-seller.html upload a photo the moment it is picked. Remove, a second pick,
    closing the edit sheet and leaving the page each left that upload in marketplace-listings, a PUBLIC bucket, served
    by its URL after the person had taken it off their screen. whHeldUpload (utils.js) now holds the upload a form has
    not saved and deletes it on each of those; a save commits it to the row that names it. (T134 already deleted a
    deleted listing's photo and the one a SAVED edit replaces.)
  * On both pages the Remove photo button could not be tapped: the zone's file input (position:absolute; inset:0)
    covered it, so a tap on Remove opened the photo picker. A photo could be replaced but never taken off.
  * inventory.html: Remove photo + Save put the photo straight back (`currentPhotoData || prev.photo`).
  * logbook.html: the photo of a defect was sent to the AI and dropped - the entry kept the AI's words about the
    picture and not the picture.
  * integrations (vehicle manual, CMMS export), resume, the GCash receipt uploads and the nameplate scan read a file
    and keep nothing - true, and measured (a marker in the file was in none of 786 text columns, no storage object) -
    but only resume.html said so. Each now does.

WHAT THIS HOLDS (static, every run):
  1. ROSTER  - every file input on every served page has a disposition below. A new one fails until it is walked.
  2. BUCKET  - the page holds its upload (whHeldUpload hold / release / commit), and Remove sits above the input.
  3. STORED  - logbook's and inventory's photo is kept with its row: uploaded to the private bucket entry-photos at
               save (BRH 9 AB; photos-in-storage holds the upload, the reads and the bucket). No `currentPhotoData ||`
               fallback can put a removed photo back, and the photo column keeps its server cap.
  4. READ    - the function the file goes to stores nothing (no storage call, no insert), and the page says so.
  5. LOGBOOK - the defect capture and Attach Photo share one encoder; a fresh entry resets the capture.
  6. SHELL   - whHeldUpload deletes on pagehide with a keepalive request; the voice file helper has no caller.
LIVE (local stack up): the public bucket holds no object older than an hour that no listing names.

    python tools/validate_file_storage.py            # the gate
    python tools/validate_file_storage.py --self-test
"""
from __future__ import annotations

import glob
import io
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# page -> {input id (or the static prefix of a generated id): (kind, where, the sentence the page must carry)}
ROSTER = {
    "integrations.html": {
        "veh-doc-file": ("read", "vehicle-doc-extract", "The file stays on your device. Only its text is sent to be read"),
        "file-input":   ("read", "", "The file is read in your browser and not uploaded."),
    },
    "inventory.html": {"f-photo-input": ("stored", "inventory_items", "")},
    "logbook.html": {
        "f-photo":        ("stored", "logbook", ""),
        "vdc-file-input": ("stored", "logbook", "This photo is saved with the entry."),
        "a-scan-input":   ("read", "equipment-label-ocr", "The photo itself is not kept."),
    },
    "marketplace.html": {
        "post-image-file": ("bucket", "marketplace-listings", ""),
        "svc-pay-img-":    ("read", "gcash-receipt-ocr", "The screenshot is read for the amount and reference, then discarded."),
    },
    "marketplace-seller.html": {
        "edit-image-file": ("bucket", "marketplace-listings", ""),
        "svc-topup-img-":  ("read", "gcash-receipt-ocr", "The screenshot is read for the amount and reference, then discarded."),
    },
    "resume.html": {
        "file-photo": ("read", "resume-extract", "Your files are read just to fill in your resume, then discarded."),
        "file-any":   ("read", "resume-extract", "Your files are read just to fill in your resume, then discarded."),
    },
}
# bucket pages: the picker's own names (upload result, the held handle, the reset, the Remove button)
BUCKET_WIRING = {
    "marketplace.html":        {"held": "_postHeld", "reset": "resetPostImagePicker", "remove": "post-image-remove"},
    "marketplace-seller.html": {"held": "_editHeld", "reset": "resetEditImagePicker", "remove": "edit-image-remove"},
}
INPUT_RX = re.compile(r"<input\b[^>]*?\btype=\\?[\"']file\\?[\"'][^>]*>", re.S)
ID_RX = re.compile(r"\bid=\\?[\"']([A-Za-z0-9_-]+)")


def served_pages() -> list[str]:
    pages = glob.glob(str(ROOT / "*.html")) + glob.glob(str(ROOT / "tools" / "*" / "index.html")) \
        + glob.glob(str(ROOT / "learn" / "**" / "*.html"), recursive=True) + glob.glob(str(ROOT / "feedback" / "*.html"))
    return sorted(str(Path(p).relative_to(ROOT)).replace("\\", "/") for p in pages
                  if not re.search(r"backup|\.bak|_bak", Path(p).name))


def file_inputs(text: str) -> list[str]:
    out = []
    for m in INPUT_RX.finditer(text):
        i = ID_RX.search(m.group(0))
        out.append(i.group(1) if i else "")
    return out


def _strip_comments(js: str) -> str:
    return re.sub(r"/\*[\s\S]*?\*/", "", re.sub(r"(?m)^\s*//.*$", "", js))


def _fn_body(text: str, name: str) -> str:
    m = re.search(r"(?:async\s+)?function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", text)
    if not m:
        return ""
    depth, i = 0, m.end() - 1
    for j in range(i, min(len(text), i + 20000)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
    return text[i:i + 20000]


def check_roster(pages: dict[str, str]) -> list[str]:
    bad = []
    for page, text in pages.items():
        known = ROSTER.get(page, {})
        for iid in file_inputs(text):
            if not iid or not any(iid == k or (k.endswith("-") and iid.startswith(k)) for k in known):
                bad.append(f"{page}: a file input ({iid or 'no id'}) with no disposition - walk it (where does the file go,"
                           " whose is it, does it come back?) and add it to ROSTER")
        for k in known:
            if not any(iid == k or (k.endswith("-") and iid.startswith(k)) for iid in file_inputs(text)):
                bad.append(f"{page}: ROSTER names {k}, which the page no longer has - re-walk and update the roster")
    for page in ROSTER:
        if page not in pages:
            bad.append(f"{page}: in ROSTER but not a served page")
    return bad


def check_bucket(page: str, text: str) -> list[str]:
    w = BUCKET_WIRING[page]
    code = _strip_comments(text)
    bad = []
    if not re.search(re.escape(w["held"]) + r"\s*=\s*whHeldUpload\(\s*db\s*,\s*STORAGE_BUCKET", code):
        bad.append(f"{page}: the picker's upload is not held (whHeldUpload) - a removed or abandoned photo stays in the public bucket")
    if not re.search(re.escape(w["held"]) + r"\)\s*" + re.escape(w["held"]) + r"\.hold\(\s*up\.key\s*\)", code) \
            and not re.search(r"\.hold\(\s*up\.key\s*\)", code):
        bad.append(f"{page}: the upload's key is never held")
    if not re.search(r"return\s*\{\s*url:[^}]*key:\s*filename", code):
        bad.append(f"{page}: uploadImageBlob no longer returns the object key a later delete needs")
    if not re.search(re.escape(w["held"]) + r"\)?\s*" + re.escape(w["held"]) + r"\.release\(\)", _fn_body(code, w["reset"])) \
            and ".release()" not in _fn_body(code, w["reset"]):
        bad.append(f"{page}: {w['reset']} (Remove) does not release the held upload")
    if len(re.findall(re.escape(w["held"]) + r"\.commit\(\)", code)) < 1:
        bad.append(f"{page}: no save path commits the held upload - a save would be followed by deleting its own photo")
    btn = re.search(r"<button\b[^>]*\bid=\"" + re.escape(w["remove"]) + r"\"[^>]*>", text)
    if not btn or not re.search(r"position:\s*relative[^\"]*z-index:\s*[1-9]", btn.group(0)):
        bad.append(f"{page}: the Remove photo button is not raised above the zone's file input - a tap on it opens the picker")
    elif not re.search(r"min-height:\s*44px", btn.group(0)):
        bad.append(f"{page}: the Remove photo button is under the 44px target")
    return bad


def check_inline(page: str, text: str, table: str, migrations: str) -> list[str]:
    bad = []
    code = _strip_comments(text)
    if re.search(r"photo\s*:\s*currentPhotoData\s*\|\|\s*[\w.]+\.photo", code):
        bad.append(f"{page}: a save falls back to the old photo (currentPhotoData || ...photo) - Remove cannot remove it")
    if not re.search(r"trg_inline_image_size_" + ("inventory" if table == "inventory_items" else table) + r"\b", migrations):
        bad.append(f"{page}: {table}.photo has no server-side size cap trigger (check_inline_image_size)")
    return bad


def check_read(page: str, iid: str, fn: str, sentence: str, text: str) -> list[str]:
    bad = []
    if sentence and sentence not in text:
        bad.append(f"{page}: {iid} reads a file and keeps none of it, and the page no longer says so ('{sentence[:50]}...')")
    if fn:
        src = ROOT / "supabase" / "functions" / fn / "index.ts"
        if not src.exists():
            bad.append(f"{page}: {iid} sends its file to {fn}, which does not exist")
        else:
            s = _strip_comments(src.read_text(encoding="utf-8"))
            if re.search(r"\.storage\s*\.\s*from\(|\.upload\(", s):
                bad.append(f"{fn}: the function {page} sends a file to now stores it - its 'not kept' sentence is false")
            if re.search(r"\.insert\(", s) and fn != "visual-defect-capture":
                bad.append(f"{fn}: the function now inserts rows - check none carries the file, then update this gate")
    return bad


def check_logbook(text: str) -> list[str]:
    bad = []
    code = _strip_comments(text)
    if len(re.findall(r"lbEncodeEntryPhoto\(", code)) < 3:   # the definition + Attach Photo + the defect capture
        bad.append("logbook.html: the defect capture and Attach Photo no longer share lbEncodeEntryPhoto - the photo of a"
                   " defect can be dropped again, or encoded past the entry's budget")
    if "_vdcAttached = got.data" not in code:
        bad.append("logbook.html: a defect capture no longer becomes the entry's photo")
    if "vdcReset();" not in _fn_body(code, "clearForm"):
        bad.append("logbook.html: a fresh entry keeps the last entry's defect capture (clearForm does not reset it)")
    vdc = ROOT / "supabase" / "functions" / "visual-defect-capture" / "index.ts"
    if vdc.exists():
        ins = re.findall(r"\.insert\(\{([\s\S]*?)\}\)", _strip_comments(vdc.read_text(encoding="utf-8")))
        if any(re.search(r"image|data_url|photo", x) for x in ins):
            bad.append("visual-defect-capture: an insert now carries the image - the photo is kept in two places")
    return bad


def check_shell() -> list[str]:
    bad = []
    u = _strip_comments((ROOT / "utils.js").read_text(encoding="utf-8"))
    body = _fn_body(u, "whHeldUpload")
    if not body:
        return ["utils.js: whHeldUpload is gone - the marketplace pickers cannot take an unsaved upload back"]
    if not re.search(r"addEventListener\(\s*['\"]pagehide['\"]", body) or "keepalive: true" not in body:
        bad.append("utils.js: whHeldUpload no longer deletes a held upload when the page is left (pagehide + keepalive)")
    if not re.search(r"hold\(key\)\s*\{\s*if\s*\(held\s*&&\s*held\s*!==\s*key\)\s*drop\(held\)", body):
        bad.append("utils.js: whHeldUpload.hold no longer deletes the upload it replaces")
    vh = (ROOT / "voice-handler.js").read_text(encoding="utf-8")
    callers = [m.start() for m in re.finditer(r"_openFileAttachment\s*\(", _strip_comments(vh))]
    if len(callers) > 1:   # the definition only
        bad.append("voice-handler.js: _openFileAttachment is now called - a file the voice assistant takes needs a"
                   " disposition (walk it, add it here)")
    return bad


def check_live() -> tuple[str, list[str]]:
    q = ("select o.name from storage.objects o where o.bucket_id = 'marketplace-listings' "
         "and o.created_at < now() - interval '1 hour' and not exists (select 1 from public.marketplace_listings l "
         "where l.image_url like '%/marketplace-listings/' || o.name || '%')")
    try:
        r = subprocess.run(["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres", "-At",
                            "-c", q], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return "skipped (no docker)", []
    if r.returncode != 0:
        return "skipped (database not reachable)", []
    names = [x for x in r.stdout.split() if x.strip()]
    if names:
        return "ran", [f"marketplace-listings: {len(names)} object(s) older than an hour that no listing names "
                       f"(first: {names[0]}) - a photo someone took off their screen is still public"]
    return "ran", []


def run() -> int:
    pages = {p: (ROOT / p).read_text(encoding="utf-8") for p in served_pages()}
    pages = {p: t for p, t in pages.items() if file_inputs(t) or p in ROSTER}
    migrations = "\n".join(Path(f).read_text(encoding="utf-8", errors="replace")
                           for f in glob.glob(str(ROOT / "supabase" / "migrations" / "*.sql")))
    bad = check_roster(pages)
    for page, inputs in ROSTER.items():
        text = pages.get(page, "")
        for iid, (kind, where, sentence) in inputs.items():
            if kind == "read":
                bad += check_read(page, iid, where, sentence, text)
            elif kind == "stored":
                if sentence and sentence not in text:
                    bad.append(f"{page}: {iid} no longer tells the person the photo is saved with the entry")
        if page in BUCKET_WIRING:
            bad += check_bucket(page, text)
        tables = {w for k, w, _ in inputs.values() if k == "stored"}
        for t in tables:
            bad += check_inline(page, text, t, migrations)
    bad += check_logbook(pages.get("logbook.html", ""))
    bad += check_shell()
    live, live_bad = check_live()
    bad += live_bad
    n_inputs = sum(len(v) for v in ROSTER.values())
    if bad:
        for b in bad:
            print("  FAIL " + b)
        print(f"FAIL file-storage-owned - {len(bad)} problem(s)")
        return 1
    print(f"PASS file-storage-owned - {n_inputs} file inputs on {len(ROSTER)} pages each have a walked disposition: 2 bucket"
          f" pickers hold their upload until a save names it, 3 photos are uploaded to entry-photos at save and named by"
          f" their row (photos-in-storage), {sum(1 for v in ROSTER.values() for k in v.values() if k[0] == 'read')} reads"
          f" keep nothing and say so;"
          f" live orphan check {live}")
    return 0


def self_test() -> int:
    ok = True
    def expect(name, cond):
        nonlocal ok
        print(("  ok   " if cond else "  FAIL ") + name)
        ok = ok and cond
    real = {p: (ROOT / p).read_text(encoding="utf-8") for p in ROSTER}
    mk, sel, inv, lb = real["marketplace.html"], real["marketplace-seller.html"], real["inventory.html"], real["logbook.html"]
    expect("real pages pass the bucket checks", not check_bucket("marketplace.html", mk) and not check_bucket("marketplace-seller.html", sel))
    expect("Remove that does not release fails",
           bool(check_bucket("marketplace.html", mk.replace("if (_postHeld)  _postHeld.release();", ""))))
    expect("an upload never held fails", bool(check_bucket("marketplace.html", mk.replace("_postHeld.hold(up.key)", "_postHeld.key"))))
    expect("no commit before the reset fails", bool(check_bucket("marketplace.html", mk.replace("_postHeld.commit()", "_postHeld.key"))))
    expect("Remove under the input fails",
           bool(check_bucket("marketplace-seller.html", sel.replace('id="edit-image-remove" style="position:relative;z-index:1;', 'id="edit-image-remove" style="'))))
    expect("the prev.photo fallback fails",
           bool(check_inline("inventory.html", inv.replace("const updated = { ...prev, ...payload };", "const updated = { ...prev, ...payload, photo: currentPhotoData || prev.photo || null };"), "inventory_items", "trg_inline_image_size_inventory")))
    expect("a missing size-cap trigger fails", bool(check_inline("inventory.html", inv, "inventory_items", "")))
    expect("a read page without its sentence fails",
           bool(check_read("resume.html", "file-any", "resume-extract", "Your files are read just to fill in your resume, then discarded.", "nothing said")))
    expect("the defect capture not attaching fails", bool(check_logbook(lb.replace("_vdcAttached = got.data", "_vdcAttached = null"))))
    expect("clearForm not resetting the capture fails", bool(check_logbook(lb.replace("  vdcReset();\n  _pendingAssetRefId", "  _pendingAssetRefId"))))
    fake = {"marketplace.html": mk + '<input type="file" id="new-upload">'}
    expect("a new file input without a disposition fails", any("new-upload" in b for b in check_roster(fake)))
    expect("a generated id is matched by its prefix", not any("svc-pay-img" in b for b in check_roster({"marketplace.html": mk})))
    print("PASS self-test" if ok else "FAIL self-test")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else run())

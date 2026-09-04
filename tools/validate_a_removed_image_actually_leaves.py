""" -*- coding: utf-8 -*-
A listing image must leave the public bucket when the listing does - and when it is replaced (T134).

Deleting a listing removed the row and left the JPEG sitting in a PUBLIC bucket at a permanent URL.
"This cannot be undone" was true of the row and quietly false of the photo: anyone holding the link
still had it, after the seller believed they had removed the listing. That is the gap between what a
destructive confirm promises and what it delivers.

★AND THE FIX-EVERY-PATH PASS FOUND THE BIGGER SOURCE. Deleting is rare. REPLACING an image on edit
is common, and it orphaned the old object exactly the same way - same bucket, same permanent URL,
far more often. A gate holding only the delete path would have locked the half that almost never
runs while the frequent one kept leaking, which is worse than no gate, because the board would say
the class was closed.

BOTH SITES, AND BOTH GUARDS:

  1. the DELETE path removes the object after the row is gone;
  2. the EDIT path removes the OLD object - but only when the URL actually CHANGED (re-saving an
     unchanged listing must not delete its own live image) and only when the old object is OURS
     (a seller may paste an external URL, and we must not try to reach into someone else's host);
  3. both are BEST-EFFORT and wrapped - cleanup runs after the write and cannot throw into it.
     A storage hiccup must never cost a seller the edit or the delete they asked for. This is the
     inverse of the coupling T12 had to break: there, the note must survive the AI; here, the
     write must survive the cleanup.

TEETH: synthetic negatives - each path removed, and each of the edit path's two guards dropped.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "marketplace-seller.html"

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"(?m)^\s*//.*$")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def _strip_comments(src: str) -> str:
    """Both fixes are documented in detail directly above the code that implements them."""
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub(" ", HTML_COMMENT.sub(" ", src)))


def audit(src: str) -> list:
    s = _strip_comments(src)
    out = []

    removes = re.findall(r"storage\s*\.\s*from\([^)]*\)\s*\.\s*remove\(", s)
    if len(removes) < 2:
        out.append(f"marketplace-seller.html: only {len(removes)} storage remove() call(s) - this page "
                   f"owns TWO image lifecycles, delete AND replace-on-edit. Holding one leaves the "
                   f"other orphaning objects into a public bucket at permanent URLs, and the rarer "
                   f"path is the one usually kept")

    # the edit path's two guards
    if not re.search(r"_old\s*!==\s*imageUrl|imageUrl\s*!==\s*_old", s):
        out.append("marketplace-seller.html: the replace-cleanup no longer checks that the URL actually "
                   "CHANGED - re-saving an unchanged listing would delete its own live image")
    # ★SCOPED TO THE EDIT BLOCK. A whole-file search for indexOf(_marker) is satisfied by the
    # DELETE path, which has its own copy - so removing the edit path's ownership guard left the
    # file still matching and the negative passed while detecting nothing. Two near-identical
    # blocks on one page is exactly the shape that makes a loose check vacuous.
    edit_block = ""
    m = re.search(r"const _old = String\(\(_editItem[\s\S]{0,700}", s)
    if m:
        edit_block = m.group(0)
    if not edit_block:
        out.append("marketplace-seller.html: the replace-on-edit cleanup block is gone - editing a "
                   "listing's image orphans the old object again, on the path that runs most often")
    elif not re.search(r"indexOf\(\s*_marker\s*\)", edit_block):
        out.append("marketplace-seller.html: the replace-cleanup no longer checks the old object is OURS "
                   "(a bucket-marker match) - a seller who pasted an external image URL would have us "
                   "trying to delete from somebody else's host")

    # both must be best-effort: a cleanup failure cannot cost the write
    guarded = len(re.findall(r"catch\s*\(\s*_imgErr\s*\)", s))
    if guarded < 2:
        out.append(f"marketplace-seller.html: only {guarded} image-cleanup catch block(s) - a storage "
                   f"hiccup can now throw into the write path and cost the seller the edit or delete "
                   f"they asked for. Cleanup is the optional half and must never break the required one")
    return out


def selftest() -> int:
    src = io.open(SRC, encoding="utf-8", errors="replace").read()
    cases = [("the real marketplace-seller.html is clean", src, 0)]
    cases.append(("losing one of the two cleanup paths is caught",
                  src.replace("if (_key) await db.storage.from(STORAGE_BUCKET).remove([_key]);", "if (_key) void 0;", 1), 1))
    cases.append(("dropping the url-changed guard is caught",
                  src.replace("_old && _old !== imageUrl && _i >= 0", "_old && _i >= 0"), 1))
    cases.append(("dropping the is-it-ours guard is caught",
                  re.sub(r"const _i = _old\.indexOf\(_marker\);", "const _i = 0;", src), 1))
    cases.append(("un-guarding a cleanup is caught",
                  src.replace("catch (_imgErr) { console.warn('replaced-image cleanup skipped:', _imgErr && _imgErr.message); }",
                              "finally { }"), 1))
    bad = 0
    for label, s, want in cases:
        f = audit(s)
        ok = (len(f) == 0) if want == 0 else (len(f) >= want)
        if not ok:
            bad += 1
        print(f"  {'ok  ' if ok else 'MISS'} {label} (findings={len(f)})")
    print(f"\nSELFTEST {'FAILED' if bad else 'ok'} - {len(cases) - bad}/{len(cases)}")
    return 1 if bad else 0


def main() -> int:
    if not SRC.exists():
        print("FAIL - marketplace-seller.html is gone; re-point this gate")
        return 1
    findings = audit(io.open(SRC, encoding="utf-8", errors="replace").read())
    print("a-removed-image-actually-leaves - the photo goes when the listing goes, and when it is replaced")
    if findings:
        print("\nFAIL - an image outlives the listing that owned it, in a public bucket:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - both lifecycles clean up, guarded on changed-and-ours, and neither can break the write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())

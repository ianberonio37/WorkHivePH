#!/usr/bin/env python3
"""copy_split_blocks.py - split every <p> the rubric's B1 counts as a verbose block (Wave CF, 2026-11-08).

B1 fails a page with more than three text blocks over 60 words. Once the sentences are short, what is left is paragraph
length - a mechanical fix: split the <p> at the sentence end nearest its middle (never inside a tag), so each half stays a
coherent run. Reads .tmp/copy/<slug>.json (tools/copy_offenders.mjs) for the blocks, finds each <p> by its opening words.

    python tools/copy_split_blocks.py learn/<slug>/index.html [--apply]
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from copy_rewrite import pattern, protected  # noqa: E402

page = Path(sys.argv[1])
apply = "--apply" in sys.argv
parts = page.as_posix().split("/")
slug = parts[-2] if parts[-1] == "index.html" and len(parts) > 1 else parts[-1].replace(".html", "")
blocks = json.loads((Path(".tmp/copy") / f"{slug}.json").read_text(encoding="utf-8")).get("b1") or []
src = page.read_text(encoding="utf-8")
done = 0
for b in blocks:
    probe = " ".join(b.split()[:6])
    prot = protected(src)
    hits = [m for m in pattern(probe).finditer(src) if not any(a <= m.start() < e for a, e in prot)]
    if len(hits) != 1:
        print(f"  skip ({len(hits)} matches): {probe!r}")
        continue
    k = hits[0].start()
    ps = src.rfind("<p", 0, k)
    pe = src.find("</p>", k)
    if ps == -1 or pe == -1 or src.rfind("</p>", ps, k) != -1:
        print(f"  skip (not inside one <p>): {probe!r}")
        continue
    open_end = src.find(">", ps) + 1
    inner = src[open_end:pe]
    if re.search(r"<(p|div|ul|ol|li|table)\b", inner):
        print(f"  skip (block children): {probe!r}")
        continue
    # sentence ends outside tags: ". " / "? " / "! " where the next char starts a word
    ends, depth = [], 0
    for i, ch in enumerate(inner):
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        elif depth == 0 and ch in ".?!" and inner[i + 1:i + 2] == " " and i + 2 < len(inner):
            ends.append(i + 1)
    if not ends:
        print(f"  skip (one sentence): {probe!r}")
        continue
    mid = len(inner) / 2
    cut = min(ends, key=lambda i: abs(i - mid))
    indent = re.match(r"[ \t]*", src[src.rfind("\n", 0, ps) + 1:]).group(0)
    new_inner = inner[:cut] + "</p>\n" + indent + "<p>" + inner[cut:].lstrip()
    src = src[:open_end] + new_inner + src[pe:]
    done += 1
print(f"{done} of {len(blocks)} block(s) split{'' if apply else ' (dry)'}")
if apply and done:
    page.write_text(src, encoding="utf-8", newline="")
    print(f"  wrote {page}")

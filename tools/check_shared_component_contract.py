# -*- coding: utf-8 -*-
"""The shared-component prover declares, per script, the global it defines and the element it leaves behind.
Those declarations were written by me from the file names, and a prover whose contract is wrong grades every
page against a promise the script never made. This checks each declaration against the script's own source."""
import re
from pathlib import Path

SRC = Path("tools/prove_shared_components.mjs").read_text(encoding="utf-8")
block = SRC.split("const CONTRACT = {", 1)[1].split("\n};", 1)[0]
rows = re.findall(r"'([^']+\.js)':\s*\{\s*el:\s*(null|'[^']*'),\s*global:\s*(null|'[^']*'),\s*persists:\s*\[([^\]]*)\]",
                  block)
print(f"declarations: {len(rows)}")
bad = []
for js, el, g, persists in rows:
    p = Path(js)
    if not p.exists():
        bad.append((js, "the script does not exist"))
        continue
    s = p.read_text(encoding="utf-8", errors="replace")
    if g != "null":
        name = g.strip("'")
        # a global is defined as `function name(`, `window.name =`, `const name =`, or `var name =`
        if not re.search(rf"(function\s+{re.escape(name)}\s*\(|window\.{re.escape(name)}\s*=|"
                         rf"(const|let|var)\s+{re.escape(name)}\s*=)", s):
            bad.append((js, f"declares global {name}, which the source never defines"))
    for key in re.findall(r"'([^']+)'", persists):
        if key not in s:
            bad.append((js, f"declares it persists {key}, which the source never writes"))
    if el != "null":
        ids = re.findall(r"#([A-Za-z0-9_-]+)", el)
        if ids and not any(i in s for i in ids):
            bad.append((js, f"declares element {el.strip(chr(39))}, none of whose ids appear in the source"))

if bad:
    print(f"WRONG DECLARATIONS: {len(bad)}")
    for js, why in bad:
        print(f"   {js:28} {why}")
else:
    print("every declaration matches the script's own source")

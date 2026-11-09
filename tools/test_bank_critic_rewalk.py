#!/usr/bin/env python3
"""test_bank_critic_rewalk.py - teeth for bank_critic_walk.py's close-by-re-walk rule (2026-10-13).

A critiqued row that HAD findings and is re-walked as its own cast with none moves to improving (its earlier findings
kept as findings_before). A re-walk that still finds anything stays critiqued; a first walk that finds nothing stays
critiqued (nothing was ever fixed); an improving row is never re-banked. Synthetic registry in a temp dir.
"""
import importlib.util
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bcw", ROOT / "tools" / "bank_critic_walk.py")
bcw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bcw)

F = [{"dim": "B3", "evidence": "hive: B3 40% long sentences", "severity": 2}]


class _TmpRio:
    """registry_io bound to one temp file. ★The banker saves through registry_io (the union, 2026-11-07), which writes
    the REAL registry whatever bcw.CRITIC says - so pointing CRITIC at a temp file stopped isolating this test, and on
    2026-11-09 its one synthetic row overwrote all 50,503 real rows (restored from HEAD; registry_io now refuses such a
    shrink). The test owns BOTH doors now: the path and the I/O layer."""
    def __init__(self, path):
        self.path = path

    def load_critic(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save_critic(self, critic, indent=2, allow_shrink=False):
        self.path.write_text(json.dumps(critic, indent=indent), encoding="utf-8")
        return {self.path.name: len(critic.get("rows") or [])}


def bank(row_status, prior, new):
    tmp = Path(tempfile.mkdtemp()) / "critic.json"
    reg = {"rows": [{"id": "X", "status": row_status, "cell": "phone-390|worker|x|y", "findings": prior, "pages": ["hive.html"]}]}
    tmp.write_text(json.dumps(reg), encoding="utf-8")
    bcw.CRITIC = tmp
    bcw._rio = _TmpRio(tmp)
    by = {r["id"]: r for r in reg["rows"]}
    with redirect_stdout(io.StringIO()):
        bcw._write_bank(reg, by, ["X"], "lens123", ["B3"], new, "test")
    return json.loads(tmp.read_text(encoding="utf-8"))["rows"][0]


cases = [
    ("re-walk of a row with findings finds none", bank("critiqued", F, []), "improving", True),
    ("re-walk still finds something", bank("critiqued", F, F), "critiqued", False),
    ("first walk finds nothing (nothing was fixed)", bank("pending", [], []), "critiqued", False),
    ("first walk finds something", bank("pending", [], F), "critiqued", False),
]
ok = True
for name, row, want, has_before in cases:
    good = row["status"] == want and (("findings_before" in row) == has_before) \
        and (bool(row.get("improvement_refs")) == (want == "improving"))
    ok &= good
    print(("ok " if good else "XX ") + f"{name}: {row['status']} (want {want})")
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)

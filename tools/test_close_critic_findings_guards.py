"""test_close_critic_findings_guards.py - teeth for close_critic_findings.py's guards (2026-10-13), on synthetic data in a temp dir.

  1. a sweep OLDER than the row's bank cannot clear its finding, a NEWER one can;
  2. a signed-out row is judged only by a signed-out sweep, never by a signed-in sweep of the same filename;
  3. a signed-in sweep (a supervisor's screen) judges only supervisor or persona-agnostic rows;
  4. a DESCOPED dim (N1) no longer holds a row open, a row whose only findings are descoped does not close, and the
     receipt written on apply says "descoped", never that the dim came back clean.
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ccf", ROOT / "tools" / "close_critic_findings.py")
ccf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ccf)

tmp = Path(tempfile.mkdtemp())
now = time.time()
banked = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now - 3600))   # banked an hour ago
E3 = {"evidence": "hive: E3 0% NO source chip"}
N1 = {"evidence": "hive: N1 75% - WH_LANG=true · lang=en · label coverage=6/11 (55%)"}


def row(i, persona, findings=None):
    return {"id": i, "status": "critiqued", "cell": f"phone-390|{persona}|x|y", "walked_at": banked[:10],
            "banked_at": banked, "findings": list(findings or [E3]), "pages": ["hive.html"]}


def run(rows, board_age_s, signed_age_s, anon_age_s, failing=(), apply=False):
    for f in tmp.glob("*"):
        f.unlink()
    (tmp / "critic.json").write_text(json.dumps({"rows": rows}), encoding="utf-8")
    sweep = {"pages": {"hive.html": {"overall": 100, "failing": list(failing)}}}   # E3 clean in every sweep
    for name, age in (("board.json", board_age_s), ("page.json", signed_age_s), ("anon.json", anon_age_s)):
        if age is None:
            continue
        p = tmp / name
        p.write_text(json.dumps(sweep), encoding="utf-8")
        os.utime(p, (now - age, now - age))
    ccf.CRITIC, ccf.BOARD_JSON, ccf.PAGE_JSON = tmp / "critic.json", tmp / "board.json", tmp / "page.json"
    ccf.ANON_PAGE_JSON, ccf.LATEST, ccf.ANON_LATEST = tmp / "anon.json", tmp / "latest.json", tmp / "anon_latest.json"
    sys.argv = ["x", "--apply"] if apply else ["x"]
    buf = io.StringIO()
    real_run = ccf.subprocess.run
    # apply ends by running the REAL validator and scoreboard generator on the real bank; a test must not write there
    ccf.subprocess.run = lambda *a, **k: type("R", (), {"returncode": 0, "stdout": "stubbed", "stderr": ""})()
    try:
        with redirect_stdout(buf):
            ccf.main()
    finally:
        ccf.subprocess.run = real_run
    first = buf.getvalue().splitlines()[0]
    return int(first.split("closable (every finding clean): ")[1].split(" ")[0])


cases = [
    ("supervisor row, board swept a month before the bank", [row("A", "supervisor")], 30 * 86400, None, None, (), 0),
    ("supervisor row, page sweep 10 min ago (after the bank an hour ago)", [row("B", "supervisor")], 30 * 86400, 600, None, (), 1),
    ("worker row, the same newer supervisor sweep (another screen)", [row("W", "worker")], 30 * 86400, 600, None, (), 0),
    ("signed-out row, only a signed-in sweep (newer)", [row("C", "anon")], None, 60, None, (), 0),
    ("signed-out row, signed-out sweep before the bank", [row("D", "anon")], None, None, 2 * 3600, (), 0),
    ("signed-out row, signed-out sweep after the bank", [row("E", "anon")], None, None, 60, (), 1),
    ("E3 clean + N1 still failing in a newer sweep (N1 descoped)", [row("F", "supervisor", [E3, N1])], None, 600, None,
     ("N1 75% - label coverage 6/11",), 1),
    ("E3 STILL failing + N1 descoped (the descope must not carry a real failure)", [row("G", "supervisor", [E3, N1])], None,
     600, None, ("E3 0% - NO source chip", "N1 75% - x"), 0),
    ("only an N1 finding (nothing on the row improved)", [row("H", "supervisor", [N1])], None, 600, None, (), 0),
]
ok = True
for name, rows, b, s, a, failing, want in cases:
    got = run(rows, b, s, a, failing)
    ok &= got == want
    print(("ok " if got == want else "XX ") + f"{name}: closable {got} (want {want})")

# the receipt: applied to F, the row says N1 was descoped and names only E3 as re-swept clean
run([row("F", "supervisor", [E3, N1])], None, 600, None, ("N1 75% - x",), apply=True)
written = json.loads((tmp / "critic.json").read_text(encoding="utf-8"))["rows"][0]
refs = " | ".join(written.get("improvement_refs") or [])
receipt_ok = (written.get("status") == "improving" and "N1 not graded - descoped" in refs
              and "with E3 clean" in refs and "N1 clean" not in refs and "E3, N1" not in refs)
ok &= receipt_ok
print(("ok " if receipt_ok else "XX ") + f"receipt on apply: status {written.get('status')}, refs: {refs[:220]}")

# the three places that carry the descope must agree: the closer's list, the lens's switch, and the sweep's N1 override,
# which re-graded every N/A N1 while it compared kind with 'NA' (the lens writes 'N/A')
import re as _re
lens = (ROOT / "survey_ufai_rubric.js").read_text(encoding="utf-8")
# code lines only: the fix's own comment quotes the old comparison, and a grep that reads comments finds it there
sweep = "\n".join(l for l in (ROOT / "tools" / "family_rubric_sweep.mjs").read_text(encoding="utf-8").splitlines()
                  if not l.lstrip().startswith("//"))
switch = _re.search(r"const _N1_DESCOPED = '([^']*)'", lens)
tied = (("N1" in ccf.DESCOPED_DIMS) == bool(switch and switch.group(1))
        and "kind !== 'NA'" not in sweep and "res.dims[i].kind === 'MEASURED'" in sweep)
ok &= tied
print(("ok " if tied else "XX ") + f"closer descopes N1={'N1' in ccf.DESCOPED_DIMS}, lens switch={'on' if switch and switch.group(1) else 'off'}, "
      f"sweep overrides a MEASURED N1 only={'kind !== ' + chr(39) + 'NA' + chr(39) not in sweep}")
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)

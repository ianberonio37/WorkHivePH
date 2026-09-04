#!/usr/bin/env python3
"""audit-is-reachable-from-a-record - T28: an audit nobody can reach is write-only.

"Who changed this?" is asked while looking at the RECORD - an asset whose details are wrong, a
reported post, a decision someone disputes. If the only way to the audit log is to know the page
exists and open it cold, the trail is technically complete and practically useless: the supervisor
either gives up or goes to SQL, and the compliance story the platform tells about itself is one
nobody can walk.

★AND A LINK THAT DROPS THE RECORD IS BARELY BETTER. Arriving at an unfiltered log of every power
action, holding the id of the thing you were looking at in your head, is the same scavenger hunt
with extra steps. So the links must carry the subject - asset-hub sends ?q=<tag>, community sends
?action=report_post - AND the audit page must CONSUME those parameters, or the context is written
into the URL and thrown away, which is a promise only the sender believes.

★THE HIVE MENU ENTRY IS NOT ENOUGH ON ITS OWN. audit-log is a hidden page: reachable, but only to
someone who already knows to look. The record-level affordances are what make it findable at the
moment the question is actually asked.

Re-drive: python tools/validate_audit_is_reachable_from_a_record.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SKIP = ("node_modules", "_fixtures", ".tmp", "test-data-seeder", "tools", ".git", "learn")
LINK = re.compile(r"""(?:href\s*=\s*['"]|\.href\s*=\s*['"])/?audit-log\.html([^'"]*)""")


def main() -> int:
    failures = []
    carried, bare = [], []

    for p in sorted(ROOT.glob("*.html")) + sorted(ROOT.glob("*.js")):
        if set(p.relative_to(ROOT).parts[:-1]) & set(SKIP):
            continue
        src = io.open(p, encoding="utf-8", errors="replace").read()
        for m in LINK.finditer(src):
            qs = m.group(1)
            (carried if re.search(r"[?&](q|actor|action|target)=", qs) else bare).append(p.name)

    if not carried:
        failures.append("no link reaches audit-log carrying the record it came from. 'Who changed "
                        "this?' is asked while looking at the RECORD, and an audit reachable only by "
                        "knowing the page exists is write-only in practice")

    # the receiving end must consume what the senders send
    audit = ROOT / "audit-log.html"
    if not audit.exists():
        failures.append("audit-log.html is gone, and several surfaces still link to it")
    else:
        asrc = io.open(audit, encoding="utf-8", errors="replace").read()
        consumed = [k for k in ("q", "actor", "action", "target")
                    if re.search(rf"\.get\(\s*['\"]{k}['\"]", asrc)]
        if not consumed:
            failures.append("audit-log.html reads NONE of the parameters its callers send - the "
                            "subject is written into the URL and then ignored, so the supervisor "
                            "still lands on an unfiltered log of every power action")
        elif len(consumed) < 2:
            failures.append(f"audit-log.html consumes only {consumed}; the senders use q and action, "
                            f"so at least one caller's context is being dropped on arrival")

    if failures:
        print("FAIL audit-is-reachable-from-a-record:")
        for f in failures:
            print("    - " + f)
        return 1

    print(f"  context-carrying links: {', '.join(sorted(set(carried)))} · "
          f"bare links: {', '.join(sorted(set(bare))) or 'none'} · audit consumes: {', '.join(consumed)}")
    print("PASS audit-is-reachable-from-a-record - the trail is reachable from the thing being "
          "disputed, and arrives filtered to it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

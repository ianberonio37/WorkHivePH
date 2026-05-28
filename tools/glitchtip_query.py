#!/usr/bin/env python3
"""Read errors from self-hosted GlitchTip via its plain REST API.

Why this exists: the official @sentry/mcp-server MCP cannot READ issues from
GlitchTip — search_issues 422s (sort enum), search_events 404s (no Discover
API), get_sentry_resource 405s (no shortId). GlitchTip implements only the
basic /api/0/ REST surface, which this tool uses directly. The Sentry MCP is
still fine for WRITING errors (envelope endpoint) and for project/release
discovery; use this for reading.

Creds are read from infra/mcp/.env.mcp (SENTRY_AUTH_TOKEN + org slug).

Usage:
  python tools/glitchtip_query.py issues                 # list open issues
  python tools/glitchtip_query.py issues --all           # include resolved
  python tools/glitchtip_query.py issue <id>             # one issue + latest event
  python tools/glitchtip_query.py events <issue_id>      # recent events for an issue
  python tools/glitchtip_query.py resolve <id>           # mark resolved (write)
  python tools/glitchtip_query.py delete <id>            # delete (write)
  python tools/glitchtip_query.py --json issues          # machine-readable
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error

ORG = "ian-beronio"
PROJECT = "workhive-frontend"
BASE = "http://127.0.0.1:8000"
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "infra", "mcp", ".env.mcp")


def _token():
    tok = os.environ.get("SENTRY_AUTH_TOKEN")
    if tok:
        return tok
    try:
        with open(ENV_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("SENTRY_AUTH_TOKEN="):
                    return line.split("=", 1)[1]
    except FileNotFoundError:
        pass
    sys.exit("SENTRY_AUTH_TOKEN not found (env or infra/mcp/.env.mcp)")


def _req(path, method="GET", body=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        sys.exit(f"GlitchTip API {e.code}: {e.read().decode()[:300]}")
    except urllib.error.URLError as e:
        sys.exit(f"GlitchTip unreachable at {BASE} — is the stack up? ({e.reason})")


def cmd_issues(args):
    q = "" if args.all else "?query=is:unresolved"
    issues = _req(f"/api/0/projects/{ORG}/{PROJECT}/issues/{q}")
    if args.json:
        print(json.dumps(issues, indent=2))
        return
    if not issues:
        print("No issues. Clean.")
        return
    print(f"{len(issues)} issue(s) in {ORG}/{PROJECT}:\n")
    for i in issues:
        print(f"  [{i.get('id')}] {i.get('level','?').upper():7} x{i.get('count','?'):<4} {i.get('title','')[:90]}")
        print(f"        last seen: {i.get('lastSeen','?')}  status: {i.get('status','?')}")


def cmd_issue(args):
    i = _req(f"/api/0/issues/{args.id}/")
    print(json.dumps(i, indent=2) if args.json else
          f"[{i.get('id')}] {i.get('level','?').upper()} x{i.get('count')}\n"
          f"  {i.get('title')}\n  status: {i.get('status')}  firstSeen: {i.get('firstSeen')}  lastSeen: {i.get('lastSeen')}")


def cmd_events(args):
    ev = _req(f"/api/0/issues/{args.issue_id}/events/")
    if args.json:
        print(json.dumps(ev, indent=2)); return
    print(f"{len(ev)} event(s) for issue {args.issue_id}:")
    for e in ev[:20]:
        print(f"  {e.get('dateCreated','?')}  {e.get('eventID','')[:12]}  {e.get('message','') or e.get('title','')}")


def cmd_resolve(args):
    _req(f"/api/0/issues/{args.id}/", method="PUT", body={"status": "resolved"})
    print(f"Issue {args.id} resolved.")


def cmd_delete(args):
    _req(f"/api/0/issues/{args.id}/", method="DELETE")
    print(f"Issue {args.id} deleted.")


def main():
    p = argparse.ArgumentParser(description="Read/triage GlitchTip errors via REST.")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("issues"); s.add_argument("--all", action="store_true"); s.set_defaults(fn=cmd_issues)
    s = sub.add_parser("issue"); s.add_argument("id"); s.set_defaults(fn=cmd_issue)
    s = sub.add_parser("events"); s.add_argument("issue_id"); s.set_defaults(fn=cmd_events)
    s = sub.add_parser("resolve"); s.add_argument("id"); s.set_defaults(fn=cmd_resolve)
    s = sub.add_parser("delete"); s.add_argument("id"); s.set_defaults(fn=cmd_delete)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

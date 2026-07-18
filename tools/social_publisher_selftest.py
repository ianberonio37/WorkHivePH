"""
Self-test for tools/social_publisher.py - environment-independent.

Locks in the verification done when the publisher was built so a future edit
can't silently break:
  1. DRY-RUN is a pure preview: every platform reports "ready", and ZERO side
     effects fire (no HTTP post, no browser open, no clipboard write, no reveal).
  2. LIVE AUTO paths post correctly: Facebook (upload -> status poll -> first
     comment), Telegram (sendVideo), Discord (webhook) - verified against a
     local mock of each API. No real account is ever touched.
  3. LIVE ASSIST paths perform their side effects (open page + clipboard +
     reveal) - verified via recorders, so no real browser opens during the test.

Run:  python tools/social_publisher_selftest.py     (exit 0 = pass, 1 = fail)
"""
import sys
import json
import tempfile
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tools.social_publisher as sp

CANNED_PACK = {
    "facebook_page": {"body": "A Cabuyao line went dark at 14:45. " + ("word " * 90),
                      "first_comment": "https://workhiveph.com/learn/"},
    "facebook_group": {"body": "Question for the group. " + ("word " * 120)},
    "youtube": {"title": "WorkHive test title", "description": "desc " * 60,
                "tags": ["maintenance", "philippines"]},
    "shorts_reels_tiktok": {"caption": "short cap", "hashtags": ["#A", "#B"]},
}

HITS = []
STATE = {"fail_videos": 0}   # >0 => the next N /videos POSTs return 500 (tests the retry)


class _Mock(BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        ln = int(self.headers.get("Content-Length", 0) or 0)
        if ln:
            self.rfile.read(ln)
        HITS.append(("POST", self.path.split("?")[0]))
        if self.path.endswith("/videos"):
            if STATE["fail_videos"] > 0:
                STATE["fail_videos"] -= 1
                self._send({"error": {"message": "transient", "error_subcode": 1363030}}, 500)
            else:
                self._send({"id": "vid_mock_1"})
        elif self.path.endswith("/comments"):
            self._send({"id": "cmt_mock_1"})
        elif self.path.endswith("/sendVideo"):
            self._send({"ok": True})
        elif "/webhooks/" in self.path:
            self.send_response(204); self.end_headers()
        else:
            self._send({"error": {"message": "unexpected " + self.path}}, 400)

    def do_GET(self):
        HITS.append(("GET", self.path.split("?")[0]))
        if "vid_mock_1" in self.path:
            self._send({"status": {"video_status": "ready"}})
        else:
            self._send({"error": {"message": "unexpected " + self.path}}, 400)

    def log_message(self, *a):
        pass


def main() -> int:
    # Temp video file + canned asset/pack resolution (decouple from real renders).
    tmp = Path(tempfile.mkdtemp(prefix="sp_selftest_"))
    vid = tmp / "fake.mp4"
    vid.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"0" * 1024)

    sp.resolve_video = lambda idea, aspect: vid
    sp.available_aspects = lambda idea: ["9x16", "1x1", "16x9"]
    sp.load_pack = lambda idea: CANNED_PACK
    sp._log = lambda entry: None  # don't write the real publish log

    # Record assisted side effects instead of performing them.
    side = {"open_url": 0, "reveal_file": 0, "set_clipboard": 0}
    sp.open_url = lambda url: side.__setitem__("open_url", side["open_url"] + 1)
    sp.reveal_file = lambda p: side.__setitem__("reveal_file", side["reveal_file"] + 1)
    sp.set_clipboard = lambda t: side.__setitem__("set_clipboard", side["set_clipboard"] + 1) or True
    sp.RETRY_BACKOFF_SEC = 0  # no real backoff sleep during the test

    srv = HTTPServer(("127.0.0.1", 0), _Mock)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    sp.FB_GRAPH = f"{base}/v25.0"
    sp.TELEGRAM_API = base

    cfg = {
        "FB_PAGE_ID": "99999", "FB_PAGE_ACCESS_TOKEN": "MOCK", "FB_PAGE_ASPECT": "1x1",
        "TELEGRAM_BOT_TOKEN": "111:MOCK", "TELEGRAM_CHAT_ID": "@t",
        "DISCORD_WEBHOOK_URL": f"{base}/api/webhooks/1/2",
        "FB_GROUP_URLS": "https://facebook.com/groups/x",
        "ASSIST_YOUTUBE": "1",
    }
    auto = ["fb_page", "telegram", "discord"]
    failures = []

    def check(name, cond):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            failures.append(name)

    # ── Test 1: DRY-RUN is a pure preview (no side effects at all) ──────────
    HITS.clear()
    for k in side:
        side[k] = 0
    r1 = sp.publish("idea_x", platforms=auto + ["fb_groups", "youtube"], live=False, cfg=cfg)
    statuses = {x["platform"]: x["status"] for x in r1["results"]}
    print("Test 1 - dry-run preview is side-effect-free:")
    check("all platforms report 'ready'", all(s == "ready" for s in statuses.values()))
    check("ZERO HTTP calls in dry-run", len(HITS) == 0)
    check("ZERO browser/clipboard/reveal in dry-run",
          side["open_url"] == 0 and side["reveal_file"] == 0 and side["set_clipboard"] == 0)

    # ── Test 2: LIVE AUTO paths post correctly ─────────────────────────────
    HITS.clear()
    r2 = sp.publish("idea_x", platforms=auto, live=True, cfg=cfg)
    s2 = {x["platform"]: x["status"] for x in r2["results"]}
    seq = [p for _, p in HITS]
    print("Test 2 - live AUTO paths:")
    check("facebook_page posted", s2.get("facebook_page") == "posted")
    check("telegram posted", s2.get("telegram") == "posted")
    check("discord posted", s2.get("discord") == "posted")
    check("FB sequence = upload -> status poll -> comment",
          any(p.endswith("/videos") for p in seq)
          and any("vid_mock_1" in p for _, p in HITS if _ == "GET")
          and any(p.endswith("/comments") for p in seq))

    # ── Test 3: LIVE ASSIST performs its side effects ──────────────────────
    for k in side:
        side[k] = 0
    r3 = sp.publish("idea_x", platforms=["youtube", "fb_groups"], live=True, cfg=cfg)
    s3 = {x["platform"]: x["status"] for x in r3["results"]}
    print("Test 3 - live ASSIST performs open + clipboard + reveal:")
    check("youtube assisted", s3.get("youtube") == "assisted")
    check("facebook_groups assisted", s3.get("facebook_groups") == "assisted")
    check("opened a page + wrote clipboard + revealed a file",
          side["open_url"] >= 1 and side["set_clipboard"] >= 1 and side["reveal_file"] >= 1)

    # ── Test 4: a transient upload failure is retried, not fatal ────────────
    HITS.clear()
    STATE["fail_videos"] = 1   # first /videos POST 500s; the retry should recover
    r4 = sp.publish("idea_x", platforms=["fb_page"], live=True, cfg=cfg)
    s4 = {x["platform"]: x["status"] for x in r4["results"]}
    n_uploads = sum(1 for m, p in HITS if m == "POST" and p.endswith("/videos"))
    print("Test 4 - transient FB upload failure is retried:")
    check("facebook_page recovered to posted after a 500", s4.get("facebook_page") == "posted")
    check("upload was attempted twice (retry fired)", n_uploads == 2)

    srv.shutdown()
    print()
    if failures:
        print(f"SELFTEST FAILED ({len(failures)}): {', '.join(failures)}")
        return 1
    print("SELFTEST PASSED - dry-run preview is inert; all AUTO live paths post; ASSIST acts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

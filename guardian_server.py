"""
WorkHive Platform Guardian — Interactive Server
================================================
Replaces `python -m http.server 8080` with a smart backend that:
  - Serves platform-health.html as the dashboard
  - Runs validator scripts on demand via API
  - Streams real-time output to the browser via Server-Sent Events (SSE)

Usage:
  python guardian_server.py          # starts on http://localhost:8080
  python guardian_server.py 9000     # custom port

Then open: http://localhost:8080
"""
import sys, os, json, subprocess, threading, time, mimetypes
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT    = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
PYTHON  = sys.executable
BASE    = os.path.dirname(os.path.abspath(__file__))

# ── Available commands ────────────────────────────────────────────────────────
COMMANDS = {
    "fast":     ([PYTHON, "run_platform_checks.py", "--fast"],          "Validate (fast)"),
    "autofix":  ([PYTHON, "run_platform_checks.py", "--fast", "--autofix"], "Validate + Auto-Fix"),
    "deploy":   ([PYTHON, "run_platform_checks.py"],                    "Validate (full)"),
    "learn":    ([PYTHON, "learn.py"],                                   "Self-Learn"),
    "improve":  ([PYTHON, "improve.py", "--fast"],                       "Improve (fast)"),
    "gate":     ([PYTHON, "run_platform_checks.py", "--gate-only"],      "Gate Only"),
    "once":     ([PYTHON, "schedule_guardian.py", "--once"],             "Schedule Once"),
    "autofix_only": ([PYTHON, "autofix.py"],                             "Auto-Fix Only"),
}

# ── Git operations (not subprocess via COMMANDS — handled separately) ─────────
GIT_BASE = BASE

# ── Track running command (one at a time) ─────────────────────────────────────
_running_lock  = threading.Lock()
_running_cmd   = None   # currently running command key
_last_output   = []     # lines from last run
_last_rc       = None   # return code from last run


class GuardianHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # suppress default access log

    # ── Routing ───────────────────────────────────────────────────────────────
    def do_GET(self):
        p = urlparse(self.path)
        path = p.path.rstrip("/") or "/"

        if path in ("/", "/platform-health.html"):
            self._serve_file("platform-health.html", "text/html")
        elif path.endswith(".json"):
            fname = os.path.basename(path)
            self._serve_file(fname, "application/json")
        elif path.startswith("/api/stream"):
            qs  = parse_qs(p.query)
            cmd = qs.get("cmd", ["fast"])[0]
            self._stream(cmd)
        elif path.startswith("/api/status"):
            self._api_status()
        else:
            self._serve_file(os.path.basename(path))

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        p = urlparse(self.path)
        if p.path == "/api/run":
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length) or b"{}")
            cmd    = body.get("cmd", "fast")
            self._run_sync(cmd)
        elif p.path == "/api/git":
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length) or b"{}")
            msg    = body.get("message", "Quick commit from Guardian")
            self._git_stream(msg)
        elif p.path == "/api/backlog":
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length) or b"{}")
            self._backlog_action(body)
        else:
            self._json({"error": "unknown endpoint"}, 404)

    # ── File serving ──────────────────────────────────────────────────────────
    def _serve_file(self, filename, content_type=None):
        path = os.path.join(BASE, filename)
        if not os.path.exists(path):
            self.send_response(404)
            self.end_headers()
            return
        if content_type is None:
            content_type, _ = mimetypes.guess_type(path)
            content_type = content_type or "text/plain"
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", len(data))
        self.send_header("Cache-Control", "no-cache")
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    # ── JSON helper ───────────────────────────────────────────────────────────
    def _json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    # ── Status endpoint ───────────────────────────────────────────────────────
    def _api_status(self):
        self._json({
            "running":     _running_cmd,
            "last_rc":     _last_rc,
            "last_lines":  _last_output[-20:] if _last_output else [],
        })

    # ── SSE streaming ─────────────────────────────────────────────────────────
    def _stream(self, cmd_key):
        global _running_cmd, _last_output, _last_rc

        cmd_entry = COMMANDS.get(cmd_key)
        if not cmd_entry:
            self._json({"error": f"Unknown command: {cmd_key}"}, 400)
            return

        # Only one command at a time
        with _running_lock:
            if _running_cmd:
                # Return busy immediately
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self._cors()
                self.end_headers()
                self._sse_write(f"ERROR: Another command is running ({_running_cmd})")
                self._sse_write("[DONE:1]")
                return
            _running_cmd = cmd_key
            _last_output = []
            _last_rc     = None

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self._cors()
        self.end_headers()

        cmd_list, label = cmd_entry
        self._sse_write(f"[START] {label}")
        self._sse_write(f"$ {' '.join(cmd_list[1:])}")  # show command without python path
        self._sse_write("─" * 60)

        try:
            proc = subprocess.Popen(
                cmd_list,
                cwd=BASE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            lines = []
            for raw_line in proc.stdout:
                line = raw_line.rstrip()
                if line:
                    import re
                    clean = re.sub(r'\x1b\[[0-9;]*m', '', line)
                    lines.append(clean)
                    _last_output.append(clean)
                    self._sse_write(clean)

            proc.wait()
            _last_rc = proc.returncode

            self._sse_write("─" * 60)
            status = "PASS" if proc.returncode == 0 else "FAIL"
            self._sse_write(f"[DONE:{proc.returncode}] {status}")

        except Exception as ex:
            _last_rc = 1
            self._sse_write(f"[ERROR] {ex}")
            self._sse_write("[DONE:1]")
        finally:
            with _running_lock:
                _running_cmd = None

    def _sse_write(self, line):
        try:
            msg = f"data: {line}\n\n"
            self.wfile.write(msg.encode("utf-8"))
            self.wfile.flush()
        except Exception:
            pass

    # ── Backlog item management ───────────────────────────────────────────────
    def _backlog_action(self, body):
        """
        Manage improvement backlog items.
        Actions: dismiss, done, restore
        Body: { "action": "dismiss"|"done"|"restore", "id": "topic-id" }
        """
        action  = body.get("action", "")
        item_id = body.get("id", "")
        bl_path = os.path.join(BASE, "improvement_backlog.json")

        if not action or not item_id:
            self._json({"error": "action and id required"}, 400)
            return
        if action not in ("dismiss", "done", "in_progress", "restore"):
            self._json({"error": f"unknown action: {action}"}, 400)
            return
        if not os.path.exists(bl_path):
            self._json({"error": "improvement_backlog.json not found"}, 404)
            return

        try:
            with open(bl_path, encoding="utf-8") as f:
                items = json.load(f)

            found = False
            for item in items:
                if item.get("id") == item_id:
                    if action == "restore":
                        item.pop("status", None)
                    else:
                        item["status"] = action   # "dismiss" or "done"
                    found = True
                    break

            if not found:
                self._json({"error": f"item '{item_id}' not found"}, 404)
                return

            with open(bl_path, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2)

            self._json({"ok": True, "id": item_id, "action": action})
        except Exception as ex:
            self._json({"ok": False, "error": str(ex)})

    # ── Sync run (for polling clients) ────────────────────────────────────────
    # ── Git commit + push (synchronous JSON response) ────────────────────────
    def _git_stream(self, message):
        import re as _re
        lines  = []
        errors = []

        def git_run(args):
            lines.append(f"$ git {' '.join(args)}")
            r = subprocess.run(
                ["git"] + args, cwd=BASE,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                timeout=60
            )
            out = _re.sub(r'\x1b\[[0-9;]*m', '',
                          (r.stdout or '') + (r.stderr or '')).strip()
            for ln in out.splitlines():
                if ln.strip():
                    lines.append(ln)
            return r.returncode

        try:
            git_run(["status", "--short"])
            rc = git_run(["add", "-A"])
            if rc != 0:
                errors.append("git add failed")
                self._json({"ok": False, "lines": lines, "errors": errors})
                return

            rc = git_run(["commit", "-m", message])
            if rc != 0:
                # Nothing to commit is OK
                lines.append("Nothing new to commit — working tree clean.")
                self._json({"ok": True, "lines": lines, "errors": []})
                return

            rc = git_run(["push", "origin", "master"])
            ok = (rc == 0)
            if ok:
                lines.append("Committed and pushed to GitHub successfully.")
            else:
                errors.append("Push failed — check your internet/credentials.")
            self._json({"ok": ok, "lines": lines, "errors": errors})

        except subprocess.TimeoutExpired:
            errors.append("Git command timed out after 60 seconds.")
            self._json({"ok": False, "lines": lines, "errors": errors})
        except Exception as ex:
            self._json({"ok": False, "lines": lines, "errors": [str(ex)]})

    def _run_sync(self, cmd_key):
        cmd_entry = COMMANDS.get(cmd_key)
        if not cmd_entry:
            self._json({"error": f"Unknown: {cmd_key}"}, 400)
            return

        cmd_list, label = cmd_entry
        result = subprocess.run(
            cmd_list, cwd=BASE,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace"
        )
        import re
        output = re.sub(r'\x1b\[[0-9;]*m', '', result.stdout + result.stderr)
        self._json({
            "cmd":    cmd_key,
            "label":  label,
            "rc":     result.returncode,
            "output": output.splitlines()[-30:],
        })


# ── Start server ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    server = ThreadingHTTPServer(("", PORT), GuardianHandler)
    print(f"\n  WorkHive Platform Guardian Server")
    print(f"  http://localhost:{PORT}")
    print(f"  Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")

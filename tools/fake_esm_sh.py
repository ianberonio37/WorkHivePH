"""fake_esm_sh.py - stand in for esm.sh over TLS so a deploy's bundle step can be walked against each failure (2026-10-27).

Used by tools/walk_esm_sh_deploy.sh: it runs in a python:3-alpine container on a private docker network under the alias
esm.sh, with a certificate for esm.sh signed by a throwaway CA; the edge-runtime bundler (the image `supabase functions
deploy` bundles with) joins that network with DENO_CERT pointing at the CA. Modes:
  429      every request answers 429 Too Many Requests (Retry-After: 60)
  slow     every request is held SLOW_S seconds, then answered by the REAL esm.sh (fetched by this server)
  changed  every request answered by the real esm.sh, except the supabase-js entry, which gains one export line -
           the same version serving different content
"""
import http.server
import os
import ssl
import sys
import time
import urllib.request

MODE = sys.argv[1]
SLOW_S = float(os.environ.get("SLOW_S", "20"))


def real(path, agent):
    req = urllib.request.Request("https://esm.sh" + path, headers={"User-Agent": agent or "Deno/1.45.2"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.getcode(), r.read(), r.headers.get("Content-Type", "application/javascript")


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if MODE == "429":
            self.send_response(429)
            self.send_header("Retry-After", "60")
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Too Many Requests")
            return
        if MODE == "slow":
            time.sleep(SLOW_S)
        code, body, ctype = real(self.path, self.headers.get("User-Agent"))
        if MODE == "changed" and self.path.rstrip("/").endswith("/@supabase/supabase-js@2.110.0"):
            body += b'\nexport const __changed_at_same_version = true;\n'
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *a):
        sys.stderr.write("[fake-esm %s] %s\n" % (MODE, fmt % a))


srv = http.server.ThreadingHTTPServer(("0.0.0.0", 443), H)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain("/certs/esm.crt", "/certs/esm.key")
srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
srv.serve_forever()

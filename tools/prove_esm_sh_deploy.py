"""prove_esm_sh_deploy.py - walk a deploy's bundle step against esm.sh healthy, down, slow, 429 and changed (2026-10-27).

OWN74-77. `supabase functions deploy` bundles each function in Docker with the edge-runtime image (the CLI's default;
--use-api is opt-in) and uploads the eszip only if the bundle succeeds; production then runs that eszip and never
fetches esm.sh again. So the question "what does an esm.sh outage do" is answered at the bundle step, and this walks it
with the same image, on a real function (login: supabase-js from esm.sh, std from deno.land, _shared), never touching
production:
  healthy  - the real esm.sh
  down     - esm.sh resolves to 127.0.0.1 inside the bundler (connection refused)
  429      - a fake esm.sh (tools/fake_esm_sh.py, TLS from a throwaway CA added to the bundler container's own trust
             store - it ignores DENO_CERT) answers 429
  slow     - the fake holds each request, then serves the real bytes; bundled once with the CLI's patience (no timeout)
             and once with --timeout shorter than the hold
  changed  - the fake serves the real bytes except the supabase-js entry, which gains one export: the bundle SUCCEEDS
             with the new content in it - the bundler cannot tell, which is why edge_remote_deps_lock.py --online exists
  runs     - the healthy bundle is SERVED by the same image (start --main-service <eszip>) with esm.sh and deno.land both
             refused, and its /health answers: what a person reaches in production never fetches esm.sh

  python tools/prove_esm_sh_deploy.py            -> esm_sh_deploy_walk.json
"""
from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMAGE = "public.ecr.aws/supabase/edge-runtime:v1.73.3"
FN = "login"
NET = "wh-esm-walk"
SLOW_S = 6
OUT = ROOT / "esm_sh_deploy_walk.json"
PORT = 9311


def sh(args: list, timeout: int = 600) -> tuple:
    t = time.monotonic()
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return p.returncode, (p.stdout + p.stderr), round(time.monotonic() - t, 1)


def bundle(work: Path, out: Path, name: str, extra: list, timeout_s: int | None = None, certs: Path | None = None) -> dict:
    cmd = ["bundle", "--entrypoint", f"/work/{FN}/index.ts", "--output", f"/out/{name}.eszip", "--disable-module-cache"]
    if timeout_s:
        cmd += ["--timeout", str(timeout_s)]
    vols = ["-v", f"{(ROOT / 'supabase' / 'functions').as_posix()}:/work:ro", "-v", f"{out.as_posix()}:/out"]
    if certs:
        # the bundler ignores DENO_CERT (measured: UnknownIssuer); it reads the system store when DENO_TLS_CA_STORE=system,
        # so the walk CA is added to THIS throwaway container's store and nowhere else
        args = ["docker", "run", "--rm", *extra, *vols, "-v", f"{certs.as_posix()}:/certs:ro", "-e", "DENO_TLS_CA_STORE=system",
                "--entrypoint", "sh", IMAGE, "-c",
                "cp /certs/ca.crt /usr/local/share/ca-certificates/wh-esm-walk.crt && update-ca-certificates >/dev/null 2>&1; "
                "exec edge-runtime " + " ".join(cmd)]
    else:
        args = ["docker", "run", "--rm", *extra, *vols, IMAGE, *cmd]
    code, text, secs = sh(args)
    f = out / f"{name}.eszip"
    lines = [ln for ln in text.splitlines() if ln.strip() and "DEBUG" not in ln]
    return {"exit": code, "secs": secs, "eszip_bytes": f.stat().st_size if f.exists() else 0,
            "said": " | ".join(lines[-3:])[:400]}


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="esmwalk_"))
    certs, out = tmp / "certs", tmp / "out"
    certs.mkdir()
    out.mkdir()
    # a throwaway CA and an esm.sh certificate it signs - the bundler trusts it only through DENO_CERT in these runs
    sh(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=wh-esm-walk-ca",
        "-keyout", str(certs / "ca.key"), "-out", str(certs / "ca.crt")])
    sh(["openssl", "req", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=esm.sh",
        "-keyout", str(certs / "esm.key"), "-out", str(certs / "esm.csr")])
    (certs / "san.ext").write_text("subjectAltName=DNS:esm.sh\n", encoding="utf-8")
    sh(["openssl", "x509", "-req", "-in", str(certs / "esm.csr"), "-CA", str(certs / "ca.crt"), "-CAkey", str(certs / "ca.key"),
        "-CAcreateserial", "-days", "1", "-extfile", str(certs / "san.ext"), "-out", str(certs / "esm.crt")])
    real_ip = socket.gethostbyname("esm.sh")
    sh(["docker", "network", "rm", NET])
    sh(["docker", "network", "create", NET])
    rec = {"ran": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "image": IMAGE, "function": FN, "cases": {}}
    try:
        rec["cases"]["healthy"] = bundle(tmp, out, "healthy", [])
        # the person's half: the deployed artifact answers with esm.sh unreachable
        sh(["docker", "rm", "-f", "wh-eszip-run"])
        code, text, _ = sh(["docker", "run", "-d", "--name", "wh-eszip-run", "--add-host", "esm.sh:127.0.0.1",
                            "--add-host", "deno.land:127.0.0.1", "-p", f"{PORT}:9000", "-v", f"{out.as_posix()}:/out:ro",
                            "-e", "SUPABASE_URL=http://127.0.0.1:1", "-e", "SUPABASE_SERVICE_ROLE_KEY=x", "-e", "SUPABASE_ANON_KEY=x",
                            IMAGE, "start", "--main-service", "/out/healthy.eszip", "--main-entrypoint", f"file:///work/{FN}/index.ts"])
        run = {"started": code == 0}
        for _ in range(20):
            time.sleep(1)
            try:
                import urllib.request
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/{FN}/health", timeout=5) as r:
                    run.update(http=r.getcode(), body=json.loads(r.read().decode())); break
            except Exception as e:   # noqa: BLE001 - still booting, or refused: the loop's last error is the reading
                run["error"] = str(e)[:120]
        rec["cases"]["runs"] = run
        sh(["docker", "rm", "-f", "wh-eszip-run"])
        rec["cases"]["down"] = bundle(tmp, out, "down", ["--add-host", "esm.sh:127.0.0.1"])
        for mode in ("429", "slow", "changed"):
            sh(["docker", "rm", "-f", "wh-fake-esm"])
            code, text, _ = sh(["docker", "run", "-d", "--name", "wh-fake-esm", "--network", NET, "--network-alias", "esm.sh",
                                "--add-host", f"esm.sh:{real_ip}", "-e", f"SLOW_S={SLOW_S}",
                                "-v", f"{(ROOT / 'tools').as_posix()}:/app:ro", "-v", f"{certs.as_posix()}:/certs:ro",
                                "python:3-alpine", "python", "/app/fake_esm_sh.py", mode])
            if code:
                rec["cases"][mode] = {"error": "fake esm.sh did not start: " + text[:200]}
                continue
            time.sleep(2)
            via = ["--network", NET]
            if mode == "slow":
                rec["cases"]["slow"] = bundle(tmp, out, "slow", via, certs=certs)
                rec["cases"]["slow_past_timeout"] = bundle(tmp, out, "slow_timeout", via, timeout_s=SLOW_S - 2, certs=certs)
            else:
                rec["cases"][mode] = bundle(tmp, out, mode, via, certs=certs)
            served = sh(["docker", "logs", "wh-fake-esm"])[1]
            rec["cases"][mode]["fake_served"] = served.count("GET ")
            if mode == "changed":
                f = out / "changed.eszip"
                rec["cases"]["changed"]["new_content_shipped"] = bool(f.exists() and b"__changed_at_same_version" in f.read_bytes())
    finally:
        sh(["docker", "rm", "-f", "wh-fake-esm"])
        sh(["docker", "network", "rm", NET])
        shutil.rmtree(tmp, ignore_errors=True)
    c = rec["cases"]
    checks = {
        "healthy esm.sh: the bundle is built": c["healthy"]["exit"] == 0 and c["healthy"]["eszip_bytes"] > 10000,
        "the built bundle answers with esm.sh and deno.land refused (a person never meets esm.sh)":
            c["runs"].get("http") == 200 and (c["runs"].get("body") or {}).get("ok") is True,
        # each failure must fail for ITS cause - a first version passed 429 on a TLS error that never reached the fake
        "esm.sh down: the bundle fails on the refused connection and nothing is written to upload":
            c["down"]["exit"] != 0 and not c["down"]["eszip_bytes"] and "Connection refused" in c["down"]["said"],
        "esm.sh 429: the bundle fails on the 429 itself and nothing is written to upload":
            c.get("429", {}).get("exit", 0) != 0 and not c.get("429", {}).get("eszip_bytes") and "429" in c.get("429", {}).get("said", "")
            and c.get("429", {}).get("fake_served", 0) >= 1,
        "esm.sh slow: with the CLI's patience the bundle is built, only later":
            c.get("slow", {}).get("exit") == 0 and c.get("slow", {}).get("secs", 0) >= SLOW_S and c.get("slow", {}).get("eszip_bytes", 0) > 10000,
        "esm.sh slow past the bundle timeout: it fails, nothing written":
            c.get("slow_past_timeout", {}).get("exit", 0) != 0 and not c.get("slow_past_timeout", {}).get("eszip_bytes")
            and "certificate" not in c.get("slow_past_timeout", {}).get("said", ""),
        "esm.sh changed at the same version: the bundler ships it silently (the lock is the only line)":
            c.get("changed", {}).get("new_content_shipped") is True,
    }
    rec["checks"] = checks
    OUT.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
    for k, v in checks.items():
        print(("  ok   " if v else "  FAIL ") + k)
    for k, v in c.items():
        if k == "runs":
            print(f"    runs: /{FN}/health -> {v.get('http')} build {(v.get('body') or {}).get('build')} {v.get('error', '') if not v.get('http') else ''}")
            continue
        print(f"    {k}: exit {v.get('exit')} in {v.get('secs')}s, eszip {v.get('eszip_bytes')} B - {v.get('said', v.get('error', ''))[:160]}")
    ok = all(checks.values())
    print(("PASS" if ok else "FAIL") + f" esm-sh-deploy-walk - {sum(checks.values())}/{len(checks)} -> {OUT.name}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

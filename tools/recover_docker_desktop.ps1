# recover_docker_desktop.ps1 - bring the local Supabase stack back when Docker Desktop's HOST FILE SHARE wedges
# (measured 2026-09-14 on the 8 GB host, after heavy-page headless-renderer crashes):
#   * every edge function 503s while its container reads "Up": the runtime logs
#     "worker boot error ... Error reading config file 'file:///Users/.../supabase/functions/<fn>/deno.json': Input/output error"
#   * `docker exec supabase_edge_runtime_workhive ls <functions dir>` -> Input/output error for every entry
#   * `docker restart` / any `docker run -v C:\...` -> "error while creating mount source path '/run/desktop/mnt/host/c/...':
#     mkdir /run/desktop/mnt/host/c: file exists"
# `docker desktop restart` HUNG (12+ min, both WSL distros left Stopped). This manual path brought the engine back in ~30 s.
# Usage:  powershell -NoProfile -ExecutionPolicy Bypass -File tools\recover_docker_desktop.ps1
$ErrorActionPreference = 'Continue'
$FN = "/Users/ILBeronio/Desktop/Industry 4.0/AI Maintenance Engineer/Self-learning Road-Map/Build & Sell with Claude Code/Website simple 1st/supabase/functions"

"--- 1. quit Docker Desktop (a hung 'docker desktop restart' included) and its distro ---"
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object { $_.CommandLine -like '*docker desktop restart*' -and $_.ProcessId -ne $PID } | ForEach-Object { "killing hung restart pid $($_.ProcessId)"; Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Get-Process -Name 'Docker Desktop','com.docker.backend','docker-desktop','com.docker.build','com.docker.dev-envs' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 6
wsl --terminate docker-desktop
Start-Sleep -Seconds 3

"--- 2. relaunch and wait for the engine ---"
Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
$up = $false
for ($i = 1; $i -le 48; $i++) {
  Start-Sleep -Seconds 5
  $v = & docker version --format '{{.Server.Version}}' 2>$null
  if ($LASTEXITCODE -eq 0 -and $v) { $up = $true; "engine up after $($i*5)s: $v"; break }
}
if (-not $up) { "engine NOT up after 240s"; wsl -l -v; exit 1 }
Start-Sleep -Seconds 12

"--- 3. containers (unless-stopped ones return alone; the edge runtime's policy is 'no') ---"
docker ps -a --format '{{.Names}}  {{.Status}}' | Select-String -Pattern 'supabase_(db|kong|auth|rest|edge|storage|realtime)_'
docker start supabase_edge_runtime_workhive
Start-Sleep -Seconds 10

"--- 4. verify: the mount reads, the gateway answers, the login function boots ---"
docker exec supabase_edge_runtime_workhive sh -c "ls '$FN/login'"
& curl.exe -s -m 15 -o NUL -w "auth via kong %{http_code} in %{time_total}s`n" http://127.0.0.1:54321/auth/v1/health
$key = (& supabase status -o env 2>$null | Select-String -Pattern '^ANON_KEY=' | ForEach-Object { $_.Line.Substring(9).Trim('"') } | Select-Object -First 1)
if ($key) {
  foreach ($n in 1, 2) { & curl.exe -s -m 60 -o NUL -w "login warm-up $n`: HTTP %{http_code} in %{time_total}s`n" -X POST http://127.0.0.1:54321/functions/v1/login -H "apikey: $key" -H "Authorization: Bearer $key" -H "Content-Type: application/json" -d '{"email":"christinedizon@auth.workhiveph.com","password":"test1234"}' }
} else { "no ANON_KEY from 'supabase status' - warm the login function by hand" }

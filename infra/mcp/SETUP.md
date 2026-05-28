# MCP Toolkit setup — what Claude can't do for you

Claude prepared everything around Docker MCP Toolkit, but six steps still need your hands.
Do them in this order; each one unblocks the next. Total: ~30 minutes.

---

## 1. Bring up Grafana + GlitchTip (one command)

```powershell
docker compose -f infra/mcp/docker-compose.mcp.yml --env-file infra/mcp/.env.mcp up -d
```

Then verify:

```powershell
.\infra\mcp\verify-mcp.ps1
```

You'll see Grafana at <http://127.0.0.1:3001> and GlitchTip at <http://127.0.0.1:8000>.
Login passwords are in `infra/mcp/.env.mcp` (gitignored). Open the file to read them.

---

## 2. Install Obsidian and enable Local REST API

1. Download from <https://obsidian.md/download> (Windows installer)
2. Open Obsidian, click **Open folder as vault**, point at:

   ```
   C:\Users\ILBeronio\.claude\projects\c--Users-ILBeronio-Desktop-Industry-4-0-AI-Maintenance-Engineer-Self-learning-Road-Map-Build---Sell-with-Claude-Code-Website-simple-1st\memory
   ```

3. Settings → Community plugins → **Turn on community plugins** → Browse → search **"Local REST API"** → Install + Enable
4. Settings → Local REST API → copy the **API Key**
5. Paste it into `infra/mcp/.env.mcp` next to `OBSIDIAN_API_KEY=`

---

## 3. Generate a GitHub PAT (read-only, this repo only)

1. Go to <https://github.com/settings/personal-access-tokens/new>
2. Name: `workhive-mcp-readonly`
3. Expiration: 90 days
4. Repository access: **Only select repositories** → pick this repo
5. Permissions (all **Read-only**):
   - Contents
   - Issues
   - Pull requests
   - Metadata
6. Generate → copy token → paste into `infra/mcp/.env.mcp` next to `GITHUB_PERSONAL_ACCESS_TOKEN=`

---

## 4. Create GlitchTip admin + project

1. Open <http://127.0.0.1:8000>
2. Click **Register** (first user becomes admin)
3. Create an Organization called `workhive`
4. Create a Team, then a Project — pick **Browser JavaScript** as the platform
5. Copy the **DSN** from Project Settings → Client Keys
6. Save it for step 5 (the Sentry MCP install)

---

## 5. Install the MCP servers in Docker Desktop

Open Docker Desktop → **MCP Toolkit** (left nav) → **Catalog** tab.
For each server below, click **Install** and fill in the credentials when prompted.

| MCP server | Search term | Credentials to enter |
|---|---|---|
| Postgres | `postgres` | `POSTGRES_CONNECTION_STRING` from `.env.mcp` |
| Obsidian | `obsidian` | `OBSIDIAN_API_KEY` + `OBSIDIAN_HOST` from `.env.mcp` |
| Grafana | `grafana` | URL: `http://host.docker.internal:3001`<br>Service account token: create one in Grafana → Administration → Service accounts → New service account → Add token (Viewer role) |
| Playwright | `playwright` | No credentials |
| GitHub | `github` | `GITHUB_PERSONAL_ACCESS_TOKEN` from `.env.mcp` |
| Sentry | `sentry` | DSN from GlitchTip (step 4)<br>URL: `http://host.docker.internal:8000` |

---

## 6. Enable Claude Code as a client

In Docker Desktop → MCP Toolkit → **Clients** tab → toggle **Claude Code** on.

Then restart Claude Code (close + reopen the IDE). The new `mcp__*` tools appear automatically.

Run the verifier once more:

```powershell
.\infra\mcp\verify-mcp.ps1
```

All 6 MCP server rows should now show PASS.

---

## Tear-down (if something goes wrong)

```powershell
# Stop everything
docker compose -f infra/mcp/docker-compose.mcp.yml down

# Stop AND erase data (DESTRUCTIVE — fresh start)
docker compose -f infra/mcp/docker-compose.mcp.yml down -v
```

Then re-run step 1.

---

## Why each one earns its slot

- **Postgres** — Claude reads your real DB instead of stale JSON reports
- **Obsidian** — graph view + backlinks over your 50+ memory notes
- **Grafana** — live cockpit on top of Supabase (replaces static HTML dashboards)
- **Playwright** — exploratory browser probing for L2 sentinel scenarios
- **GitHub** — read commit history, sentinel proposals → GitHub issues
- **Sentry/GlitchTip** — real error context when validators flag regressions

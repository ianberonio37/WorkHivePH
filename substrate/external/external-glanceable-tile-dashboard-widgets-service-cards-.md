---
name: external-glanceable-tile-dashboard-widgets-service-cards-
type: reference
source: https://github.com/gethomepage/homepage
source_sha: 6fb4bf817eeed257
fetched_at: 2026-08-17T19:35:56Z
last_verified: 2026-08-18
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: glanceable tile dashboard widgets service cards homepage
---

## reference · glanceable tile dashboard widgets service cards homepage
*   Homepage is a fully static, fast, secure, and fully proxied application dashboard.
*   Configuration is managed via YAML files or Docker label discovery.
*   It supports over 100 service integrations and translations into over 40 languages.
*   Images are built for AMD64 and ARM64 architectures.
*   All API requests to backend services are proxied, keeping API keys hidden.
*   The site is statically generated at build time for instant load times.
*   **Docker Integration**:
    *   Automatically discovers and adds services based on Docker labels.
    *   Requires mounting `/var/run/docker.sock` as read-only (`/var/run/docker.sock:ro`).
    *   Default Docker image: `ghcr.io/gethomepage/homepage:latest`.
    *   Default container port: `3000`.
    *   Required environment variable: `HOMEPAGE_ALLOWED_HOSTS` (e.g., `gethomepage.dev`).
    *   Optional environment variables: `PUID`, `PGID`.
*   **Service Widgets**: Integrates with hundreds of 3rd-party services, including:
    *   \*arr apps: Radarr, Sonarr, Lidarr, Bazarr.
    *   Media servers: Ombi, Tautulli, Plex, Jellyfin, Emby.
    *   Download clients: Transmission, qBittorrent, Deluge, Jackett, NZBGet, SABnzbd.
    *   Also supports information providers from external 3rd-party APIs.
*   **Information Widgets**: Provides built-in support for weather, time, date, search, and system/status information (e.g., Glances).
*   **Customization**: Supports custom themes, CSS, JS, layouts, formatting, and localization.
*   **Security Notice**:
    *   If Homepage is reachable from untrusted networks and accesses personal information (e.g., home automation), it **must** sit behind a reverse proxy (and/or VPN) that enforces authentication, TLS, and strictly validates Host headers.
    *   An optional built-in OIDC login flow or simple password login is available.
*   **Development**:
    *   Uses `pnpm` for package management.
    *   Built with `Next.js`.
    *   To initialize configuration from source, copy `src/skeleton` to `config/`.
    *   Development server runs on `http://localhost:3000`.
*   **Documentation**: Available at `https://gethomepage.dev/`.

Sources: https://github.com/gethomepage/homepage

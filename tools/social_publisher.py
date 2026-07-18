"""
WorkHive Social Auto-Publisher
==============================

Takes ONE produced video idea (the flagship render + its platform pack) and
publishes it to every social platform the operator has credentials for, while
gracefully skipping the rest. This is the "I only paste my accounts once, then
it posts" layer that sits on top of the existing render + platform-pack stack.

Two posting modes per platform (Ian's chosen design — auto-where-safe,
assisted-where-risky):

  * AUTO   — posts 100% by itself via the platform's official API using a token
             the operator pasted into `social_accounts.env`. Zero ban risk.
             Implemented: Facebook Page, Telegram, Discord, (optional) YouTube.
  * ASSIST — opens the platform's native upload page with the matching video
             revealed in Explorer + the caption already on the clipboard, so
             the operator just attaches + pastes + clicks Post. No token, no
             ban risk, works on the gated platforms (Groups, TikTok, IG, X,
             Reddit, LinkedIn, and YouTube-by-default).

SAFETY: defaults to DRY-RUN. AUTO platforms only post for real when the run is
`live` (SOCIAL_PUBLISH_MODE=live in the env file OR --live on the CLI). ASSIST
platforms only ever OPEN a page + copy text — nothing posts until the operator
clicks, so they run in either mode.

Inputs it reads (all already produced by the existing pipeline):
  * Rendered videos : remotion_scenes/out/<idea>_<aspect>_audio.mp4
                      (aspects: 9x16 vertical, 1x1 square, 16x9 wide)
  * Platform pack   : .tmp/platform_packs/<idea>.json   (the social copy)
  * Credentials     : social_accounts.env               (operator-pasted; gitignored)

CLI:
  python tools/social_publisher.py --list
  python tools/social_publisher.py --check
  python tools/social_publisher.py --idea idea_020                  # dry-run, all armed platforms
  python tools/social_publisher.py --idea idea_020 --platforms fb_page,youtube
  python tools/social_publisher.py --idea idea_020 --live           # actually post to AUTO platforms

Returns (when imported) via publish(): a structured result dict the dashboard
can render.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from datetime import datetime, timezone

try:
    import requests  # used by the AUTO adapters; same dep the Flask app uses
except Exception:  # pragma: no cover - degrade gracefully
    requests = None

ROOT = Path(__file__).resolve().parent.parent
FLAGSHIP_OUT = ROOT / "remotion_scenes" / "out"
PACK_DIR = ROOT / ".tmp" / "platform_packs"
DESKTOP = Path.home() / "Desktop"
CREDS_FILE = ROOT / "social_accounts.env"
CREDS_EXAMPLE = ROOT / "social_accounts.env.example"
LOG_FILE = ROOT / ".social_publish_log.jsonl"

FB_API_VERSION = "v25.0"
FB_GRAPH = f"https://graph.facebook.com/{FB_API_VERSION}"
TELEGRAM_API = "https://api.telegram.org"   # module-level so tests can point it at a mock

UPLOAD_MAX_ATTEMPTS = 3      # FB video uploads can transiently fail on slow links
RETRY_BACKOFF_SEC = 4        # backoff base (x attempt#); 0 in tests

# Per-platform default rendered aspect.
ASPECT_VERTICAL = "9x16"   # Reels / Shorts / TikTok / IG
ASPECT_SQUARE = "1x1"      # Facebook feed / Instagram feed
ASPECT_WIDE = "16x9"       # YouTube long-form / LinkedIn

# Assisted upload entry points (open in the operator's logged-in browser).
ASSIST_URLS = {
    "youtube":   "https://www.youtube.com/upload",
    "tiktok":    "https://www.tiktok.com/tiktokstudio/upload",
    "instagram": "https://www.instagram.com/",
    "linkedin":  "https://www.linkedin.com/feed/?shareActive=true",
    "x":         "https://x.com/compose/post",
    "reddit":    "https://www.reddit.com/submit?type=VIDEO",
}


# ── Config ───────────────────────────────────────────────────────────────────

def load_config() -> dict:
    """Parse social_accounts.env (KEY=value, # comments). Real os.environ wins
    so a value can be overridden ad-hoc. Missing file => empty config (every
    platform skipped, with a clear message)."""
    cfg: dict[str, str] = {}
    if CREDS_FILE.exists():
        for raw in CREDS_FILE.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            cfg[key.strip()] = val.strip().strip('"').strip("'")
    # Live environment overrides the file.
    for k, v in os.environ.items():
        if k in cfg or k.startswith(("FB_", "YT_", "TELEGRAM_", "DISCORD_", "ASSIST_", "SOCIAL_")):
            cfg[k] = v
    return cfg


def _truthy(v: str | None) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "yes", "on")


def _has(cfg: dict, *keys: str) -> bool:
    return all((cfg.get(k) or "").strip() for k in keys)


# ── Asset resolution ─────────────────────────────────────────────────────────

def resolve_video(idea_id: str, aspect: str) -> Path | None:
    """Find the rendered file for an idea+aspect. Prefers the muxed _audio.mp4
    flagship output; falls back to the silent render, then the Desktop copy."""
    candidates = [
        FLAGSHIP_OUT / f"{idea_id}_{aspect}_audio.mp4",
        FLAGSHIP_OUT / f"{idea_id}_{aspect}.mp4",
        DESKTOP / f"WorkHive_{idea_id}_{aspect}.mp4",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def available_aspects(idea_id: str) -> list[str]:
    return [a for a in (ASPECT_VERTICAL, ASPECT_SQUARE, ASPECT_WIDE)
            if resolve_video(idea_id, a)]


def load_pack(idea_id: str) -> dict:
    """Return the pack dict (the social copy) for an idea, or {} if not generated."""
    p = PACK_DIR / f"{idea_id}.json"
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("pack", {}) or {}
    except Exception:
        return {}


def list_produced_ideas() -> list[dict]:
    """Scan the render output for ideas that have at least one finished aspect."""
    if not FLAGSHIP_OUT.exists():
        return []
    ideas: dict[str, set] = {}
    for f in FLAGSHIP_OUT.glob("*_audio.mp4"):
        # name pattern: <idea>_<aspect>_audio.mp4
        stem = f.name[:-len("_audio.mp4")]
        for asp in (ASPECT_VERTICAL, ASPECT_SQUARE, ASPECT_WIDE):
            if stem.endswith("_" + asp):
                idea = stem[: -(len(asp) + 1)]
                ideas.setdefault(idea, set()).add(asp)
    out = []
    for idea, aspects in sorted(ideas.items()):
        out.append({
            "idea_id": idea,
            "aspects": sorted(aspects),
            "has_pack": (PACK_DIR / f"{idea}.json").exists(),
        })
    return out


# ── Caption builders (from the platform pack) ────────────────────────────────

def _fb_page_caption(pack: dict) -> tuple[str, str]:
    fb = pack.get("facebook_page", {}) or {}
    body = (fb.get("body") or "").strip()
    first_comment = (fb.get("first_comment") or "").strip()
    return body, first_comment


def _fb_group_caption(pack: dict) -> str:
    fg = pack.get("facebook_group", {}) or {}
    return (fg.get("body") or "").strip()


def _youtube_caption(pack: dict) -> tuple[str, str, list[str]]:
    yt = pack.get("youtube", {}) or {}
    title = (yt.get("title") or "").strip()
    desc = (yt.get("description") or "").strip()
    tags = yt.get("tags") or []
    return title, desc, tags


def _short_caption(pack: dict) -> str:
    sh = pack.get("shorts_reels_tiktok", {}) or {}
    cap = (sh.get("caption") or "").strip()
    tags = sh.get("hashtags") or []
    if tags:
        cap = (cap + "\n\n" + " ".join(tags)).strip()
    return cap


# ── Windows assist primitives ────────────────────────────────────────────────

def set_clipboard(text: str) -> bool:
    """Put text on the Windows clipboard (unicode + multiline safe) via
    PowerShell Set-Clipboard, falling back to clip.exe."""
    if not text:
        return False
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"],
            input=text, text=True, encoding="utf-8", check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        try:
            subprocess.run("clip", input=text, text=True, encoding="utf-8", check=True)
            return True
        except Exception:
            return False


def reveal_file(path: Path) -> None:
    """Open Explorer with the file pre-selected so the file picker is one click."""
    try:
        # explorer returns a non-zero exit even on success; ignore it.
        subprocess.run(["explorer", "/select,", str(path)])
    except Exception:
        pass


def open_url(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception:
        try:
            os.startfile(url)  # type: ignore[attr-defined]
        except Exception:
            pass


# ── Result helpers ───────────────────────────────────────────────────────────

def _r(platform: str, status: str, mode: str, detail: str, **extra) -> dict:
    out = {"platform": platform, "status": status, "mode": mode, "detail": detail}
    out.update(extra)
    return out


# ── AUTO adapter: Facebook Page ──────────────────────────────────────────────

def publish_fb_page(cfg: dict, idea_id: str, pack: dict, live: bool) -> dict:
    if not _has(cfg, "FB_PAGE_ID", "FB_PAGE_ACCESS_TOKEN"):
        return _r("facebook_page", "skipped", "auto",
                  "No FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN in social_accounts.env.")
    aspect = (cfg.get("FB_PAGE_ASPECT") or ASPECT_SQUARE).strip()
    video = resolve_video(idea_id, aspect) or resolve_video(idea_id, ASPECT_SQUARE) \
        or resolve_video(idea_id, ASPECT_WIDE) or resolve_video(idea_id, ASPECT_VERTICAL)
    if not video:
        return _r("facebook_page", "error", "auto",
                  f"No rendered video found for {idea_id} (looked for {aspect}).")
    body, first_comment = _fb_page_caption(pack)
    if not body:
        return _r("facebook_page", "error", "auto",
                  "No facebook_page caption in the platform pack — generate it first.")

    if not live:
        return _r("facebook_page", "ready", "auto",
                  f"DRY-RUN: would upload {video.name} to Page {cfg['FB_PAGE_ID']} "
                  f"({len(body)} char caption" + (", + first comment" if first_comment else "") + ").",
                  video=str(video), caption_preview=body[:160])

    if requests is None:
        return _r("facebook_page", "error", "auto", "`requests` not importable; cannot call Graph API.")

    page_id = cfg["FB_PAGE_ID"]
    token = cfg["FB_PAGE_ACCESS_TOKEN"]
    # Upload with retry: FB video uploads transiently fail on slow/flaky links
    # (error_subcode 1363030 / 5xx). Retry those; give up immediately on a real
    # 4xx (e.g. a #200 permission/scope error — retrying won't help).
    data, resp, err = {}, None, None
    for attempt in range(UPLOAD_MAX_ATTEMPTS):
        try:
            with open(video, "rb") as fh:
                resp = requests.post(
                    f"{FB_GRAPH}/{page_id}/videos",
                    data={"description": body, "access_token": token},
                    files={"source": (video.name, fh, "video/mp4")},
                    timeout=600,
                )
            data = resp.json() if resp.content else {}
            if resp.status_code == 200 and "id" in data:
                break
            err = (data.get("error") or {}).get("message") or resp.text[:300]
            transient = resp.status_code >= 500 or "1363030" in str(err)
            if not transient:
                return _r("facebook_page", "error", "auto",
                          f"Upload failed (HTTP {resp.status_code}): {err}")
        except Exception as exc:           # network/timeout — transient, retry
            err = str(exc)
        if attempt < UPLOAD_MAX_ATTEMPTS - 1:
            time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))

    if "id" not in data:
        return _r("facebook_page", "error", "auto",
                  f"Upload failed after {UPLOAD_MAX_ATTEMPTS} attempts: {err}")
    video_id = data["id"]

    comment_status = "no first comment"
    if first_comment:
        comment_status = _fb_comment_when_ready(page_id, video_id, first_comment, token)
    _log({"platform": "facebook_page", "idea": idea_id, "video_id": video_id,
          "video": str(video), "comment": comment_status})
    return _r("facebook_page", "posted", "auto",
              f"Posted to Page {page_id} (video {video_id}); first comment: {comment_status}.",
              video_id=video_id)


def _fb_comment_when_ready(page_id: str, video_id: str, message: str, token: str,
                           max_wait_s: int = 90) -> str:
    """Poll the video's status, then post the first comment. Returns a status string."""
    deadline = time.time() + max_wait_s
    last = ""
    while time.time() < deadline:
        try:
            s = requests.get(f"{FB_GRAPH}/{video_id}",
                             params={"fields": "status", "access_token": token}, timeout=30)
            st = (s.json().get("status") or {}) if s.content else {}
            vstatus = st.get("video_status") or (st.get("processing_phase") or {}).get("status")
            last = str(vstatus)
            if vstatus in ("ready", "complete", "published"):
                break
        except Exception as exc:
            last = f"status-poll error: {exc}"
        time.sleep(5)
    # Try the comment (retry a couple of times on not-ready object).
    for _ in range(3):
        try:
            c = requests.post(f"{FB_GRAPH}/{video_id}/comments",
                              data={"message": message, "access_token": token}, timeout=60)
            cj = c.json() if c.content else {}
            if c.status_code == 200 and "id" in cj:
                return f"posted ({cj['id']})"
            err = (cj.get("error") or {})
            if err.get("code") == 100 and err.get("error_subcode") == 33:
                time.sleep(8)  # video not ready yet
                continue
            return f"comment failed: {err.get('message') or c.text[:160]}"
        except Exception as exc:
            return f"comment exception: {exc}"
    return f"comment skipped (video still processing, last status={last})"


# ── AUTO adapter: Telegram ───────────────────────────────────────────────────

def publish_telegram(cfg: dict, idea_id: str, pack: dict, live: bool) -> dict:
    if not _has(cfg, "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        return _r("telegram", "skipped", "auto", "No TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID.")
    video = resolve_video(idea_id, ASPECT_VERTICAL) or resolve_video(idea_id, ASPECT_SQUARE)
    if not video:
        return _r("telegram", "error", "auto", f"No rendered video for {idea_id}.")
    caption = _short_caption(pack) or _fb_page_caption(pack)[0]
    caption = caption[:1024]  # Telegram caption hard limit
    if not live:
        return _r("telegram", "ready", "auto",
                  f"DRY-RUN: would send {video.name} to chat {cfg['TELEGRAM_CHAT_ID']}.",
                  video=str(video))
    if requests is None:
        return _r("telegram", "error", "auto", "`requests` not importable.")
    try:
        with open(video, "rb") as fh:
            resp = requests.post(
                f"{TELEGRAM_API}/bot{cfg['TELEGRAM_BOT_TOKEN']}/sendVideo",
                data={"chat_id": cfg["TELEGRAM_CHAT_ID"], "caption": caption},
                files={"video": (video.name, fh, "video/mp4")},
                timeout=600,
            )
        ok = resp.status_code == 200 and (resp.json() or {}).get("ok")
        if ok:
            _log({"platform": "telegram", "idea": idea_id, "video": str(video)})
            return _r("telegram", "posted", "auto", f"Sent to chat {cfg['TELEGRAM_CHAT_ID']}.")
        return _r("telegram", "error", "auto", f"Send failed: {resp.text[:200]}")
    except Exception as exc:
        return _r("telegram", "error", "auto", f"Exception: {exc}")


# ── AUTO adapter: Discord webhook ────────────────────────────────────────────

def publish_discord(cfg: dict, idea_id: str, pack: dict, live: bool) -> dict:
    if not _has(cfg, "DISCORD_WEBHOOK_URL"):
        return _r("discord", "skipped", "auto", "No DISCORD_WEBHOOK_URL.")
    video = resolve_video(idea_id, ASPECT_VERTICAL) or resolve_video(idea_id, ASPECT_SQUARE)
    if not video:
        return _r("discord", "error", "auto", f"No rendered video for {idea_id}.")
    content = (_short_caption(pack) or _fb_page_caption(pack)[0])[:2000]
    size_mb = video.stat().st_size / 1_000_000
    if not live:
        note = f" (note: {size_mb:.1f}MB; Discord free upload cap is ~8-10MB)" if size_mb > 8 else ""
        return _r("discord", "ready", "auto",
                  f"DRY-RUN: would post {video.name} to the webhook{note}.", video=str(video))
    if requests is None:
        return _r("discord", "error", "auto", "`requests` not importable.")
    try:
        with open(video, "rb") as fh:
            resp = requests.post(cfg["DISCORD_WEBHOOK_URL"],
                                 data={"content": content},
                                 files={"file": (video.name, fh, "video/mp4")},
                                 timeout=600)
        if resp.status_code in (200, 204):
            _log({"platform": "discord", "idea": idea_id, "video": str(video)})
            return _r("discord", "posted", "auto", "Posted via webhook.")
        return _r("discord", "error", "auto", f"Failed (HTTP {resp.status_code}): {resp.text[:200]}")
    except Exception as exc:
        return _r("discord", "error", "auto", f"Exception: {exc}")


# ── AUTO/ASSIST adapter: YouTube (long-form + Short) ─────────────────────────

def publish_youtube(cfg: dict, idea_id: str, pack: dict, live: bool, short: bool = False) -> dict:
    label = "youtube_short" if short else "youtube"
    aspect = ASPECT_VERTICAL if short else ASPECT_WIDE
    video = resolve_video(idea_id, aspect)
    if not video:
        return _r(label, "error", "assist", f"No {aspect} render for {idea_id}.")
    title, desc, tags = _youtube_caption(pack)
    if short:
        cap = _short_caption(pack)
        title = (title or cap[:90] or f"WorkHive — {idea_id}")
        if "#shorts" not in (title + desc).lower():
            desc = (cap + "\n\n#Shorts\n\n" + desc).strip()
    if not title:
        title = f"WorkHive — {idea_id}"

    mode = (cfg.get("YT_MODE") or "assist").strip().lower()
    if mode == "api" and live:
        return _youtube_api_upload(cfg, video, title, desc, tags, label)

    # ASSIST: open the upload page + clipboard + reveal file (only when live;
    # dry-run is a pure preview with no side effects).
    clip = f"TITLE:\n{title}\n\nDESCRIPTION:\n{desc}"
    if tags:
        clip += "\n\nTAGS:\n" + ", ".join(tags)
    if not live:
        return _r(label, "ready", "assist",
                  f"DRY-RUN: would open YouTube upload, reveal {video.name}, "
                  f"and copy the title/description to the clipboard.", video=str(video))
    set_clipboard(clip)
    reveal_file(video)
    open_url(ASSIST_URLS["youtube"])
    return _r(label, "assisted", "assist",
              f"Opened YouTube upload; {video.name} revealed + title/description copied to clipboard. "
              f"Drop the file, paste (Ctrl+V) into the description, set the title, Publish.",
              video=str(video))


def _youtube_api_upload(cfg: dict, video: Path, title: str, desc: str,
                        tags: list[str], label: str) -> dict:
    secret = (cfg.get("YT_CLIENT_SECRET_JSON") or "").strip()
    if not secret or not Path(secret).exists():
        return _r(label, "error", "auto",
                  "YT_MODE=api but YT_CLIENT_SECRET_JSON missing/not found. "
                  "Falling back to assist next run, or fix the path.")
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except Exception:
        return _r(label, "error", "auto",
                  "YouTube API libs not installed. Run: pip install google-api-python-client "
                  "google-auth-oauthlib google-auth-httplib2  (or keep YT_MODE=assist).")
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    token_path = ROOT / ".tmp" / "yt_token.json"
    creds = None
    try:
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), scopes)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(secret, scopes)
                creds = flow.run_local_server(port=0)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json(), encoding="utf-8")
        yt = build("youtube", "v3", credentials=creds)
        body = {
            "snippet": {"title": title[:100], "description": desc,
                        "tags": tags[:15], "categoryId": "28"},
            "status": {"privacyStatus": (cfg.get("YT_PRIVACY") or "private").strip(),
                       "selfDeclaredMadeForKids": False},
        }
        media = MediaFileUpload(str(video), chunksize=-1, resumable=True)
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = None
        while resp is None:
            _, resp = req.next_chunk()
        vid = resp.get("id")
        _log({"platform": label, "video": str(video), "youtube_id": vid})
        return _r(label, "posted", "auto",
                  f"Uploaded to YouTube as {vid} (privacy={body['status']['privacyStatus']}). "
                  f"NOTE: unverified API projects force uploads PRIVATE until Google audits the app.",
                  youtube_id=vid)
    except Exception as exc:
        return _r(label, "error", "auto", f"YouTube API upload failed: {exc}")


# ── ASSIST adapter: generic (FB groups + TikTok/IG/X/Reddit/LinkedIn) ────────

def publish_fb_groups(cfg: dict, idea_id: str, pack: dict, live: bool) -> dict:
    urls = [u.strip() for u in (cfg.get("FB_GROUP_URLS") or "").split(",") if u.strip()]
    if not urls:
        return _r("facebook_groups", "skipped", "assist", "No FB_GROUP_URLS set.")
    body = _fb_group_caption(pack) or _fb_page_caption(pack)[0]
    video = resolve_video(idea_id, ASPECT_SQUARE) or resolve_video(idea_id, ASPECT_WIDE) \
        or resolve_video(idea_id, ASPECT_VERTICAL)
    if not live:
        return _r("facebook_groups", "ready", "assist",
                  f"DRY-RUN: would open {len(urls)} group page(s), copy the group caption, "
                  + (f"and reveal {video.name}." if video else "(no video found)."), groups=urls)
    set_clipboard(body)
    if video:
        reveal_file(video)
    for u in urls:
        open_url(u)
    return _r("facebook_groups", "assisted", "assist",
              f"Opened {len(urls)} group page(s) + copied the group caption to clipboard"
              + (f" + revealed {video.name}." if video else " (no video found)."),
              groups=urls)


def publish_assist_simple(cfg: dict, idea_id: str, pack: dict, platform: str, live: bool) -> dict:
    """TikTok / Instagram / X / Reddit / LinkedIn — open upload page + clipboard + reveal file."""
    if not _truthy(cfg.get(f"ASSIST_{platform.upper()}")):
        return _r(platform, "skipped", "assist", f"ASSIST_{platform.upper()} not enabled.")
    vertical = platform in ("tiktok", "instagram")
    aspect = ASPECT_VERTICAL if vertical else ASPECT_SQUARE
    video = resolve_video(idea_id, aspect) or resolve_video(idea_id, ASPECT_VERTICAL) \
        or resolve_video(idea_id, ASPECT_SQUARE)
    caption = _short_caption(pack) if vertical else (_fb_page_caption(pack)[0] or _short_caption(pack))
    if not live:
        return _r(platform, "ready", "assist",
                  f"DRY-RUN: would open {platform} upload, copy the caption, "
                  + (f"and reveal {video.name}." if video else "(no video found)."),
                  video=str(video) if video else None)
    set_clipboard(caption)
    if video:
        reveal_file(video)
    open_url(ASSIST_URLS[platform])
    return _r(platform, "assisted", "assist",
              f"Opened {platform} upload + caption copied"
              + (f" + revealed {video.name}." if video else " (no video found)."),
              video=str(video) if video else None)


# ── Logging ──────────────────────────────────────────────────────────────────

def _log(entry: dict) -> None:
    entry = {"ts": datetime.now(timezone.utc).isoformat(), **entry}
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ── Orchestrator ─────────────────────────────────────────────────────────────

ALL_PLATFORMS = [
    "fb_page", "fb_groups", "youtube", "youtube_short",
    "telegram", "discord", "tiktok", "instagram", "linkedin", "x", "reddit",
]


def armed_platforms(cfg: dict) -> list[str]:
    """Which platforms are configured to run (have creds or are toggled on)."""
    armed = []
    if _has(cfg, "FB_PAGE_ID", "FB_PAGE_ACCESS_TOKEN"):
        armed.append("fb_page")
    if (cfg.get("FB_GROUP_URLS") or "").strip():
        armed.append("fb_groups")
    if _truthy(cfg.get("ASSIST_YOUTUBE", "1")) or (cfg.get("YT_MODE") or "").lower() == "api":
        armed += ["youtube", "youtube_short"]
    if _has(cfg, "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        armed.append("telegram")
    if _has(cfg, "DISCORD_WEBHOOK_URL"):
        armed.append("discord")
    for p in ("tiktok", "instagram", "linkedin", "x", "reddit"):
        if _truthy(cfg.get(f"ASSIST_{p.upper()}")):
            armed.append(p)
    return armed


def publish(idea_id: str, platforms: list[str] | None = None,
            live: bool | None = None, cfg: dict | None = None) -> dict:
    """Publish one idea to the requested (or all armed) platforms. Returns a
    structured result the CLI and the dashboard both render."""
    cfg = cfg or load_config()
    if live is None:
        live = (cfg.get("SOCIAL_PUBLISH_MODE") or "dry_run").strip().lower() == "live"
    targets = platforms or armed_platforms(cfg)
    pack = load_pack(idea_id)
    results = []

    for p in targets:
        if p == "fb_page":
            results.append(publish_fb_page(cfg, idea_id, pack, live))
        elif p == "fb_groups":
            results.append(publish_fb_groups(cfg, idea_id, pack, live))
        elif p == "youtube":
            results.append(publish_youtube(cfg, idea_id, pack, live, short=False))
        elif p == "youtube_short":
            results.append(publish_youtube(cfg, idea_id, pack, live, short=True))
        elif p == "telegram":
            results.append(publish_telegram(cfg, idea_id, pack, live))
        elif p == "discord":
            results.append(publish_discord(cfg, idea_id, pack, live))
        elif p in ("tiktok", "instagram", "linkedin", "x", "reddit"):
            results.append(publish_assist_simple(cfg, idea_id, pack, p, live))
        else:
            results.append(_r(p, "error", "?", f"Unknown platform '{p}'."))

    return {
        "idea_id": idea_id,
        "mode": "live" if live else "dry_run",
        "has_pack": bool(pack),
        "available_aspects": available_aspects(idea_id),
        "results": results,
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

def _print_check(cfg: dict) -> None:
    print("WorkHive Social Auto-Publisher - config check\n")
    if not CREDS_FILE.exists():
        print(f"  ! No {CREDS_FILE.name} yet. Copy {CREDS_EXAMPLE.name} -> {CREDS_FILE.name} and paste your tokens.")
        return
    mode = (cfg.get("SOCIAL_PUBLISH_MODE") or "dry_run").strip().lower()
    print(f"  Mode: {mode.upper()}  ({'WILL POST for real' if mode == 'live' else 'safe; AUTO platforms will NOT post'})\n")
    rows = [
        ("Facebook Page (AUTO)",   _has(cfg, "FB_PAGE_ID", "FB_PAGE_ACCESS_TOKEN")),
        ("Facebook Groups (ASSIST)", bool((cfg.get("FB_GROUP_URLS") or '').strip())),
        ("YouTube (ASSIST/API)",   _truthy(cfg.get("ASSIST_YOUTUBE", "1")) or (cfg.get("YT_MODE") or '').lower() == "api"),
        ("Telegram (AUTO)",        _has(cfg, "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")),
        ("Discord (AUTO)",         _has(cfg, "DISCORD_WEBHOOK_URL")),
        ("TikTok (ASSIST)",        _truthy(cfg.get("ASSIST_TIKTOK"))),
        ("Instagram (ASSIST)",     _truthy(cfg.get("ASSIST_INSTAGRAM"))),
        ("LinkedIn (ASSIST)",      _truthy(cfg.get("ASSIST_LINKEDIN"))),
        ("X / Twitter (ASSIST)",   _truthy(cfg.get("ASSIST_X"))),
        ("Reddit (ASSIST)",        _truthy(cfg.get("ASSIST_REDDIT"))),
    ]
    for name, on in rows:
        print(f"   [{'ARMED' if on else '  -  '}] {name}")
    print(f"\n  Armed platforms: {', '.join(armed_platforms(cfg)) or '(none — paste some tokens)'}")


def main(argv=None) -> int:
    # Windows consoles default to cp1252 and crash on any non-ASCII byte
    # (captions/pack content can contain unicode). Make stdout tolerant.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="WorkHive social auto-publisher")
    ap.add_argument("--idea", help="idea id, e.g. idea_020")
    ap.add_argument("--platforms", help="comma list; default = all armed")
    ap.add_argument("--live", action="store_true", help="actually post to AUTO platforms")
    ap.add_argument("--list", action="store_true", help="list produced ideas")
    ap.add_argument("--check", action="store_true", help="show which platforms are armed")
    args = ap.parse_args(argv)

    cfg = load_config()

    if args.check:
        _print_check(cfg)
        return 0
    if args.list:
        ideas = list_produced_ideas()
        if not ideas:
            print("No produced videos found in remotion_scenes/out/. Produce a flagship video first.")
            return 0
        print("Produced ideas (ready to publish):\n")
        for i in ideas:
            pack = "pack OK" if i["has_pack"] else "NO PACK"
            print(f"  {i['idea_id']:<14} aspects: {','.join(i['aspects']):<14} {pack}")
        return 0
    if not args.idea:
        ap.print_help()
        print("\nTip: run --list to see produced ideas, --check to see armed platforms.")
        return 1

    platforms = [p.strip() for p in args.platforms.split(",")] if args.platforms else None
    live = True if args.live else None
    result = publish(args.idea, platforms=platforms, live=live, cfg=cfg)

    print(f"\nPublish {result['idea_id']} - mode: {result['mode'].upper()} "
          f"- pack: {'yes' if result['has_pack'] else 'NO'} "
          f"- aspects: {','.join(result['available_aspects']) or 'none'}\n")
    for rrow in result["results"]:
        icon = {"posted": "OK", "assisted": "->", "ready": "..",
                "skipped": "  ", "error": "XX"}.get(rrow["status"], "??")
        print(f"  [{icon}] {rrow['platform']:<15} {rrow['status']:<9} {rrow['detail']}")
    if result["mode"] == "dry_run":
        print("\n  (dry-run - nothing posted, no pages opened. It's a safe preview. "
              "Re-run with --live, or set SOCIAL_PUBLISH_MODE=live, to publish for real.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

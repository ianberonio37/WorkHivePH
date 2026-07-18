# Publish your WorkHive videos — paste once, then it posts

You make the videos in the dashboard already. This adds the **last mile**: posting
them to your social accounts. You touch ONE file, once.

## The one thing you do

1. Double-click **`video_marketing.bat`** (or **`publish_video.bat`**).
   The first time, it creates **`social_accounts.env`** and opens it in Notepad.
2. Paste whatever account tokens you have. **Fill in what you have, leave the rest
   blank.** Save and close.
3. That's it. Blank platforms are skipped automatically.

The file is git-ignored — your tokens stay on this PC and are never committed.

## What posts how

| Platform | How it posts | What you paste |
|---|---|---|
| **Facebook Page** | **Auto** — uploads the video + caption + first comment by itself | Page ID + long-lived Page token (steps are in the file) |
| **Telegram / Discord** | **Auto** — sends the video by itself | A bot token / webhook URL (optional) |
| **YouTube + Shorts** | **Assisted** — opens the upload page with your video revealed + the title/description copied to your clipboard; you click Publish | nothing (just be logged in) |
| **Facebook Groups, TikTok, Instagram, X, LinkedIn** | **Assisted** — same one-click open + paste | nothing |

"Assisted" exists on purpose: auto-driving those accounts could get your real brand
account flagged, so the tool just teed it up and you hit Post.

## Voice

All narration uses the **James** Edge-TTS voice (already the default in the render
pipeline) — nothing to set.

## How to publish a video

**Easiest — the dashboard:** after a flagship video finishes, you'll see two buttons:
- **📣 Preview publish** — shows exactly what WOULD post (nothing happens, no tabs open).
- **🚀 Publish to my accounts** — asks you to confirm, then posts to your AUTO accounts
  and opens the upload pages for the rest.

**Or the one-click bat:** double-click **`publish_video.bat`** → it lists your produced
videos and which accounts are armed → type the idea id (e.g. `idea_020`) → pick
**1 (dry-run preview)** or **2 (publish for real)**.

**Or the command line:**
```
python tools/social_publisher.py --check          # which accounts are armed
python tools/social_publisher.py --list           # which videos are ready
python tools/social_publisher.py --idea idea_020          # safe preview (nothing posts)
python tools/social_publisher.py --idea idea_020 --live   # publish for real
```

## Safety

- **Dry-run is the default and is a true preview** — it never posts and never opens a
  page. You only go live with the LIVE button, `--live`, or `SOCIAL_PUBLISH_MODE=live`
  in the file.
- Start with a preview. Once it looks right, go live.

## First-time Facebook token (5 minutes, free, one-time)

The exact click-path is written inside `social_accounts.env.example` under the
Facebook section. Short version: create a Business app at developers.facebook.com →
Graph API Explorer → grant `pages_show_list, pages_read_engagement,
pages_manage_posts, pages_manage_engagement` → exchange for a long-lived token →
read your Page token from `me/accounts`. Paste the Page id + token. Done — it doesn't
expire.

(If you'd rather skip the developer step entirely, leave the Facebook token blank and
just add your Page under the assisted flow — the tool will open your Page composer
with the video + caption ready instead.)

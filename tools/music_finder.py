"""
WorkHive Music Finder
Searches Jamendo (600k+ royalty-free tracks) and downloads the best match
for a video's mood — completely automated, no browser, no clicking.

Requires a free Jamendo client_id:
  1. Go to https://devportal.jamendo.com/signup (30 seconds)
  2. Add JAMENDO_CLIENT_ID=your_id to supabase/functions/.env

Mood-to-tag mapping is derived from the video script's Music Direction section.
"""

import os
import re
import json
import requests
from pathlib import Path

ROOT      = Path(__file__).parent.parent
MUSIC_DIR = ROOT / ".tmp/music"

def _load_env():
    for p in [ROOT / "supabase/functions/.env", ROOT / "test-data-seeder/.env", ROOT / ".env"]:
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

_load_env()

JAMENDO_ID = os.getenv("JAMENDO_CLIENT_ID", "")

# ── Mood-to-Jamendo-tag mapping ───────────────────────────────────────────────

MOOD_TAGS = {
    "urgency":          "cinematic+dramatic",
    "quiet urgency":    "ambient+cinematic",
    "industrial":       "ambient+electronic",
    "industrial ambient": "ambient+electronic",
    "lo-fi":            "lofi+relaxing",
    "lofi":             "lofi+relaxing",
    "hip hop":          "hiphop+urban",
    "upbeat":           "pop+upbeat",
    "hope":             "inspirational+uplifting",
    "hopeful":          "inspirational+uplifting",
    "pride":            "motivational+uplifting",
    "emotional":        "cinematic+emotional",
    "fear":             "dramatic+tense",
    "tension":          "dramatic+tense",
    "relief":           "ambient+relaxing",
    "ambition":         "motivational+epic",
    "corporate":        "corporate+background",
    "opm":              "pop+acoustic",
    "factory":          "electronic+ambient",
}

DEFAULT_TAGS = "ambient+cinematic"


def _mood_to_tags(mood_text: str) -> str:
    mood_lower = mood_text.lower()
    for keyword, tags in MOOD_TAGS.items():
        if keyword in mood_lower:
            return tags
    return DEFAULT_TAGS


# ── Jamendo search ────────────────────────────────────────────────────────────

def search_tracks(tags: str, duration_max: int = 120, limit: int = 5) -> list:
    if not JAMENDO_ID:
        raise RuntimeError(
            "JAMENDO_CLIENT_ID not set.\n"
            "Get a free key at: https://devportal.jamendo.com/signup\n"
            "Then add it to supabase/functions/.env as:\n"
            "  JAMENDO_CLIENT_ID=your_client_id"
        )

    resp = requests.get(
        "https://api.jamendo.com/v3.0/tracks/",
        params={
            "client_id":      JAMENDO_ID,
            "format":         "json",
            "tags":           tags,
            "limit":          limit,
            "include":        "musicinfo+licenses",
            "audioformat":    "mp31",
            "audiodlformat":  "mp31",
            "durationbetween": f"30_{duration_max}",
            "ccsa":           "false",   # allow commercial use
            "ccnd":           "false",   # allow modifications
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("results", [])


def _pick_best(tracks: list) -> dict | None:
    if not tracks:
        return None
    # Prefer tracks with higher stats.rate (popularity)
    return sorted(tracks, key=lambda t: t.get("stats", {}).get("rate", 0), reverse=True)[0]


def download_track(track: dict, out_dir: Path = None) -> Path:
    out_dir = out_dir or MUSIC_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    dl_url   = track.get("audiodownload") or track.get("audio")
    name     = re.sub(r"[^\w\s-]", "", track.get("name", "track"))[:40].strip()
    artist   = re.sub(r"[^\w\s-]", "", track.get("artist_name", ""))[:20].strip()
    filename = f"{artist}_{name}.mp3".replace(" ", "_")
    out_path = out_dir / filename

    print(f"  Downloading: {track.get('name')} by {track.get('artist_name')}")
    print(f"  License: {track.get('license_ccurl', 'CC')}")

    with requests.get(dl_url, stream=True, timeout=30) as r:
        r.raise_for_status()
        out_path.write_bytes(r.content)

    size_kb = out_path.stat().st_size // 1024
    print(f"  Saved: {out_path.name}  ({size_kb} KB)")
    return out_path


# ── High-level: find music for a video mood ───────────────────────────────────

def find_music_for_mood(mood_text: str, duration_max: int = 120) -> Path:
    tags   = _mood_to_tags(mood_text)
    print(f"\nSearching Jamendo: tags={tags}, duration<={duration_max}s")

    tracks = search_tracks(tags, duration_max)
    if not tracks:
        # Widen the search
        print("  No results — retrying with broader tags...")
        tracks = search_tracks("ambient+background", duration_max)

    track = _pick_best(tracks)
    if not track:
        raise RuntimeError(f"No tracks found on Jamendo for tags: {tags}")

    return download_track(track)


def find_music_for_script(script_content: str) -> Path:
    """Extract music direction from a generated script and find a matching track."""
    mood_match  = re.search(r"\*\*Mood:\*\*\s*(.+)", script_content)
    style_match = re.search(r"\*\*Style:\*\*\s*(.+)", script_content)
    bpm_match   = re.search(r"\*\*BPM:\*\*\s*(\d+)", script_content)

    mood  = mood_match.group(1).strip()  if mood_match  else "ambient"
    style = style_match.group(1).strip() if style_match else ""
    bpm   = int(bpm_match.group(1))      if bpm_match   else 80

    # Build a combined search query from the script's music direction
    combined_mood = f"{mood} {style}".strip()
    duration_max  = 120 if bpm < 90 else 90

    print(f"  Music direction: '{combined_mood}' ~{bpm}bpm")
    return find_music_for_mood(combined_mood, duration_max)


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    mood = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "quiet urgency industrial"
    try:
        result = find_music_for_mood(mood)
        print(f"\nDone: {result}")
    except RuntimeError as e:
        print(f"\nError: {e}")

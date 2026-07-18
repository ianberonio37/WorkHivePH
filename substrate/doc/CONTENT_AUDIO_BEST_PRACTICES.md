---
name: doc-CONTENT_AUDIO_BEST_PRACTICES
type: doc
source: file:CONTENT_AUDIO_BEST_PRACTICES.md
source_sha: 6d01f23d08ecda7f
last_verified: 2026-07-13
supersedes: null
---
## doc · CONTENT_AUDIO_BEST_PRACTICES

**Purpose:** actionable, cited reference to improve the WorkHive product-overview explainer (74s, 9:16, James/Filipino-accented TTS, pure-Python Pillow+ffmpeg engine). Focus: music selection, music le

**Sections:** Audio Best Practices for Short-Form Marketing / Explainer Video · TL;DR — the numbers that matter for our video · 1. Loudness targets (how loud the FINAL mix should be) · 2. Music-under-voice level (the ducking gap) · 3. Sidechain / auto-ducking (the upgrade over a static low volume) · 4. Music selection (track, tempo, energy, emotional arc) · 5. EQ — carve space so music never masks speech · 6. Fades & editing to the beat · 7. Sound design / SFX (tasteful, minimal) · 8. TTS VO quality — make James sound premium, not robotic · RECOMMENDED MIX CHAIN (ffmpeg) for our explainer · --- PASS 1: build the mix (no final loudnorm yet), measure it --- · 1) PASS 2: measure with loudnorm print_format=json on mix_premaster.wav: · ffmpeg -i mix_premaster.wav -af "loudnorm=I=-14:TP=-1.0:LRA=11:print_format=json" -f null - · then apply linear normalization to the video: · Sources

(Deep source: `file:CONTENT_AUDIO_BEST_PRACTICES.md` — retrieve this TOC to know WHICH section to read.)

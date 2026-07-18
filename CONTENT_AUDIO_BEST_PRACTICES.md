# Audio Best Practices for Short-Form Marketing / Explainer Video

**Purpose:** actionable, cited reference to improve the WorkHive product-overview explainer (74s, 9:16, James/Filipino-accented TTS, pure-Python Pillow+ffmpeg engine). Focus: music selection, music level under voiceover, ducking, loudness, EQ, fades, SFX, and TTS polish. Every rule has concrete numbers and an ffmpeg apply-note.

## TL;DR — the numbers that matter for our video

- **Final mix loudness:** normalize the WHOLE video to **-14 LUFS integrated** (the target YouTube / TikTok / Instagram / Spotify all normalize to) with a true-peak ceiling of **-1 dBTP**. [YouTube/TikTok/IG/Spotify all -14 LUFS](https://clickyapps.com/creator/video/guides/lufs-targets-2025)
- **Voice vs music gap:** music bed should sit **18-20 dB below** the narration (W3C minimum: **≥20 dB below foreground speech**). Our current `volume=0.14` (~ -17 dBFS gain) is in range statically, but a static level is inferior to ducking. [Pure Audio Insight](https://pureaudioinsight.com/blogs/content-production/background-music-volume-how-loud-should-it-be)
- **Switch to sidechain ducking** so the music dips ~**6-12 dB** automatically only while James talks, and rises in the gaps/CTA. This is the single biggest upgrade over a fixed `volume=0.14`. [FFmpegLab](https://www.ffmpeglab.com/articles/ffmpeg-audio-mixing-amix-guide.html)
- **Carve the music:** high-pass the music at ~**80-100 Hz** and dip it **-3 to -5 dB around 2-4 kHz** so it stops masking speech consonants (1.5-4 kHz carry ~60% of intelligibility). [343 Labs](https://www.343labs.com/vocal-eq-cheat-sheet/) / [FlexRadio](https://helpdesk.flexradio.com/hc/en-us/articles/203853305-Rules-for-EQing-Voice-for-Optimal-Phone-Operation)
- **Track selection:** instrumental only; even, mid-tempo bed (~90-120 BPM) for the problem/explainer body, lifting to a brighter/higher-energy cue on the solution reveal; consider a music-drop pause on the biggest reveal. [Music for Makers](https://musicformakers.com/blog/background-music-for-video) / [Vidyard](https://www.vidyard.com/blog/background-music-for-video/)

---

## 1. Loudness targets (how loud the FINAL mix should be)

- **Broadcast reference / measurement basis:** loudness is measured per **ITU-R BS.1770** (K-weighting, gating) and reported in **LUFS**; EBU R128 targets **-23 LUFS ±0.5** for broadcast with a **-1 dBTP** max true peak. This is the standard the whole industry builds on, but broadcast -23 is NOT the web target. [EBU R128 / Wikipedia](https://en.wikipedia.org/wiki/EBU_R_128)
- **Web/social is louder:** YouTube, TikTok, Instagram, and Spotify all **normalize playback to ~-14 LUFS integrated**. Master to -14 and the platform leaves you alone; master quieter and it may turn you up (adding nothing) or you sound weak next to others. Apple Music is -16 LUFS. [Clicky LUFS targets 2025](https://clickyapps.com/creator/video/guides/lufs-targets-2025)
- **True-peak ceiling:** keep true peak **≤ -1 dBTP** (some engineers use -1.5 dBTP) to avoid inter-sample clipping after lossy AAC/MP3 transcode. [EBU R128](https://en.wikipedia.org/wiki/EBU_R_128) / [DEV two-pass loudnorm](https://dev.to/masonwritescode/two-pass-loudness-normalization-with-ffmpeg-loudnorm-the-right-way-1nm3)
- **Why -14, not louder:** the platforms un-do extra loudness anyway (end of the "loudness war"); -14 LUFS is the sweet spot that survives normalization with dynamics intact. [iMusician loudness 2025](https://imusician.pro/en/resources/blog/mastering-and-the-loudness-war-an-update)

→ **Apply (ffmpeg):** two-pass `loudnorm` to hit exactly -14 LUFS / -1 dBTP.
Pass 1 (measure): `-af "loudnorm=I=-14:TP=-1.0:LRA=11:print_format=json"` then read `input_i/input_tp/input_lra/input_thresh` from the JSON.
Pass 2 (apply, linear so dynamics survive): `-af "loudnorm=I=-14:TP=-1.0:LRA=11:measured_I=..:measured_TP=..:measured_LRA=..:measured_thresh=..:offset=..:linear=true"`. [DEV two-pass loudnorm](https://dev.to/masonwritescode/two-pass-loudness-normalization-with-ffmpeg-loudnorm-the-right-way-1nm3)

## 2. Music-under-voice level (the ducking gap)

- **Target gap: music 18-20 dB below the narration.** Under 15 dB = masking (music drowns speech); over 25 dB = music inaudible on phone speakers. Sweet spot 18-20 dB. [Pure Audio Insight](https://pureaudioinsight.com/blogs/content-production/background-music-volume-how-loud-should-it-be)
- **W3C accessibility floor:** non-speech (incl. music) must be **≥ 20 dB below foreground speech** — their worked example: voice -17.5 dB RMS, music -37.5 dB RMS (a clean 20 dB gap). Treat 20 dB as the safe target. [Pure Audio Insight citing W3C](https://pureaudioinsight.com/blogs/content-production/background-music-volume-how-loud-should-it-be)
- **In LUFS terms:** if VO sits around **-12 to -16 LUFS**, the music bed under it should sit around **-30 to -36 LUFS** during speech. [The Vocal Market LUFS guide](https://thevocalmarket.com/blogs/how-to/how-to-mix-vocals-for-streaming-lufs-loudness-2026)
- **BBC trick:** mix music normally, then pull it down an extra **~4 dB** — cheap insurance for intelligibility. [Pure Audio Insight citing BBC](https://pureaudioinsight.com/blogs/content-production/background-music-volume-how-loud-should-it-be)
- **Our current setting:** `volume=0.14` ≈ -17 dB of gain applied to the music. Whether that lands at the ~20 dB gap depends on the source track's own loudness, so it's fragile. Ducking (Section 3) makes the gap self-correcting.

→ **Apply (ffmpeg):** as a static floor, keep music around `volume=0.12-0.15` during speech, but prefer sidechain ducking below. For a hard target, loudnorm the music stem alone to ~-32 LUFS before mixing: `-af "loudnorm=I=-32:TP=-6:LRA=11"`.

## 3. Sidechain / auto-ducking (the upgrade over a static low volume)

- **What it is:** the voice track acts as a trigger; whenever James speaks, a compressor pulls the music down automatically, then lets it swell back up in the pauses and at the CTA. A static `volume=0.14` is always-low (dull in the gaps AND still muddy under dense speech); ducking gives you a loud, present bed between phrases and a clean bed under them. [FFmpegLab](https://www.ffmpeglab.com/articles/ffmpeg-audio-mixing-amix-guide.html)
- **Duck depth:** a good start is **~6-12 dB of gain reduction** while speech is present (Descript/Premiere "auto-duck ~ -18 dB amount"; in practice 6-12 dB reads as natural for a bed you still want audible). [Descript audio levels](https://www.descript.com/blog/article/how-to-set-the-perfect-audio-levels-for-video) / [Storyblocks](https://www.storyblocks.com/resources/tutorials/how-to-balance-audio-premiere-pro)
- **Timing:** fast-ish attack (**~20 ms**) so music drops as speech starts; slow-ish release (**~250-400 ms**) so it doesn't pump between words. [FFmpegLab](https://www.ffmpeglab.com/articles/ffmpeg-audio-mixing-amix-guide.html)

→ **Apply (ffmpeg):** `[music][voice]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300:makeup=1[ducked]` then `[voice][ducked]amix=inputs=2:duration=first`. Increase `ratio` (8→12) or lower `threshold` (0.03→0.02) for deeper ducking. [FFmpegLab](https://www.ffmpeglab.com/articles/ffmpeg-audio-mixing-amix-guide.html)

## 4. Music selection (track, tempo, energy, emotional arc)

- **Instrumental only** under narration — lyrics compete with James's words for the same speech-processing attention. Use vocal tracks only where there's no VO. [Music for Makers](https://musicformakers.com/blog/background-music-for-video)
- **Tempo:** for a B2B/tech explainer keep an **even, unobtrusive mid-tempo bed** that "adds interest without drawing attention"; ~**90-120 BPM** reads calm-competent, **140-200 BPM** signals high energy (save that for the reveal, not the problem setup). [Vidyard](https://www.vidyard.com/blog/background-music-for-video/) / [Artlist BPM guide](https://artlist.io/blog/music-bpm/)
- **Match energy to the story beat (problem→solution arc):** low/tense energy under the "downtime is expensive / chaos" problem section; lift to **hopeful, brighter, higher-energy** on the WorkHive solution reveal and CTA. Energy directs the viewer to emotional focal points. [Music for Makers](https://musicformakers.com/blog/background-music-for-video)
- **Reconsider "dramatic/cinematic":** a heavy dramatic bed can fight a clear product explainer. If our library has a cleaner "even mid-tempo" or hopeful/uplifting cue, A/B it against the current dramatic track — the owner's dissatisfaction with the TRACK suggests the current one is too heavy/tense for the whole runtime.
- **When NO music is better:** a deliberate **music drop-out on the single biggest reveal** grabs attention precisely because the pattern breaks; works best when the bed has a steady rhythm so the pause lands. Also fine to run VO-only for a beat before the CTA. [Music for Makers](https://musicformakers.com/blog/background-music-for-video)

→ **Apply (engine):** pick the lightest/most-hopeful instrumental in the royalty-free library for the body; optionally swap to a brighter cue at the reveal timestamp, or cut music entirely for ~1-2 s at the reveal via an `afade`/`volume` envelope keyed to that timecode.

## 5. EQ — carve space so music never masks speech

- **Consonants (intelligibility) live at 1.5-4 kHz:** the 1-8 kHz band is only ~5% of the power but ~60% of intelligibility, so protect it in the voice and vacate it in the music. [FlexRadio EQ rules](https://helpdesk.flexradio.com/hc/en-us/articles/203853305-Rules-for-EQing-Voice-for-Optimal-Phone-Operation)
- **High-pass the music** at **~80-100 Hz** to clear low-mid mud that otherwise competes with vocal body. [343 Labs vocal EQ](https://www.343labs.com/vocal-eq-cheat-sheet/)
- **Subtractive dip in the music, not just a boost on the voice:** cutting the music **-3 to -5 dB around 2-5 kHz** does more for clarity than boosting the VO. [Sage Audio vocal EQ tips](https://www.sageaudio.com/articles/top-10-vocal-eq-tips)
- **On the voice:** gentle presence boost **+2-4 dB around 3-5 kHz** for clarity, and a high-pass at **~80-100 Hz** to remove rumble. [343 Labs](https://www.343labs.com/vocal-eq-cheat-sheet/)

→ **Apply (ffmpeg):** music: `highpass=f=90, equalizer=f=3000:width_type=o:width=1.5:g=-4`. Voice: `highpass=f=90, equalizer=f=4000:width_type=o:width=1:g=3`.

## 6. Fades & editing to the beat

- **Fade durations:** our current **1.2 s in / 1.5 s out** on the music bed is reasonable; a slightly longer tail (**~2 s**) reads smoother at the end. Use a triangular/linear curve. [FFmpegLab acrossfade example](https://www.ffmpeglab.com/articles/ffmpeg-audio-mixing-amix-guide.html)
- **Duck harder at the CTA:** at the closing call-to-action, either dip the music an extra few dB (let ducking do it) or fade it out entirely so the CTA line lands clean.
- **Sync scene cuts to the beat/downbeat:** land title reveals and hard cuts on musical **downbeats**; a title fading in on a downbeat or a color shift on a "drop" creates satisfying sync viewers feel. Simple cuts on strong beats work best; 4-8 s per shot for higher-energy sections. [Bitcut beat-sync](https://bitcut.app/blog/beat-sync-video-editing)

→ **Apply (ffmpeg/engine):** music `afade=t=in:st=0:d=1.2, afade=t=out:st=<end-2>:d=2`. For the CTA, add a `volume` automation point or shorten music before the last line. If beat times are known, align the Pillow scene-change timestamps to those downbeats.

## 7. Sound design / SFX (tasteful, minimal)

- **One signature SFX per beat, not clutter:** a **whoosh into the headline** (hook), a **soft tap/click on the on-screen button/UI**, a **subtle pop/impact on the reveal**. Consistency of tone beats quantity. [SoundMorph whoosh guide](https://soundmorph.com/blogs/news/best-whoosh-sound-effects-for-film-trailers-and-ui-a-designer-s-guide)
- **Level:** keep SFX **4-8 dB below the narration** so speech stays intelligible. [SoundMorph](https://soundmorph.com/blogs/news/best-whoosh-sound-effects-for-film-trailers-and-ui-a-designer-s-guide)
- **EQ the SFX:** roll off sub-bass on whooshes to avoid mud; tame harsh clicks around **3-5 kHz**. [SoundMorph](https://soundmorph.com/blogs/news/best-whoosh-sound-effects-for-film-trailers-and-ui-a-designer-s-guide)
- **Where:** start strong (whoosh/click in the first ~3 s hook), keep transitions tight, one impact on the main reveal — don't SFX every transition. [SoundMorph](https://soundmorph.com/blogs/news/best-whoosh-sound-effects-for-film-trailers-and-ui-a-designer-s-guide)

→ **Apply (ffmpeg):** add an SFX stem via `adelay` to place it at a timecode, `volume=0.4` (≈ -8 dB) relative to VO, `highpass=f=120` on whooshes, then include it in the final `amix`. e.g. `[sfx]adelay=3000|3000,volume=0.4,highpass=f=120[sfx1]`.

## 8. TTS VO quality — make James sound premium, not robotic

Processing order = corrective first, then character, then space. [Rys Up Audio vocal chain order](https://rysupaudio.com/blogs/news/best-vocal-chain-order)
- **EQ before de-ess** so you don't amplify sibilance, then de-ess. [Sonarworks AI vocals](https://www.sonarworks.com/blog/learn/mastering-ai-vocals-eq-and-compression-tips)
- **Light compression, low ratio** to glue/even the TTS dynamics (TTS is already fairly flat, so keep it gentle). [Sonarworks](https://www.sonarworks.com/blog/learn/mastering-ai-vocals-eq-and-compression-tips)
- **De-ess** the harsh S/T sibilance TTS tends to over-articulate (target ~5-8 kHz). [Sonarworks](https://www.sonarworks.com/blog/learn/mastering-ai-vocals-eq-and-compression-tips)
- **Subtle room reverb at ~5-10% wet** for depth/realism (dry TTS sounds "in a vacuum"). Keep it low or it muddies speech. [Voice.ai TTS tips](https://voice.ai/hub/tts/how-to-make-text-to-speech-sound-less-robotic/)
- **Normalize** the VO stem to a consistent level before mixing.

→ **Apply (ffmpeg), voice chain (in order):**
`highpass=f=90, equalizer=f=4000:width_type=o:width=1:g=3, deesser=i=0.1, acompressor=threshold=-18dB:ratio=3:attack=15:release=200, aecho=0.8:0.85:12:0.08` (the `aecho` gives a tiny room; keep the last mix ~0.08 low). Then feed into the sidechain trigger + final loudnorm. [Rys Up Audio](https://rysupaudio.com/blogs/news/best-vocal-chain-order) / [Sonarworks](https://www.sonarworks.com/blog/learn/mastering-ai-vocals-eq-and-compression-tips) / [Voice.ai](https://voice.ai/hub/tts/how-to-make-text-to-speech-sound-less-robotic/)

---

## RECOMMENDED MIX CHAIN (ffmpeg) for our explainer

Inputs: `[0:a]` = James narration (TTS), `[1:a]` = music bed (looped), optional `[2:a]` = SFX stem.
This replaces the current `amix + volume=0.14 + alimiter` with: voice-polish → music-carve → sidechain-duck → mix → SFX → loudnorm to -14 LUFS / -1 dBTP.

```bash
# --- PASS 1: build the mix (no final loudnorm yet), measure it ---
ffmpeg -i narration.wav -i music.mp3 -i sfx.wav -filter_complex "
  # 8) Voice polish (corrective -> character -> space)
  [0:a]highpass=f=90,
       equalizer=f=4000:width_type=o:width=1:g=3,
       acompressor=threshold=-18dB:ratio=3:attack=15:release=200,
       aecho=0.8:0.85:12:0.08,
       aformat=sample_rates=48000:channel_layouts=stereo[vox];

  # 5) Music: high-pass + carve the 2-4kHz speech band + set bed level
  [1:a]highpass=f=90,
       equalizer=f=3000:width_type=o:width=1.5:g=-4,
       volume=0.6,
       afade=t=in:st=0:d=1.2,afade=t=out:st=72:d=2,
       aformat=sample_rates=48000:channel_layouts=stereo[music];

  # 3) Sidechain-duck the music under the voice (~8-12 dB, natural timing)
  [music][vox]sidechaincompress=threshold=0.03:ratio=10:attack=20:release=300:makeup=1[ducked];

  # 7) SFX: place, level (-8 dB), de-mud
  [2:a]adelay=2500|2500,volume=0.4,highpass=f=120[sfx1];

  # 2) Mix voice + ducked music (+ sfx), then true-peak safety limit
  [vox][ducked][sfx1]amix=inputs=3:duration=first:normalize=0,
       alimiter=limit=0.97[mix]
" -map "[mix]" -ac 2 -ar 48000 mix_premaster.wav

# 1) PASS 2: measure with loudnorm print_format=json on mix_premaster.wav:
#    ffmpeg -i mix_premaster.wav -af "loudnorm=I=-14:TP=-1.0:LRA=11:print_format=json" -f null -
#    then apply linear normalization to the video:
ffmpeg -i video.mp4 -i mix_premaster.wav -filter_complex "
  [1:a]loudnorm=I=-14:TP=-1.0:LRA=11:measured_I=<M_I>:measured_TP=<M_TP>:measured_LRA=<M_LRA>:measured_thresh=<M_TH>:offset=<M_OFF>:linear=true[a]
" -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k final.mp4
```

**Exact numbers baked in:** final **-14 LUFS / -1 dBTP** ([DEV loudnorm](https://dev.to/masonwritescode/two-pass-loudness-normalization-with-ffmpeg-loudnorm-the-right-way-1nm3)); music **high-passed 90 Hz**, **-4 dB @ 3 kHz** carve ([343 Labs](https://www.343labs.com/vocal-eq-cheat-sheet/)); **sidechain duck ratio 10:1, 20 ms attack / 300 ms release** ([FFmpegLab](https://www.ffmpeglab.com/articles/ffmpeg-audio-mixing-amix-guide.html)); voice **+3 dB @ 4 kHz presence, 3:1 comp, tiny room** ([Rys Up Audio](https://rysupaudio.com/blogs/news/best-vocal-chain-order)); SFX **-8 dB, HPF 120 Hz** ([SoundMorph](https://soundmorph.com/blogs/news/best-whoosh-sound-effects-for-film-trailers-and-ui-a-designer-s-guide)); fades **1.2 s in / 2 s out** ([FFmpegLab](https://www.ffmpeglab.com/articles/ffmpeg-audio-mixing-amix-guide.html)).

> Tune `volume=0.6` on the music and the sidechain `ratio`/`threshold` so the ducked bed lands ~**18-20 dB below** the narration ([Pure Audio Insight](https://pureaudioinsight.com/blogs/content-production/background-music-volume-how-loud-should-it-be)); verify the final file measures -14 LUFS integrated / ≤ -1 dBTP with `loudnorm ... print_format=json`.

## Sources
- [EBU R128 / ITU-R BS.1770 — Wikipedia](https://en.wikipedia.org/wiki/EBU_R_128) · [EBU R128 official PDF](https://tech.ebu.ch/docs/r/r128.pdf) · [EBU R128 s1 short-form (adverts/promos)](https://tech.ebu.ch/docs/r/r128s1.pdf)
- [LUFS targets 2025 — YouTube/TikTok/Spotify (Clicky)](https://clickyapps.com/creator/video/guides/lufs-targets-2025) · [Streaming loudness table (Soundplate)](https://soundplate.com/streaming-loudness-lufs-table/) · [Loudness war 2025 (iMusician)](https://imusician.pro/en/resources/blog/mastering-and-the-loudness-war-an-update)
- [Set perfect audio levels for video (Descript)](https://www.descript.com/blog/article/how-to-set-the-perfect-audio-levels-for-video) · [Background music volume (Pure Audio Insight)](https://pureaudioinsight.com/blogs/content-production/background-music-volume-how-loud-should-it-be) · [Balance audio in Premiere (Storyblocks)](https://www.storyblocks.com/resources/tutorials/how-to-balance-audio-premiere-pro) · [Mix vocals for streaming LUFS (The Vocal Market)](https://thevocalmarket.com/blogs/how-to/how-to-mix-vocals-for-streaming-lufs-loudness-2026)
- [FFmpeg amix/sidechaincompress ducking (FFmpegLab)](https://www.ffmpeglab.com/articles/ffmpeg-audio-mixing-amix-guide.html) · [Two-pass loudnorm the right way (DEV)](https://dev.to/masonwritescode/two-pass-loudness-normalization-with-ffmpeg-loudnorm-the-right-way-1nm3) · [loudnorm guide (mitz17)](https://mitz17.com/en/blog/ffmpeg-loudnorm-guide/)
- [Choosing background music (Music for Makers)](https://musicformakers.com/blog/background-music-for-video) · [Best background music for video (Vidyard)](https://www.vidyard.com/blog/background-music-for-video/) · [Music BPM for video (Artlist)](https://artlist.io/blog/music-bpm/)
- [Vocal EQ cheat sheet (343 Labs)](https://www.343labs.com/vocal-eq-cheat-sheet/) · [Top 10 vocal EQ tips (Sage Audio)](https://www.sageaudio.com/articles/top-10-vocal-eq-tips) · [EQing voice intelligibility (FlexRadio)](https://helpdesk.flexradio.com/hc/en-us/articles/203853305-Rules-for-EQing-Voice-for-Optimal-Phone-Operation)
- [Whoosh/SFX designer guide (SoundMorph)](https://soundmorph.com/blogs/news/best-whoosh-sound-effects-for-film-trailers-and-ui-a-designer-s-guide) · [Beat-sync video editing (Bitcut)](https://bitcut.app/blog/beat-sync-video-editing)
- [Make TTS less robotic (Voice.ai)](https://voice.ai/hub/tts/how-to-make-text-to-speech-sound-less-robotic/) · [Mastering AI vocals EQ+comp (Sonarworks)](https://www.sonarworks.com/blog/learn/mastering-ai-vocals-eq-and-compression-tips) · [Best vocal chain order (Rys Up Audio)](https://rysupaudio.com/blogs/news/best-vocal-chain-order)

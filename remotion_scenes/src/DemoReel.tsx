import React from 'react';
import {
  AbsoluteFill, Video, Img, staticFile, useCurrentFrame,
  useVideoConfig, spring, interpolate, Sequence, Easing, random,
} from 'remotion';
import {ORANGE, FONT} from './Ambient';
import {CAMERA_KEYS, CamKey, CAPTIONS} from './demoCamera';
import {CameraMotionBlur} from '@remotion/motion-blur';

// ════════════════════════════════════════════════════════════════════════
// DemoReel v2 — "the same as the video sample" (Ian, 2026-07-30).
//
// v1 got the sample's SKELETON (beats, inset footage, held end card) but
// painted the whole video in WorkHive's dark page navy. The sample is a
// LIGHT-WORLD video: near-white kinetic cards (#F4F4F4 measured), pale-blue
// product backdrops (#DDEAF7 measured), bold dark type — and BLACK is used
// only as the stage for the 3D device reveals. "Follow my platform theme"
// means WorkHive's logo/ink/orange/cyan INSIDE that bright look, not the
// app's dark background stretched over the video.
//
// The sample's signature moves, all measured/observed in
// .tmp/video_ref/Video Marketing_study/ (sheet_trans.jpg, _spec.json):
//   1. one-word kinetic hook, ~0.9s cadence, motion-blur entry
//   2. logo sting on white
//   3. BLACK interlude: a 3D device rises tilted with a blue rim glint,
//      straightens to face camera, screen alive -> camera PUSHES INTO it
//   4. product walkthroughs slightly inset on a pale backdrop (2.8% margins)
//   5. section titles that land with an elastic WAVE and exit by SCATTER
//   6. end card on white, HELD ~10.4s
//
// FOOTAGE: pre-cut VP9 webm segments (journey_seg0..5) decoded by the render
// browser via <Video> — the Rust compositor failed on both the raw Playwright
// VP8 and a clean H.264 ("No frame found at position", version-mismatched
// tree); per-beat files starting at 0 sidestep decode AND deep seeks.
// ════════════════════════════════════════════════════════════════════════

// WorkHive palette in light-world ROLES: CLOUD is the brand's own light token
// (FlagshipReel CLOUD / site --text inverse), INK the site ink; accents as-is.
const CLOUD = '#F4F6FA';          // card world      (sample measured #F4F4F4)
const PALE = '#E4EDF7';           // product backdrop (sample measured #DDEAF7)
const INK = '#16202F';            // type             (sample uses near-black)
const CYAN = '#38BDF8';
const BLACK = '#050608';          // device-reveal stage

const FPS = 30;
const sec = (s: number) => Math.round(s * FPS);

type Beat =
  | {kind: 'word'; text: string; accent?: boolean; frames: number}
  | {kind: 'logo'; frames: number}
  | {kind: 'device'; seg: number; frames: number}
  | {kind: 'phone'; frames: number}
  | {kind: 'title'; lines: string[]; frames: number}
  | {kind: 'section'; seg: number; frames: number}
  | {kind: 'whip'; frames: number}
  | {kind: 'end'; frames: number};

export const DEMO_BEATS: Beat[] = [
  {kind: 'word', text: 'Every', frames: 26},
  {kind: 'word', text: 'fix.', frames: 26},
  {kind: 'word', text: 'Every', frames: 26},
  {kind: 'word', text: 'part.', frames: 26},
  {kind: 'word', text: 'Kept.', accent: true, frames: 40},
  {kind: 'logo', frames: 58},
  {kind: 'device', seg: 0, frames: 170},

  // CHAPTER 1 - LOGBOOK (the journey Ian named first)
  {kind: 'whip', frames: 18},
  {kind: 'title', lines: ['Log what you fixed'], frames: 96},
  {kind: 'section', seg: 0, frames: 540},
  {kind: 'section', seg: 1, frames: 450},
  {kind: 'section', seg: 2, frames: 660},
  {kind: 'section', seg: 3, frames: 240},

  // CHAPTER 2 - INVENTORY
  {kind: 'whip', frames: 18},
  {kind: 'title', lines: ['Know what you have'], frames: 96},
  {kind: 'section', seg: 4, frames: 690},

  // CHAPTER 3 - PM SCHEDULER
  {kind: 'whip', frames: 18},
  {kind: 'title', lines: ['Never miss a PM'], frames: 96},
  {kind: 'section', seg: 5, frames: 570},

  // CHAPTER 4 - DAY PLANNER
  {kind: 'whip', frames: 18},
  {kind: 'title', lines: ['Plan your whole day'], frames: 96},
  {kind: 'section', seg: 6, frames: 420},

  {kind: 'end', frames: 270},
];

export const DEMO_DURATION = DEMO_BEATS.reduce((a, b) => a + b.frames, 0);

// ── kinetic type ────────────────────────────────────────────────────────

// Hook word on the light card: fast blur-in with a horizontal stretch — the
// sample's smeared-entry read (its "Filing" arrives as a motion trail).
const Word: React.FC<{text: string; accent?: boolean; frames: number}> = ({text, accent, frames}) => {
  const f = useCurrentFrame();
  const {height} = useVideoConfig();
  // TRACED, not styled (tools/trace_motion_curve.py, curve_word1.json): the
  // sample word is LOCKED - scale flat, blur 0.01, zero drift - for ~11
  // frames, then ERUPTS (blur 0.95, scale sweeping 0.74->1.07) across ~5-6
  // frames, and the NEXT word is already locked dead-sharp one frame later.
  // A word is never seen animating: it is locked, or it is mush. Twelve
  // spring variants failed because they showed the in-between.
  const ERUPT = 6;
  const k = Math.max(0, f - (frames - ERUPT)) / ERUPT;    // 0 locked .. 1 gone
  const arriving = f < 2 ? (2 - f) / 2 : 0;               // <=2f residual snap
  const e = Math.pow(k, 1.6);
  return (
    <AbsoluteFill style={{background: CLOUD, alignItems: 'center', justifyContent: 'center'}}>
      <div style={{
        fontFamily: FONT, fontWeight: 800,
        fontSize: height * (accent ? 0.28 : 0.24),
        color: accent ? ORANGE : INK,
        transform: `scale(${1 + e * 0.38}) translateX(${e * height * 0.06}px)`,
        filter: `blur(${e * 26 + arriving * 8}px)`,
        opacity: 1 - e * 0.65,
      }}>{text}</div>
    </AbsoluteFill>
  );
};

const Logo: React.FC<{frames: number}> = ({frames}) => {
  const f = useCurrentFrame();
  const {fps, height} = useVideoConfig();
  const s = spring({frame: f, fps, config: {damping: 15, stiffness: 120}});
  const out = interpolate(f, [frames - 6, frames], [1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: CLOUD, alignItems: 'center', justifyContent: 'center'}}>
      <Img src={staticFile('workhive-logo-clean.png')}
           style={{height: height * 0.38, transform: `scale(${0.86 + 0.14 * s})`,
                   opacity: s * out}} />
    </AbsoluteFill>
  );
};

// Section title: per-letter elastic WAVE landing (the tail arrives late and
// curls — the sample's "Extract Data from Your Documents" move), then a
// physics SCATTER exit (letters fly apart with gravity — its
// "Track/Compliance/Deadlines" move). Deterministic velocities via random(seed).
const Title: React.FC<{lines: string[]; frames: number}> = ({lines, frames}) => {
  const f = useCurrentFrame();
  const {fps, height} = useVideoConfig();
  // TRACED (curve_title_enter/scatter.json): lines POP in one at a time -
  // sharp ON the arrival frame, ~0.45s apart, with only a 3-4 frame sharpen
  // settle. Before the scatter the whole stack INFLATES (~1.0 -> 1.35 with a
  // wobble) for ~6 frames, THEN erupts downward. Holds are LOCKED.
  const SCATTER_AT = frames - 14;
  const INFLATE_AT = SCATTER_AT - 6;
  const ex = Math.max(0, f - SCATTER_AT);
  const inflate = f >= INFLATE_AT && ex === 0
    ? 1 + 0.3 * Math.sin(((f - INFLATE_AT) / 6) * Math.PI * 0.9)
    : 1;
  let letterIndex = 0;
  return (
    <AbsoluteFill style={{background: CLOUD, alignItems: 'center', justifyContent: 'center'}}>
      <div style={{transform: `scale(${inflate})`}}>
        {lines.map((ln, li) => {
          const lineAt = li * 14;                    // ~0.45s stagger
          const on = f >= lineAt;
          const settle = Math.max(0, 4 - (f - lineAt));   // 4-frame sharpen
          return (
            <div key={li} style={{textAlign: 'center', whiteSpace: 'pre',
                                  lineHeight: 1.12, opacity: on ? 1 : 0}}>
              {ln.split('').map((ch, ci) => {
                const i = letterIndex++;
                const vx = (random(`x${li}-${ci}`) - 0.5) * height * 0.10;
                const vy = -random(`y${li}-${ci}`) * height * 0.06;
                const sx = ex * vx * 0.35;
                const sy = ex * vy * 0.5 + ex * ex * height * 0.0045;  // faster fall
                const srot = ex * (random(`r${li}-${ci}`) - 0.5) * 30;
                const op = ex > 0 ? Math.max(0, 1 - ex / 7) : 1;   // gone in ~7f
                return (
                  <span key={ci} style={{
                    display: 'inline-block',
                    fontFamily: FONT, fontWeight: 800, color: INK,
                    fontSize: height * 0.135,
                    transform: `translate(${sx}px, ${sy}px) rotate(${srot}deg) scale(${ex > 0 ? Math.max(0.25, 1 - ex * 0.12) : 1})`,
                    filter: ex > 0 ? `blur(${Math.min(30, ex * ex * 1.6)}px)` : `blur(${settle * 1.6}px)`,
                    opacity: op,
                  }}>{ch === ' ' ? ' ' : ch}</span>
                );
              })}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ── the black device interlude ──────────────────────────────────────────
// Two CSS "laptops" both read as fake to Ian ("weird laptop", twice) - a
// hand-drawn 3D machine is uncanny next to the sample's photoreal render. So
// no pretend hardware: a clean SCREEN LIFT - the live screen rises as itself
// on the black stage, glow underneath, settles, then the camera pushes in.
// Same rhythm as the sample's reveal, zero fake geometry to give it away.
const DeviceReveal: React.FC<{seg: number; frames: number}> = ({seg, frames}) => {
  const f = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const rise = spring({frame: f * 1.5, fps,
                       config: {damping: 24, stiffness: 70, mass: 0.9}});
  const ty = interpolate(rise, [0, 1], [height * 0.9, 0]);
  const alive = interpolate(rise, [0.45, 0.95], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const PUSH_AT = frames - 34;
  const push = interpolate(f, [PUSH_AT, frames], [1, 2.5], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.in(Easing.cubic)});
  const sw = width * 0.66, sh = sw * 9 / 16;
  return (
    <AbsoluteFill style={{background: BLACK, alignItems: 'center',
                          justifyContent: 'center'}}>
      <div style={{transform: `scale(${push})`, transformOrigin: '50% 46%'}}>
        <div style={{
          width: sw, height: sh, borderRadius: 14, overflow: 'hidden',
          background: '#07090c',
          transform: `translateY(${ty}px)`,
          boxShadow: `0 0 ${64 * alive}px rgba(56,189,248,${0.28 * alive}), ` +
                     `0 44px 110px rgba(0,0,0,.9)`,
        }}>
          <Video muted src={staticFile(`journey_seg${seg}.webm`)}
                 style={{width: '100%', height: '100%', objectFit: 'cover',
                         opacity: alive,
                         filter: `brightness(${0.5 + 0.5 * alive})`}} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── the phone interlude ─────────────────────────────────────────────────
// The sample's second device beat: a phone rises tilted on black, straightens
// with the same rim glint, screen alive - here with the REAL mobile UI
// (journey_segm0.webm, 390x844 live capture). No push-in: in the sample the
// push belongs to the laptop; the phone cuts on to the next title.
const PhoneReveal: React.FC<{frames: number}> = ({frames}) => {
  const f = useCurrentFrame();
  const {fps, height} = useVideoConfig();
  const rise = spring({frame: f, fps,
                       config: {damping: 16, stiffness: 52, mass: 1.2}});
  const ty = interpolate(rise, [0, 1], [height * 0.95, 0]);
  const rx = interpolate(rise, [0, 1], [38, 0]);
  const ry = interpolate(rise, [0, 1], [-24, 0]);
  const glow = interpolate(rise, [0.5, 1], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  // settled float: a slow bob so the hold never reads as a freeze-frame
  const bob = Math.sin(f / 14) * 4 * glow;
  const out = interpolate(f, [frames - 6, frames], [1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const ph = height * 0.84, pw = ph * 390 / 844;
  return (
    <AbsoluteFill style={{background: BLACK, alignItems: 'center',
                          justifyContent: 'center', perspective: 1300,
                          opacity: out}}>
      <div style={{
        width: pw + 16, height: ph + 16, borderRadius: 34,
        background: 'linear-gradient(160deg, #23262c, #0c0e12)',
        padding: 8,
        transform: `translateY(${ty + bob}px) rotateX(${rx}deg) rotateY(${ry}deg)`,
        boxShadow: `0 0 ${46 * glow}px rgba(56,189,248,${0.38 * glow}), ` +
                   `0 34px 90px rgba(0,0,0,.85)`,
      }}>
        <div style={{width: pw, height: ph, borderRadius: 27, overflow: 'hidden',
                     background: '#0a0c10'}}>
          <Video muted src={staticFile('journey_segm0.webm')}
                 style={{width: '100%', height: '100%', objectFit: 'cover',
                         opacity: interpolate(rise, [0.5, 0.85], [0, 1],
                           {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── product walkthrough on the pale backdrop ────────────────────────────
// The measured treatment: footage inset (2.8% side margins), rounded, soft
// shadow, slow settle — on PALE like the sample, not on the dark page navy.
const CaptionBar: React.FC<{seg: number}> = ({seg}) => {
  const f = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = f / fps;
  const list = CAPTIONS[seg] ?? [];
  const cur = list.find((c) => t >= c.t && t <= c.t + c.d);
  if (!cur) return null;
  const local = t - cur.t;
  // quick wipe in, hold, quick wipe out - never a slow fade competing with
  // the footage for attention
  const inK = Math.min(1, local / 0.22);
  const outK = Math.min(1, Math.max(0, (cur.t + cur.d - t) / 0.22));
  const k = Math.min(inK, outK);
  return (
    <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center',
                          paddingBottom: height * 0.075, pointerEvents: 'none'}}>
      <div style={{
        maxWidth: width * 0.74,
        padding: `${height * 0.022}px ${height * 0.042}px`,
        borderRadius: height * 0.012,
        background: 'rgba(12,20,32,0.93)',
        borderLeft: `${Math.round(height * 0.008)}px solid ${ORANGE}`,
        boxShadow: '0 12px 40px rgba(0,0,0,.42)',
        transform: `translateY(${(1 - k) * height * 0.05}px)`,
        opacity: k,
      }}>
        <div style={{fontFamily: FONT, fontWeight: 700,
                     fontSize: height * 0.05, lineHeight: 1.25,
                     color: '#FFFFFF', textAlign: 'center',
                     whiteSpace: 'pre-wrap'}}>{cur.text}</div>
      </div>
    </AbsoluteFill>
  );
};

const Section: React.FC<{seg: number; frames: number}> = ({seg, frames}) => {
  const f = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const sIn = spring({frame: f, fps, config: {damping: 16, stiffness: 80}});
  const out = interpolate(f, [frames - 5, frames], [1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  // THE CAMERA FOLLOWS THE ACTION (Ian: "the zoom in zoom out, the scrolling
  // and clicking"). Keys are GENERATED from the recorder's own click log
  // (gen_camera_keys.py): the view pushes toward each click as it happens and
  // relaxes to wide between - the sample's measured pattern (bbox tightening
  // 0.92 -> ~0.80 with the centroid moving to the action). Actionless
  // segments get a slow documentary drift so nothing ever sits still.
  const keys: CamKey[] = CAMERA_KEYS[seg] ?? [];
  const t = f / fps;
  let scale = 1.0, fx = 0.5, fy = 0.5;
  if (keys.length > 1) {
    let a = keys[0], b = keys[keys.length - 1];
    for (let i = 0; i < keys.length - 1; i++) {
      if (t >= keys[i].t && t <= keys[i + 1].t) { a = keys[i]; b = keys[i + 1]; break; }
      if (t > keys[keys.length - 1].t) { a = b = keys[keys.length - 1]; }
    }
    const span = Math.max(0.001, b.t - a.t);
    const k = Math.min(1, Math.max(0, (t - a.t) / span));
    const e = k * k * (3 - 2 * k);          // smoothstep between keyframes
    scale = a.s + (b.s - a.s) * e;
    fx = a.fx + (b.fx - a.fx) * e;
    fy = a.fy + (b.fy - a.fy) * e;
  } else {
    // MEASURED: the sample's camera is perfectly static on actionless beats -
    // the footage's own scrolling is the motion. The slow drift I had here
    // was invented, and invented motion is what reads as "weird".
    scale = 1.0; fx = 0.5; fy = 0.5;
  }

  return (
    <AbsoluteFill style={{background: PALE, alignItems: 'center',
                          justifyContent: 'center'}}>
      <div style={{
        width: width * 0.935, height: height * 0.94,
        borderRadius: 12, overflow: 'hidden',
        boxShadow: '0 18px 55px rgba(22,32,47,.28)',
        transform: `scale(${0.97 + 0.03 * sIn})`,
        opacity: Math.min(sIn * 1.6, 1) * out,
      }}>
        <Video muted src={staticFile(`journey_seg${seg}.webm`)}
               style={{width: '100%', height: '100%', objectFit: 'cover',
                       transform: `scale(${scale})`,
                       transformOrigin: `${fx * 100}% ${fy * 100}%`}} />
      </div>
      <CaptionBar seg={seg} />
    </AbsoluteFill>
  );
};

// The sample's transitions register as 0.5-0.8s MICRO-SCENES (7 of them,
// PySceneDetect) - fast directional smears between blocks. Mine had none.
const Whip: React.FC<{frames: number}> = ({frames}) => {
  const f = useCurrentFrame();
  const {height} = useVideoConfig();
  const k = f / Math.max(1, frames - 1);
  // three sub-phases, hard-edged: white pop (2f) -> dark smear sweep -> gone.
  const flash = f < 2 ? 1 : 0;
  const streak = Math.sin(Math.min(1, Math.max(0, (k - 0.08) / 0.84)) * Math.PI);
  return (
    <AbsoluteFill style={{background: flash ? '#FFFFFF' : CLOUD,
                          alignItems: 'center', justifyContent: 'center'}}>
      <div style={{
        width: '170%', height: '72%',
        background: `linear-gradient(90deg, transparent, rgba(15,25,35,${0.55 * streak}), transparent)`,
        filter: `blur(${18 * streak}px)`,
        transform: `translateX(${(k - 0.5) * height * 2.4}px) skewX(-14deg)`,
      }} />
    </AbsoluteFill>
  );
};

// LOWER-THIRD CAPTION. Ian: "there is not even a caption what are you doing."
// A product demo without narration is a stranger clicking things. Each caption
// is generated from the recorder's own action log, so it is true by
// construction and lands on the exact frame of the action it describes.
const End: React.FC = () => {
  const f = useCurrentFrame();
  const {fps, height} = useVideoConfig();
  const s = spring({frame: f, fps, config: {damping: 15, stiffness: 90}});
  return (
    <AbsoluteFill style={{background: CLOUD, alignItems: 'center',
                          justifyContent: 'center', gap: height * 0.05}}>
      <Img src={staticFile('workhive-logo-clean.png')}
           style={{height: height * 0.30, opacity: s,
                   transform: `scale(${0.9 + 0.1 * s})`}} />
      <div style={{fontFamily: FONT, fontWeight: 800, fontSize: height * 0.075,
                   color: INK, opacity: s}}>Built for the plant floor.</div>
      <div style={{fontFamily: FONT, fontWeight: 600, fontSize: height * 0.042,
                   color: CYAN, opacity: s}}>workhiveph.com · start free</div>
    </AbsoluteFill>
  );
};

// ── assembly ────────────────────────────────────────────────────────────

export const DemoReel: React.FC = () => {
  let at = 0;
  return (
    <AbsoluteFill style={{background: CLOUD}}>
      {DEMO_BEATS.map((b, i) => {
        const from = at;
        at += b.frames;
        return (
          <Sequence key={i} from={from} durationInFrames={b.frames}>
            {b.kind === 'word' && (
              <CameraMotionBlur samples={6} shutterAngle={200}>
                <Word text={b.text} accent={b.accent} frames={b.frames} />
              </CameraMotionBlur>)}
            {b.kind === 'logo' && <Logo frames={b.frames} />}
            {b.kind === 'device' && (
              <CameraMotionBlur samples={4} shutterAngle={180}>
                <DeviceReveal seg={b.seg} frames={b.frames} />
              </CameraMotionBlur>)}
            {b.kind === 'phone' && <PhoneReveal frames={b.frames} />}
            {b.kind === 'title' && (
              <CameraMotionBlur samples={6} shutterAngle={200}>
                <Title lines={b.lines} frames={b.frames} />
              </CameraMotionBlur>)}
            {b.kind === 'section' && (
              <CameraMotionBlur samples={3} shutterAngle={160}>
                <Section seg={b.seg} frames={b.frames} />
              </CameraMotionBlur>)}
            {b.kind === 'whip' && (
              <CameraMotionBlur samples={6} shutterAngle={240}>
                <Whip frames={b.frames} />
              </CameraMotionBlur>)}
            {b.kind === 'end' && <End />}
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

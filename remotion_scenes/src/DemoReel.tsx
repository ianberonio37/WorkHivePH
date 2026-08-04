import React from 'react';
import {
  AbsoluteFill, Video, Img, staticFile, useCurrentFrame,
  useVideoConfig, spring, interpolate, Sequence, Easing, random,
} from 'remotion';
import {ORANGE, FONT} from './Ambient';
import {CAPTIONS} from './demoCamera';
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
// THE MASCOT POSTER IS THE DESIGN BRIEF (Ian, 2026-08-04: "revolve your
// animation to that concept of my mascot image, it has more information").
//
// The poster is a dark INDUSTRIAL world - deep navy, hexagon motifs, amber and
// cyan accents, white display type - with the 3D bee as the guide and a named
// feature list down the left. That replaces the borrowed light-SaaS palette
// wholesale. It also fixes a fight the light world could never win: WorkHive's
// own UI is dark navy, so light cards made every screen recording look pasted
// on. Now the chrome and the product share one world.
const CLOUD = '#0D1928';          // the world (poster backdrop)
const PALE = '#101C2E';           // behind product footage
const INK = '#FFFFFF';            // display type is white here, not near-black
const INK_DIM = '#9FB2C9';
const CYAN = '#29B6F6';           // poster cyan
const AMBER = '#F5A623';          // poster amber
const BLACK = '#05090F';          // device-reveal stage

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
  // HOOK - the poster's own headline, delivered one line at a time.
  {kind: 'word', text: 'Track every machine.', frames: 34},
  {kind: 'word', text: 'Stop breakdowns', frames: 30},
  {kind: 'word', text: 'before they cost you.', accent: true, frames: 44},
  {kind: 'logo', frames: 56},
  {kind: 'device', seg: 0, frames: 170},

  // The poster names the product's parts; each becomes a chapter.
  {kind: 'whip', frames: 18},
  {kind: 'title', lines: ['Digital', 'Logbook'], frames: 104},
  {kind: 'section', seg: 0, frames: 540},
  {kind: 'section', seg: 1, frames: 450},
  {kind: 'section', seg: 2, frames: 660},
  {kind: 'section', seg: 3, frames: 240},

  {kind: 'whip', frames: 18},
  {kind: 'title', lines: ['Spare-parts', 'Inventory'], frames: 104},
  {kind: 'section', seg: 4, frames: 690},

  {kind: 'whip', frames: 18},
  {kind: 'title', lines: ['PM', 'Scheduler'], frames: 104},
  {kind: 'section', seg: 5, frames: 570},

  {kind: 'whip', frames: 18},
  {kind: 'title', lines: ['Your', 'Day Planner'], frames: 104},
  {kind: 'section', seg: 6, frames: 420},

  {kind: 'end', frames: 280},
];

export const DEMO_DURATION = DEMO_BEATS.reduce((a, b) => a + b.frames, 0);

// ── one layout unit for BOTH aspects ────────────────────────────────────
// Everything below sizes off `height`. In a 9:16 frame a raw height of 1920
// makes 0.17*height type 326px - absurd. So each component shadows `height`
// with U: the height of the largest 16:9 frame that fits the current width.
// The result is one set of beats that composes correctly in both aspects,
// rather than a second hand-tuned vertical edit that would drift.
const useU = () => {
  const {width, height} = useVideoConfig();
  return Math.min(height, width * 9 / 16);
};

// ── the poster's world ──────────────────────────────────────────────────

// The poster's hexagon field - drawn, not an image, so it stays crisp at any
// size and costs nothing to re-scale per beat.
const HexField: React.FC<{opacity?: number}> = ({opacity = 0.5}) => {
  const {width, height} = useVideoConfig();
  const r = height * 0.085;
  const dx = r * Math.sqrt(3);
  const cells: React.ReactNode[] = [];
  let key = 0;
  for (let row = -1; row * r * 1.5 < height + r; row++) {
    for (let col = -1; col * dx < width + dx; col++) {
      const cx = col * dx + (row % 2 ? dx / 2 : 0);
      const cy = row * r * 1.5;
      const pts = Array.from({length: 6}, (_, k) => {
        const ang = (Math.PI / 180) * (60 * k - 30);
        return `${cx + r * Math.cos(ang)},${cy + r * Math.sin(ang)}`;
      }).join(' ');
      cells.push(<polygon key={key++} points={pts} fill="none"
                          stroke="#1E3350" strokeWidth={1.4} />);
    }
  }
  return (
    <AbsoluteFill style={{opacity}}>
      <svg width={width} height={height} style={{display: 'block'}}>{cells}</svg>
    </AbsoluteFill>
  );
};

// IAN'S OWN 3D MASCOT, cut from his poster (tools/prep_mascot.py, GrabCut +
// soft bottom fade). He rejected the project's flat vector bee as ugly, so
// this is the real character and nothing stands in for it.
//
// Placement rule stands: card beats only, never over the product footage -
// the screenshots remain the hero and the bee is the guide beside them.
const Mascot: React.FC<{
  side?: 'left' | 'right'; heightFrac?: number; delay?: number;
}> = ({side = 'right', heightFrac = 0.7, delay = 0}) => {
  const f = useCurrentFrame();
  const {fps, height} = useVideoConfig();
  const s = spring({frame: f - delay, fps,
                    config: {damping: 15, stiffness: 82, mass: 0.9}});
  const bob = Math.sin((f - delay) / fps * 1.7) * height * 0.006;
  return (
    <div style={{
      position: 'absolute', bottom: -height * 0.02,
      [side]: `-${height * 0.03}px`,
      height: height * heightFrac,
      transform: `translateY(${(1 - s) * height * 0.3 + bob}px)`,
      opacity: s,
    }}>
      <Img src={staticFile('mascot-cut.png')}
           style={{height: '100%', width: 'auto', display: 'block',
                   transform: side === 'left' ? 'scaleX(-1)' : undefined,
                   filter: 'drop-shadow(0 18px 40px rgba(0,0,0,.55))'}} />
    </div>
  );
};

// ── kinetic type ────────────────────────────────────────────────────────

// Hook word on the light card: fast blur-in with a horizontal stretch — the
// sample's smeared-entry read (its "Filing" arrives as a motion trail).
const Word: React.FC<{text: string; accent?: boolean; frames: number}> = ({text, accent, frames}) => {
  const f = useCurrentFrame();
  const height = useU();
  // traced grammar kept: LOCKED, then a short blur ERUPTION out.
  const ERUPT = 6;
  const k = Math.max(0, f - (frames - ERUPT)) / ERUPT;
  const arriving = f < 2 ? (2 - f) / 2 : 0;
  const e = Math.pow(k, 1.6);
  return (
    <AbsoluteFill style={{background: CLOUD, alignItems: 'center', justifyContent: 'center'}}>
      <HexField opacity={0.55} />
      <div style={{
        fontFamily: FONT, fontWeight: 800,
        fontSize: height * (accent ? 0.2 : 0.17),
        color: accent ? AMBER : INK,
        letterSpacing: '-0.01em', textAlign: 'center', lineHeight: 1.05,
        maxWidth: '86%',
        transform: `scale(${1 + e * 0.34}) translateX(${e * height * 0.05}px)`,
        filter: `blur(${e * 26 + arriving * 8}px)`,
        opacity: 1 - e * 0.65,
      }}>{text}</div>
    </AbsoluteFill>
  );
};

const Logo: React.FC<{frames: number}> = ({frames}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const height = useU();
  const s = spring({frame: f, fps, config: {damping: 15, stiffness: 120}});
  const out = interpolate(f, [frames - 6, frames], [1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: CLOUD, alignItems: 'center', justifyContent: 'center'}}>
      <HexField opacity={0.6} />
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
// The poster's feature row, promoted to a full chapter card: an amber hex
// badge, the feature name in white display type, a cyan rule, and the mascot
// standing beside it. This is the poster's own layout language rather than a
// borrowed kinetic-type card.
const Title: React.FC<{lines: string[]; frames: number; side?: 'left' | 'right'}> =
({lines, frames, side = 'right'}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const height = useU();
  const s0 = spring({frame: f * 1.9, fps, config: {damping: 16, stiffness: 200, mass: 0.5}});
  const out = interpolate(f, [frames - 8, frames], [1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const hex = (sz: number) => {
    const pts = Array.from({length: 6}, (_, k) => {
      const a2 = (Math.PI / 180) * (60 * k - 30);
      return `${sz / 2 + (sz / 2) * Math.cos(a2)},${sz / 2 + (sz / 2) * Math.sin(a2)}`;
    }).join(' ');
    return (
      <svg width={sz} height={sz}><polygon points={pts} fill="none"
        stroke={AMBER} strokeWidth={sz * 0.055} /></svg>
    );
  };
  return (
    <AbsoluteFill style={{background: CLOUD}}>
      <HexField opacity={0.5} />
      <Mascot side={side} heightFrac={0.72} delay={4} />
      <AbsoluteFill style={{
        justifyContent: 'center',
        alignItems: side === 'right' ? 'flex-start' : 'flex-end',
        padding: `0 ${height * 0.09}px`, opacity: out,
      }}>
        <div style={{transform: `translateX(${(1 - s0) * (side === 'right' ? -1 : 1) * height * 0.12}px)`,
                     opacity: Math.min(1, s0 * 1.4),
                     textAlign: side === 'right' ? 'left' : 'right'}}>
          <div style={{marginBottom: height * 0.028,
                       display: 'flex',
                       justifyContent: side === 'right' ? 'flex-start' : 'flex-end'}}>
            {hex(height * 0.10)}
          </div>
          {lines.map((ln, li) => (
            <div key={li} style={{fontFamily: FONT, fontWeight: 800,
                                  fontSize: height * 0.105, color: INK,
                                  lineHeight: 1.08, letterSpacing: '-0.01em'}}>{ln}</div>
          ))}
          <div style={{marginTop: height * 0.03,
                       marginLeft: side === 'right' ? 0 : 'auto',
                       width: height * 0.22 * Math.min(1, s0 * 1.2),
                       height: Math.max(2, height * 0.006),
                       background: CYAN}} />
        </div>
      </AbsoluteFill>
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
  const {fps, width} = useVideoConfig();
  const height = useU();
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
  const {fps, width} = useVideoConfig();
  const height = useU();
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
  const {fps, width} = useVideoConfig();
  const height = useU();
  const sIn = spring({frame: f, fps, config: {damping: 16, stiffness: 80}});
  const out = interpolate(f, [frames - 5, frames], [1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  // NO CAMERA MOVE. AT ALL. (Ian, 2026-08-04: "just remove the zoom in and
  // zoom out because still like a brainless child.")
  //
  // Four attempts to make programmatic zoom look intentional all failed:
  // synthetic snaps (v10, "chaotic"), per-action snaps (v15, "brainless"),
  // intent-clustered snaps (v17, still brainless). The footage already
  // contains motion - the cursor moves, the page scrolls, panels open - and
  // adding a second, invented camera on top of real motion is what reads as
  // amateur. The frame is now LOCKED and the product does the moving.
  // CAMERA_KEYS is still generated (the captions ship from the same file);
  // it is simply not consumed. Deliberate, not dead code by accident.
  const scale = 1;
  const fx = 0.5;
  const fy = 0.5;

  return (
    <AbsoluteFill style={{background: PALE, alignItems: 'center',
                          justifyContent: 'center'}}>
      <HexField opacity={0.35} />
      <div style={{
        width: width * 0.94, height: width * 0.94 * 9 / 16,
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
  const height = useU();
  const k = f / Math.max(1, frames - 1);
  // three sub-phases, hard-edged: white pop (2f) -> dark smear sweep -> gone.
  const flash = f < 2 ? 1 : 0;
  const streak = Math.sin(Math.min(1, Math.max(0, (k - 0.08) / 0.84)) * Math.PI);
  return (
    <AbsoluteFill style={{background: flash ? '#16283E' : CLOUD,
                          alignItems: 'center', justifyContent: 'center'}}>
      <HexField opacity={0.5} />
      <div style={{
        width: '130%', height: '34%',
        background: `linear-gradient(90deg, transparent, rgba(41,182,246,${0.26 * streak}), transparent)`,
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
  const {fps} = useVideoConfig();
  const height = useU();
  const s0 = spring({frame: f, fps, config: {damping: 15, stiffness: 90}});
  return (
    <AbsoluteFill style={{background: CLOUD}}>
      <HexField opacity={0.6} />
      <Mascot side="right" heightFrac={0.8} delay={10} />
      <AbsoluteFill style={{justifyContent: 'center', alignItems: 'flex-start',
                            padding: `0 ${height * 0.1}px`}}>
        <div style={{opacity: s0, transform: `translateY(${(1 - s0) * height * 0.05}px)`}}>
          <Img src={staticFile('workhive-logo-clean.png')}
               style={{height: height * 0.19, display: 'block',
                       marginBottom: height * 0.05}} />
          <div style={{fontFamily: FONT, fontWeight: 800, fontSize: height * 0.082,
                       color: INK, lineHeight: 1.12}}>Track every machine.</div>
          <div style={{fontFamily: FONT, fontWeight: 800, fontSize: height * 0.082,
                       color: AMBER, lineHeight: 1.12}}>Stop breakdowns.</div>
          <div style={{marginTop: height * 0.045, fontFamily: FONT, fontWeight: 600,
                       fontSize: height * 0.04, color: CYAN}}>
            workhiveph.com · free in your browser
          </div>
        </div>
      </AbsoluteFill>
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
                <Title lines={b.lines} frames={b.frames}
                       side={i % 2 === 0 ? 'right' : 'left'} />
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

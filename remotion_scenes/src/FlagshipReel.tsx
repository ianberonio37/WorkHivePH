import React from 'react';
import {
  AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig, spring, interpolate,
} from 'remotion';
import {TransitionSeries, springTiming, linearTiming} from '@remotion/transitions';
import {slide} from '@remotion/transitions/slide';
import {fade} from '@remotion/transitions/fade';
import {NAVY, ORANGE, ORANGE_LT, FONT} from './Ambient';

// ── extra brand tokens (match promo-poster.html exactly) ──
const BLUE = '#29B6D9';
const BLUE_LT = '#5FCCE8';
const CLOUD = '#F4F6FA';
const STEEL = '#9FB0C3';
const RED = '#F87171';

// ── timeline (30fps) ──
const BEAT = {hook: 84, stakes: 72, reveal: 142, plan: 112, payoff: 80, end: 96};
const TR = 14; // every transition overlaps 14 frames
const beatVals = Object.values(BEAT);
export const FLAGSHIP_DURATION =
  beatVals.reduce((a, b) => a + b, 0) - (beatVals.length - 1) * TR;

// responsive layout — one source -> 9:16 / 1:1 / 16:9
const useLayout = () => {
  const {width, height} = useVideoConfig();
  const isLand = width > height * 1.05;
  const isSquare = !isLand && width > height * 0.95;
  return {width, height, isLand, isSquare, isPort: !isLand && !isSquare};
};

// ════════════════════════════════════════════════════════════
//  Data model — a video idea becomes ONE FlagshipSpec (props)
// ════════════════════════════════════════════════════════════
type ColorName = 'cloud' | 'orange' | 'blue' | 'steel';
const CMAP: Record<ColorName, string> = {cloud: CLOUD, orange: ORANGE, blue: BLUE_LT, steel: STEEL};

type Line = {text: string; size: number; weight?: number; color?: ColorName; accentWords?: string[]};
type ProductSpec = {
  caption: string; accent: string[]; screen: string;
  flagTitle: string; flagSub: string; flagColor: ColorName; flagSide: 'left' | 'right';
};
export type FlagshipSpec = {
  hook: Line[]; stakes: Line[]; reveal: ProductSpec; plan: ProductSpec; payoff: Line[];
  endTagline: string; endSub: string; endCta: string;
};

// The living style reference + fallback (idea: "access your memory"). On-brand per
// CONTENT_MESSAGING_RESEARCH: memory/build-your-own-AI/save-time positioning, a fresh
// curiosity hook (NOT 3AM), real screens, and ZERO invented tags (no TX-001). The
// Python driver overrides this per video idea.
export const DEFAULT_SPEC: FlagshipSpec = {
  hook: [
    {text: 'You already', size: 92},
    {text: 'solved this.', size: 150, weight: 900},
    {text: 'Can you remember how?', size: 72, color: 'orange', accentWords: ['remember']},
  ],
  stakes: [
    {text: 'Your best fixes', size: 84},
    {text: 'live in your head.', size: 84},
    {text: 'Until they walk out the door.', size: 60, color: 'steel', accentWords: ['walk', 'out']},
  ],
  reveal: {
    caption: 'Build your own AI.', accent: ['your', 'AI'], screen: 'wh_assistant_fresh.png',
    flagTitle: 'Your AI, your plant', flagSub: 'Learns your hive, not the web', flagColor: 'orange', flagSide: 'right',
  },
  plan: {
    caption: 'It remembers, so you don\'t.', accent: ['remembers'], screen: 'wh_logbook_clean.png',
    flagTitle: 'Every fix, kept', flagSub: 'Found again in one tap', flagColor: 'blue', flagSide: 'left',
  },
  payoff: [
    {text: 'Never lose a fix again.', size: 78},
    {text: 'An AI that\'s truly yours.', size: 78, color: 'orange'},
    {text: 'Hours back, every week.', size: 74, color: 'blue'},
  ],
  endTagline: 'Access your memory.',
  endSub: 'Free · mobile-first · for every Filipino worker',
  endCta: 'workhiveph.com · start free',
};

// ════════════════════════════════════════════════════════════
//  Shared continuous background — navy gradient + aurora + hex
// ════════════════════════════════════════════════════════════
const HEX = '50,3 95,29 95,87 50,113 5,87 5,29';

const Background: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const dx = Math.sin(t * 0.4) * 26;
  const dy = Math.cos(t * 0.33) * 22;
  return (
    <AbsoluteFill
      style={{
        background: 'linear-gradient(162deg,#13243a 0%,#162032 40%,#1b2a40 72%,#23344e 100%)',
        fontFamily: FONT,
      }}
    >
      <div style={{position: 'absolute', width: 760, height: 760, left: -200 + dx, top: -160 + dy,
        borderRadius: '50%', filter: 'blur(150px)',
        background: `radial-gradient(circle, ${ORANGE}66, transparent 62%)`, opacity: 0.55}} />
      <div style={{position: 'absolute', width: 900, height: 900, right: -300 - dx, bottom: -300 - dy,
        borderRadius: '50%', filter: 'blur(160px)',
        background: `radial-gradient(circle, ${BLUE}55, transparent 62%)`, opacity: 0.5}} />
      <AbsoluteFill style={{opacity: 0.05}}>
        <svg width="420" height="486" viewBox="0 0 100 116" fill="none" stroke={ORANGE} strokeWidth="2"
          style={{position: 'absolute', right: 30, top: 120}}><polygon points={HEX} /></svg>
        <svg width="260" height="300" viewBox="0 0 100 116" fill="none" stroke={BLUE} strokeWidth="2"
          style={{position: 'absolute', left: -40, bottom: 360}}><polygon points={HEX} /></svg>
      </AbsoluteFill>
      <AbsoluteFill style={{background: 'radial-gradient(circle at 50% 42%, transparent 50%, rgba(8,14,22,.45) 100%)'}} />
    </AbsoluteFill>
  );
};

// ════════════════════════════════════════════════════════════
//  Word-staggered kinetic line (mute-first caption)
// ════════════════════════════════════════════════════════════
const Words: React.FC<{
  text: string; accent?: string[]; delay?: number; size: number;
  weight?: number; color?: string; lh?: number; max?: number; align?: 'center' | 'flex-start';
}> = ({text, accent = [], delay = 0, size, weight = 800, color = CLOUD, lh = 1.04, max = 940, align = 'center'}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const words = text.split(' ');
  return (
    <div style={{display: 'flex', flexWrap: 'wrap', justifyContent: align, alignItems: 'baseline',
      gap: `${size * 0.12}px ${size * 0.28}px`, maxWidth: max, margin: align === 'center' ? '0 auto' : '0'}}>
      {words.map((w, i) => {
        const s = spring({frame: frame - delay - i * 4, fps, config: {damping: 14, stiffness: 130, mass: 0.7}});
        const isAcc = accent.includes(w.replace(/[.,!?]/g, ''));
        return (
          <span key={i} style={{
            display: 'inline-block', transform: `translateY(${(1 - s) * 46}px)`, opacity: s,
            fontFamily: FONT, fontWeight: weight, fontSize: size, lineHeight: lh,
            letterSpacing: '-0.02em', color: isAcc ? ORANGE : color,
            textShadow: '0 6px 30px rgba(0,0,0,.5)',
          }}>{w}</span>
        );
      })}
    </div>
  );
};

const Lines: React.FC<{lines: Line[]; gap: number; step: number; base?: number; align?: 'center' | 'flex-start'}>
  = ({lines, gap, step, base = 2, align = 'center'}) => (
  <div style={{display: 'flex', flexDirection: 'column', gap, alignItems: align === 'center' ? 'center' : 'flex-start'}}>
    {lines.map((l, i) => (
      <Words key={i} text={l.text} size={l.size} weight={l.weight} accent={l.accentWords}
        color={l.color ? CMAP[l.color] : CLOUD} delay={base + i * step} align={align} />
    ))}
  </div>
);

// ════════════════════════════════════════════════════════════
//  Phone mockup (poster frame) with spring-in + slow push
// ════════════════════════════════════════════════════════════
const Phone: React.FC<{src: string; width: number; localDur: number}> = ({src, width, localDur}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame, fps, config: {damping: 17, stiffness: 95, mass: 1}});
  const scale = interpolate(s, [0, 1], [0.84, 1]);
  const ty = interpolate(s, [0, 1], [150, 0]);
  const push = interpolate(frame, [0, localDur], [1, 1.1], {extrapolateRight: 'clamp'});
  const pad = width * 0.032;
  return (
    <div style={{
      width, transform: `translateY(${ty}px) scale(${scale * push})`,
      borderRadius: width * 0.13, background: '#0a0f18', padding: pad,
      boxShadow: '0 50px 90px rgba(0,0,0,.6), 0 0 0 2px rgba(255,255,255,.10)',
    }}>
      <div style={{position: 'relative', borderRadius: width * 0.1, overflow: 'hidden', background: '#0F1923'}}>
        <div style={{position: 'absolute', top: pad * 0.7, left: '50%', transform: 'translateX(-50%)',
          width: width * 0.3, height: width * 0.028, borderRadius: 99, background: 'rgba(0,0,0,.55)', zIndex: 2}} />
        <Img src={staticFile(src)} style={{width: '100%', display: 'block'}} />
        <div style={{position: 'absolute', inset: 0, borderRadius: width * 0.1,
          background: 'linear-gradient(125deg,rgba(255,255,255,.10) 0%,rgba(255,255,255,0) 30%)'}} />
      </div>
    </div>
  );
};

const Flag: React.FC<{title: string; sub: string; delay: number; color?: string; style: React.CSSProperties}>
  = ({title, sub, delay, color = ORANGE, style}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: frame - delay, fps, config: {damping: 13, stiffness: 140, mass: 0.6}});
  return (
    <div style={{position: 'absolute', ...style, opacity: s, transform: `scale(${interpolate(s, [0, 1], [0.6, 1])})`,
      display: 'flex', alignItems: 'center', gap: 12, padding: '14px 20px', borderRadius: 18,
      background: 'rgba(22,32,50,.94)', border: `1.5px solid ${color}`, boxShadow: '0 22px 46px rgba(0,0,0,.55)'}}>
      <span style={{width: 40, height: 40, borderRadius: 11, flex: 'none', display: 'flex', alignItems: 'center',
        justifyContent: 'center', background: `${color}28`, color, fontWeight: 900, fontSize: 22}}>!</span>
      <span>
        <div style={{fontFamily: FONT, fontSize: 14, fontWeight: 800, letterSpacing: 1, color, textTransform: 'uppercase'}}>{title}</div>
        <div style={{fontFamily: FONT, fontSize: 19, fontWeight: 700, color: CLOUD, marginTop: 2}}>{sub}</div>
      </span>
    </div>
  );
};

// ════════════════════════════════════════════════════════════
//  WorkHive AI Companion — the animated guide/mascot (on-brand, pure SVG,
//  no new deps). A glowing hive-cell face: blink + look + smile, an antenna
//  spark, a pulsing halo. Moods: greet | idle | think | happy.
//  Research (CONTENT_MESSAGING_RESEARCH §2): character-driven explainers lift
//  watch-time, retention, recall & brand identity. The worker is the HERO;
//  this companion is the GUIDE (StoryBrand). It supplements the loved product
//  screenshots — it never replaces them.
// ════════════════════════════════════════════════════════════
type Mood = 'greet' | 'idle' | 'think' | 'happy';

const Companion: React.FC<{
  size: number; delay?: number; mood?: Mood; look?: number; thinkUntil?: number;
}> = ({size, delay = 0, mood = 'idle', look = 0, thinkUntil = 0}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const local = frame - delay;
  const f = Math.max(0, local);
  const s = spring({frame: local, fps, config: {damping: 12, stiffness: 120, mass: 0.7}});
  const pop = interpolate(s, [0, 1], [0.35, 1]);
  const bob = Math.sin(f * 0.09) * size * 0.022;      // gentle idle float
  const tilt = Math.sin(f * 0.055) * 2.4;             // subtle wobble
  const blink = f % 82 < 4 ? 0.12 : 1;                // blink ~every 2.7s
  const glow = 0.55 + 0.45 * Math.sin(f * 0.13);
  const m: Mood = thinkUntil > 0 ? (local < thinkUntil ? 'think' : 'happy') : mood;
  const eyeDX = look * 4.5;                            // pupils track the product
  const isHappy = m === 'happy' || m === 'greet';
  const W = size, H = size * 1.4;
  const pupilR = blink > 0.5 ? 3.4 : 0.7;
  return (
    <div style={{position: 'relative', width: W, height: H, opacity: s,
      transform: `translateY(${bob}px) rotate(${tilt}deg) scale(${pop})`}}>
      {/* pulsing halo */}
      <div style={{position: 'absolute', left: '50%', top: '52%', width: W * 1.5, height: W * 1.5,
        transform: 'translate(-50%,-50%)', borderRadius: '50%', filter: `blur(${W * 0.09}px)`,
        background: `radial-gradient(circle, ${ORANGE}${isHappy ? '88' : '55'}, transparent 66%)`,
        opacity: 0.45 + 0.4 * glow}} />
      <svg width={W} height={H} viewBox="0 -20 100 140" style={{position: 'relative', overflow: 'visible'}}>
        <defs>
          <linearGradient id="whc-body" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#22344e" />
            <stop offset="1" stopColor="#111d2e" />
          </linearGradient>
          <radialGradient id="whc-cheek" cx="0.5" cy="0.5" r="0.5">
            <stop offset="0" stopColor={ORANGE} stopOpacity="0.55" />
            <stop offset="1" stopColor={ORANGE} stopOpacity="0" />
          </radialGradient>
        </defs>
        {/* antenna spark (the "AI") */}
        <line x1="50" y1="2" x2="50" y2="-11" stroke={ORANGE} strokeWidth="2.4" strokeLinecap="round" />
        <circle cx="50" cy="-14" r="8" fill="none" stroke={ORANGE} strokeWidth="1.4" opacity={0.25 + 0.5 * glow} />
        <circle cx="50" cy="-14" r="4.6" fill={ORANGE_LT} />
        {/* hive-cell body */}
        <polygon points="50,4 92,29 92,86 50,111 8,86 8,29" fill="url(#whc-body)"
          stroke={ORANGE} strokeWidth="2.6" strokeLinejoin="round" />
        <polygon points="50,12 85,32 85,83 50,103 15,83 15,32" fill="none"
          stroke={BLUE} strokeWidth="1.1" opacity="0.35" />
        {/* cheeks */}
        <circle cx="30" cy="66" r="9" fill="url(#whc-cheek)" opacity={isHappy ? 1 : 0.5} />
        <circle cx="70" cy="66" r="9" fill="url(#whc-cheek)" opacity={isHappy ? 1 : 0.5} />
        {/* eyes */}
        <ellipse cx="37" cy="52" rx="8" ry={9 * blink} fill={CLOUD} />
        <ellipse cx="63" cy="52" rx="8" ry={9 * blink} fill={CLOUD} />
        <circle cx={37 + eyeDX} cy="53" r={pupilR} fill="#0f1a29" />
        <circle cx={63 + eyeDX} cy="53" r={pupilR} fill="#0f1a29" />
        <circle cx={35.2 + eyeDX} cy="50.4" r="1.5" fill="#fff" opacity={blink > 0.5 ? 0.9 : 0} />
        <circle cx={61.2 + eyeDX} cy="50.4" r="1.5" fill="#fff" opacity={blink > 0.5 ? 0.9 : 0} />
        {/* mouth by mood */}
        {m === 'think' ? (
          <circle cx="50" cy="75" r="3.2" fill="none" stroke={CLOUD} strokeWidth="2.2" />
        ) : isHappy ? (
          <path d="M 39 71 Q 50 86 61 71 Q 50 77 39 71 Z" fill={ORANGE_LT} stroke={ORANGE}
            strokeWidth="1.4" strokeLinejoin="round" />
        ) : (
          <path d="M 41 72 Q 50 79 59 72" fill="none" stroke={CLOUD} strokeWidth="2.6" strokeLinecap="round" />
        )}
      </svg>
      {/* thinking dots */}
      {m === 'think' && (
        <div style={{position: 'absolute', left: '63%', top: 0, display: 'flex', gap: W * 0.035}}>
          {[0, 1, 2].map((i) => (
            <div key={i} style={{width: W * 0.055, height: W * 0.055, borderRadius: '50%', background: ORANGE_LT,
              opacity: 0.25 + 0.75 * (0.5 + 0.5 * Math.sin(f * 0.3 - i * 1.1))}} />
          ))}
        </div>
      )}
    </div>
  );
};

// ════════════════════════════════════════════════════════════
//  Beats
// ════════════════════════════════════════════════════════════
const center: React.CSSProperties = {alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '0 80px'};

const Hook: React.FC<{lines: Line[]}> = ({lines}) => {
  const {isLand, isSquare} = useLayout();
  const cSize = isLand ? 208 : isSquare ? 240 : 300;
  // Face on the first frame = a pattern-interrupt + face-close-up hook (§1),
  // and it introduces the mascot that closes the loop on the end card.
  return (
    <AbsoluteFill style={{...center, gap: isLand ? 4 : 20}}>
      <Companion size={cSize} mood="greet" delay={0} />
      <Lines lines={lines} gap={16} step={13} base={10} />
    </AbsoluteFill>
  );
};

const Stakes: React.FC<{lines: Line[]}> = ({lines}) => (
  <AbsoluteFill style={center}><Lines lines={lines} gap={22} step={12} /></AbsoluteFill>
);

const ProductBeat: React.FC<{data: ProductSpec; localDur: number; thinkUntil?: number}> = ({data, localDur, thinkUntil = 0}) => {
  const {isLand, isSquare} = useLayout();
  const phoneW = isLand ? 392 : isSquare ? 346 : 486;
  const flagTop = phoneW * (data.screen.includes('analytics') ? 0.6 : 0.5);
  const color = CMAP[data.flagColor];
  const flag = (
    <Flag title={data.flagTitle} sub={data.flagSub} delay={42} color={color}
      style={data.flagSide === 'left' ? {left: -36, top: flagTop} : {right: isLand ? -20 : -26, top: flagTop}} />
  );
  // AI companion sits on the side OPPOSITE the flag and looks at the screen —
  // the guide walking the worker through the product (never covering it).
  const compSide: 'left' | 'right' = data.flagSide === 'left' ? 'right' : 'left';
  const cSize = isLand ? 136 : isSquare ? 140 : 152;
  const compStyle: React.CSSProperties = compSide === 'left'
    ? {position: 'absolute', left: -cSize * 0.5, bottom: -cSize * 0.16, zIndex: 3}
    : {position: 'absolute', right: -cSize * 0.5, bottom: -cSize * 0.16, zIndex: 3};
  const companion = (
    <div style={compStyle}>
      <Companion size={cSize} delay={30} mood="happy" thinkUntil={thinkUntil}
        look={compSide === 'left' ? 1 : -1} />
    </div>
  );
  if (isLand) {
    return (
      <AbsoluteFill style={{flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 60, padding: '0 110px'}}>
        <div style={{flex: '0 0 760px', maxWidth: 760}}>
          <Words text={data.caption} accent={data.accent} size={78} delay={4} align="flex-start" max={760} />
        </div>
        <div style={{position: 'relative'}}>
          <Phone src={data.screen} width={phoneW} localDur={localDur} />
          {flag}
          {companion}
        </div>
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: isSquare ? 'center' : 'flex-start',
      padding: isSquare ? '0 60px' : '150px 60px 0'}}>
      <Words text={data.caption} accent={data.accent} size={isSquare ? 56 : 62} delay={4} />
      <div style={{position: 'relative', marginTop: isSquare ? 26 : 40}}>
        <Phone src={data.screen} width={phoneW} localDur={localDur} />
        {flag}
        {companion}
      </div>
    </AbsoluteFill>
  );
};

const Payoff: React.FC<{lines: Line[]}> = ({lines}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const {isPort} = useLayout();
  const hex = spring({frame: frame - 4, fps, config: {damping: 18, stiffness: 80}});
  return (
    <AbsoluteFill style={{...center, gap: isPort ? 22 : 12}}>
      <svg width={300} height={348} viewBox="0 0 100 116" fill="none" stroke={ORANGE} strokeWidth="2.4"
        style={{position: 'absolute', opacity: 0.12 * hex, transform: `scale(${interpolate(hex, [0, 1], [0.6, 1])})`}}>
        <polygon points={HEX} /></svg>
      <Companion size={isPort ? 148 : 124} mood="happy" delay={6} />
      <Lines lines={lines} gap={20} step={16} />
    </AbsoluteFill>
  );
};

const EndCard: React.FC<{tagline: string; sub: string; cta: string}> = ({tagline, sub, cta}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const {isLand} = useLayout();
  const logo = spring({frame, fps, config: {damping: 14, stiffness: 110, mass: 0.8}});
  const ctaS = spring({frame: frame - 26, fps, config: {damping: 15, stiffness: 130}});
  return (
    <AbsoluteFill style={center}>
      {/* mascot closes the loop it opened in the hook (loop-completion, §1/§9) */}
      <div style={{marginBottom: 4}}><Companion size={isLand ? 146 : 184} mood="happy" delay={2} /></div>
      <Img src={staticFile('workhive-logo-tight.png')}
        style={{width: 460, opacity: logo, transform: `scale(${interpolate(logo, [0, 1], [0.8, 1])})`,
          filter: 'drop-shadow(0 10px 30px rgba(247,162,27,.3))'}} />
      <div style={{marginTop: 26, fontFamily: FONT, fontSize: 40, fontWeight: 700, color: CLOUD}}>{tagline}</div>
      <div style={{marginTop: 8, fontFamily: FONT, fontSize: 24, fontWeight: 500, color: STEEL}}>{sub}</div>
      <div style={{marginTop: 40, opacity: ctaS, transform: `translateY(${interpolate(ctaS, [0, 1], [30, 0])}px)`,
        display: 'inline-flex', alignItems: 'center', gap: 12, padding: '22px 44px', borderRadius: 999,
        background: `linear-gradient(95deg, ${ORANGE}, ${ORANGE_LT})`, color: '#11192a',
        fontFamily: FONT, fontSize: 32, fontWeight: 800, boxShadow: '0 18px 40px rgba(247,162,27,.35)'}}>
        {cta}
      </div>
    </AbsoluteFill>
  );
};

// ════════════════════════════════════════════════════════════
//  Data-driven: pass a FlagshipSpec (partial) to override the default.
//  The Python render driver renders this composition per video idea.
// ════════════════════════════════════════════════════════════
export const FlagshipReel: React.FC<Partial<FlagshipSpec>> = (props) => {
  const spec: FlagshipSpec = {...DEFAULT_SPEC, ...props};
  const springT = springTiming({config: {damping: 200}, durationInFrames: TR});
  const fadeT = linearTiming({durationInFrames: TR});
  return (
    <AbsoluteFill style={{backgroundColor: NAVY}}>
      <Background />
      <TransitionSeries>
        <TransitionSeries.Sequence durationInFrames={BEAT.hook}><Hook lines={spec.hook} /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={fadeT} />
        <TransitionSeries.Sequence durationInFrames={BEAT.stakes}><Stakes lines={spec.stakes} /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={slide({direction: 'from-bottom'})} timing={springT} />
        <TransitionSeries.Sequence durationInFrames={BEAT.reveal}><ProductBeat data={spec.reveal} localDur={BEAT.reveal} thinkUntil={66} /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={slide({direction: 'from-right'})} timing={springT} />
        <TransitionSeries.Sequence durationInFrames={BEAT.plan}><ProductBeat data={spec.plan} localDur={BEAT.plan} /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={fadeT} />
        <TransitionSeries.Sequence durationInFrames={BEAT.payoff}><Payoff lines={spec.payoff} /></TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={fadeT} />
        <TransitionSeries.Sequence durationInFrames={BEAT.end}><EndCard tagline={spec.endTagline} sub={spec.endSub} cta={spec.endCta} /></TransitionSeries.Sequence>
      </TransitionSeries>
    </AbsoluteFill>
  );
};

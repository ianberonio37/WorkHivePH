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

// The hand-tuned flagship (idea: "the breakdown nobody caught") = the default + the
// living style reference. The Python driver overrides this per video idea.
export const DEFAULT_SPEC: FlagshipSpec = {
  hook: [
    {text: '3AM.', size: 150, weight: 900},
    {text: 'The line just stopped.', size: 78},
    {text: 'Again.', size: 88, weight: 900, color: 'orange'},
  ],
  stakes: [
    {text: 'No warning.', size: 84},
    {text: 'No history.', size: 84},
    {text: 'A whole shift, gone.', size: 70, color: 'steel', accentWords: ['gone']},
  ],
  reveal: {
    caption: 'WorkHive saw it coming.', accent: ['WorkHive'], screen: 'wh_home_clean.png',
    flagTitle: 'Critical Risk · Today', flagSub: 'TX-001 · 96% · MTBF 9d', flagColor: 'orange', flagSide: 'left',
  },
  plan: {
    caption: 'Fix it on your schedule.', accent: ['your', 'schedule'], screen: 'wh_analytics_clean.png',
    flagTitle: 'OEE · World Class', flagSub: '87% · ISO 22400', flagColor: 'blue', flagSide: 'right',
  },
  payoff: [
    {text: 'Less downtime.', size: 86},
    {text: 'Longer asset life.', size: 86, color: 'orange'},
    {text: 'Lower cost.', size: 86, color: 'blue'},
  ],
  endTagline: 'Built for the plant floor.',
  endSub: 'Free. Mobile-first. Philippines.',
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
//  Beats
// ════════════════════════════════════════════════════════════
const center: React.CSSProperties = {alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: '0 80px'};

const Hook: React.FC<{lines: Line[]}> = ({lines}) => {
  const frame = useCurrentFrame();
  const pulse = 0.5 + 0.5 * Math.sin(frame * 0.4);
  return (
    <AbsoluteFill style={center}>
      <div style={{position: 'absolute', top: '32%', width: 300, height: 300, borderRadius: '50%',
        border: `2px solid ${RED}`, opacity: 0.18 + 0.18 * pulse, transform: `scale(${1 + pulse * 0.25})`}} />
      <Lines lines={lines} gap={18} step={13} base={4} />
    </AbsoluteFill>
  );
};

const Stakes: React.FC<{lines: Line[]}> = ({lines}) => (
  <AbsoluteFill style={center}><Lines lines={lines} gap={22} step={12} /></AbsoluteFill>
);

const ProductBeat: React.FC<{data: ProductSpec; localDur: number}> = ({data, localDur}) => {
  const {isLand, isSquare} = useLayout();
  const phoneW = isLand ? 392 : isSquare ? 346 : 486;
  const flagTop = phoneW * (data.screen.includes('analytics') ? 0.6 : 0.5);
  const color = CMAP[data.flagColor];
  const flag = (
    <Flag title={data.flagTitle} sub={data.flagSub} delay={42} color={color}
      style={data.flagSide === 'left' ? {left: -36, top: flagTop} : {right: isLand ? -20 : -26, top: flagTop}} />
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
      </div>
    </AbsoluteFill>
  );
};

const Payoff: React.FC<{lines: Line[]}> = ({lines}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const hex = spring({frame: frame - 4, fps, config: {damping: 18, stiffness: 80}});
  return (
    <AbsoluteFill style={center}>
      <svg width={300} height={348} viewBox="0 0 100 116" fill="none" stroke={ORANGE} strokeWidth="2.4"
        style={{position: 'absolute', opacity: 0.12 * hex, transform: `scale(${interpolate(hex, [0, 1], [0.6, 1])})`}}>
        <polygon points={HEX} /></svg>
      <Lines lines={lines} gap={20} step={16} />
    </AbsoluteFill>
  );
};

const EndCard: React.FC<{tagline: string; sub: string; cta: string}> = ({tagline, sub, cta}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const logo = spring({frame, fps, config: {damping: 14, stiffness: 110, mass: 0.8}});
  const ctaS = spring({frame: frame - 26, fps, config: {damping: 15, stiffness: 130}});
  return (
    <AbsoluteFill style={center}>
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
        <TransitionSeries.Sequence durationInFrames={BEAT.reveal}><ProductBeat data={spec.reveal} localDur={BEAT.reveal} /></TransitionSeries.Sequence>
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

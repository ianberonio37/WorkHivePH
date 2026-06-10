import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {Ambient, ORANGE, ORANGE_DK, NAVY, NAVY_DEEP, FONT} from './Ambient';
import {KineticHeadline} from './KineticHeadline';

type Props = {
  headline: string;
  subhead: string;
  nodes: string[];
};

/**
 * WorkHiveMindmap — a hub-and-spoke node graph. The feature is the centre hub;
 * related concepts branch out with links that DRAW in, then everything floats
 * gently. Best for "how it connects" explainers. The graph fans right but stays
 * left of the UI PiP (x < 740).
 */
export const WorkHiveMindmap: React.FC<Props> = ({headline, subhead, nodes}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;

  // subhead IS the feature name now (the "WorkHive · " prefix was dropped —
  // the brand was appearing 4× per frame); keep the legacy split as fallback.
  const hub = (subhead.includes('·') ? subhead.split('·').pop()! : (subhead || headline)).trim().slice(0, 22);
  const list = (nodes && nodes.length ? nodes : ['Faster', 'Clearer', 'Safer']).slice(0, 5);

  const CX = 300, CY = 350, R = 200;   // fan stays above the caption-safe band
  const hubIn = spring({frame: frame - 2, fps, config: {damping: 14, mass: 0.6}});

  const positioned = list.map((label, i) => {
    const span = list.length > 1 ? 110 : 0;                 // total degrees fanned
    const a = (-span / 2 + (span / Math.max(1, list.length - 1)) * i) * Math.PI / 180;
    const fx = Math.sin(t * 0.8 + i) * 6;                    // gentle float
    const fy = Math.cos(t * 0.7 + i) * 6;
    return {
      label,
      x: CX + Math.cos(a) * R + fx,
      y: CY + Math.sin(a) * R + fy,
      start: 6 + i * 6,   // nodes appear fast — no dead first half-second on a beat cut
    };
  });

  return (
    <>
      <Ambient />
      {/* title top-left — word-by-word kinetic reveal (silent-first) */}
      <KineticHeadline text={headline} x={100} y={124} size={32} maxWidth={260} />

      <svg width="100%" height="100%" style={{position: 'absolute', inset: 0}}>
        {/* links draw in */}
        {positioned.map((n, i) => {
          const draw = interpolate(frame, [n.start, n.start + 16], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          const ex = CX + (n.x - CX) * draw;
          const ey = CY + (n.y - CY) * draw;
          return <line key={i} x1={CX} y1={CY} x2={ex} y2={ey} stroke={ORANGE} strokeWidth={2.5} strokeOpacity={0.55} />;
        })}
      </svg>

      {/* child nodes */}
      {positioned.map((n, i) => {
        const inP = spring({frame: frame - n.start - 14, fps, config: {damping: 14, mass: 0.6}});
        return (
          <div key={i} style={{
            position: 'absolute', left: n.x, top: n.y, transform: `translate(-50%,-50%) scale(${interpolate(inP, [0, 1], [0.6, 1])})`,
            opacity: inP, padding: '12px 18px', borderRadius: 14, fontFamily: FONT,
            background: `linear-gradient(160deg, ${NAVY} 0%, ${NAVY_DEEP} 100%)`,
            border: '1px solid #ffffff1f', color: '#e7eefb', fontWeight: 700, fontSize: 20,
            whiteSpace: 'nowrap', boxShadow: '0 10px 26px rgba(0,0,0,.4)',
          }}>{n.label}</div>
        );
      })}

      {/* centre hub */}
      <div style={{
        position: 'absolute', left: CX, top: CY, transform: `translate(-50%,-50%) scale(${interpolate(hubIn, [0, 1], [0.5, 1])})`,
        opacity: hubIn, padding: '18px 26px', borderRadius: 18, fontFamily: FONT,
        background: `linear-gradient(135deg, ${ORANGE} 0%, ${ORANGE_DK} 100%)`,
        color: NAVY_DEEP, fontWeight: 800, fontSize: 26, whiteSpace: 'nowrap',
        boxShadow: `0 0 0 6px ${ORANGE}22, 0 16px 40px rgba(0,0,0,.5)`,
      }}>{hub}</div>
    </>
  );
};

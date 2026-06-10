import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {Ambient, ORANGE, ORANGE_LT, NAVY_DEEP, FONT} from './Ambient';

/**
 * WorkHiveEndCard — the branded CTA close (the Direct in ABCD: never ship a
 * video without ONE clear action). Centered wordmark, a pulse-ring CTA pill
 * (the designer-skill cta-pulse pattern: motion on the periphery of the
 * button, never the label), and the audience line.
 */
export const WorkHiveEndCard: React.FC<{headline: string; subhead: string}> = ({headline, subhead}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const inP = spring({frame: frame - 4, fps, config: {damping: 15, mass: 0.6}});
  const ctaIn = spring({frame: frame - 16, fps, config: {damping: 13, mass: 0.6}});
  const pulse = ((frame / fps) * 1.1) % 1; // expanding-fading CTA ring

  return (
    <>
      <Ambient wordmark={false} />
      <div
        style={{
          position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', textAlign: 'center', fontFamily: FONT,
        }}
      >
        <div
          style={{
            fontWeight: 900, fontSize: 66, opacity: inP,
            transform: `translateY(${interpolate(inP, [0, 1], [28, 0])}px)`,
            textShadow: '0 6px 30px rgba(0,0,0,.5)',
          }}
        >
          <span style={{color: ORANGE}}>Work</span>
          <span style={{color: '#fff'}}>Hive</span>
        </div>
        <div style={{marginTop: 10, color: '#ffffffb0', fontWeight: 600, fontSize: 22, opacity: inP}}>
          {subhead}
        </div>

        <div
          style={{
            position: 'relative', marginTop: 38, opacity: ctaIn,
            transform: `scale(${interpolate(ctaIn, [0, 1], [0.82, 1])})`,
          }}
        >
          <div
            style={{
              position: 'absolute', inset: -8 - pulse * 16, borderRadius: 999,
              border: `2px solid rgba(247,162,27,${(0.55 * (1 - pulse)).toFixed(3)})`,
            }}
          />
          <div
            style={{
              padding: '16px 46px', borderRadius: 999, fontWeight: 800, fontSize: 30,
              color: NAVY_DEEP, background: `linear-gradient(135deg, ${ORANGE}, ${ORANGE_LT})`,
              boxShadow: '0 10px 40px rgba(247,162,27,.4)',
            }}
          >
            {headline || 'Free at workhiveph.com'}
          </div>
        </div>

        <div style={{marginTop: 26, color: '#ffffff70', fontSize: 17, fontWeight: 600, opacity: ctaIn}}>
          Free for every Filipino industrial worker · field to management
        </div>
      </div>
    </>
  );
};

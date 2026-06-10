import React from 'react';
import {Series} from 'remotion';
import {WorkHiveMotionBG} from './MotionBG';
import {WorkHiveKinetic} from './Kinetic';
import {WorkHiveInfographic} from './Infographic';
import {WorkHiveMindmap} from './Mindmap';

/**
 * One background beat: the style to play, how long, and the content for that
 * style. Produced by tools/storyboard.py (one entry per narration beat).
 */
export type Segment = {
  style: 'dashboard' | 'kinetic' | 'infographic' | 'mindmap';
  frames: number;
  headline: string;
  subhead: string;
  phrases?: string[];
  stats?: {value: string; label: string; dir?: 'up' | 'down' | 'flat'}[];
  nodes?: string[];
};

type Props = {segments: Segment[]};

const MIN_FRAMES = 30;

/** Render the right style component for a segment (frame resets per Sequence,
 *  so each style's intro animation replays — that's the visible variety). */
const StyleScene: React.FC<{seg: Segment}> = ({seg}) => {
  switch (seg.style) {
    case 'kinetic':
      return (
        <WorkHiveKinetic
          headline={seg.headline}
          subhead={seg.subhead}
          phrases={seg.phrases && seg.phrases.length ? seg.phrases : [seg.headline]}
        />
      );
    case 'infographic':
      return (
        <WorkHiveInfographic
          headline={seg.headline}
          subhead={seg.subhead}
          stats={seg.stats && seg.stats.length ? seg.stats : [{value: '100%', label: 'Free', dir: 'up'}]}
        />
      );
    case 'mindmap':
      return (
        <WorkHiveMindmap
          headline={seg.headline}
          subhead={seg.subhead}
          nodes={seg.nodes && seg.nodes.length ? seg.nodes : ['Logbook', 'PM', 'Inventory', 'Alerts']}
        />
      );
    case 'dashboard':
    default:
      return <WorkHiveMotionBG headline={seg.headline} subhead={seg.subhead} />;
  }
};

/**
 * WorkHiveStoryboard — sequences the per-beat styles back-to-back so the
 * background tracks the narration and never just loops one clip. Total length is
 * the sum of the segment frames (see calculateStoryboardMetadata), which the
 * pipeline sets to the narration's exact running time.
 */
export const WorkHiveStoryboard: React.FC<Props> = ({segments}) => {
  const segs = segments && segments.length
    ? segments
    : [{style: 'dashboard', frames: 600, headline: 'WorkHive', subhead: 'WorkHive'} as Segment];
  return (
    <Series>
      {segs.map((seg, i) => (
        <Series.Sequence key={i} durationInFrames={Math.max(MIN_FRAMES, Math.round(seg.frames))}>
          <StyleScene seg={seg} />
        </Series.Sequence>
      ))}
    </Series>
  );
};

/** Composition duration = sum of all segment frames. Lets one render match the
 *  narration length exactly, with whatever beat breakdown the storyboard chose. */
export const calculateStoryboardMetadata = ({props}: {props: Props}) => {
  const segs = props.segments || [];
  const total = segs.reduce((a, s) => a + Math.max(MIN_FRAMES, Math.round(s.frames || 0)), 0);
  return {durationInFrames: Math.max(MIN_FRAMES, total || 600)};
};

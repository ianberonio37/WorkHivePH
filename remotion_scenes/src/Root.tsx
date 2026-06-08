import React from 'react';
import {Composition} from 'remotion';
import {WorkHiveOEEScene} from './WorkHiveScene';

// 1280x720 matches what video_assembler.py normalises the scene clip to,
// so this renders straight into the existing scene_clip slot with no rescale.
export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="WorkHiveOEEScene"
      component={WorkHiveOEEScene}
      durationInFrames={360}
      fps={30}
      width={1280}
      height={720}
      defaultProps={{
        kpiLabel: 'OEE',
        kpiValue: 87,
        kpiUnit: '%',
        caption: 'See your whole plant. Live.',
        // A real maintenance trend — this is the part stock footage can never do.
        spark: [62, 65, 61, 70, 74, 72, 80, 78, 85, 83, 87],
      }}
    />
  );
};

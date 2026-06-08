import {Config} from '@remotion/cli/config';

// JPEG frames = faster render; quality is plenty for a motion background.
Config.setVideoImageFormat('jpeg');
Config.setOverwriteOutput(true);
Config.setConcurrency(null); // let Remotion pick based on CPU cores

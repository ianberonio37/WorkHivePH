---
name: external-react-native-performance-jank-60fps
type: reference
source: https://reactnative.dev/docs/performance
source_sha: dd67a6b6d893ece9
fetched_at: 2026-07-18T10:47:59Z
last_verified: 2026-07-18
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: react native performance jank 60fps
---

## reference · react native performance jank 60fps
* Aim for at least 60 frames per second to achieve a native look and feel.
* The JavaScript thread has a maximum of 16.67ms to generate a frame.
* Dropped frames occur when the JavaScript thread is unresponsive for a frame.
* Use `InteractionManager` or `LayoutAnimation` to handle work on the JavaScript thread during animations.
* Avoid using `console.log` statements in production code, as they can cause a bottleneck in the JavaScript thread.
* Remove `console.*` calls using the `babel-plugin-transform-remove-console` plugin.
* Implement `getItemLayout` to optimize `FlatList` rendering speed.
* Use third-party list libraries like `FlashList` or `Legend List` for better performance.
* Enable `renderToHardwareTextureAndroid` to improve UI thread FPS when moving views on Android.
* Use `shouldRasterizeIOS` to improve UI thread FPS when moving views on iOS.
* Avoid overusing `renderToHardwareTextureAndroid` and `shouldRasterizeIOS` to prevent high memory usage.
* Use `transform: [{scale}]` to animate image sizes instead of adjusting width and height.
* Wrap actions in `requestAnimationFrame` to improve responsiveness of `Touchable` views.
* Test performance in release builds, not development mode.
* Profile performance and memory usage when using optimization props.
* Avoid doing expensive work on the JavaScript thread during animations.
Sources: https://reactnative.dev/docs/performance

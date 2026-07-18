---
name: external-react-native-list-virtualization-long-lists
type: reference
source: https://reactnative.dev/docs/optimizing-flatlist-configuration
source_sha: c907fd8763061c72
fetched_at: 2026-07-18T10:48:06Z
last_verified: 2026-07-18
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: react native list virtualization long lists
---

## reference · react native list virtualization long lists

* **VirtualizedList:** The component behind `FlatList` (React Native's implementation of the [`Virtual List`](https://bvaughn.github.io/react-virtualized/#/components/List) concept.)
* **Memory consumption:** How much information about your list is being stored in memory, which could lead to an app crash.
* **Responsiveness:** Application ability to respond to interactions. Low responsiveness, for instance, is when you touch on a component and it waits a bit to respond, instead of responding immediately as expected.
* **Blank areas:** When `VirtualizedList` can't render your items fast enough, you may enter a part of your list with non-rendered components that appear as blank space.
* **Viewport:** The visible area of content that is rendered to pixels.
* **Window:** The area in which items should be mounted, which is generally much larger than the viewport.

### Optimizing FlatList Configuration

* `removeClippedSubviews`: If `true`, views that are outside of the viewport are automatically detached from the native view hierarchy.
	+ Pros: Reduces time spent on the main thread, reduces the risk of dropped frames.
	+ Cons: Can have bugs, especially if you are doing complex things with transforms and/or absolute positioning.
* `maxToRenderPerBatch`: Controls the amount of items rendered per batch.
	+ Pros: Setting a bigger number means less visual blank areas when scrolling.
	+ Cons: More items per batch means longer periods of JavaScript execution potentially blocking other event processing.
* `updateCellsBatchingPeriod`: Controls the delay in milliseconds between batch renders.
	+ Pros: Combining this prop with `maxToRenderPerBatch` gives you the power to, for example, render more items in a less frequent batch, or less items in a more frequent batch.
	+ Cons: Less frequent batches may cause blank areas, More frequent batches may cause responsiveness issues.
* `initialNumToRender`: The initial amount of items to render.
	+ Pros: Define precise number of items that would cover the screen for every device.
	+ Cons: Setting a low `initialNumToRender` may cause blank areas.
* `windowSize`: The number passed here is a measurement unit where 1 is equivalent to your viewport height.
	+ Pros: Bigger `windowSize` will result in less chance of seeing blank space while scrolling.
	+ Cons: For a bigger `windowSize`, you will have more memory consumption.

### Optimizing List Items

* Use basic components: The more complex your components are, the slower they will render.
* Use light components: The heavier your components are, the slower they render.
* Use `memo()`: Creates a memoized component that will be re-rendered only when the props passed to the component change.
* Use cached optimized images: You can use the community packages (such as [@d11/react-native-fast-image](https://github.com/ds-horizon/react-native-fast-image) from [Dream11](https://github.com/ds-horizon)) for more performant images.
* Use `getItemLayout`: If all your list item components have the same height (or width, for a horizontal list), providing the `getItemLayout` prop removes the need for your `FlatList` to manage async layout calculations.
* Use `keyExtractor` or `key`: You can set the `keyExtractor` to your `FlatList` component. This prop is used for caching and as the React `key` to track item re-ordering.
* Avoid anonymous function on `renderItem`: For functional components, move the `renderItem` function outside of the returned JSX. Also, ensure that it is wrapped in a `useCallback` hook to prevent it from being recreated each render.

Sources: https://reactnative.dev/docs/optimizing-flatlist-configuration

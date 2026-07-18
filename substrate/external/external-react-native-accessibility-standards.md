---
name: external-react-native-accessibility-standards
type: reference
source: https://reactnative.dev/docs/accessibility
source_sha: a545a4f158ad316d
fetched_at: 2026-07-18T10:47:54Z
last_verified: 2026-07-18
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: react native accessibility standards
---

## reference · react native accessibility standards
* Set `accessible` to `true` to indicate a view is discoverable by assistive technologies.
* Use `accessibilityLabel` to provide a custom string for screen readers to verbalize when an element is selected.
* Set `accessibilityLabelledBy` to reference another element's `nativeID` for complex forms.
* Provide `accessibilityHint` to offer additional context for the result of an action.
* Use `accessibilityLanguage` to specify the language for screen readers to use when reading an element's label, value, and hint.
* Set `accessibilityIgnoresInvertColors` to `true` to prevent inverting screen colors for a specific view.
* Use `accessibilityLiveRegion` to alert the end user of dynamic changes, with options `none`, `polite`, and `assertive`.
* Set `accessibilityRole` to communicate the purpose of a component to assistive technology users, with options including `adjustable`, `alert`, `button`, and more.
* Use `accessibilityShowsLargeContentViewer` and `accessibilityLargeContentTitle` to control the display of a large content viewer on iOS.
* Set `accessibilityState` to describe the current state of a component, with fields including `disabled`, `selected`, `checked`, `busy`, and `expanded`.
* Use `accessibilityValue` to represent the current value of a component, with fields including `min`, `max`, `now`, and `text`.
* Set `accessibilityViewIsModal` to `true` to indicate that VoiceOver should ignore elements within sibling views on iOS.
Sources: https://reactnative.dev/docs/accessibility

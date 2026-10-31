---
name: change_external-schema-org-softwareapplication-type-official-pro_2026-10-31
type: source-change
chunk: external-schema-org-softwareapplication-type-official-pro
topic: Schema.org SoftwareApplication type official properties offers applicationCategory
source: https://schema.org/SoftwareApplication
detected: 2026-10-31
age_days: 86
ttl_days: 30
---

# external-schema-org-softwareapplication-type-official-pro changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-schema-org-softwareapplication-type-official-pro (before)
+++ external-schema-org-softwareapplication-type-official-pro (after)
@@ -1,12 +1,26 @@
-## reference · SoftwareApplication
-* The `applicationCategory` property of a `SoftwareApplication` can be either `Text` or `URL`.
-* The `applicationSubCategory` property of a `SoftwareApplication` can be either `Text` or `URL`.
-* The `fileSize` property of a `SoftwareApplication` should include a unit (e.g. MB, KB) or KB will be assumed.
-* The `operatingSystem` property of a `SoftwareApplication` can be either `OperatingSystem` or `Text`.
-* The `softwareVersion` property of a `SoftwareApplication` is a `Text` value.
-* The `storageRequirements` property of a `SoftwareApplication` can be either `Text` or `URL`.
-* The `countriesNotSupported` and `countriesSupported` properties of a `SoftwareApplication` can include two-letter ISO 3166-1 alpha-2 country codes.
-* The `accessMode`, `accessModeSufficient`, `accessibilityAPI`, `accessibilityControl`, `accessibilityFeature`, and `accessibilityHazard` properties of a `CreativeWork` (including `SoftwareApplication`) should use values from the approved vocabulary.
-* The `author` property of a `CreativeWork` (including `SoftwareApplication`) can be either `Organization` or `Person`.
-* The `commentCount` property of a `CreativeWork` (including `SoftwareApplication`) is an `Integer` value.
-Sources: https://schema.org/SoftwareApplication
+## reference · SoftwareApplication type official properties offers applicationCategory
+
+- `applicationCategory` (Text or URL) – indicates the high‑level category of the software (e.g., “Game”, “Multimedia”).  
+- `applicationSubCategory` (Text or URL) – specifies a more granular subcategory (e.g., “Arcade Game”).  
+- `applicationSuite` (Text) – name of the suite the application belongs to (e.g., “Office” for Excel).  
+- `availableOnDevice` (Text) – required device or make/model to run the application; supersedes `device`.  
+- `countriesSupported` / `countriesNotSupported` (Text) – ISO 3166‑1 alpha‑2 codes or country names indicating where the app is available or blocked.  
+- `downloadUrl` (URL) – direct link to download the application binary.  
+- `featureList` (Text or URL) – list of features or modules the application provides.  
+- `fileSize` (Text) – size of the application package (e.g., “18MB”; if no unit, KB is assumed).  
+- `installUrl` (URL) – URL for installing the app if different from the main page.  
+- `memoryRequirements` (Text or URL) – minimum memory needed to run the app.  
+- `operatingSystem` (OperatingSystem or Text) – supported OSes (e.g., “Windows 7”, “OS X 10.6”, “Android 1.6”).  
+- `permissions` (Text) – required permissions (e.g., full internet access, Wi‑Fi only).  
+- `processorRequirements` (Text) – required CPU architecture (e.g., “IA64”).  
+- `releaseNotes` (Text or URL) – description of changes in the current version.  
+- `runtimePlatform` (RuntimePlatform or Text) – runtime or interpreter dependencies (e.g., “Java v1”, “Python 2.3”, “.NET Framework 3.0”).  
+- `screenshot` (ImageObject or URL) – link to a screenshot image.  
+- `softwareAddOn` (SoftwareApplication) – additional content or add‑ons for the application.  
+- `softwareHelp` (CreativeWork) – help documentation for the application.  
+- `softwareRequirements` (SoftwareApplication, Text, or URL) – external dependencies (e.g., DirectX, Java runtime).  
+- `softwareVersion` (Text) – version identifier of the software instance.  
+- `storageRequirements` (Text or URL) – free disk space required.  
+- `supportingData` (DataFeed) – data supporting the application.  
+
+**Sources:** https://schema.org/SoftwareApplication
```

## Decision (2026-10-31)

No lever moves. The schema.org SoftwareApplication property list (applicationCategory, offers, featureList...) is unchanged; the calculator pages' SoftwareApplication markup (STRATEGY_V2 line 127) uses properties it still defines.

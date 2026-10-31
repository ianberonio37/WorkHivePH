---
name: external-schema-org-softwareapplication-type-official-pro
type: reference
source: https://schema.org/SoftwareApplication
source_sha: c62b0a68ddd1d61e
fetched_at: 2026-10-30T17:03:54Z
last_verified: 2026-10-31
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: Schema.org SoftwareApplication type official properties offers applicationCategory
---

## reference · SoftwareApplication type official properties offers applicationCategory

- `applicationCategory` (Text or URL) – indicates the high‑level category of the software (e.g., “Game”, “Multimedia”).  
- `applicationSubCategory` (Text or URL) – specifies a more granular subcategory (e.g., “Arcade Game”).  
- `applicationSuite` (Text) – name of the suite the application belongs to (e.g., “Office” for Excel).  
- `availableOnDevice` (Text) – required device or make/model to run the application; supersedes `device`.  
- `countriesSupported` / `countriesNotSupported` (Text) – ISO 3166‑1 alpha‑2 codes or country names indicating where the app is available or blocked.  
- `downloadUrl` (URL) – direct link to download the application binary.  
- `featureList` (Text or URL) – list of features or modules the application provides.  
- `fileSize` (Text) – size of the application package (e.g., “18MB”; if no unit, KB is assumed).  
- `installUrl` (URL) – URL for installing the app if different from the main page.  
- `memoryRequirements` (Text or URL) – minimum memory needed to run the app.  
- `operatingSystem` (OperatingSystem or Text) – supported OSes (e.g., “Windows 7”, “OS X 10.6”, “Android 1.6”).  
- `permissions` (Text) – required permissions (e.g., full internet access, Wi‑Fi only).  
- `processorRequirements` (Text) – required CPU architecture (e.g., “IA64”).  
- `releaseNotes` (Text or URL) – description of changes in the current version.  
- `runtimePlatform` (RuntimePlatform or Text) – runtime or interpreter dependencies (e.g., “Java v1”, “Python 2.3”, “.NET Framework 3.0”).  
- `screenshot` (ImageObject or URL) – link to a screenshot image.  
- `softwareAddOn` (SoftwareApplication) – additional content or add‑ons for the application.  
- `softwareHelp` (CreativeWork) – help documentation for the application.  
- `softwareRequirements` (SoftwareApplication, Text, or URL) – external dependencies (e.g., DirectX, Java runtime).  
- `softwareVersion` (Text) – version identifier of the software instance.  
- `storageRequirements` (Text or URL) – free disk space required.  
- `supportingData` (DataFeed) – data supporting the application.  

**Sources:** https://schema.org/SoftwareApplication

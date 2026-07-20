---
name: page-resume
type: page
source: file:resume.html
source_sha: c8e2f68d7a4ba21e
last_verified: 2026-07-13
supersedes: null
---
## page · `resume.html` — Resume / CV Builder | WorkHive

Size: 135KB · 108 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (5): `resume_documents.delete`, `resume_documents.insert`, `resume_documents.update`, `resume_versions.delete`, `resume_versions.insert`
**RPC calls**: (none)
**Edge invokes**: `resume-extract`, `resume-polish`
**Truth views read**: `v_logbook_truth`, `v_skill_badges_truth`

**Functions**: _entryHasContent, _hasMetric, _norm, _normKw, _normLoose, _para, _parseYear, _present, _prettyKw, _resetAiPanels, _resumeYears, _run, _syncJdAddBtn, _wireBusy, _wordInCorpus, _xe, addSelectedJdSkills, basicsField, buildDocxBody, buildResumeCorpus, buildResumeFacts, buildResumeHTML, bullet, callResumeExtract, callResumePolish, cap, cleanResume, closePreview, closeResumeManager, closeReview, compressImage, deleteResume, downloadPDF, emptyResume, ensureWork0, entryExists, entryKey, exportDocx, exportJSON, extractDocx, extractItemsFromFile, extractJdKeywordsLocal, extractPdf, extractXlsx, fieldsToChecklist, fmtDate, focusables, handleFiles, idb, idbGet, idbPut, isEmptyResume, keywordPresent, listResumes, loadCloud, loadCloudById, loadScript, mergeDefaults, mkBasic, newItem …

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]

---
name: page-report-sender
type: page
source: file:report-sender.html
source_sha: cc3ba9cf06b2b2d7
last_verified: 2026-07-13
supersedes: null
---
## page · `report-sender.html` — Report Sender | WorkHive

Size: 120KB · 47 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (2): `report_contacts.delete`, `report_contacts.insert`
**RPC calls**: (none)
**Edge invokes**: `scheduled-agents`, `send-report-email`, `voice-report-intent`, `voice-transcribe`
**Truth views read**: `v_ai_reports_truth`

**Functions**: _fnErrorReason, _getGuide, _rsSummaryAfterContacts, applyRecipientHint, avatarColor, buildVoiceSummary, checkSilence, clearVoiceContext, closeSheet, confirmOutsiders, deleteContact, doSend, generateReport, initSpeech, initials, isValidEmail, loadBounces, loadContacts, loadHistory, openAddSheet, parseVoiceIntent, relativeTime, renderChips, renderContacts, renderHistory, renderProcList, renderReportSenderSummary, renderResults, reportColor, reportLabel, resendReport, resetPage, saveContact, sendReportEmail, setCard, setCardState, setEmailStatus, setMicState, showToast, startAutoReset, startListening, startMediaRecorder, stopListening, transcribeAndParse, updateCount, updateProcRow, updateSendBtn

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]

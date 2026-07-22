---
name: page-assistant
type: page
source: file:assistant.html
source_sha: f05aa45e063ff266
last_verified: 2026-07-13
supersedes: null
---
## page · `assistant.html` — AI Work Assistant: WorkHive

Size: 67KB · 22 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (1): `ai_reply_feedback.insert`
**RPC calls**: (none)
**Edge invokes**: `ai-gateway`, `semantic-search`
**Truth views read**: `v_inventory_items_truth`, `v_logbook_truth`, `v_pm_compliance_truth`, `v_skill_badges_truth`

**Functions**: _attachChatFeedback, _raceGatewayData, _recordChatFeedback, addAssistantBubble, addStarterChips, addTypingIndicator, addUserBubble, autoResize, buildSystemPrompt, clearChat, getSemanticContext, handleBack, handleInputKey, loadRecordsSummary, mkBtn, removeTypingIndicator, scrollToBottom, sendMessage, showScreen, showToast, startChat, switchAssistantTab

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]

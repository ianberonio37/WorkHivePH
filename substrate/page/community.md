---
name: page-community
type: page
source: file:community.html
source_sha: 042449a26dabf208
last_verified: 2026-07-13
supersedes: null
---
## page · `community.html` — Community: WorkHive

Size: 196KB · 80 top-level fns. (Retrieve THIS instead of reading the file.)

**DB writes** (6): `community_posts.insert`, `community_posts.update`, `community_reactions.delete`, `community_reactions.insert`, `community_replies.insert`, `hive_audit_log.insert`
**RPC calls**: `get_community_reputation`, `get_hive_trade_peers`, `notify_post_mentions`, `notify_reply_accepted`, `notify_reply_posted`, `report_community_post`, `set_community_best_answer`
**Edge invokes**: (none)
**Truth views read**: `v_community_posts_truth`, `v_marketplace_listings_truth`, `v_marketplace_sellers_truth`, `v_worker_truth`

**Functions**: _addGlobalPostFromRealtime, _appendMoreStubs, _commSyncUrl, _expandAllStubs, _fetchPage, _findPost, _hideMentionDropdown, _initObservers, _makeStub, _markCommunitySeen, _maybeOpenMentionDropdown, _mentionDropdownEl, _prependPostCard, _queueOfflinePost, _reEscape, _removePostCard, _renderMentionDropdown, _renderNextMilestone, _resetFeed, _setCommunityAiContext, _updateRenderedCard, cleanup, closeComposer, closePersonCard, closeReport, closeThread, communityRetryAll, copyThreadLink, deletePost, formatTimeAgo, listFocusable, loadGlobalFeed, loadHiveMembers, loadLeaderboard, loadModQueue, loadMoreGlobalPosts, loadMorePosts, loadPosts, loadProfileStats, loadReactions, loadRelatedListings, loadReplies, loadReplyCounts, loadReportReasons, loadTradePeers, markAnswer, onKeyDown, openComposer, openEditor, openPersonCard, openReport, openThread, parseMentions, renderContentWithMentions, renderFeed, renderGlobalPostCard, renderPersonCard, renderPostCard, renderPresence, renderProfileCard …

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]

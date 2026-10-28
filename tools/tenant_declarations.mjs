// tenant_declarations.mjs — the by-design exceptions, in ONE place because two provers now read them.
//
// ★WHY A MODULE AND NOT A SECOND COPY. prove_tenant_refusal asks "may a stranger read this hive's rows" and
// prove_lxp_au_identity_after_change asks "does a REVOKED member stop reading them". Both must make the same
// exceptions - a public feed is public to a stranger and to an ex-member alike - and a second hand-maintained
// copy is how the two silently disagree: the day someone narrows a policy in one list, the other keeps vouching
// for the old behaviour and two green gates agree on a stale fact
// ([[feedback_two_stale_lists_agreeing_is_not_a_check]], [[feedback_the_lesson_landed_in_the_small_applier_only]]).
// Each entry states the POLICY it mirrors and, where expressible, carries a SQL oracle so the claim is measured
// on every run rather than described once.

export const PUBLIC_BY_DESIGN = {
  community_posts: 'community_posts_read: (public = true AND flagged = false) - the public feed is a product surface',
  marketplace_listings: 'mkt_listings_read: status = published - a marketplace that hid its listings would have no buyers',
  marketplace_sellers: 'mkt_sellers_read: any signed-in user sees the seller directory; anon sees only sellers WITH a published listing',
  service_providers: 'service_providers_read: the provider directory is readable by any signed-in user',
  marketplace_orders: 'mkt_orders_read: buyer OR seller - an order spans two hives by nature, so its hive_id is not the reader test',
  marketplace_inquiries: 'mkt_inq_read: buyer OR seller - same shape as orders',
};

export const BLIND_BY_DESIGN = {
  agent_memory: 'per-user store: auth.uid() = auth_uid', agent_episodic_memory: 'per-user store',
  resume_documents: 'per-user store', ai_reply_feedback: 'per-user store',
  analytics_events: 'admin/grafana only', hive_audit_log: 'supervisor/admin only',
  integration_configs: 'supervisor/admin only', project_roles: 'project membership, not hive membership',
  embedding_outbox: 'service-role queue, no client policy', community_post_xp_awards: 'service-role ledger',
  community_reaction_xp_awards: 'service-role ledger', community_reply_xp_awards: 'service-role ledger',
  ai_cost_log: 'admin/grafana only', auth_session_events: 'admin/grafana only',
  // SL AU4 (20261014000004): each read follows the page that shows it - the hive's active supervisor or a platform
  // admin. A plain worker read a teammate's AI questions and device fingerprints through the API before it.
  gateway_audit_log: 'supervisor/admin only (plant-connections is supervisors-only)',
  agentic_rag_traces: 'supervisor/admin only (no auth_uid, so no own-rows clause)',
  worker_known_devices: 'no policy and no grant: only note_device() (SECURITY DEFINER) reads or writes it (20261013000001)',
  // Read from the policies rather than assumed: ai_rate_limits carries exactly two, an
  // `ai_rate_limits_locked [ALL roles=public] USING false` that refuses every client outright and an
  // `ai_rate_limits_grafana_read` for the dashboard reader. A counter that decides whether somebody
  // may make another call must not be readable OR writable by the person it limits, so a worker
  // seeing none of it is the control working. Undeclared, it failed this gate as a broken probe.
  ai_rate_limits: 'locked to every client (USING false); only grafana_reader and the service role read it',
  // ★DECLARED 2026-09-28. Read from the policies, not assumed. ai_user_rate_limits carries two:
  // ai_user_rate_limits_grafana_read (grafana_reader, USING true) and ai_user_rate_limits_own
  // (SELECT only since 20261008000006 - it was FOR ALL, so a person could zero their own count - USING
  // auth.uid() IS NOT NULL AND user_id = auth.uid()::text). So the per-user
  // read DOES work - this is a per-user store, the same shape as agent_memory above, and the
  // control reads BLIND for a reason worth writing down: the probe's notion of "own" is
  // hive-scoped, and this table is NOT hive-scoped in practice. Its `hive_id` is NULL on most
  // rows, and `user_id` is not always a uid at all - the live table holds `ip:172.18.0.10` and
  // `status` buckets beside real auth uids, because anonymous and health-check traffic still has
  // to be rate-limited. A member therefore sees none of the row the hive probe calls his, which
  // is the policy working (that row belongs to another identity), not a refusal to show him his.
  ai_user_rate_limits: 'per-user store (user_id = auth.uid()::text) + non-user ip:/status buckets; hive_id is incidental and mostly NULL, so a hive-scoped control reads BLIND',
  // ★DECLARED 2026-10-27, read from the policies: platform_feedback has no own-rows read at all - "feedback public reads
  // published" (is_public = true), "feedback admin reads all" (is_platform_admin()) and the grafana reader. A private
  // note goes to the operator and nobody else, its author included. The control read 'n/a' until the seed's probe
  // fixture put a private row in the member's hive; BLIND on that row is the policy working.
  platform_feedback: 'private until published: only is_public rows, a platform admin and grafana_reader read it - the author included, nobody reads a private note back',
  // ★DECLARED 2026-10-28, read from the policies: mkt_orders_read and mkt_inq_read are (buyer_auth_uid = auth.uid() OR
  // listing_is_mine(listing_id) OR is_marketplace_admin()) - a PARTY test, never a hive test. The default actor's hive
  // holds no order, so the control read n/a and the question went unasked; asked as a member of Manila, whose hive
  // holds one order and one inquiry between OTHER people, the control came back BLIND. A colleague's purchase is his
  // and the seller's, not the hive's: seeing none of it is the policy working. Their truth views inherit it (invoker).
  marketplace_orders: 'party-scoped (mkt_orders_read: buyer OR seller OR marketplace admin) - a hive member who is neither party reads none of the hive\'s orders',
  marketplace_inquiries: 'party-scoped (mkt_inq_read: buyer OR seller OR marketplace admin) - same shape as orders',
  v_marketplace_orders_truth: 'invoker view over marketplace_orders - inherits the party test',
  v_marketplace_inquiries_truth: 'invoker view over marketplace_inquiries - inherits the party test',
  // ★DECLARED 2026-09-28, AND THE DECLARATION IS ALSO A FINDING. wh_traces carries two policies:
  // wh_traces_grafana_slo_read (grafana_reader) and wh_traces_hive_read (SELECT, authenticated,
  // USING hive_id = (request.jwt.claims ->> 'hive_id')::uuid). That second one reads the hive from
  // a JWT CLAIM - and this platform never mints one. Measured: of the policies in `public`, 95 use
  // `hive_members` and exactly ONE uses a jwt hive_id claim, this one; there are zero
  // custom-access-token / custom-claims functions in the database to put it there. So the clause
  // evaluates NULL for every signed-in caller and the policy can never return a row. It fails
  // CLOSED, so this is not a leak - it is a capability that was written and never worked, and the
  // BLIND control is the honest reading of it. Widening it to the `hive_members` idiom the rest of
  // the platform uses would GRANT trace access that nobody has today, which is a product call
  // about what one member may see of another's activity - not a mechanical fix to make a gate
  // green, and not something to slip into a deploy. Recorded for Ian instead.
  wh_traces: 'service-role/grafana only in practice: its one authenticated policy keys off a request.jwt.claims hive_id that nothing mints, so it can never match (inert, fails closed)',
  // ★DECLARED 2026-09-09, AND ONLY BECAUSE THE TABLE FINALLY HAD A ROW. api_keys sat empty for the whole
  // program, so this gate had nothing to test and never asked the question; reseeding one CMMS connector
  // per hive populated it, the control came back BLIND, and the gate correctly refused to guess. Read from
  // the policies, not assumed: api_keys carries exactly ONE policy, api_keys_supervisor_all, whose USING
  // requires an active SUPERVISOR of that same hive. A plain worker seeing none of his own hive's keys is
  // therefore the control working, the same shape as integration_configs above. An empty table is not a
  // passing one - it is an unasked question, and this is what it answers when finally asked.
  api_keys: 'supervisor-only (api_keys_supervisor_all: auth.uid() is an active supervisor of this hive)',
  // ★DECLARED 2026-09-11, and the SAME SHAPE AS api_keys ABOVE, for the same reason: the table only
  // just became answerable. client_errors now holds 208 rows for Baguio, so the control came back BLIND
  // for a plain member and the gate refused to guess rather than call a refusal a pass.
  // Read from the policy, not assumed: client_errors carries exactly two, and the READ one -
  // client_errors_read, FOR SELECT TO authenticated - has USING (EXISTS ... hm.role = 'supervisor'),
  // so only a supervisor of that hive may read it. Its migration says so in its own words: "READ:
  // supervisors of the hive (triage is a supervisor job) ... A worker does not need to read the error
  // log." The INSERT side is deliberately wider (any active member, or hive_id IS NULL so a login or
  // onboarding surface can still report), which is why a worker can WRITE an error he cannot READ -
  // asymmetric by design, and not a leak in either direction.
  client_errors: 'supervisor-only read (client_errors_read: USING hm.role = \'supervisor\' for that hive); insert is member-wide by design',
};

export const PUBLIC_VIEWS_BY_DESIGN = {
  v_community_posts_truth: 'over community_posts (public feed): member+anon saw 8 of 50 foreign rows = exactly the public AND NOT flagged subset',
  v_community_reputation_truth: 'aggregate over community_posts/replies/xp: member saw 4 of 8 foreign participants - the authors reachable through the public-feed subset, which is the counterparty reputation the marketplace profile is for',
  v_marketplace_listings_truth: 'over marketplace_listings: member saw 7 of 9 foreign = exactly the `published` subset; anon saw 0',
  v_marketplace_listings_public: 'over marketplace_listings, runs as owner by design: 7 of 9 = the `published` subset, to anon too - a marketplace that hid its listings would have no buyers',
  v_marketplace_sellers_truth: 'over marketplace_sellers: any signed-in user sees the seller directory (6 of 6); anon saw 5 = only sellers with a published listing',
  v_marketplace_sellers_public: 'over marketplace_sellers, runs as owner by design: same 6/5 split as the truth view above',
  // added 2026-10-05 after the AU revocation sweep flagged it. Verified against the base policy rather than the
  // name: `mkt_inq_read` is `buyer_name IN auth_worker_names() OR seller_name IN auth_worker_names() OR
  // is_marketplace_admin()` - keyed on the PERSON, never on hive membership. So a counterparty keeps reading the
  // inquiry they are a party to even after their hive membership ends, which is the point: an inquiry spans two
  // hives, and cutting one side out of their own conversation is the absence-shaped failure, not a leak.
  v_marketplace_inquiries_truth: 'over marketplace_inquiries: mkt_inq_read admits the buyer OR the seller by name, not by hive - the party to a cross-hive conversation keeps it',
  v_service_provider_truth: 'over service_providers: the provider directory is readable by any signed-in user (1 of 1); anon saw 0',
};

export const SUBSET_ORACLES = {
  v_community_posts_truth: {
    sql: (hive) => `select count(*) from community_posts where hive_id = '${hive}' and public = true `
      + `and coalesce(flagged,false) = false and deleted_at is null`,
    says: 'only posts that are public AND NOT flagged AND NOT deleted',
  },
  v_marketplace_listings_truth: {
    sql: (hive) => `select count(*) from marketplace_listings where hive_id = '${hive}' and status = 'published'`,
    says: 'only listings whose status is published',
  },
  v_marketplace_listings_public: {
    sql: (hive) => `select count(*) from marketplace_listings where hive_id = '${hive}' and status = 'published'`,
    says: 'only listings whose status is published',
  },
};

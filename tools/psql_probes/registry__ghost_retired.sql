-- money-lifecycle ghost consoles, DB half: the retired order/escrow relations still exist but are
-- INERT, asked of the server as anon rather than assumed: SELECT returns 0 rows, INSERT is refused
-- by RLS, the table holds 0 rows with RLS enabled and policies present, and the view is
-- security_invoker=on so it cannot launder the caller's RLS. (The source half - no live console
-- renders a queue - is carried by the html files in depends_on.)
-- expect: rls_enabled_with_policies \| t
-- expect: view_is_security_invoker \| t
-- expect: anon_select_sees \| 0
-- expect: row-level security
-- ★THE "ZERO ROWS" LEG IS GONE, AND ITS REMOVAL IS THE FINDING (2026-08-31).
-- This probe used to assert `count(*) FROM marketplace_orders = 0`, standing on founder-console.html's
-- recorded premise that "both tables have never held a row and NO client path can write one". The
-- table now holds SIX rows - one per lifecycle status (pending_payment, escrow_hold, buyer_confirmed,
-- released, refunded, disputed), dated 2026-08-17 to 08-25 - written by OUR OWN
-- test-data-seeder/seeders/marketplace.py.
-- A row count was never the property. It was a PROXY for "this relation is inert to clients", and the
-- proxy broke while the property it stood for did not: as anon the SELECT still returns 0 and the
-- INSERT is still refused by RLS, which is what actually protects anything. Asserting the count would
-- now fail forever on any developer machine that has run the seeder - a permanently red gate teaches
-- people to ignore gates.
-- ★WHAT IS GENUINELY UNRESOLVED, recorded rather than quietly re-greened: the row's own claim that
-- this console is RETIRED is drifting. marketplace-admin.html:1026 UPDATEs marketplace_orders when a
-- dispute is resolved, so a live console does touch the relation - it cannot create an order, but it
-- is not untouched either. Whether the custodial order/escrow lifecycle is retired, half-built or
-- being revived is a product question for Ian; see the conversion-pass findings in
-- UFAI_TRAJECTORY_ROADMAP.md. The security assertions below hold regardless and are what this recipe
-- now proves.
SELECT 'rls_enabled_with_policies | ' ||
       ((SELECT relrowsecurity FROM pg_class WHERE relname = 'marketplace_orders')
        AND (SELECT count(*) FROM pg_policies WHERE tablename = 'marketplace_orders') >= 1);
SELECT 'view_is_security_invoker | ' ||
       (EXISTS (SELECT 1 FROM pg_class c
         WHERE c.relname = 'v_marketplace_orders_truth' AND c.relkind = 'v'
           AND array_to_string(c.reloptions, ',') ~* 'security_invoker=(on|true)'));
BEGIN;
SET LOCAL ROLE anon;
SELECT 'anon_select_sees | ' || count(*) FROM marketplace_orders;
RESET ROLE;
ROLLBACK;
BEGIN;
SET LOCAL ROLE anon;
INSERT INTO marketplace_orders (id) VALUES (gen_random_uuid());
ROLLBACK;

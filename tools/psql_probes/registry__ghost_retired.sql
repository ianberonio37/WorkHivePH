-- money-lifecycle ghost consoles, DB half: the retired order/escrow relations still exist but are
-- INERT, asked of the server as anon rather than assumed: SELECT returns 0 rows, INSERT is refused
-- by RLS, the table holds 0 rows with RLS enabled and policies present, and the view is
-- security_invoker=on so it cannot launder the caller's RLS. (The source half - no live console
-- renders a queue - is carried by the html files in depends_on.)
-- expect: table_holds_zero_rows \| t
-- expect: rls_enabled_with_policies \| t
-- expect: view_is_security_invoker \| t
-- expect: anon_select_sees \| 0
-- expect: row-level security
SELECT 'table_holds_zero_rows | ' || ((SELECT count(*) FROM marketplace_orders) = 0);
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

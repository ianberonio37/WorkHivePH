-- approver_stated: every change order names its requester, and every APPROVED one names its
-- approver — an approval nobody signed is not an approval.
-- expect: requester_missing \| 0
-- expect: approved_cos \| [1-9][0-9]*
-- expect: unsigned_approvals \| 0
SELECT 'requester_missing | ' || count(*) FROM project_change_orders WHERE requested_by IS NULL;
SELECT 'approved_cos | ' || count(*) FROM project_change_orders WHERE status = 'approved';
SELECT 'unsigned_approvals | ' || count(*) FROM project_change_orders
WHERE status = 'approved' AND (approved_by IS NULL OR approved_at IS NULL);

# Accounting Review Inbox decision permission

Review Inbox already defines `review_inbox.act` as the permission to accept or
reject items. The API used the unrelated `integrations.manage` or People &
Payroll `approvals.act` permission for those decisions. A user with either
permission alone could reach a financial acceptance path that can create a
journal, receivable, payable or cash transaction.

Accept and reject now require `review_inbox.act` on the server. Existing Owner
and Admin bypass semantics remain. The user interface checks the same effective
permission before showing decision controls and shows a clear read-only note.
Integration retry remains under its existing `integrations.manage` permission.
The financial-account picker allows a decision reviewer to see account metadata
without granting full Cash & Treasury access. Read-only Review Inbox still loads
when the separate account endpoint returns 403; it has no posting fields.

HTTP tests cover Payroll approvers, integration operators, Cashiers, Auditors,
Managers, Accounting Admins and Owners. Browser tests cover the read-only
desktop/mobile state and existing authorized acceptance flow. No pending
financial event is automatically accepted, rejected, retried or posted by this
change. The business decision on 22 current pending financial reviews remains
with authorized finance reviewers and original supporting documents.

If the permission changes while a drawer is open, a server 403 for that precise
permission refreshes the user session and removes posting controls. The failed
request remains visible; it is never reported as an accepted financial action.

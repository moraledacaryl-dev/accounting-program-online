# Read-only producer outbox parity audit

This offline command compares **explicitly exported, sanitized producer outbox
identities** with **Accounting Integration Review intake identities**. It does
not connect to live databases, use tokens, import financial statements, post a
journal, retry events, or update the Accounting application.

```bash
cd backend
python3 scripts/audit_source_outbox_parity.py --snapshot /path/to/sanitized-snapshot.json
```

The source export is a reviewer-controlled, **point-in-time** and **same time
window** snapshot. Export only the permitted, minimal ID/status/event-type
columns; never include employee data, guest names, amounts, bank details,
payload JSON, tokens or personally identifiable information. Run it locally
or in a protected environment. The output contains only aggregate counts
and truncated SHA-256 event fingerprints, not raw event IDs.

## Input contract

```json
{
  "schema_version": 1,
  "producers": {
    "inventory": {
      "complete_for_window": false,
      "events": [
        {"id": "example-inventory-uuid", "destination_system": "accounting",
         "status": "completed"}
      ]
    },
    "staff": {
      "complete_for_window": false,
      "events": [
        {"external_id": "payroll-example:Paid", "destination": "accounting",
         "event_type": "payroll.run.paid", "source_revision": 1,
         "status": "Completed"}
      ]
    },
    "pos": {
      "complete_for_window": false,
      "events": [
        {"event_type": "payment.collected", "status": "synced"}
      ]
    }
  },
  "accounting_review": [
    {"source_app": "inventory", "source_event_id": "example-inventory-uuid",
     "source_revision": 1},
    {"source_app": "staff", "source_event_id": "payroll-example:Paid",
     "source_revision": 1}
  ]
}
```

A source may be omitted if its data is not available. Set
`complete_for_window` to `true` **only** when the export has no pagination
cutoff, no excluded historical records, and all matching Accounting Review
rows are restricted to precisely that same window. Otherwise use `false`.
Use a frozen snapshot from both sides to avoid racing newly delivered events.
The tool does not infer or verify completeness on its own.

## Identity contracts confirmed from repository implementations

| Producer | Scoped outbox | Accounting review source identity | Sent/delivered marker |
| --- | --- | --- | --- |
| Inventory Procurement | `destination_system=accounting` | `source_app=inventory`, `source_event_id=IntegrationEvent.id`, revision 1 | `completed` means intake delivered, **not** posted journal |
| Staff / Payroll | `destination=accounting` and financial event types | `source_app=staff`, `source_event_id=external_id`, source revision supplied/default 1 | `Completed` means delivered, **not** payroll cash paid in Accounting |
| POS Cloud | Legacy sync outbox `synced` | **Not generally Integration Review**: distinct cashflow, transfer, POS sale, room-charge and reconciliation endpoints | `synced` alone does not prove journal linkage or bank settlement |

Staff `employee.sync` is intentionally excluded. It uses a separate
employee-identity endpoint, not the financial Review Inbox. POS must not be
compared by assuming its outbox row ID is an Accounting
`source_event_id`: this would fabricate missing or duplicate reviews.

The tool checks matching source IDs and revisions, duplicate identities,
source-completed records without retained Review Inbox receipt, uncompleted
source records already received, and Accounting-only identities **only when**
the producer export is declared complete.

## Interpreting outcomes

- `present_in_accounting` means the source identity matches an Accounting
  *review item*, **not** that the event was accepted or posted.
- `source_completed_without_accounting_receipt` indicates a review
  discrepancy requiring source/receiver investigation; it does not alone
  prove lost delivery or an accounting omission.
- `source_pending_without_receipt` describes the producer's backlog, not
  automatically a breach.
- `receipt_absent_from_complete_source_window` is only valid when
  `complete_for_window=true`. With partial snapshots this is **unknown**.
- `legacy_direct_pos_not_review_comparable` is **not** a healthy count.
  POS requires separate endpoint-specific comparison against transaction,
  transfer, receivable, sale and reconciliation external IDs.
- `fully_certified=false` and `live_connectivity_checked=false` always
  remain explicit, irrespective of whether zero findings are returned.

This is a preparatory source-to-Accounting parity tool, not a certified live
end-to-end producer-delivery audit. Before closing Group 3, obtain actual
source outbox snapshots or authenticated read-only APIs and independently
check source acknowledgements, Accounting record links, reversals, journals,
financial accounts and cash/bank/GCash settlement. Do not automatically
replay any event based only on this report.


## Restricted Accounting intake identity export

For an authorized read-only snapshot of Accounting's retained review identities,
run the following from an access-controlled Accounting host (with the usual
database configuration). It performs **SELECT statements only**, emits no
financial or payroll payloads, and creates a **new** 0600-permission local file.
It refuses to overwrite existing files or follow an existing symlink.

```bash
cd /opt/accounting-program-online/backend
python3 scripts/export_accounting_review_identities.py \
  --source inventory --source staff \
  --output /root/restricted-accounting-intake-identities.json
```

The file contains the `accounting_review` array expected by the parity
auditor plus export metadata. Combine the exported array with the sanitized
`producers` snapshot *locally* in a restricted working directory. Do not
publish raw IDs, payroll details, guest information, connection strings or
this export as a GitHub Actions artifact, and do not check it into Git.

This exporter does **not** poll Staff, Inventory or POS, nor can it prove
that upstream source outboxes were fully exported. The exporter scans the
selected Accounting sources without an arbitrary pagination cutoff, but
a changing live database is not a transactionally coordinated point-in-time
snapshot of the producer systems. For meaningful missing-event classification,
take producer and receiver snapshots from the same agreed window using
appropriate read-only transaction isolation, and set
`complete_for_window` to true only with verified full source coverage.


## Direct combination of the three protected exports (no manual JSON editing)

After authorized read-only local exports have been created by the source owners,
copy them only into a restricted directory on an authorized machine. Do not
upload the actual identity files to GitHub, Slack, workflow artifacts or chat.

```bash
cd backend
python3 scripts/audit_source_outbox_parity.py \
  --accounting /root/private/accounting-intake.json \
  --staff /root/private/staff-source.json \
  --inventory /root/private/inventory-source.json
```

Either `--staff` or `--inventory` may be omitted, but `--accounting`
is required. The command checks exact source exporter type, source identity,
unpaginated scan evidence and the minimal allowed row schema. It refuses
unexpected fields such as payroll details or source payloads. The report
shows aggregate counts and bounded, hashed event fingerprints only.

**This direct-combination method always retains
`complete_for_window=false`.** The Inventory PostgreSQL, Staff SQLite,
and Accounting PostgreSQL transactions were not captured by one atomic
cross-database snapshot. A missing record can be due to capture timing and
must remain an investigation lead, not an automatic lost-delivery assertion.
Proof of a common cutoff, retry finality, and posting evidence is separate.
To preserve compatibility, the original `--snapshot` command remains
available for manually prepared, separately certified snapshots.


## Live protected source-to-receiver aggregate probe

The optional `Accounting Live Source Parity (Read Only)` workflow executes
`scripts/dr/live-source-parity.py` **on the protected Accounting server**.
It uses established environment files for Accounting PostgreSQL, Inventory
PostgreSQL and Staff SQLite, and never transfers actual source event IDs,
private payloads, bank details or credentials to GitHub Actions. Only
integer event counts and fixed-scope caveats appear in its logs.

The script performs three **separate** read-only database scans and compares
the exact in-memory Inventory event UUIDs and Staff external IDs/revisions
with retained Accounting Review Inbox keys. It reports:
- each producer's financial event total, delivered/unacknowledged statuses,
  missing receipt candidates, already-received but unacknowledged events,
  duplicate source/receiver keys, and receiver IDs absent from source scans
- explicit `CROSS_DATABASE_ATOMIC_SNAPSHOT=NO`,
  `SOURCE_COMPLETED_MEANS_ACCOUNTING_ACCEPTED=NO`, and
  `BANK_SETTLEMENT_AND_JOURNAL_POSTING=NOT_TESTED`

Because the databases are read at different instants, an apparent missing or
extra source event requires a later same-cutoff/receipt audit before concluding
the transport dropped an event. The probe does not distinguish an old deleted
producer outbox row from a missing one without separately retained source
history. **Never replay or post an event automatically** based on its results.

It fails closed if either protected source database, configuration or data
contract cannot be read. A failure is `NOT_CERTIFIED`, not zero events.
The workflow starts on changes to its own audited script or workflow file;
its `workflow_dispatch` mode can repeat the read-only check, and it never
runs the separate restore-rehearsal or journal posting routines. All source
credential handling remains on the server. If production is not co-hosted
with the three source databases, this workflow correctly fails and requires
a separately authorized, protected multi-host audit.



## Inventory domain activity, separate from outbox delivery

A later version of the live read-only source-parity probe also prints the
Inventory PostgreSQL counts of purchase orders, approved purchase orders,
goods receipts, purchase returns, and posted stock documents. It reports
no supplier, item, stock, purchase or document IDs or amounts.

These counts explain whether an **empty Inventory Accounting outbox** was
observed alongside any current domain activity. A purchase order or posted
stock document does not automatically imply a financial event: some
operations are nonfinancial, some status changes are historical, and source
rules can differ by workflow/release. An apparent domain-to-outbox gap is
a **manual engineering investigation**, not grounds to generate a missing
payable, copy a journal, or backfill source events. The domain scan and
outbox scan also have separate database snapshots and are not atomic.


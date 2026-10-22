# Accounting Program — evidence-based goal tracker

**Snapshot:** 2026-10-22 (Philippines local date); this is a dated checkpoint, not a live dashboard.
**Source of truth:** production GitHub Actions + owner-controlled underlying receipts, folios, cash books, bank/GCash statements, GL and physical cash. Never infer a verified reconciliation from a green CI run.
**Parent:** [historical journal-linkage issue #249](https://github.com/moraledacaryl-dev/accounting-program-online/issues/249).

## Status vocabulary

- **Implemented:** code merged, with passing exact-SHA checks; production is separately verified.
- **Deployed:** exact release identified by successful server activation and backup logs.
- **Operationally verified:** a read-only production check establishes the stated invariant.
- **Reconciled:** original documentary evidence has been matched and independently reviewed; no aggregate/code-only test can grant this status.
- **Blocked by evidence:** source records, human signoff, or an isolated restore rehearsal remain necessary.

## Original six audit groups

| Goal | Software progress | Financial/operational closure |
|---|---|---|
| 1. Report classification (PR #241) | Implemented and covered by a subsequent deployed release | Validate actual chart-of-accounts mapping, COGS and income classifications for real periods |
| 2. Settlement integrity (PR #242) | Implemented and covered by a subsequent deployed release | Reconcile underlying settlement receipts, AR/AP aging and cash/bank effects independently |
| 3. Beds24 synchronization/cancellation (PR #243) | Implemented and deployed; historical cancellation repairs and read-only audit present | Review latest distinct booking-status mismatches against current Beds24, before any status-only change |
| 4. Reports accessibility/UX (PR #244) | Implemented, tested and deployed | Continue user acceptance, realistic data/role/mobile checking |
| 5. Monetary precision, report architecture and guarded deployment (PRs #245–247) | Implemented; immutable preparation, PostgreSQL readiness, mandatory verified backup and atomic rollback-capable activation exercised | Run separately isolated restore rehearsal and verify retention/restore evidence |
| 6. Financial integrity and reconciliation (issue #249, PRs #250–266) | Secure private worklist, journal review history, source profiling, exports, accurate progress and audit certification implemented | **Not reconciled.** 166 historical receipts still require original evidence and decision per transaction |

The first five implementation groups should not be scored as five-sixths of *financial reconciliation*. Their financial/operational acceptance items remain separate.

## Verified late-October 22 integration control progress (newer than checkpoints below)

- **Accounting production:** [Certified release #39766260636](https://github.com/moraledacaryl-dev/accounting-program-online/actions/runs/39766260636) activated exact `50c23f15f1164fc20465650dacaf1744244b9ed2` with **35,598,680,064 bytes** free at preflight, immutable prepare/verify PASS, mandatory database/uploads backup PASS, PostgreSQL Alembic `0017_journal_linkage_review`, and atomic activation PASS. Previous `86d4fdb1…` was retained for rollback. This supersedes older production SHAs listed below.
- **Delivery evidence:** [PR #310](https://github.com/moraledacaryl-dev/accounting-program-online/pull/310) provides source-intake observations, not proof of sender uptime or missing upstream outbox events. [PR #311](https://github.com/moraledacaryl-dev/accounting-program-online/pull/311) surfaces aged reviews without claiming missing timestamps are recent.
- **Accepted financial records:** [PR #317](https://github.com/moraledacaryl-dev/accounting-program-online/pull/317) checks local accepted target existence and statuses; [PR #323](https://github.com/moraledacaryl-dev/accounting-program-online/pull/323) extends proof to POS cash **and** matching posted balanced journal, and Staff exact-net payroll cash, matched payable, and separate recorded rounding expenses. The control is read-only; secondary record checks are not independent bank reconciliation.
- **Upstream parity:** [PR #324](https://github.com/moraledacaryl-dev/accounting-program-online/pull/324) adds an **offline** identity-only comparison for sanitized Inventory and Staff producer outboxes versus Accounting retained Review Inbox identities. POS legacy direct transaction/transfer/sale/room-charge endpoints are **not** comparable to generic Review Inbox IDs. No live producer snapshot has yet been certified; unobserved or paginated source events are **unknown**, not zero.
- **Receipts exporter:** [PR #328](https://github.com/moraledacaryl-dev/accounting-program-online/pull/328) passed CI; it provides a restricted, read-only local Accounting identity export for eventual source parity analysis. It must not be described as executed on live Accounting until an authorized private run is documented.
- **Remaining critical closure:** [issue #249](https://github.com/moraledacaryl-dev/accounting-program-online/issues/249) remains **open**. Last protected count was 166 posted Money In records lacking direct journal foreign keys (not necessarily absent journals). No documentary matching, independent financial-review certification, cash/bank/GCash tie-out or isolated restore rehearsal has been established by these software release logs. Inventory/Staff producer acknowledgements and POS direct-sync transactions require real read-only source-system checks.

## Latest verified production and safety evidence

- [Accounting deployment #39601553031](https://github.com/moraledacaryl-dev/accounting-program-online/actions/runs/39601553031) activated exact release `6b0fce5497a0da16ae331ae90cb0363ed4edb506`, Alembic `0017_journal_linkage_review`, with validated backup and atomic activation.
- [One-time Accounting journal-proof release #39603853909](https://github.com/moraledacaryl-dev/accounting-program-online/actions/runs/39603853909) subsequently activated `dc3ab7c82009d8c792c14dc20fcd37ebd7f64927` after successful exact-SHA CI; backup `/var/backups/hiddenoasis/accounting/accounting-20261021T125830Z.dump`; previous release preserved. The Inventory event journal-proof endpoint is read-only and must not be mistaken for a completed inventory-accounting reconciliation.
- [Verified Accounting batch-release #39610427751](https://github.com/moraledacaryl-dev/accounting-program-online/actions/runs/39610427751) **superseded the earlier journal-proof release**: atomic production activation of `c5faae3836f18cec0d30c11ba571ef14e82404ea`, mandatory validated backup `/var/backups/hiddenoasis/accounting/accounting-20261021T134359Z.dump`, Alembic `0017_journal_linkage_review`, with previous `dc3ab7c8` release retained. The owner/admin UI now exports the exact displayed page (up to 25) or the entire private filtered worklist, including original linkage and reversal fields. Temporary one-time release trigger was removed in [PR #273](https://github.com/moraledacaryl-dev/accounting-program-online/pull/273). This does **not** imply any human-reviewed/reconciled money transactions.
- [Read-only Inventory–Accounting audit #39609277177](https://github.com/moraledacaryl-dev/accounting-program-online/actions/runs/39609277177) reported zero Inventory outbox events and zero Accounting Inventory integration-review records; the new journal-proof API cannot yet be considered validated on real Inventory event traffic.
- [Read-only Journal Review production smoke #39602647657](https://github.com/moraledacaryl-dev/accounting-program-online/actions/runs/39602647657) verified 166 missing direct journal links, **zero** transaction-level reviews, zero orphan history records, and HTTP 401 for unauthenticated Journal Review and private CSV export. These are counts at the time of the smoke, not an assertion that no later review could exist.
- [Group 6 original baseline #39458680436](https://github.com/moraledacaryl-dev/accounting-program-online/actions/runs/39458680436): 1,131 posted journals; zero unbalanced/invalid journals; 1,044 money transactions; 166 posted money-in transactions with null journal foreign keys. A null foreign key does **not** prove an absent journal, missing revenue or missing cash.
- The read-only 166-row worklist and the owner/admin-only Reports → Journal Review CSV are private data. They must not be committed, pasted into CI logs or uploaded as public artifacts.

## October 22 delivery and operational checkpoint

- **Latest independently verified Accounting production activation:** [#39732430480](https://github.com/moraledacaryl-dev/accounting-program-online/actions/runs/39732430480) activated exact `ecceb0cbce9c3fb30c6fe53150bf7ac55cfba2c8` on October 22, with immutable release preparation/verification, mandatory PostgreSQL/uploads backup, Alembic `0017_journal_linkage_review`, and atomic activation all **PASS**. Previous `7c5e89f2` release retained. This is a software release, **not a financial reconciliation sign-off**.
- **Read-only Reconciliation Control Center:** [PR #292](https://github.com/moraledacaryl-dev/accounting-program-online/pull/292) plus [PR #294](https://github.com/moraledacaryl-dev/accounting-program-online/pull/294) combined owner-only journal exception review, cash account checks, authorized integration intake and financial close checks. Permission restrictions and source outages must not appear as zero exceptions.
- **Integration review operations:** [PR #293](https://github.com/moraledacaryl-dev/accounting-program-online/pull/293) improved filtered review UX, [PR #304](https://github.com/moraledacaryl-dev/accounting-program-online/pull/304) added secure paginated listing of *all* filtered review events (25 per page), exact totals and Staff payroll Approved/Paid revision visibility filtering before pagination. [CI #39731742141](https://github.com/moraledacaryl-dev/accounting-program-online/actions/runs/39731742141) PASS: 542 backend tests, 17 PostgreSQL tests, 167 browser tests; [visual audit #39731742161](https://github.com/moraledacaryl-dev/accounting-program-online/actions/runs/39731742161) PASS. No automatic journal posting or bank-statement import was added.
- **Deployment trigger retired:** [PR #305](https://github.com/moraledacaryl-dev/accounting-program-online/pull/305) removed the older temporary `workflow_run` automatic release workflow after successful production activation. Permanent manual `deploy-accounting.yml` remains.
- **Disk capacity warning:** release preflight had only **5,171,851,264 available bytes** before preparation/backup against the 4 GiB minimum. Safely evaluate disk, immutable releases, and backup retention *before* a future production deployment. Never delete production backups or an active/rollback release casually.
- **Latest Beds24 evidence:** [read-only historical audit #39722678257](https://github.com/moraledacaryl-dev/accounting-program-online/actions/runs/39722678257) covered 1,543 linked IDs and still reported 12 `OTHER_STATUS_MISMATCH` findings requiring source review (11 Accounting cancelled / Beds24 confirmed; one Accounting checked-out / Beds24 confirmed). The [two-booking repair #39724198485](https://github.com/moraledacaryl-dev/accounting-program-online/actions/runs/39724198485) reported those previous verified repairs already complete and made no new API request.
- **Unchanged critical limitation:** 166 historical money-in transactions without direct journal FK was the most recent owner-authenticated journal-linkage baseline; it is **not** a new October 22 live count and is not equivalent to 166 absent journal postings. A fresh protected audit and original source evidence are required before updating the classification count.

## Financial reconciliation backlog and acceptance gates

| Priority | Work | Known starting point | Evidence needed for closure |
|---|---|---|---|
| P0 | Classify 166 missing journal links | 166 awaiting first review at last production smoke | For **each ID**: source invoice/receipt, folio/booking/cash-book line, receiving account, posting rule at original transaction time, existing GL/journal comparison and recorded reviewed decision |
| P0 | Verify cash drawer, bank and GCash against books | No full physical cash/bank signoff documented | Opening balances, daily cash counts, bank/GCash statements, deposit slips, cashbook tie-outs, explained differences and independent reviewer |
| P0 | Validate AR/AP and financial statements | Baseline dedicated receivable/payable tables empty; operational records may hold AR/AP | Reconcile folio/Record aging, payable/invoice obligations, settlements, Trial Balance, Balance Sheet and Profit & Loss by period |
| P1 | Beds24 historical consistency | [Historical status audit #39599644324](https://github.com/moraledacaryl-dev/accounting-program-online/actions/runs/39599644324) processed 1,543 linked IDs and reported **12 other-status mismatches** | Re-fetch exact IDs from live Beds24, verify date/identity/status semantics, approve safe status-only corrections as needed; do not rewrite folio/cash history |
| P1 | Staff manual advance repayments | Read-only cross-app worklist documents five historical manual repayments with missing Staff outbox; related candidate matches are not proof of receipt | Staff ledger, payment evidence, correct receiving account, Accounting event identity, duplicate/reversal protection and human signoff |
| P1 | Inventory journal proof | Authoritative read-only event-to-posted-journal verification added via PR #265 | Cross-app acceptance against real Inventory event delivery, reference-only cases, payable treatment, cancellation/reversal scenarios; no guessed postings |
| P1 | Restore rehearsal | Backups and immutable deployments verified | Isolated, timed restore to a nonproduction DB with integrity comparison, documented rollback and authorized signoff |

**Safety invariants:** no heuristic-only journalization; no synthetic balancing entries; no mass backdated adjustments; no private transaction details in GitHub logs; no double matching one cash movement to multiple receipts without independent proof; no production write as part of a certification.

## Per-transaction review procedure (private worklist)

1. Preserve the unmodified export and a checksum. Record reviewer, date, evidence references and case outcome separately.
2. Match exact external-source identity **and** documentary receipt/folio/cash-book evidence; only use nearby date/amount matches as leads.
3. Check existing posted journal and account legs, reversals and prior classifications before proposing *any* posting.
4. Classify as legitimate historical cashflow-only, existing-journal candidate, new posting needing independent approval, or unresolved evidence gap. A saved review is **not** a journal link or reconciliation.
5. Keep the total open count independent of reviewed count; close an exception only after its approved accounting disposition and period tie-out are verified.

## Next operational checkpoints

- Export the **private** Journal Review list from owner/admin Reports UI. Use **Export displayed page** to create a controlled first batch of up to 25 transactions, or **Export private CSV** for the entire selected queue. Both preserve the year/source/review filters; displayed-page downloads also verify the precise visible transaction IDs and reject a shifted queue with HTTP 409 rather than silently substituting another transaction. Downloads are confidential. Verify source, linkage, receivable/payable, reversal and posted-date fields against original evidence. The goal is reducing **166 awaiting first review**, not hiding the exceptions via queue filters.
- Investigate all 12 Beds24 status mismatches as of the latest audit; retain mismatches marked REVIEW_REQUIRED until current state is confirmed.
- Cross-check the five Staff repayment candidates against source receipts and receiving ledger before any replay.
- Record separate trial balance/AR/AP and physical cash/bank sign-offs.
- Re-run read-only integrity certification and perform an isolated restore rehearsal before declaring full financial closure.

### Completion definition

The project is **accounting-reconciled** only once all material unsupported balances/transactions are explained or correctly adjusted with independently reviewed evidence, cash/bank and AR/AP agree to source records, posted GL reports tie out, integration duplicates are controlled, and a documented restore rehearsal succeeds. Until then: **technical controls largely implemented, financial reconciliation OPEN**.

# Accounting Program — evidence-based goal tracker

**Snapshot:** 2026-10-21 (Philippines local date); this is a dated checkpoint, not a live dashboard.
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

## Latest verified production and safety evidence

- [Accounting deployment #39601553031](https://github.com/moraledacaryl-dev/accounting-program-online/actions/runs/39601553031) activated exact release `6b0fce5497a0da16ae331ae90cb0363ed4edb506`, Alembic `0017_journal_linkage_review`, with validated backup and atomic activation.
- [One-time Accounting journal-proof release #39603853909](https://github.com/moraledacaryl-dev/accounting-program-online/actions/runs/39603853909) subsequently activated `dc3ab7c82009d8c792c14dc20fcd37ebd7f64927` after successful exact-SHA CI; backup `/var/backups/hiddenoasis/accounting/accounting-20261021T125830Z.dump`; previous release preserved. The Inventory event journal-proof endpoint is read-only and must not be mistaken for a completed inventory-accounting reconciliation.
- [Verified Accounting batch-release #39610427751](https://github.com/moraledacaryl-dev/accounting-program-online/actions/runs/39610427751) **superseded the earlier journal-proof release**: atomic production activation of `c5faae3836f18cec0d30c11ba571ef14e82404ea`, mandatory validated backup `/var/backups/hiddenoasis/accounting/accounting-20261021T134359Z.dump`, Alembic `0017_journal_linkage_review`, with previous `dc3ab7c8` release retained. The owner/admin UI now exports the exact displayed page (up to 25) or the entire private filtered worklist, including original linkage and reversal fields. Temporary one-time release trigger was removed in [PR #273](https://github.com/moraledacaryl-dev/accounting-program-online/pull/273). This does **not** imply any human-reviewed/reconciled money transactions.
- [Read-only Inventory–Accounting audit #39609277177](https://github.com/moraledacaryl-dev/accounting-program-online/actions/runs/39609277177) reported zero Inventory outbox events and zero Accounting Inventory integration-review records; the new journal-proof API cannot yet be considered validated on real Inventory event traffic.
- [Read-only Journal Review production smoke #39602647657](https://github.com/moraledacaryl-dev/accounting-program-online/actions/runs/39602647657) verified 166 missing direct journal links, **zero** transaction-level reviews, zero orphan history records, and HTTP 401 for unauthenticated Journal Review and private CSV export. These are counts at the time of the smoke, not an assertion that no later review could exist.
- [Group 6 original baseline #39458680436](https://github.com/moraledacaryl-dev/accounting-program-online/actions/runs/39458680436): 1,131 posted journals; zero unbalanced/invalid journals; 1,044 money transactions; 166 posted money-in transactions with null journal foreign keys. A null foreign key does **not** prove an absent journal, missing revenue or missing cash.
- The read-only 166-row worklist and the owner/admin-only Reports → Journal Review CSV are private data. They must not be committed, pasted into CI logs or uploaded as public artifacts.

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

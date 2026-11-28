# Accounting Training — trainer guide

This standalone course uses the deployed Accounting release `ad1a350b87cb19f09533043143f44dbb532b9cff` as its baseline. It adds a course and guide around the actual Accounting screens and handlers. Every attempt has a separate fictional Accounting database. It cannot send transactions or integration messages to the live systems.

The course contains 35 lessons across 13 modules and six paths: Cashier, Front Desk, Accounting, Manager, Auditor and Owner. Lesson definitions are shared across applicable paths; three practice modes provide different amounts and counterparties. These are 35 distinct lessons, rather than 105 different workflows.

## Teach and assess

Start with the learner's assigned path. Explain the situation and supporting document, demonstrate once, then let the learner use the real controls. Review the account, counterparty, reference, amount and resulting balance together. Encourage a documented refusal when a proposal is invalid.

Each lesson has a guided attempt, an assisted attempt with optional hints, and an independent attempt. Guided and assisted passes unlock independent work. The checker requires saved business evidence as well as a knowledge answer. Inspection lessons require an actual record read, a correct observation, and unchanged financial records. Protective-refusal lessons require the specific business refusal and unchanged records; a failed request alone is insufficient. Using an independent hint turns that attempt into practice and prevents an independent pass.

Module finals require guided and assisted completion of their assigned lessons. The duty final requires all three modes and passed applicable module finals. Each final starts fresh independent tasks; historical practice passes cannot substitute for those tasks. Pass marks are 85% knowledge, 90% practical and 100% critical controls. Results, source evidence and certificate identifiers remain in history. A retake creates a fresh result. Training certification does not grant production permissions or establish actual cash or bank balances.

The practice sequences group related lessons. Each lesson has its own records; they are not a shared multi-user workday simulation.

## Coverage and limits

Covered hands-on: receipts and optional journal posting, receipt reversal, payments, insufficient cash and role refusals, internal transfers and reversals, customer receivables and collections, supplier bills and payments, physical counts and variance, folio charges and settlement, journal review/posting/reversal, asset creation/depreciation/disposal and duplicate protection, and locked-period refusal.

Covered as inspections: account positions, original saved references, closed counts, settled folios, trial balance, profit, the approved-Record aging report, asset history, Review Inbox proposals, and generated BIR books. Inbox acceptance/rejection, BIR filing/submission, supplier credit, bank feeds, payroll, imports, attachments and external delivery are not practical certification claims in this version. The source aging report reads approved credit Records; it is not presented as a reconciliation of the separate cashflow receivables screen.

The training branch includes two verified screen corrections: the Daily Close drawer submits the actual typed count, and the guest-folio page resolves dynamic route parameters through Next's supported client hook. These are included in this training package. Installing this package does not deploy changes to live Accounting.

## Review progress privately

Open **Trainer progress** from the course footer. The trainer access code is the `manager-key` file in the local training data directory. Keep it private; an Owner practice role does not grant roster access.

- macOS default: `~/.local/share/HiddenOasis/accounting-training`
- Windows default: `%LOCALAPPDATA%\HiddenOasis\accounting-training`

The roster shows assignments, independent skills, hints, corrections, attempts and final results. Learners can download their own progress. Training identity is a local learning record, not a verified production identity. Use separate operating-system accounts when employees should not share local files.

## Save and recover

Quit the training app and ensure both local services have stopped before copying state. Do not distribute a used data directory with a package: it contains employee progress, practice records and private session/trainer keys.

Use the executable's offline recovery command. On macOS the executable is inside `Hidden Oasis Accounting Training.app/Contents/MacOS/Hidden Oasis Accounting Training`; on Windows it is `Hidden Oasis Accounting Training.exe` in the extracted folder.

```text
<executable> --training-recovery backup --training-is-stopped --data <accounting-training-directory> --archive <new-private-backup.zip>
<executable> --training-recovery restore --training-is-stopped --data <new-parent>/accounting-training --archive <private-backup.zip>
```

Restore only into an absent directory named `accounting-training`. Preserve the old installation until the restored history has been checked. Recovery verifies checksums, SQLite integrity, relationships and saved attempt files. It refuses existing destinations and unexpected archive paths. The private recovery archive belongs in protected storage; it is not a distributable app or a production backup.

## Troubleshooting

If startup reports a busy port, close the earlier Accounting Training instance. The dedicated ports are 3420 and 8420; Operations and Inventory use different ports. If a practice changed in another tab, return to the course to continue the current attempt. If a source action is outside the current assignment, start its lesson rather than changing the fictional database directly.

If startup fails, preserve `launcher-error.log` in the local data folder and the original package. Do not point the trainer at operational credentials or add an operational `.env` file. A source build should be refreshed only after source-contract review, real-screen exercises and the normal Accounting regression checks pass.

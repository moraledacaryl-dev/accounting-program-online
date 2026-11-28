export const trainingQuestions = [
  {question:'The save button was slow. Should I enter the receipt again?',answer:'First find the original reference in the ledger and inspect its account, amount and status. A delayed response does not establish failure.',checklist:['Keep the original document reference.','Search the saved ledger.','Ask the authorized reviewer if the result is unclear.'],lessons:['find-before-retry','receipt','refuse-repeat-disposal']},
  {question:'Why are cash received and income different?',answer:'Cash is a movement in a financial account. Income is a journal classification. Loans, owner contributions and internal transfers can add cash without being sales.',checklist:['Check the source document.','Distinguish the receiving account from the income account.','Inspect the linked posted journal when posting is required.'],lessons:['receipt-with-journal','transfer','read-profit']},
  {question:'What should I do when the drawer count differs?',answer:'Enter what you actually counted. Keep the difference and explain it. Never copy the book balance merely to remove a variance.',checklist:['Count independently.','Record the observed amount.','Request the authorized review and keep supporting evidence.'],lessons:['count-cash','read-close-control']},
  {question:'Can I change a settled guest folio?',answer:'Finalized folio lines must be explicitly reopened through the authorized workflow before correction. Preserve the earlier charges and payment evidence.',checklist:['Check the guest and folio.','Ask for the authorized reopening.','Record and review the correction.'],lessons:['read-settled-folio','settle-folio','folio-charge']},
  {question:'Why did the payment or collection get refused?',answer:'Check the remaining obligation, the actual account balance and your role. Do not split or move a proposal merely to evade a protection.',checklist:['Read the existing bill or customer balance.','Confirm actual payment evidence.','Ask the authorized Accounting colleague to resolve the discrepancy.'],lessons:['refuse-overcollection','refuse-overpayment','refuse-overdraw','cashier-authority']},
  {question:'Can I depreciate the normal amount in the final month?',answer:'Only up to the remaining depreciable value. Automatic depreciation caps the final posting; an excessive manual amount is rejected.',checklist:['Check cost and salvage.','Read all earlier depreciation logs.','Inspect the final linked accounting record.'],lessons:['depreciation-cap','refuse-excess-depreciation','read-asset-history']},
  {question:'Does a pending connected-team proposal prove that money moved?',answer:'No. It is an item for review. Source identity, approval, actual financial effects and posted journal evidence are separate checks.',checklist:['Identify the source and revision.','Check duplicates and supporting documents.','Inspect accepted links before claiming posting or payment.'],lessons:['read-inbox']},
];

export const trainingTerms = [
  {term:'Receivable',meaning:'An amount a customer or another party still owes the resort.'},
  {term:'Payable',meaning:'An amount the resort still owes to a supplier or another party.'},
  {term:'Reconciliation',meaning:'A comparison between recorded money and independent evidence, with differences explained.'},
  {term:'Variance',meaning:'The difference between the expected amount and the amount independently observed.'},
  {term:'Posted journal',meaning:'An accounting entry accepted into the general ledger; a saved draft is different.'},
  {term:'Reversal',meaning:'A linked offset that preserves the original transaction and its audit history.'},
  {term:'Salvage value',meaning:'The asset value retained after its planned depreciation.'},
  {term:'Depreciable value',meaning:'Cost less salvage, reduced by depreciation already recorded.'},
  {term:'Source reference',meaning:'The identifier linking a saved entry to the supporting receipt, invoice or other evidence.'},
  {term:'Training result',meaning:'Evidence of performance in fictional local practice. It does not grant production access.'},
];

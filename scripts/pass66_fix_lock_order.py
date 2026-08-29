from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / 'backend/app/services/cashflow_service.py'
text = path.read_text(encoding='utf-8')

old = """    row_account = db.get(FinancialAccount, int(payload.financial_account_id))\n    if not row_account:\n        raise ValueError('financial_account_id not found.')\n\n    tx_date = _safe_date(payload.transaction_date)\n"""
new = """    # Lock the cash account before inserting any transaction row that references it.\n    # PostgreSQL FK checks acquire key-share locks during INSERT; taking FOR UPDATE\n    # only after the insert allows concurrent writers to deadlock while upgrading\n    # those locks. Acquiring the authoritative balance row first also makes the\n    # balance validation below concurrency-safe.\n    row_account = (\n        db.query(FinancialAccount)\n        .filter(FinancialAccount.id == int(payload.financial_account_id))\n        .populate_existing()\n        .with_for_update()\n        .first()\n    )\n    if not row_account:\n        raise ValueError('financial_account_id not found.')\n\n    # Composite cashflow mutations always lock in account -> subledger order.\n    # This prevents event/AR/AP writers from taking the same rows in opposite\n    # order and makes the balance_due re-check in _apply_money_effect authoritative.\n    if payload.receivable_id:\n        linked_receivable = (\n            db.query(Receivable)\n            .filter(Receivable.id == int(payload.receivable_id))\n            .populate_existing()\n            .with_for_update()\n            .first()\n        )\n        if not linked_receivable:\n            raise ValueError('Linked receivable not found.')\n    if payload.payable_id:\n        linked_payable = (\n            db.query(Payable)\n            .filter(Payable.id == int(payload.payable_id))\n            .populate_existing()\n            .with_for_update()\n            .first()\n        )\n        if not linked_payable:\n            raise ValueError('Linked payable not found.')\n\n    tx_date = _safe_date(payload.transaction_date)\n"""
if text.count(old) != 1:
    raise SystemExit(f'cashflow_service.py: expected one row_account block, found {text.count(old)}')
text = text.replace(old, new, 1)

# Guard the transaction construction order: no MoneyTransaction may be added/flushed
# before the authoritative account lock in create_money_transaction.
func = text.split('def create_money_transaction', 1)[1].split('\ndef list_money_transactions', 1)[0]
if func.index('.with_for_update()') > func.index('tx = MoneyTransaction('):
    raise SystemExit('cashflow_service.py: account lock still occurs after transaction construction')

path.write_text(text, encoding='utf-8')
print('Pass 66 lock order fixed: authoritative account/subledger rows lock before FK-backed transaction insert.')

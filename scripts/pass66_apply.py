from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch(path: str, old: str, new: str, count: int = 1):
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    found = text.count(old)
    if found != count:
        raise SystemExit(f'{path}: expected {count} occurrence(s), found {found}: {old[:120]!r}')
    p.write_text(text.replace(old, new, count), encoding='utf-8')


cash = 'backend/app/services/cashflow_service.py'

# Lock mutable financial rows at the point money effects are applied.
patch(cash,
"    account = db.get(FinancialAccount, int(tx.financial_account_id))\n    if not account:\n        raise ValueError('Linked financial account not found.')",
"    account = (\n        db.query(FinancialAccount)\n        .filter(FinancialAccount.id == int(tx.financial_account_id))\n        .populate_existing()\n        .with_for_update()\n        .first()\n    )\n    if not account:\n        raise ValueError('Linked financial account not found.')",
count=2)

patch(cash,
"        receivable = db.get(Receivable, int(tx.receivable_id))\n        if not receivable:\n            raise ValueError('Linked receivable not found.')\n        receivable.amount_collected = round(float(receivable.amount_collected or 0) + amount, 4)",
"        receivable = (\n            db.query(Receivable)\n            .filter(Receivable.id == int(tx.receivable_id))\n            .populate_existing()\n            .with_for_update()\n            .first()\n        )\n        if not receivable:\n            raise ValueError('Linked receivable not found.')\n        if amount - float(receivable.balance_due or 0) > 0.0001:\n            raise ValueError('Collection amount cannot exceed receivable balance.')\n        receivable.amount_collected = round(float(receivable.amount_collected or 0) + amount, 4)")

patch(cash,
"        payable = db.get(Payable, int(tx.payable_id))\n        if not payable:\n            raise ValueError('Linked payable not found.')\n        payable.amount_paid = round(float(payable.amount_paid or 0) + amount, 4)",
"        payable = (\n            db.query(Payable)\n            .filter(Payable.id == int(tx.payable_id))\n            .populate_existing()\n            .with_for_update()\n            .first()\n        )\n        if not payable:\n            raise ValueError('Linked payable not found.')\n        if amount - float(payable.balance_due or 0) > 0.0001:\n            raise ValueError('Payment amount cannot exceed payable balance.')\n        payable.amount_paid = round(float(payable.amount_paid or 0) + amount, 4)")

# Nested services can now participate in a caller-owned transaction.
patch(cash,
"def create_money_transaction(db: Session, payload: MoneyTransactionCreate, username: str | None = None):",
"def create_money_transaction(db: Session, payload: MoneyTransactionCreate, username: str | None = None, *, commit: bool = True):")

patch(cash,
"    tx.journal_entry_id = linked_journal_id\n    db.add(tx)\n    db.commit()\n\n    tx = (\n        db.query(MoneyTransaction)\n        .options(selectinload(MoneyTransaction.financial_account))\n        .filter(MoneyTransaction.id == tx.id)\n        .first()\n    )\n    return _serialize_money_transaction(tx)",
"    tx.journal_entry_id = linked_journal_id\n    db.add(tx)\n    db.flush()\n    if commit:\n        db.commit()\n        tx = (\n            db.query(MoneyTransaction)\n            .options(selectinload(MoneyTransaction.financial_account))\n            .filter(MoneyTransaction.id == tx.id)\n            .first()\n        )\n    else:\n        db.refresh(tx)\n    return _serialize_money_transaction(tx)")

patch(cash,
"def create_receivable(db: Session, payload: ReceivableCreate):",
"def create_receivable(db: Session, payload: ReceivableCreate, *, commit: bool = True):")

# Both create-receivable commit sites (reversal adjustment + normal receivable).
patch(cash,
"        _update_receivable_balance(db, original.id)\n        db.commit()\n        db.refresh(original)\n        return _serialize_receivable(original)",
"        _update_receivable_balance(db, original.id)\n        db.flush()\n        if commit:\n            db.commit()\n            db.refresh(original)\n        return _serialize_receivable(original)")
patch(cash,
"    _update_receivable_balance(db, row.id)\n    db.commit()\n    db.refresh(row)\n    return _serialize_receivable(row)",
"    _update_receivable_balance(db, row.id)\n    db.flush()\n    if commit:\n        db.commit()\n        db.refresh(row)\n    return _serialize_receivable(row)",
count=1)

patch(cash,
"def collect_receivable(db: Session, receivable_id: int, payload: ReceivableCollectPayload, username: str | None = None):",
"def collect_receivable(db: Session, receivable_id: int, payload: ReceivableCollectPayload, username: str | None = None, *, commit: bool = True):")
patch(cash,
"        ),\n        username=username,\n    )\n    receivable = db.get(Receivable, int(receivable_id))\n    return {\n        'receivable': _serialize_receivable(receivable),\n        'transaction': tx,\n    }",
"        ),\n        username=username,\n        commit=False,\n    )\n    db.flush()\n    if commit:\n        db.commit()\n    receivable = db.get(Receivable, int(receivable_id))\n    return {\n        'receivable': _serialize_receivable(receivable),\n        'transaction': tx,\n    }")

patch(cash,
"def create_payable(db: Session, payload: PayableCreate):",
"def create_payable(db: Session, payload: PayableCreate, *, commit: bool = True):")
patch(cash,
"    _update_payable_balance(db, row.id)\n    db.commit()\n    db.refresh(row)\n    return _serialize_payable(row)",
"    _update_payable_balance(db, row.id)\n    db.flush()\n    if commit:\n        db.commit()\n        db.refresh(row)\n    return _serialize_payable(row)",
count=1)

# Lock original transaction before state-changing cancellation/reversal races.
patch(cash,
"def reverse_money_transaction(db: Session, tx_id: int, payload: CashflowActionPayload, username: str | None = None):\n    row = db.get(MoneyTransaction, int(tx_id))",
"def reverse_money_transaction(db: Session, tx_id: int, payload: CashflowActionPayload, username: str | None = None):\n    row = (\n        db.query(MoneyTransaction)\n        .filter(MoneyTransaction.id == int(tx_id))\n        .populate_existing()\n        .with_for_update()\n        .first()\n    )")

# Transfers lock both accounts in deterministic ID order to prevent overspend and deadlocks.
patch(cash,
"    from_account = db.get(FinancialAccount, int(payload.from_account_id))\n    to_account = db.get(FinancialAccount, int(payload.to_account_id))\n    if not from_account or not to_account:\n        raise ValueError('Invalid from_account_id or to_account_id.')",
"    account_ids = sorted({int(payload.from_account_id), int(payload.to_account_id)})\n    locked_accounts = (\n        db.query(FinancialAccount)\n        .filter(FinancialAccount.id.in_(account_ids))\n        .order_by(FinancialAccount.id.asc())\n        .populate_existing()\n        .with_for_update()\n        .all()\n    )\n    account_by_id = {int(account.id): account for account in locked_accounts}\n    from_account = account_by_id.get(int(payload.from_account_id))\n    to_account = account_by_id.get(int(payload.to_account_id))\n    if not from_account or not to_account:\n        raise ValueError('Invalid from_account_id or to_account_id.')")

patch(cash,
"def reverse_transfer(db: Session, transfer_id: int, payload: CashflowActionPayload, username: str | None = None):\n    row = db.get(AccountTransfer, int(transfer_id))",
"def reverse_transfer(db: Session, transfer_id: int, payload: CashflowActionPayload, username: str | None = None):\n    row = (\n        db.query(AccountTransfer)\n        .filter(AccountTransfer.id == int(transfer_id))\n        .populate_existing()\n        .with_for_update()\n        .first()\n    )")
patch(cash,
"        from_account = db.get(FinancialAccount, int(reversal.from_account_id))\n        to_account = db.get(FinancialAccount, int(reversal.to_account_id))",
"        account_ids = sorted({int(reversal.from_account_id), int(reversal.to_account_id)})\n        locked_accounts = (\n            db.query(FinancialAccount)\n            .filter(FinancialAccount.id.in_(account_ids))\n            .order_by(FinancialAccount.id.asc())\n            .populate_existing()\n            .with_for_update()\n            .all()\n        )\n        account_by_id = {int(account.id): account for account in locked_accounts}\n        from_account = account_by_id.get(int(reversal.from_account_id))\n        to_account = account_by_id.get(int(reversal.to_account_id))")

# Event confirmation/collection/payment now share one request transaction.
event = 'backend/app/services/event_service.py'
patch(event,
"            ),\n        )\n        event = db.get(EventBooking, int(event.id))",
"            ),\n            commit=False,\n        )\n        event = db.get(EventBooking, int(event.id))")
patch(event,
"def confirm_event(db: Session, event_id: int, payload: EventActionPayload, username: str | None = None):",
"def confirm_event(db: Session, event_id: int, payload: EventActionPayload, username: str | None = None, *, commit: bool = True):")
patch(event,
"    _sync_financial_links(db, event, username)\n    db.commit()\n    return get_event(db, event.id)\n\n\ndef complete_event",
"    _sync_financial_links(db, event, username)\n    db.flush()\n    if commit:\n        db.commit()\n    return get_event(db, event.id)\n\n\ndef complete_event")
patch(event,
"        confirm_event(db, event.id, EventActionPayload(action_date=payload.payment_date or _today(), note='Auto-confirmed by event payment.'), username=username)",
"        confirm_event(db, event.id, EventActionPayload(action_date=payload.payment_date or _today(), note='Auto-confirmed by event payment.'), username=username, commit=False)")
patch(event,
"        _sync_financial_links(db, event, username)\n        db.commit()\n        event = _event_query(db).filter(EventBooking.id == int(event_id)).first()",
"        _sync_financial_links(db, event, username)\n        db.flush()\n        event = _event_query(db).filter(EventBooking.id == int(event_id)).first()")
patch(event,
"        ),\n        username=username,\n    )\n    tx_data = result.get('transaction') or {}",
"        ),\n        username=username,\n        commit=False,\n    )\n    tx_data = result.get('transaction') or {}")

# Receiving's stock movements + supplier bill commit together at the receiving boundary.
proc = 'backend/app/services/procurement_service.py'
patch(proc,
"            bir_include=True,\n        ),\n    )",
"            bir_include=True,\n        ),\n        commit=False,\n    )")

print('Pass 66 transaction-integrity patch applied.')

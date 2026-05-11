from __future__ import annotations
from sqlalchemy.orm import Session
from app.models.entities import JournalEntry, JournalLine, Record

DEFAULT_ACCOUNT_MAP = {
    ('rooms', 'income'): ('4000', 'Rooms Revenue'),
    ('rooms', 'liability'): ('2100', 'Unearned Room Revenue'),
    ('rooms', 'expense'): ('5040', 'Rooms Contra Revenue / Refunds'),
    ('restaurant', 'income'): ('4010', 'Restaurant Revenue'),
    ('breakfast', 'income'): ('4011', 'Breakfast Revenue'),
    ('cafe', 'income'): ('4012', 'Cafe Revenue'),
    ('bar', 'income'): ('4013', 'Bar Revenue'),
    ('events', 'income'): ('4014', 'Events Revenue'),
    ('restaurant', 'expense'): ('5010', 'Restaurant Expense'),
    ('breakfast', 'expense'): ('5011', 'Breakfast Expense'),
    ('inventory', 'expense'): ('5020', 'Inventory Consumption Expense'),
    ('channel_ota', 'expense'): ('5030', 'OTA Commission Expense'),
    ('channel_ota', 'asset'): ('1040', 'OTA Receivable'),
    ('assets', 'asset'): ('1500', 'Property and Equipment'),
    ('assets', 'expense'): ('5110', 'Depreciation and Asset Expense'),
    ('inventory', 'asset'): ('1200', 'Inventory Asset'),
    ('finance', 'liability'): ('2000', 'Accounts Payable'),
    ('other-income', 'income'): ('4090', 'Other Income'),
    ('other_income', 'income'): ('4090', 'Other Income'),
    ('finance', 'asset'): ('1000', 'Cash and Cash Equivalents'),
}
PAYMENT_ACCOUNT = {
    'cash': ('1000', 'Cash on Hand'),
    'gcash': ('1010', 'GCash'),
    'bank transfer': ('1020', 'Bank'),
    'bank_transfer': ('1020', 'Bank'),
    'card': ('1030', 'Card Receivable'),
    'ota payout': ('1040', 'OTA Receivable'),
    'ota_payout': ('1040', 'OTA Receivable'),
    'inventory': ('1200', 'Inventory Asset'),
    'on_account': ('1100', 'Accounts Receivable'),
    'accumulated_depreciation': ('1590', 'Accumulated Depreciation'),
}

def autopost_record(db: Session, record: Record, commit: bool = True):
    if record.direction not in {'income', 'expense', 'liability', 'asset'}:
        return None
    if record.workflow_status != 'approved':
        return None
    # Avoid double posting by reference
    existing = db.query(JournalEntry).filter(JournalEntry.reference_no == f"REC-{record.id}").first()
    if existing:
        return existing
    raw_amount = float(record.amount or 0)
    if abs(raw_amount) <= 0:
        return None
    amount = abs(raw_amount)
    reverse = raw_amount < 0
    payment_key = (record.payment_method or 'cash').strip().lower()
    if payment_key in {'on_account', 'credit'}:
        if record.direction == 'income':
            pay_code, pay_name = ('1100', 'Accounts Receivable')
        elif record.direction in {'expense', 'asset'}:
            pay_code, pay_name = ('2000', 'Accounts Payable')
        else:
            pay_code, pay_name = ('1000', 'Cash on Hand')
    else:
        pay_code, pay_name = PAYMENT_ACCOUNT.get(payment_key, ('1000', 'Cash on Hand'))
    main_code, main_name = DEFAULT_ACCOUNT_MAP.get((record.module_slug, record.direction), ('5999', 'Unmapped Account'))
    if record.direction == 'expense':
        main_code, main_name = DEFAULT_ACCOUNT_MAP.get((record.module_slug, 'expense'), ('5000', 'Operating Expense'))
    elif record.direction == 'liability':
        main_code, main_name = DEFAULT_ACCOUNT_MAP.get((record.module_slug, 'liability'), ('2100', 'Current Liability'))
    elif record.direction == 'asset':
        main_code, main_name = DEFAULT_ACCOUNT_MAP.get((record.module_slug, 'asset'), ('1500', 'Asset'))
    je = JournalEntry(entry_date=record.transaction_date, reference_no=f"REC-{record.id}", description=record.name or record.item, source_module=record.module_slug, status='posted')
    db.add(je)
    db.flush()
    if record.direction == 'income':
        dr, cr = (amount, 0) if not reverse else (0, amount)
        db.add(JournalLine(journal_entry_id=je.id, account_code=pay_code, account_name=pay_name, debit=dr, credit=cr, memo=record.name))
        db.add(JournalLine(journal_entry_id=je.id, account_code=main_code, account_name=main_name, debit=cr, credit=dr, memo=record.name))
    elif record.direction == 'expense':
        dr, cr = (amount, 0) if not reverse else (0, amount)
        db.add(JournalLine(journal_entry_id=je.id, account_code=main_code, account_name=main_name, debit=dr, credit=cr, memo=record.name))
        db.add(JournalLine(journal_entry_id=je.id, account_code=pay_code, account_name=pay_name, debit=cr, credit=dr, memo=record.name))
    elif record.direction == 'liability':
        dr, cr = (amount, 0) if not reverse else (0, amount)
        db.add(JournalLine(journal_entry_id=je.id, account_code=pay_code, account_name=pay_name, debit=dr, credit=cr, memo=record.name))
        db.add(JournalLine(journal_entry_id=je.id, account_code=main_code, account_name=main_name, debit=cr, credit=dr, memo=record.name))
    elif record.direction == 'asset':
        dr, cr = (amount, 0) if not reverse else (0, amount)
        db.add(JournalLine(journal_entry_id=je.id, account_code=main_code, account_name=main_name, debit=dr, credit=cr, memo=record.name))
        db.add(JournalLine(journal_entry_id=je.id, account_code=pay_code, account_name=pay_name, debit=cr, credit=dr, memo=record.name))
    if commit:
        db.commit()
        db.refresh(je)
    else:
        db.flush()
    return je

"""Shared validation and eligibility rules for ledger writes and reports."""
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from app.models.entities import ChartAccount, JournalEntry

MONEY_QUANTUM = Decimal('0.0001')


def money(value):
    try:
        number = Decimal(str(value or 0))
        if not number.is_finite():
            raise ValueError('Amounts must be finite numbers.')
        return number.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError):
        raise ValueError('Invalid monetary amount.') from None


def posted_journal_filter():
    # Original entries remain posted after reversal; their reversing entries offset them.
    return JournalEntry.status == 'posted'


def validate_journal(db, entry_date, lines, *, check_accounts=True):
    try:
        if not entry_date or date.fromisoformat(str(entry_date)).isoformat() != str(entry_date):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('A valid journal date in YYYY-MM-DD format is required.') from None
    if not check_accounts:
        # Older automatic payroll postings can include zero-valued deduction lines.
        lines = [line for line in lines if money(line.debit) or money(line.credit)]
    if len(lines) < 2:
        raise ValueError('A journal requires at least two nonzero lines.')
    debit = credit = Decimal(0)
    codes = set()
    for line in lines:
        dr, cr = money(line.debit), money(line.credit)
        if dr < 0 or cr < 0 or (dr > 0) == (cr > 0):
            raise ValueError('Each line must have a positive debit or credit, never both.')
        codes.add(line.account_code)
        debit += dr
        credit += cr
    if debit != credit:
        raise ValueError('Debits and credits must balance exactly to four decimal places.')
    if check_accounts:
        available = {row.code for row in db.query(ChartAccount).filter(ChartAccount.code.in_(codes), ChartAccount.is_active == True).all()}
        missing = sorted(codes - available)
        if missing:
            raise ValueError(f'Choose active chart accounts: {", ".join(missing)}.')
    return debit, credit

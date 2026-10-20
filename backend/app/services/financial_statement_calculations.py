"""Ledger statement calculations and management cash-movement schedules.

Extracted verbatim from the reporting HTTP router in Group 5. Keep the report
JSON contract and four-decimal money rounding unchanged. This module has no
HTTP dependencies; the router re-exports names for existing integrations.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.entities import (
    AccountTransfer, ChartAccount, JournalEntry, JournalLine, MoneyTransaction,
)
from app.services.journal_integrity_service import money, posted_journal_filter

def _norm(value: str | None) -> str:
    return (value or '').strip().lower()

def _round_money(value) -> float:
    return float(money(value))

def _account_family(account_code: str | None, account_type: str | None = None) -> str:
    raw_type = _norm(account_type)
    if raw_type:
        if 'asset' in raw_type:
            return 'assets'
        if 'liabil' in raw_type or 'payable' in raw_type:
            return 'liabilities'
        if 'equity' in raw_type or 'capital' in raw_type:
            return 'equity'
        if 'revenue' in raw_type or 'income' in raw_type or 'sales' in raw_type:
            return 'revenue'
        if 'expense' in raw_type or 'cost' in raw_type or raw_type in {'cogs', 'direct costs'}:
            return 'expenses'
    code = (account_code or '').strip()
    if code.startswith('1'):
        return 'assets'
    if code.startswith('2'):
        return 'liabilities'
    if code.startswith('3'):
        return 'equity'
    if code.startswith('4'):
        return 'revenue'
    if code.startswith(('5', '6', '8')):
        return 'expenses'
    return 'other'


def _chart_account_map(db: Session) -> dict[str, ChartAccount]:
    return {row.code: row for row in db.query(ChartAccount).all()}


def _posted_journal_rows(
    db: Session,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    as_of_date: str | None = None,
) -> list[tuple[JournalEntry, JournalLine]]:
    query = (
        db.query(JournalEntry, JournalLine)
        .join(JournalLine, JournalLine.journal_entry_id == JournalEntry.id)
        .filter(posted_journal_filter())
    )
    if as_of_date:
        query = query.filter(JournalEntry.entry_date <= as_of_date)
    else:
        if start_date:
            query = query.filter(JournalEntry.entry_date >= start_date)
        if end_date:
            query = query.filter(JournalEntry.entry_date <= end_date)
    return query.order_by(JournalEntry.entry_date.asc(), JournalEntry.id.asc(), JournalLine.id.asc()).all()


def _group_lines(rows: list[tuple[JournalEntry, JournalLine]], chart_map: dict[str, ChartAccount]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for _entry, line in rows:
        account = chart_map.get(line.account_code)
        key = line.account_code or 'unmapped'
        item = grouped.setdefault(
            key,
            {
                'account_code': line.account_code,
                'account_name': (account.name if account else line.account_name) or 'Unmapped',
                'account_type': account.account_type if account else None,
                'account_subtype': account.subtype if account else None,
                'family': _account_family(line.account_code, account.account_type if account else None),
                'debit': Decimal(0),
                'credit': Decimal(0),
            },
        )
        item['debit'] += Decimal(str(line.debit or 0))
        item['credit'] += Decimal(str(line.credit or 0))

    result = []
    for item in grouped.values():
        family = item['family']
        if family in {'assets', 'expenses'}:
            balance = item['debit'] - item['credit']
        else:
            balance = item['credit'] - item['debit']
        result.append({
            **item,
            'debit': _round_money(item['debit']),
            'credit': _round_money(item['credit']),
            'balance': _round_money(balance),
        })
    return sorted(result, key=lambda row: (row.get('account_code') or ''))


def _sum_family(items: list[dict], family: str) -> float:
    return _round_money(sum(float(row.get('balance') or 0) for row in items if row.get('family') == family))


def _is_cost_of_sales_account(row: dict) -> bool:
    """Use explicit chart classification or unambiguous account names, never a 5xxx guess."""
    words = ' '.join(str(row.get(field) or '') for field in ('account_type', 'account_subtype', 'account_name'))
    words = ' '.join(words.lower().replace('_', ' ').replace('-', ' ').split())
    return any(f' {phrase} ' in f' {words} ' for phrase in (
        'cost of goods sold', 'cost of sales', 'cost of services',
        'cogs', 'direct costs', 'direct cost of',
    ))


def _build_profit_and_loss(period_items: list[dict]) -> dict:
    revenue = [row for row in period_items if row.get('family') == 'revenue' and abs(money(row.get('balance'))) > 0]
    expenses = [row for row in period_items if row.get('family') == 'expenses' and abs(money(row.get('balance'))) > 0]
    cost_of_sales = [row for row in expenses if _is_cost_of_sales_account(row)]
    operating_expenses = [row for row in expenses if not _is_cost_of_sales_account(row)]
    revenue_amount = sum((money(row['balance']) for row in revenue), Decimal(0))
    cogs_amount = sum((money(row['balance']) for row in cost_of_sales), Decimal(0))
    operating_amount = sum((money(row['balance']) for row in operating_expenses), Decimal(0))
    expense_amount = cogs_amount + operating_amount
    return {
        'revenue': revenue,
        'expenses': expenses,  # Compatibility: all expenses, including classified COGS.
        'cost_of_sales': cost_of_sales,
        'operating_expenses': operating_expenses,
        'cost_of_sales_identified': bool(cost_of_sales),
        'totals': {
            'revenue': _round_money(revenue_amount),
            'cost_of_sales': _round_money(cogs_amount),
            'operating_expenses': _round_money(operating_amount),
            'expenses': _round_money(expense_amount),
            'gross_profit': _round_money(revenue_amount - cogs_amount),
            'net_income': _round_money(revenue_amount - expense_amount),
        },
    }


def _build_balance_sheet(as_of_items: list[dict]) -> dict:
    assets = [row for row in as_of_items if row.get('family') == 'assets' and abs(money(row.get('balance'))) > 0]
    liabilities = [row for row in as_of_items if row.get('family') == 'liabilities' and abs(money(row.get('balance'))) > 0]
    equity = [row for row in as_of_items if row.get('family') == 'equity' and abs(money(row.get('balance'))) > 0]
    current_earnings = _round_money(_sum_family(as_of_items, 'revenue') - _sum_family(as_of_items, 'expenses'))
    if abs(current_earnings) > 0.0001:
        equity.append({
            'account_code': '3999',
            'account_name': 'Current Earnings',
            'account_type': 'equity',
            'family': 'equity',
            'debit': 0,
            'credit': 0,
            'balance': current_earnings,
        })

    total_assets = _round_money(sum(float(row['balance']) for row in assets))
    total_liabilities = _round_money(sum(float(row['balance']) for row in liabilities))
    total_equity = _round_money(sum(float(row['balance']) for row in equity))
    return {
        'assets': assets,
        'liabilities': liabilities,
        'equity': equity,
        'totals': {
            'assets': total_assets,
            'liabilities': total_liabilities,
            'equity': total_equity,
            'liabilities_and_equity': _round_money(total_liabilities + total_equity),
            'balance_check': _round_money(total_assets - total_liabilities - total_equity),
        },
    }


def _build_trial_balance(as_of_items: list[dict]) -> dict:
    debit_total = _round_money(sum(float(row.get('debit') or 0) for row in as_of_items))
    credit_total = _round_money(sum(float(row.get('credit') or 0) for row in as_of_items))
    return {
        'lines': as_of_items,
        'totals': {
            'debit': debit_total,
            'credit': credit_total,
            'variance': _round_money(debit_total - credit_total),
            'is_balanced': money(debit_total) == money(credit_total),
        },
    }


def _cash_activity_classification(tx: MoneyTransaction) -> str:
    """Classify only when source metadata gives reliable economic purpose.

    Unknown finance movements remain unclassified rather than pretending to be
    operating cash flows. This is a management movement schedule, not a
    standards-compliant statement of cash flows.
    """
    module = _norm(tx.module).replace('_', ' ').replace('-', ' ')
    category = ' '.join(_norm(getattr(tx, key, None)) for key in ('category', 'subcategory', 'level3_item'))
    description = ' '.join((module, category)).replace('_', ' ').replace('-', ' ')
    if any(label in description for label in (
        'loan proceeds', 'loan repayment', 'loan principal', 'capital injection',
        'owner contribution', 'owner withdrawal', 'dividend', 'financing activity',
    )):
        return 'financing'
    if any(label in description for label in (
        'fixed asset', 'asset purchase', 'asset disposal', 'capital expenditure',
        'equipment purchase', 'investing activity',
    )):
        return 'investing'
    if module in {
        'events', 'event', 'restaurant', 'pos', 'cafe', 'bar',
        'room', 'rooms', 'hotel', 'hospitality', 'reservation', 'reservations',
        'payroll', 'staff payroll', 'supplier', 'suppliers', 'procurement',
        'accounts payable', 'accounts receivable',
    }:
        return 'operating'
    return 'unclassified'


def _build_cash_flow_statement(db: Session, start_date: str | None, end_date: str | None) -> dict:
    # Keep the historical posted original together with its later reversing
    # transaction. Excluding the original would invent a net cash outflow.
    tx_query = db.query(MoneyTransaction).filter(or_(
        MoneyTransaction.status == 'posted',
        (
            (MoneyTransaction.status == 'reversed')
            & MoneyTransaction.is_reversed.is_(True)
            & MoneyTransaction.posted_at.isnot(None)
        ),
    ))
    if start_date:
        tx_query = tx_query.filter(MoneyTransaction.transaction_date >= start_date)
    if end_date:
        tx_query = tx_query.filter(MoneyTransaction.transaction_date <= end_date)
    transactions = tx_query.order_by(MoneyTransaction.transaction_date.asc(), MoneyTransaction.id.asc()).all()

    grouped = {}
    classification_counts = {label: 0 for label in ('operating', 'investing', 'financing', 'unclassified')}
    for tx in transactions:
        classification = _cash_activity_classification(tx)
        classification_counts[classification] += 1
        activity = (tx.module or 'finance').strip() or 'finance'
        category = (tx.category or 'Uncategorized').strip() or 'Uncategorized'
        key = (classification, activity, category)
        row = grouped.setdefault(key, {
            'classification': classification, 'activity': activity, 'category': category,
            'cash_in': Decimal(0), 'cash_out': Decimal(0),
        })
        amount = money(tx.amount)
        if _norm(tx.direction) == 'in':
            row['cash_in'] += amount
        else:
            row['cash_out'] += amount

    transfer_query = db.query(AccountTransfer).filter(AccountTransfer.status == 'posted', AccountTransfer.is_reversed == False)
    if start_date:
        transfer_query = transfer_query.filter(AccountTransfer.transfer_date >= start_date)
    if end_date:
        transfer_query = transfer_query.filter(AccountTransfer.transfer_date <= end_date)
    transfers = transfer_query.all()

    schedules = {name: [] for name in classification_counts}
    total_in = Decimal(0)
    total_out = Decimal(0)
    for row in sorted(grouped.values(), key=lambda item: (item['classification'], item['activity'], item['category'])):
        cash_in, cash_out = row['cash_in'], row['cash_out']
        total_in += cash_in
        total_out += cash_out
        schedules[row['classification']].append({
            'activity': row['activity'], 'category': row['category'],
            'cash_in': _round_money(cash_in), 'cash_out': _round_money(cash_out),
            'net': _round_money(cash_in - cash_out),
        })
    return {
        'method': 'management_direct_cash_movements',
        'classification_status': 'requires_review' if classification_counts['unclassified'] else 'classified_by_source_metadata',
        'classification_counts': classification_counts,
        'operating_activities': schedules['operating'],
        'investing_activities': schedules['investing'],
        'financing_activities': schedules['financing'],
        'unclassified_activities': schedules['unclassified'],
        'transfers': {
            'count': len(transfers),
            'gross_transfer_amount': _round_money(sum((money(row.amount) for row in transfers), Decimal(0))),
            'net_cash_effect': 0,
        },
        'totals': {
            'cash_in': _round_money(total_in),
            'cash_out': _round_money(total_out),
            'net_cash_flow': _round_money(total_in - total_out),
        },
    }

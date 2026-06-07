from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import require_any_permissions, require_permissions
from app.db.database import get_db
from app.models.entities import (
    AccountTransfer,
    AttendanceEntry,
    Asset,
    AssetDepreciationLog,
    BIRBookEntry,
    Booking,
    ChannelPayout,
    ChartAccount,
    FinancialAccount,
    InventoryItem,
    JournalEntry,
    JournalLine,
    MoneyTransaction,
    Payable,
    PeriodLock,
    PayrollLine,
    PayrollPeriod,
    PayrollPeriodLine,
    PayrollRun,
    PurchaseOrder,
    PurchaseRequest,
    Record,
    RecordSettlement,
    ReceivingRecord,
    Receivable,
    SaleOrder,
    SaleOrderLine,
    StaffMealLog,
    StockMovement,
    Supplier,
)
from app.schemas.common import RecordSettlementCreate
from app.services.cashflow_service import cashflow_summary

router = APIRouter()


def _today() -> str:
    return datetime.utcnow().strftime('%Y-%m-%d')


def _norm(value: str | None) -> str:
    return (value or '').strip().lower()


def _is_on_account(payment_method: str | None) -> bool:
    return _norm(payment_method) in {'on_account', 'credit'}


def _age_bucket(days: int) -> str:
    if days <= 30:
        return '0-30'
    if days <= 60:
        return '31-60'
    if days <= 90:
        return '61-90'
    return '91+'


def _parse_iso_date(value: str | None) -> datetime | None:
    text = (value or '').strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, '%Y-%m-%d')
    except ValueError:
        return None


def _round_money(value) -> float:
    return round(float(value or 0), 4)


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
        if 'expense' in raw_type or 'cost' in raw_type:
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
        .filter(JournalEntry.status.notin_(['draft', 'cancelled', 'voided', 'reversed']))
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
                'family': _account_family(line.account_code, account.account_type if account else None),
                'debit': 0.0,
                'credit': 0.0,
            },
        )
        item['debit'] += float(line.debit or 0)
        item['credit'] += float(line.credit or 0)

    result = []
    for item in grouped.values():
        family = item['family']
        if family in {'assets', 'expenses'}:
            balance = float(item['debit']) - float(item['credit'])
        else:
            balance = float(item['credit']) - float(item['debit'])
        result.append({
            **item,
            'debit': _round_money(item['debit']),
            'credit': _round_money(item['credit']),
            'balance': _round_money(balance),
        })
    return sorted(result, key=lambda row: (row.get('account_code') or ''))


def _sum_family(items: list[dict], family: str) -> float:
    return _round_money(sum(float(row.get('balance') or 0) for row in items if row.get('family') == family))


def _build_profit_and_loss(period_items: list[dict]) -> dict:
    revenue = [row for row in period_items if row.get('family') == 'revenue' and abs(float(row.get('balance') or 0)) > 0.0001]
    expenses = [row for row in period_items if row.get('family') == 'expenses' and abs(float(row.get('balance') or 0)) > 0.0001]
    revenue_total = _round_money(sum(float(row['balance']) for row in revenue))
    expense_total = _round_money(sum(float(row['balance']) for row in expenses))
    return {
        'revenue': revenue,
        'expenses': expenses,
        'totals': {
            'revenue': revenue_total,
            'expenses': expense_total,
            'gross_profit': revenue_total,
            'net_income': _round_money(revenue_total - expense_total),
        },
    }


def _build_balance_sheet(as_of_items: list[dict]) -> dict:
    assets = [row for row in as_of_items if row.get('family') == 'assets' and abs(float(row.get('balance') or 0)) > 0.0001]
    liabilities = [row for row in as_of_items if row.get('family') == 'liabilities' and abs(float(row.get('balance') or 0)) > 0.0001]
    equity = [row for row in as_of_items if row.get('family') == 'equity' and abs(float(row.get('balance') or 0)) > 0.0001]
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
            'is_balanced': abs(debit_total - credit_total) <= 0.01,
        },
    }


def _build_cash_flow_statement(db: Session, start_date: str | None, end_date: str | None) -> dict:
    tx_query = db.query(MoneyTransaction).filter(
        MoneyTransaction.status == 'posted',
        MoneyTransaction.is_reversed == False,
    )
    if start_date:
        tx_query = tx_query.filter(MoneyTransaction.transaction_date >= start_date)
    if end_date:
        tx_query = tx_query.filter(MoneyTransaction.transaction_date <= end_date)
    transactions = tx_query.order_by(MoneyTransaction.transaction_date.asc(), MoneyTransaction.id.asc()).all()

    grouped: dict[str, dict] = {}
    for tx in transactions:
        activity = (tx.module or 'finance').strip() or 'finance'
        category = (tx.category or 'Uncategorized').strip() or 'Uncategorized'
        key = f'{activity}::{category}'
        row = grouped.setdefault(key, {'activity': activity, 'category': category, 'cash_in': 0.0, 'cash_out': 0.0, 'net': 0.0})
        amount = float(tx.amount or 0)
        if _norm(tx.direction) == 'in':
            row['cash_in'] += amount
        else:
            row['cash_out'] += amount
        row['net'] = row['cash_in'] - row['cash_out']

    transfer_query = db.query(AccountTransfer).filter(AccountTransfer.status == 'posted', AccountTransfer.is_reversed == False)
    if start_date:
        transfer_query = transfer_query.filter(AccountTransfer.transfer_date >= start_date)
    if end_date:
        transfer_query = transfer_query.filter(AccountTransfer.transfer_date <= end_date)
    transfers = transfer_query.all()

    lines = [
        {
            **row,
            'cash_in': _round_money(row['cash_in']),
            'cash_out': _round_money(row['cash_out']),
            'net': _round_money(row['net']),
        }
        for row in sorted(grouped.values(), key=lambda item: (item['activity'], item['category']))
    ]
    cash_in = _round_money(sum(float(row['cash_in']) for row in lines))
    cash_out = _round_money(sum(float(row['cash_out']) for row in lines))
    return {
        'method': 'direct',
        'operating_activities': lines,
        'transfers': {
            'count': len(transfers),
            'gross_transfer_amount': _round_money(sum(float(row.amount or 0) for row in transfers)),
            'net_cash_effect': 0,
        },
        'totals': {
            'cash_in': cash_in,
            'cash_out': cash_out,
            'net_cash_flow': _round_money(cash_in - cash_out),
        },
    }


def _build_operational_supplement(db: Session) -> dict:
    accounts = db.query(FinancialAccount).order_by(FinancialAccount.account_type.asc(), FinancialAccount.name.asc()).all()
    receivables = db.query(Receivable).all()
    payables = db.query(Payable).all()
    inventory_rows = db.query(InventoryItem).all()
    asset_rows = db.query(Asset).all()
    depreciation_total = float(db.query(func.coalesce(func.sum(AssetDepreciationLog.amount), 0)).scalar() or 0)
    asset_cost = sum(float(row.acquisition_cost or 0) for row in asset_rows)

    return {
        'cash_position': {
            'total': _round_money(sum(float(row.current_balance or 0) for row in accounts)),
            'accounts': [
                {
                    'id': row.id,
                    'name': row.name,
                    'code': row.code,
                    'account_type': row.account_type,
                    'current_balance': float(row.current_balance or 0),
                }
                for row in accounts
            ],
        },
        'receivables': {
            'gross_amount': _round_money(sum(float(row.gross_amount or 0) for row in receivables)),
            'amount_collected': _round_money(sum(float(row.amount_collected or 0) for row in receivables)),
            'balance_due': _round_money(sum(float(row.balance_due or 0) for row in receivables)),
            'open_count': len([row for row in receivables if _norm(row.status) in {'open', 'partial'}]),
        },
        'payables': {
            'gross_amount': _round_money(sum(float(row.gross_amount or 0) for row in payables)),
            'amount_paid': _round_money(sum(float(row.amount_paid or 0) for row in payables)),
            'balance_due': _round_money(sum(float(row.balance_due or 0) for row in payables)),
            'open_count': len([row for row in payables if _norm(row.status) in {'open', 'partial'}]),
        },
        'inventory': {
            'valuation': _round_money(sum(float(row.quantity_on_hand or 0) * float(row.average_cost or 0) for row in inventory_rows)),
            'item_count': len(inventory_rows),
        },
        'assets': {
            'asset_count': len(asset_rows),
            'acquisition_cost': _round_money(asset_cost),
            'accumulated_depreciation': _round_money(depreciation_total),
            'net_book_value': _round_money(asset_cost - depreciation_total),
        },
    }


def _build_financial_statements(db: Session, start_date: str | None = None, end_date: str | None = None, as_of_date: str | None = None):
    as_of = as_of_date or end_date or _today()
    chart_map = _chart_account_map(db)
    period_rows = _posted_journal_rows(db, start_date=start_date, end_date=end_date)
    as_of_rows = _posted_journal_rows(db, as_of_date=as_of)
    period_items = _group_lines(period_rows, chart_map)
    as_of_items = _group_lines(as_of_rows, chart_map)
    unposted_count = int(db.query(JournalEntry).filter(JournalEntry.status.in_(['draft', 'cancelled', 'voided', 'reversed'])).count() or 0)

    return {
        'period': {
            'start_date': start_date,
            'end_date': end_date,
            'as_of_date': as_of,
        },
        'profit_and_loss': _build_profit_and_loss(period_items),
        'balance_sheet': _build_balance_sheet(as_of_items),
        'cash_flow': _build_cash_flow_statement(db, start_date, end_date),
        'trial_balance': _build_trial_balance(as_of_items),
        'operational_supplement': _build_operational_supplement(db),
        'ledger_coverage': {
            'posted_journal_entries_in_period': len({entry.id for entry, _line in period_rows}),
            'posted_journal_lines_in_period': len(period_rows),
            'posted_journal_entries_as_of': len({entry.id for entry, _line in as_of_rows}),
            'posted_journal_lines_as_of': len(as_of_rows),
            'excluded_unposted_or_reversed_entries': unposted_count,
        },
        'notes': [
            'Profit & Loss, Balance Sheet, and Trial Balance are generated from non-draft journal entries.',
            'Cash Flow uses posted money-in and money-out transactions, with transfers shown separately at zero net cash effect.',
            'Operational supplement shows live subledger values for cash accounts, receivables, payables, inventory, and assets where legacy rows may not yet be fully journalized.',
        ],
    }


def _sum_settlements_by_record(db: Session, record_ids: list[int]) -> dict[int, float]:
    if not record_ids:
        return {}
    rows = (
        db.query(RecordSettlement.record_id, func.coalesce(func.sum(RecordSettlement.amount), 0))
        .filter(RecordSettlement.record_id.in_(record_ids))
        .group_by(RecordSettlement.record_id)
        .all()
    )
    return {int(row[0]): float(row[1] or 0) for row in rows}


def _build_aging_report(db: Session, as_of_date: str | None = None):
    as_of = _parse_iso_date(as_of_date) or datetime.utcnow()
    as_of_str = as_of.strftime('%Y-%m-%d')

    rows = db.query(Record).filter(Record.workflow_status == 'approved').order_by(Record.id.asc()).all()
    candidate_rows = [
        row for row in rows
        if _is_on_account(row.payment_method) and _norm(row.direction) in {'income', 'expense', 'asset', 'liability'}
    ]

    settlement_map = _sum_settlements_by_record(db, [int(row.id) for row in candidate_rows])

    receivables = []
    payables = []
    for row in candidate_rows:
        base_amount = abs(float(row.amount or 0))
        settled = float(settlement_map.get(int(row.id), 0))
        outstanding = round(base_amount - settled, 4)
        if outstanding <= 0:
            continue

        basis_date_text = row.due_date or row.transaction_date or as_of_str
        basis_date = _parse_iso_date(basis_date_text) or as_of
        age_days = max((as_of - basis_date).days, 0)
        item = {
            'record_id': row.id,
            'module_slug': row.module_slug,
            'name': row.name,
            'counterparty': row.counterparty,
            'reference_no': row.document_ref,
            'transaction_date': row.transaction_date,
            'due_date': row.due_date,
            'original_amount': round(base_amount, 4),
            'settled_amount': round(settled, 4),
            'outstanding_amount': round(outstanding, 4),
            'payment_method': row.payment_method,
            'age_days': age_days,
            'bucket': _age_bucket(age_days),
        }
        if _norm(row.direction) == 'income':
            receivables.append(item)
        else:
            payables.append(item)

    def summarize(items: list[dict]):
        buckets = {'0-30': 0.0, '31-60': 0.0, '61-90': 0.0, '91+': 0.0}
        for item in items:
            buckets[item['bucket']] += float(item['outstanding_amount'] or 0)
        return {
            'count': len(items),
            'total_outstanding': round(sum(float(x['outstanding_amount'] or 0) for x in items), 4),
            'bucket_totals': {k: round(v, 4) for k, v in buckets.items()},
        }

    receivables_sorted = sorted(receivables, key=lambda x: (-int(x['age_days']), -float(x['outstanding_amount'] or 0)))
    payables_sorted = sorted(payables, key=lambda x: (-int(x['age_days']), -float(x['outstanding_amount'] or 0)))

    return {
        'as_of_date': as_of_str,
        'receivables': {
            **summarize(receivables_sorted),
            'items': receivables_sorted,
        },
        'payables': {
            **summarize(payables_sorted),
            'items': payables_sorted,
        },
    }


def _build_close_readiness(exceptions: dict) -> dict:
    rules = [
        ('draft_records', 'Draft or pending records', 'critical', 'Approve, cancel, or correct records before closing the period.'),
        ('unreconciled_cashflow_accounts', 'Unreconciled cash/bank accounts', 'critical', 'Finish daily cash and bank reconciliation before closing.'),
        ('unposted_payroll_periods', 'Unposted payroll periods', 'warning', 'Post payroll or confirm it belongs outside this close period.'),
        ('ar_over_30_days', 'Receivables over 30 days', 'warning', 'Review collection notes, settlement status, or write-off/dispute handling.'),
        ('ap_over_30_days', 'Payables over 30 days', 'warning', 'Review supplier payment timing and hold reasons.'),
        ('low_stock_items', 'Low stock items', 'info', 'Review purchasing needs. This does not block financial close.'),
    ]
    penalties = {'critical': 24, 'warning': 10, 'info': 3}
    checks = []
    score = 100
    critical_count = 0
    warning_count = 0
    for key, label, severity, action in rules:
        value = int(exceptions.get(key) or 0)
        passed = value == 0
        if not passed:
            score -= min(40, penalties[severity] + max(0, value - 1))
            if severity == 'critical':
                critical_count += 1
            elif severity == 'warning':
                warning_count += 1
        checks.append({
            'key': key,
            'label': label,
            'value': value,
            'severity': severity,
            'passed': passed,
            'action': 'OK' if passed else action,
        })
    if critical_count:
        status = 'blocked'
        summary = 'Do not close yet. Critical reconciliation or approval work remains.'
    elif warning_count:
        status = 'review'
        summary = 'Close is possible after manager review of the warning items.'
    else:
        status = 'ready'
        summary = 'No close-blocking exceptions found for the selected period.'
    return {
        'status': status,
        'score': max(0, min(100, int(round(score)))),
        'can_close': critical_count == 0,
        'critical_count': critical_count,
        'warning_count': warning_count,
        'summary': summary,
        'checks': checks,
    }


def _build_management_report(db: Session, start_date: str | None = None, end_date: str | None = None):
    records_query = db.query(Record).filter(Record.workflow_status == 'approved')
    if start_date:
        records_query = records_query.filter(Record.transaction_date >= start_date)
    if end_date:
        records_query = records_query.filter(Record.transaction_date <= end_date)
    records = records_query.order_by(Record.id.asc()).all()

    totals = {
        'income': 0.0,
        'expense': 0.0,
        'asset': 0.0,
        'liability': 0.0,
    }
    module_breakdown: dict[str, dict] = {}
    for row in records:
        direction = _norm(row.direction)
        amount = float(row.amount or 0)
        slug = row.module_slug or 'unknown'
        module = module_breakdown.setdefault(
            slug,
            {'module_slug': slug, 'income': 0.0, 'expense': 0.0, 'asset': 0.0, 'liability': 0.0, 'net_income': 0.0},
        )
        if direction in totals:
            totals[direction] += amount
            module[direction] += amount
        module['net_income'] = round(float(module['income']) - float(module['expense']), 4)

    record_count = len(records)
    record_net_income = round(float(totals['income']) - float(totals['expense']), 4)

    sales_query = db.query(SaleOrder)
    if start_date:
        sales_query = sales_query.filter(SaleOrder.order_date >= start_date)
    if end_date:
        sales_query = sales_query.filter(SaleOrder.order_date <= end_date)
    sale_rows = sales_query.order_by(SaleOrder.id.asc()).all()

    posted_sales = [x for x in sale_rows if _norm(x.status) != 'voided']
    voided_sales = [x for x in sale_rows if _norm(x.status) == 'voided']

    inventory_rows = db.query(InventoryItem).order_by(InventoryItem.name.asc()).all()
    inventory_value = sum(float(row.quantity_on_hand or 0) * float(row.average_cost or 0) for row in inventory_rows)
    low_stock = [
        row for row in inventory_rows
        if float(row.quantity_on_hand or 0) <= float(row.reorder_level or 0)
    ]

    finance = cashflow_summary(db, target_date=end_date or _today())
    finance_cards = finance.get('summary_cards') or {}
    unreconciled_accounts = int(finance_cards.get('unreconciled_accounts') or 0)

    payroll_periods_q = db.query(PayrollPeriod)
    if start_date:
        payroll_periods_q = payroll_periods_q.filter(PayrollPeriod.period_end >= start_date)
    if end_date:
        payroll_periods_q = payroll_periods_q.filter(PayrollPeriod.period_end <= end_date)
    payroll_periods = payroll_periods_q.order_by(PayrollPeriod.id.asc()).all()
    payroll_period_ids = [int(row.id) for row in payroll_periods]

    payroll_gross = 0.0
    payroll_net = 0.0
    if payroll_period_ids:
        payroll_gross, payroll_net = (
            db.query(
                func.coalesce(func.sum(PayrollPeriodLine.gross_pay), 0),
                func.coalesce(func.sum(PayrollPeriodLine.net_pay), 0),
            )
            .filter(PayrollPeriodLine.payroll_period_id.in_(payroll_period_ids))
            .first()
        )
    else:
        # Backward compatibility for older payroll-run data.
        payroll_runs_q = db.query(PayrollRun)
        if start_date:
            payroll_runs_q = payroll_runs_q.filter(PayrollRun.period_end >= start_date)
        if end_date:
            payroll_runs_q = payroll_runs_q.filter(PayrollRun.period_end <= end_date)
        payroll_runs = payroll_runs_q.order_by(PayrollRun.id.asc()).all()
        payroll_run_ids = [int(row.id) for row in payroll_runs]
        if payroll_run_ids:
            payroll_gross, payroll_net = (
                db.query(
                    func.coalesce(func.sum(PayrollLine.gross_pay), 0),
                    func.coalesce(func.sum(PayrollLine.net_pay), 0),
                )
                .filter(PayrollLine.payroll_run_id.in_(payroll_run_ids))
                .first()
            )

    payroll_posted_count = len([row for row in payroll_periods if _norm(row.status) == 'posted'])

    bir_q = db.query(BIRBookEntry)
    period_start = start_date[:7] if start_date else None
    period_end = end_date[:7] if end_date else None
    if period_start:
        bir_q = bir_q.filter(BIRBookEntry.period_key >= period_start)
    if period_end:
        bir_q = bir_q.filter(BIRBookEntry.period_key <= period_end)
    bir_entries = bir_q.all()

    aging = _build_aging_report(db, end_date or _today())

    draft_records_q = db.query(Record).filter(Record.workflow_status != 'approved')
    if start_date:
        draft_records_q = draft_records_q.filter(Record.transaction_date >= start_date)
    if end_date:
        draft_records_q = draft_records_q.filter(Record.transaction_date <= end_date)
    draft_records_count = int(draft_records_q.count() or 0)

    settlements_recent_rows = db.query(RecordSettlement).order_by(RecordSettlement.id.desc()).limit(20).all()

    def _date_between(value: str | None) -> bool:
        if not value:
            return False
        if start_date and value < start_date:
            return False
        if end_date and value > end_date:
            return False
        return True

    booking_rows = db.query(Booking).order_by(Booking.id.asc()).all()
    room_revenue_by_type: dict[str, float] = {}
    room_revenue_by_channel: dict[str, dict] = {}
    arrivals = 0
    departures = 0
    in_house = 0
    cancelled = 0
    no_show = 0
    for row in booking_rows:
        if row.status == 'checked_in':
            in_house += 1
        if row.status == 'cancelled':
            cancelled += 1
        if _norm(row.status) in {'no_show', 'noshow'}:
            no_show += 1

        if _date_between(row.check_in):
            arrivals += 1
            room_type = (row.room_type or 'Unassigned').strip() or 'Unassigned'
            channel = (row.channel or 'Walk-in').strip() or 'Walk-in'
            gross = float(row.gross_amount or 0)
            room_revenue_by_type[room_type] = room_revenue_by_type.get(room_type, 0.0) + gross
            item = room_revenue_by_channel.setdefault(channel, {'channel': channel, 'bookings': 0, 'gross_revenue': 0.0})
            item['bookings'] += 1
            item['gross_revenue'] += gross
        if _date_between(row.check_out):
            departures += 1

    channel_payout_rows = db.query(ChannelPayout).order_by(ChannelPayout.id.asc()).all()
    channel_payout_summary: dict[str, dict] = {}
    for row in channel_payout_rows:
        if not (_date_between(row.expected_payout_date) or _date_between(row.actual_payout_date)):
            continue
        channel = (row.channel or 'Unassigned').strip() or 'Unassigned'
        item = channel_payout_summary.setdefault(channel, {
            'channel': channel,
            'gross_amount': 0.0,
            'commission_amount': 0.0,
            'net_amount': 0.0,
            'paid_net_amount': 0.0,
        })
        item['gross_amount'] += float(row.gross_amount or 0)
        item['commission_amount'] += float(row.commission_amount or 0)
        item['net_amount'] += float(row.net_amount or 0)
        if _norm(row.status) == 'paid':
            item['paid_net_amount'] += float(row.net_amount or 0)

    sales_line_query = (
        db.query(
            SaleOrderLine.item_name,
            SaleOrderLine.quantity,
            SaleOrderLine.line_total,
            SaleOrder.order_date,
        )
        .join(SaleOrder, SaleOrderLine.sale_order_id == SaleOrder.id)
        .filter(SaleOrder.status != 'voided')
    )
    if start_date:
        sales_line_query = sales_line_query.filter(SaleOrder.order_date >= start_date)
    if end_date:
        sales_line_query = sales_line_query.filter(SaleOrder.order_date <= end_date)
    sales_line_rows = sales_line_query.all()
    sales_by_item: dict[str, dict] = {}
    for line in sales_line_rows:
        item_name = (line.item_name or '').strip() or 'Unnamed Item'
        item = sales_by_item.setdefault(item_name, {'item_name': item_name, 'quantity': 0.0, 'net_sales': 0.0})
        item['quantity'] += float(line.quantity or 0)
        item['net_sales'] += float(line.line_total or 0)

    fnb_income_rows = [
        row for row in records
        if _norm(row.direction) == 'income' and _norm(row.module_slug) in {'restaurant', 'breakfast', 'cafe', 'bar'}
    ]
    sales_by_outlet: dict[str, float] = {}
    for row in fnb_income_rows:
        outlet = (row.module_slug or 'restaurant').strip()
        sales_by_outlet[outlet] = sales_by_outlet.get(outlet, 0.0) + float(row.amount or 0)

    staff_meal_rows = db.query(StaffMealLog).order_by(StaffMealLog.id.desc()).all()
    if start_date or end_date:
        staff_meal_rows = [row for row in staff_meal_rows if _date_between(row.meal_date)]

    movement_rows = db.query(StockMovement).order_by(StockMovement.id.asc()).all()
    movement_in_qty = 0.0
    movement_out_qty = 0.0
    movement_in_cost = 0.0
    movement_out_cost = 0.0
    waste_rows = []
    for row in movement_rows:
        if start_date and (row.movement_date or '') < start_date:
            continue
        if end_date and (row.movement_date or '') > end_date:
            continue
        qty = float(row.quantity or 0)
        cost = float(row.total_cost or 0)
        if _norm(row.movement_type) == 'in':
            movement_in_qty += qty
            movement_in_cost += cost
        else:
            movement_out_qty += qty
            movement_out_cost += cost
        reason = _norm(row.reason)
        if 'waste' in reason or 'spoil' in reason:
            waste_rows.append(row)

    pr_rows = db.query(PurchaseRequest).order_by(PurchaseRequest.id.desc()).all()
    po_rows = db.query(PurchaseOrder).order_by(PurchaseOrder.id.desc()).all()
    receiving_rows = db.query(ReceivingRecord).order_by(ReceivingRecord.id.desc()).all()
    if start_date or end_date:
        pr_rows = [row for row in pr_rows if _date_between(row.request_date)]
        po_rows = [row for row in po_rows if _date_between(row.po_date)]
        receiving_rows = [row for row in receiving_rows if _date_between(row.receiving_date)]

    supplier_totals: dict[str, float] = {}
    for row in receiving_rows:
        supplier = db.get(Supplier, int(row.supplier_id)) if row.supplier_id else None
        supplier_name = supplier.name if supplier else 'Unassigned'
        supplier_totals[supplier_name] = supplier_totals.get(supplier_name, 0.0) + float(row.total_amount or 0)

    attendance_rows = db.query(AttendanceEntry).order_by(AttendanceEntry.id.desc()).all()
    if start_date or end_date:
        attendance_rows = [row for row in attendance_rows if _date_between(row.work_date)]
    attendance_summary = {
        'rows': len(attendance_rows),
        'absent_count': len([row for row in attendance_rows if bool(row.is_absent)]),
        'overtime_hours': round(sum(float(row.overtime_hours or 0) for row in attendance_rows), 4),
        'night_diff_hours': round(sum(float(row.night_diff_hours or 0) for row in attendance_rows), 4),
    }

    payroll_department_rows = (
        db.query(
            PayrollPeriodLine.department,
            func.coalesce(func.sum(PayrollPeriodLine.gross_pay), 0),
            func.coalesce(func.sum(PayrollPeriodLine.net_pay), 0),
        )
        .filter(PayrollPeriodLine.payroll_period_id.in_(payroll_period_ids) if payroll_period_ids else False)
        .group_by(PayrollPeriodLine.department)
        .all()
    ) if payroll_period_ids else []

    bir_lock_rows = (
        db.query(PeriodLock)
        .filter(PeriodLock.scope == 'bir')
        .order_by(PeriodLock.period_key.desc(), PeriodLock.id.desc())
        .limit(50)
        .all()
    )

    exceptions = {
        'draft_records': draft_records_count,
        'unposted_payroll_periods': len(payroll_periods) - payroll_posted_count,
        'unreconciled_cashflow_accounts': int(unreconciled_accounts),
        'low_stock_items': len(low_stock),
        'ar_over_30_days': len([x for x in aging['receivables']['items'] if int(x['age_days']) > 30]),
        'ap_over_30_days': len([x for x in aging['payables']['items'] if int(x['age_days']) > 30]),
    }

    return {
        'period': {
            'start_date': start_date,
            'end_date': end_date,
        },
        'kpis': {
            'record_count': record_count,
            'income_total': round(float(totals['income']), 4),
            'expense_total': round(float(totals['expense']), 4),
            'net_income': record_net_income,
            'sales_count': len(posted_sales),
            'voided_sales_count': len(voided_sales),
            'sales_net_total': round(sum(float(row.net_amount or 0) for row in posted_sales), 4),
            'sales_cogs_total': round(sum(float(row.cogs_amount or 0) for row in posted_sales), 4),
            'inventory_value': round(float(inventory_value), 4),
            'low_stock_count': len(low_stock),
            'payroll_periods': len(payroll_periods),
            'payroll_posted_periods': payroll_posted_count,
            'payroll_gross': round(float(payroll_gross or 0), 4),
            'payroll_net': round(float(payroll_net or 0), 4),
            'cash_on_hand': round(float(finance_cards.get('total_cash_on_hand') or 0), 4),
            'bank_balance': round(float(finance_cards.get('total_bank_balance') or 0), 4),
            'money_in_today': round(float(finance_cards.get('todays_money_in') or 0), 4),
            'money_out_today': round(float(finance_cards.get('todays_money_out') or 0), 4),
            'ar_outstanding': float(aging['receivables']['total_outstanding']),
            'ap_outstanding': float(aging['payables']['total_outstanding']),
        },
        'module_breakdown': sorted(module_breakdown.values(), key=lambda x: x['module_slug']),
        'cashflow': {
            'summary_cards': finance_cards,
            'accounts_requiring_reconciliation': finance.get('accounts_requiring_reconciliation') or [],
            'recent_variances': finance.get('recent_variances') or [],
        },
        'rooms': {
            'arrivals': arrivals,
            'departures': departures,
            'in_house': in_house,
            'cancelled': cancelled,
            'no_show': no_show,
            'revenue_by_room_type': [
                {'room_type': key, 'gross_revenue': round(value, 4)}
                for key, value in sorted(room_revenue_by_type.items(), key=lambda item: item[1], reverse=True)
            ],
            'revenue_by_channel': [
                {
                    'channel': row['channel'],
                    'bookings': int(row['bookings']),
                    'gross_revenue': round(float(row['gross_revenue']), 4),
                }
                for row in sorted(room_revenue_by_channel.values(), key=lambda item: item['gross_revenue'], reverse=True)
            ],
        },
        'channels': {
            'payouts': [
                {
                    'channel': row['channel'],
                    'gross_amount': round(float(row['gross_amount']), 4),
                    'commission_amount': round(float(row['commission_amount']), 4),
                    'net_amount': round(float(row['net_amount']), 4),
                    'paid_net_amount': round(float(row['paid_net_amount']), 4),
                    'variance': round(float(row['net_amount']) - float(row['paid_net_amount']), 4),
                }
                for row in sorted(channel_payout_summary.values(), key=lambda item: item['net_amount'], reverse=True)
            ],
        },
        'fnb': {
            'sales_by_outlet': [
                {'outlet': key, 'sales': round(value, 4)}
                for key, value in sorted(sales_by_outlet.items(), key=lambda item: item[1], reverse=True)
            ],
            'sales_by_item': sorted(sales_by_item.values(), key=lambda item: item['net_sales'], reverse=True)[:30],
            'staff_meals': {
                'count': len(staff_meal_rows),
                'cost_total': round(sum(float(row.cogs_amount or 0) for row in staff_meal_rows), 4),
            },
            'waste_movements': {
                'count': len(waste_rows),
                'cost_total': round(sum(float(row.total_cost or 0) for row in waste_rows), 4),
            },
        },
        'inventory': {
            'stock_on_hand_count': len(inventory_rows),
            'valuation': round(float(inventory_value), 4),
            'low_stock_items': [
                {
                    'item_id': row.id,
                    'item_name': row.name,
                    'quantity_on_hand': float(row.quantity_on_hand or 0),
                    'reorder_level': float(row.reorder_level or 0),
                    'unit': row.unit,
                }
                for row in sorted(low_stock, key=lambda item: float(item.quantity_on_hand or 0))[:40]
            ],
            'movement_totals': {
                'in_qty': round(movement_in_qty, 4),
                'out_qty': round(movement_out_qty, 4),
                'in_cost': round(movement_in_cost, 4),
                'out_cost': round(movement_out_cost, 4),
            },
        },
        'procurement': {
            'open_pr_count': len([row for row in pr_rows if _norm(row.status) in {'draft', 'submitted', 'approved'}]),
            'open_po_count': len([row for row in po_rows if _norm(row.status) in {'draft', 'issued', 'partially_received'}]),
            'partially_received_po_count': len([row for row in po_rows if _norm(row.status) == 'partially_received']),
            'receiving_posted_count': len([row for row in receiving_rows if _norm(row.status) == 'posted']),
            'supplier_purchase_totals': [
                {'supplier_name': key, 'total_amount': round(value, 4)}
                for key, value in sorted(supplier_totals.items(), key=lambda item: item[1], reverse=True)
            ],
        },
        'payroll_labor': {
            'payroll_by_department': [
                {
                    'department': row[0] or 'Unassigned',
                    'gross_pay': round(float(row[1] or 0), 4),
                    'net_pay': round(float(row[2] or 0), 4),
                }
                for row in payroll_department_rows
            ],
            'attendance_summary': attendance_summary,
        },
        'compliance': {
            'bir_entry_count': len(bir_entries),
            'bir_total_amount': round(sum(float(x.amount or 0) for x in bir_entries), 4),
            'bir_locks': [
                {
                    'period_key': row.period_key,
                    'is_locked': bool(row.is_locked),
                    'scope': row.scope,
                    'locked_by': row.locked_by,
                    'notes': row.notes,
                    'updated_at': row.updated_at.isoformat() if row.updated_at else None,
                }
                for row in bir_lock_rows
            ],
        },
        'exceptions': exceptions,
        'close_readiness': _build_close_readiness(exceptions),
        'settlements_recent': [
            {
                'id': row.id,
                'record_id': row.record_id,
                'settlement_date': row.settlement_date,
                'amount': float(row.amount or 0),
                'payment_method': row.payment_method,
                'reference_no': row.reference_no,
                'created_by': row.created_by,
                'created_at': row.created_at.isoformat() if row.created_at else None,
            }
            for row in settlements_recent_rows
        ],
        'aging': aging,
    }


def _serialize_settlement(db: Session, row: RecordSettlement) -> dict:
    record = db.get(Record, int(row.record_id))
    return {
        'id': row.id,
        'record_id': row.record_id,
        'record_name': record.name if record else None,
        'record_module_slug': record.module_slug if record else None,
        'record_direction': record.direction if record else None,
        'settlement_date': row.settlement_date,
        'amount': float(row.amount or 0),
        'payment_method': row.payment_method,
        'reference_no': row.reference_no,
        'notes': row.notes,
        'created_by': row.created_by,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get('/management')
def management_report(
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('reports.view')),
):
    return _build_management_report(db, start_date=start_date, end_date=end_date)


@router.get('/financial-statements')
def financial_statements(
    start_date: str | None = None,
    end_date: str | None = None,
    as_of_date: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('reports.view')),
):
    return _build_financial_statements(db, start_date=start_date, end_date=end_date, as_of_date=as_of_date)


@router.get('/management.csv')
def management_report_csv(
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('reports.view')),
):
    report = _build_management_report(db, start_date=start_date, end_date=end_date)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['section', 'metric', 'value'])
    for key, value in report.get('kpis', {}).items():
        writer.writerow(['kpi', key, value])
    for key, value in report.get('exceptions', {}).items():
        writer.writerow(['exception', key, value])
    for key, value in (report.get('cashflow', {}).get('summary_cards') or {}).items():
        writer.writerow(['cashflow_total', key, value])
    compliance = report.get('compliance') or {}
    writer.writerow(['compliance', 'bir_entry_count', compliance.get('bir_entry_count', 0)])
    writer.writerow(['compliance', 'bir_total_amount', compliance.get('bir_total_amount', 0)])

    for row in report.get('module_breakdown') or []:
        slug = row.get('module_slug')
        writer.writerow(['module', f'{slug}.income', row.get('income', 0)])
        writer.writerow(['module', f'{slug}.expense', row.get('expense', 0)])
        writer.writerow(['module', f'{slug}.asset', row.get('asset', 0)])
        writer.writerow(['module', f'{slug}.liability', row.get('liability', 0)])
        writer.writerow(['module', f'{slug}.net_income', row.get('net_income', 0)])

    csv_content = output.getvalue()
    filename_start = (start_date or 'all').replace('-', '')
    filename_end = (end_date or 'latest').replace('-', '')
    return Response(
        content=csv_content,
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="management-report-{filename_start}-{filename_end}.csv"'},
    )


@router.get('/ar-ap-aging')
def ar_ap_aging(
    as_of_date: str | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_permissions('reports.view')),
):
    return _build_aging_report(db, as_of_date=as_of_date)


@router.get('/settlements')
def list_settlements(
    record_id: int | None = None,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    user=Depends(require_permissions('reports.view')),
):
    q = db.query(RecordSettlement)
    if record_id:
        q = q.filter(RecordSettlement.record_id == int(record_id))
    rows = q.order_by(RecordSettlement.id.desc()).limit(limit).all()
    return [_serialize_settlement(db, row) for row in rows]


@router.post('/settlements')
def create_settlement(
    payload: RecordSettlementCreate,
    db: Session = Depends(get_db),
    user=Depends(require_any_permissions('cashflow.money_in', 'cashflow.money_out')),
):
    record = db.get(Record, int(payload.record_id))
    if not record:
        raise HTTPException(status_code=404, detail=f'Record {payload.record_id} not found.')
    if record.workflow_status != 'approved':
        raise HTTPException(status_code=400, detail='Only approved records can be settled.')
    if not _is_on_account(record.payment_method):
        raise HTTPException(status_code=400, detail='Record is not marked as on-account/credit.')

    amount = float(payload.amount or 0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail='Settlement amount must be greater than zero.')

    settled_total = float(
        db.query(func.coalesce(func.sum(RecordSettlement.amount), 0))
        .filter(RecordSettlement.record_id == record.id)
        .scalar()
        or 0
    )
    outstanding = round(abs(float(record.amount or 0)) - settled_total, 4)
    if outstanding <= 0:
        raise HTTPException(status_code=400, detail='Record is already fully settled.')
    if amount > outstanding + 0.0001:
        raise HTTPException(status_code=400, detail=f'Settlement exceeds outstanding amount ({outstanding}).')

    row = RecordSettlement(
        record_id=record.id,
        settlement_date=payload.settlement_date or _today(),
        amount=amount,
        payment_method=payload.payment_method or record.payment_method,
        reference_no=payload.reference_no,
        notes=payload.notes,
        created_by=getattr(user, 'username', None),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    new_settled_total = float(
        db.query(func.coalesce(func.sum(RecordSettlement.amount), 0))
        .filter(RecordSettlement.record_id == record.id)
        .scalar()
        or 0
    )
    return {
        'settlement': _serialize_settlement(db, row),
        'outstanding_before': round(outstanding, 4),
        'outstanding_after': round(abs(float(record.amount or 0)) - new_settled_total, 4),
    }

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    AccountTransfer,
    CashReconciliation,
    CashReconciliationLine,
    CashflowTemplate,
    FinancialAccount,
    JournalEntry,
    MoneyTransaction,
    Payable,
    Receivable,
    ReceivableAdjustment,
)
from app.schemas.cashflow import (
    AccountTransferUpdate,
    AccountTransferCreate,
    CashflowActionPayload,
    CashReconciliationCreate,
    CashflowTemplateCreate,
    CashflowTemplateUpdate,
    FinancialAccountCreate,
    FinancialAccountUpdate,
    MoneyTransactionCreate,
    MoneyTransactionUpdate,
    PayableCreate,
    PayablePayPayload,
    ReceivableCollectPayload,
    ReceivableCreate,
)
from app.services.bir_service import ensure_date_unlocked
from app.services.code_service import ensure_editable_after_create, generate_code
from app.services.restaurant_service import create_approved_record


FINANCIAL_ACCOUNT_TYPES = {'cash_drawer', 'petty_cash', 'safe', 'bank', 'ewallet'}
STRICT_CASH_TYPES = {'cash_drawer', 'petty_cash', 'safe', 'ewallet'}

DEFAULT_FINANCIAL_ACCOUNTS = [
    {
        'name': 'Reception Vault',
        'code': 'DRW-RECEPTION',
        'account_type': 'cash_drawer',
        'subtype': 'front_desk_drawer',
        'department': 'rooms',
        'requires_daily_reconciliation': True,
    },
    {
        'name': 'Chiller',
        'code': 'DRW-CHILLER',
        'account_type': 'cash_drawer',
        'subtype': 'chiller_drawer',
        'department': 'inventory',
        'requires_daily_reconciliation': True,
    },
    {
        'name': 'Pool Cafe',
        'code': 'DRW-POOL-CAFE',
        'account_type': 'cash_drawer',
        'subtype': 'pool_cafe_drawer',
        'department': 'restaurant',
        'requires_daily_reconciliation': True,
    },
    {
        'name': 'Cafe',
        'code': 'DRW-CAFE',
        'account_type': 'cash_drawer',
        'subtype': 'cafe_drawer',
        'department': 'restaurant',
        'requires_daily_reconciliation': True,
    },
    {
        'name': 'Bar',
        'code': 'DRW-BAR',
        'account_type': 'cash_drawer',
        'subtype': 'bar_drawer',
        'department': 'restaurant',
        'requires_daily_reconciliation': True,
    },
    {
        'name': 'Main Safe',
        'code': 'SAFE-MAIN',
        'account_type': 'safe',
        'subtype': 'main_safe',
        'department': 'finance',
        'requires_daily_reconciliation': True,
    },
    {
        'name': 'Petty Cash',
        'code': 'PETTY-CASH',
        'account_type': 'petty_cash',
        'subtype': 'general_petty_cash',
        'department': 'finance',
        'requires_daily_reconciliation': True,
    },
    {
        'name': 'Bank Account 1',
        'code': 'BNK-01',
        'account_type': 'bank',
        'subtype': 'main_operating_bank',
        'department': 'finance',
        'requires_daily_reconciliation': True,
    },
    {
        'name': 'Bank Account 2',
        'code': 'BNK-02',
        'account_type': 'bank',
        'subtype': 'secondary_bank',
        'department': 'finance',
        'requires_daily_reconciliation': True,
    },
    {
        'name': 'Bank Account 3',
        'code': 'BNK-03',
        'account_type': 'bank',
        'subtype': 'reserve_bank',
        'department': 'finance',
        'requires_daily_reconciliation': True,
    },
    {
        'name': 'Bank Account 4',
        'code': 'BNK-04',
        'account_type': 'bank',
        'subtype': 'payroll_bank',
        'department': 'finance',
        'requires_daily_reconciliation': True,
    },
    {
        'name': 'GCash',
        'code': 'EWL-GCASH',
        'account_type': 'ewallet',
        'subtype': 'gcash',
        'department': 'finance',
        'requires_daily_reconciliation': True,
    },
]


def _today() -> str:
    return datetime.utcnow().strftime('%Y-%m-%d')


def _normalize(value: str | None) -> str:
    return (value or '').strip().lower()


def _code(value: str | None) -> str:
    return (value or '').strip().upper()


def _safe_date(value: str | None) -> str:
    return (value or '').strip() or _today()


def _as_float(value, default: float = 0.0) -> float:
    try:
        return float(value if value is not None else default)
    except Exception:
        return float(default)


def _serialize_account(row: FinancialAccount) -> dict:
    return {
        'id': row.id,
        'name': row.name,
        'code': row.code,
        'account_type': row.account_type,
        'subtype': row.subtype,
        'currency': row.currency,
        'is_active': bool(row.is_active),
        'requires_daily_reconciliation': bool(row.requires_daily_reconciliation),
        'opening_balance': float(row.opening_balance or 0),
        'current_balance': float(row.current_balance or 0),
        'department': row.department,
        'notes': row.notes,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_money_transaction(row: MoneyTransaction) -> dict:
    account = row.financial_account
    return {
        'id': row.id,
        'transaction_date': row.transaction_date,
        'direction': row.direction,
        'financial_account_id': row.financial_account_id,
        'financial_account_name': account.name if account else None,
        'financial_account_code': account.code if account else None,
        'module': row.module,
        'category': row.category,
        'subcategory': row.subcategory,
        'level3_item': row.level3_item,
        'amount': float(row.amount or 0),
        'payment_method': row.payment_method,
        'reference_no': row.reference_no,
        'counterparty_name': row.counterparty_name,
        'notes': row.notes,
        'linked_record_type': row.linked_record_type,
        'linked_record_id': row.linked_record_id,
        'receivable_id': row.receivable_id,
        'payable_id': row.payable_id,
        'bir_include': bool(row.bir_include),
        'journal_entry_id': row.journal_entry_id,
        'status': row.status,
        'reversed_from_id': row.reversed_from_id,
        'is_reversed': bool(row.is_reversed),
        'posted_at': row.posted_at,
        'created_by': row.created_by,
        'approved_by': row.approved_by,
        'external_source': row.external_source,
        'external_id': row.external_id,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_transfer(row: AccountTransfer) -> dict:
    return {
        'id': row.id,
        'transfer_date': row.transfer_date,
        'from_account_id': row.from_account_id,
        'from_account_name': row.from_account.name if row.from_account else None,
        'from_account_code': row.from_account.code if row.from_account else None,
        'to_account_id': row.to_account_id,
        'to_account_name': row.to_account.name if row.to_account else None,
        'to_account_code': row.to_account.code if row.to_account else None,
        'amount': float(row.amount or 0),
        'reference_no': row.reference_no,
        'notes': row.notes,
        'journal_entry_id': row.journal_entry_id,
        'status': row.status,
        'reversed_from_id': row.reversed_from_id,
        'is_reversed': bool(row.is_reversed),
        'posted_at': row.posted_at,
        'created_by': row.created_by,
        'approved_by': row.approved_by,
        'external_source': row.external_source,
        'external_id': row.external_id,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_reconciliation(row: CashReconciliation) -> dict:
    account = row.financial_account
    return {
        'id': row.id,
        'financial_account_id': row.financial_account_id,
        'financial_account_name': account.name if account else None,
        'financial_account_code': account.code if account else None,
        'reconciliation_date': row.reconciliation_date,
        'shift_name': row.shift_name,
        'opening_balance': float(row.opening_balance or 0),
        'expected_in': float(row.expected_in or 0),
        'expected_out': float(row.expected_out or 0),
        'expected_closing': float(row.expected_closing or 0),
        'actual_counted': float(row.actual_counted or 0),
        'variance': float(row.variance or 0),
        'status': row.status,
        'counted_by': row.counted_by,
        'approved_by': row.approved_by,
        'posted_at': row.posted_at,
        'closed_at': row.closed_at,
        'locked_at': row.locked_at,
        'notes': row.notes,
        'lines': [
            {
                'id': line.id,
                'line_label': line.line_label,
                'amount': float(line.amount or 0),
                'notes': line.notes,
                'sort_order': line.sort_order,
            }
            for line in sorted(row.lines or [], key=lambda x: (x.sort_order, x.id))
        ],
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_receivable(row: Receivable) -> dict:
    adjustments = list(row.adjustments or [])
    sorted_adjustments = sorted(adjustments, key=lambda item: (item.adjustment_date or '', item.id or 0))
    latest_adjustment = sorted_adjustments[-1] if sorted_adjustments else None
    adjustments_total = round(sum(float(item.amount or 0) for item in adjustments), 4)
    return {
        'id': row.id,
        'source_type': row.source_type,
        'source_id': row.source_id,
        'counterparty_name': row.counterparty_name,
        'receivable_type': row.receivable_type,
        'transaction_date': row.transaction_date,
        'due_date': row.due_date,
        'gross_amount': float(row.gross_amount or 0),
        'amount_collected': float(row.amount_collected or 0),
        'balance_due': float(row.balance_due or 0),
        'status': row.status,
        'posted_at': row.posted_at,
        'closed_at': row.closed_at,
        'notes': row.notes,
        'bir_include': bool(row.bir_include),
        'external_source': row.external_source,
        'external_id': row.external_id,
        'adjustment_amount': adjustments_total,
        'adjustments_total': adjustments_total,
        'adjustments_count': len(adjustments),
        'latest_adjustment_date': latest_adjustment.adjustment_date if latest_adjustment else None,
        'latest_adjustment_source_type': latest_adjustment.source_type if latest_adjustment else None,
        'adjustments': [
            {
                'id': item.id,
                'adjustment_date': item.adjustment_date,
                'amount': float(item.amount or 0),
                'source_type': item.source_type,
                'source_id': item.source_id,
                'external_source': item.external_source,
                'external_id': item.external_id,
                'notes': item.notes,
            }
            for item in adjustments
        ],
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_payable(row: Payable) -> dict:
    return {
        'id': row.id,
        'source_type': row.source_type,
        'source_id': row.source_id,
        'supplier_name': row.supplier_name,
        'payable_type': row.payable_type,
        'bill_date': row.bill_date,
        'due_date': row.due_date,
        'gross_amount': float(row.gross_amount or 0),
        'amount_paid': float(row.amount_paid or 0),
        'balance_due': float(row.balance_due or 0),
        'status': row.status,
        'posted_at': row.posted_at,
        'closed_at': row.closed_at,
        'notes': row.notes,
        'bir_include': bool(row.bir_include),
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_template(row: CashflowTemplate) -> dict:
    return {
        'id': row.id,
        'name': row.name,
        'direction': row.direction,
        'default_module': row.default_module,
        'default_category': row.default_category,
        'default_subcategory': row.default_subcategory,
        'default_level3_item': row.default_level3_item,
        'default_account_id': row.default_account_id,
        'default_account_name': row.default_account.name if row.default_account else None,
        'default_payment_method': row.default_payment_method,
        'default_bir_include': bool(row.default_bir_include),
        'default_notes': row.default_notes,
        'is_active': bool(row.is_active),
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def ensure_default_financial_accounts(db: Session) -> int:
    created = 0
    existing_codes = {row.code for row in db.query(FinancialAccount.code).all()}
    for item in DEFAULT_FINANCIAL_ACCOUNTS:
        code = _code(item.get('code'))
        if code in existing_codes:
            continue
        row = FinancialAccount(
            name=item.get('name') or code,
            code=code,
            account_type=item.get('account_type') or 'cash_drawer',
            subtype=item.get('subtype'),
            currency='PHP',
            is_active=True,
            requires_daily_reconciliation=bool(item.get('requires_daily_reconciliation', True)),
            opening_balance=0,
            current_balance=0,
            department=item.get('department'),
        )
        db.add(row)
        created += 1
    if created:
        db.commit()
    return created


def recompute_all_financial_balances(db: Session):
    accounts = db.query(FinancialAccount).all()
    by_id = {row.id: row for row in accounts}
    balances = {row.id: float(row.opening_balance or 0) for row in accounts}

    tx_rows = db.query(MoneyTransaction).order_by(MoneyTransaction.id.asc()).all()
    for row in tx_rows:
        account_id = int(row.financial_account_id)
        if account_id not in balances:
            continue
        if _normalize(row.direction) == 'in':
            balances[account_id] += float(row.amount or 0)
        else:
            balances[account_id] -= float(row.amount or 0)

    transfer_rows = db.query(AccountTransfer).order_by(AccountTransfer.id.asc()).all()
    for row in transfer_rows:
        amount = float(row.amount or 0)
        if row.from_account_id in balances:
            balances[row.from_account_id] -= amount
        if row.to_account_id in balances:
            balances[row.to_account_id] += amount

    for account_id, balance in balances.items():
        target = by_id.get(account_id)
        if not target:
            continue
        target.current_balance = round(balance, 4)
        db.add(target)
    db.commit()


def _account_balances_as_of(db: Session, as_of_date: str | None = None) -> dict[int, float]:
    balances = {row.id: float(row.opening_balance or 0) for row in db.query(FinancialAccount).all()}

    tx_q = db.query(MoneyTransaction)
    if as_of_date:
        tx_q = tx_q.filter(MoneyTransaction.transaction_date <= as_of_date)
    for row in tx_q.all():
        account_id = int(row.financial_account_id)
        if account_id not in balances:
            continue
        if _normalize(row.direction) == 'in':
            balances[account_id] += float(row.amount or 0)
        else:
            balances[account_id] -= float(row.amount or 0)

    tr_q = db.query(AccountTransfer)
    if as_of_date:
        tr_q = tr_q.filter(AccountTransfer.transfer_date <= as_of_date)
    for row in tr_q.all():
        amount = float(row.amount or 0)
        if row.from_account_id in balances:
            balances[row.from_account_id] -= amount
        if row.to_account_id in balances:
            balances[row.to_account_id] += amount

    return balances


def _account_opening_balance_at(db: Session, account_id: int, on_date: str) -> float:
    account = db.get(FinancialAccount, int(account_id))
    if not account:
        return 0.0
    base = float(account.opening_balance or 0)

    in_total = (
        db.query(func.sum(MoneyTransaction.amount))
        .filter(
            MoneyTransaction.financial_account_id == account.id,
            MoneyTransaction.transaction_date < on_date,
            MoneyTransaction.direction == 'in',
        )
        .scalar()
        or 0
    )
    out_total = (
        db.query(func.sum(MoneyTransaction.amount))
        .filter(
            MoneyTransaction.financial_account_id == account.id,
            MoneyTransaction.transaction_date < on_date,
            MoneyTransaction.direction == 'out',
        )
        .scalar()
        or 0
    )
    transfer_in = (
        db.query(func.sum(AccountTransfer.amount))
        .filter(AccountTransfer.to_account_id == account.id, AccountTransfer.transfer_date < on_date)
        .scalar()
        or 0
    )
    transfer_out = (
        db.query(func.sum(AccountTransfer.amount))
        .filter(AccountTransfer.from_account_id == account.id, AccountTransfer.transfer_date < on_date)
        .scalar()
        or 0
    )
    return round(base + float(in_total) - float(out_total) + float(transfer_in) - float(transfer_out), 4)


def _resolve_bir_status(include_bir: bool) -> str:
    return 'ready_for_bir' if include_bir else 'internal_only'


def _payment_method_default(account: FinancialAccount, direction: str) -> str:
    account_type = _normalize(account.account_type)
    if account_type == 'bank':
        return 'bank_transfer'
    if account_type == 'ewallet':
        return 'e_wallet'
    return 'cash' if _normalize(direction) in {'in', 'out'} else 'cash'


def _preferred_finance_paths(direction: str, category: str | None, subcategory: str | None, level3: str | None):
    if category and subcategory and level3:
        return [(category, subcategory, level3)]
    if _normalize(direction) == 'in':
        return [('Cash', 'Cash Movements', 'Cash In')]
    return [('Cash', 'Cash Movements', 'Cash Out')]


def list_financial_accounts(
    db: Session,
    *,
    account_type: str | None = None,
    only_active: bool = False,
    on_date: str | None = None,
):
    ensure_default_financial_accounts(db)
    target_date = on_date or _today()

    q = db.query(FinancialAccount)
    if account_type:
        q = q.filter(FinancialAccount.account_type == _normalize(account_type))
    if only_active:
        q = q.filter(FinancialAccount.is_active == True)

    rows = q.order_by(FinancialAccount.account_type.asc(), FinancialAccount.name.asc()).all()

    tx_in = (
        db.query(MoneyTransaction.financial_account_id, func.sum(MoneyTransaction.amount))
        .filter(MoneyTransaction.transaction_date == target_date, MoneyTransaction.direction == 'in')
        .group_by(MoneyTransaction.financial_account_id)
        .all()
    )
    tx_out = (
        db.query(MoneyTransaction.financial_account_id, func.sum(MoneyTransaction.amount))
        .filter(MoneyTransaction.transaction_date == target_date, MoneyTransaction.direction == 'out')
        .group_by(MoneyTransaction.financial_account_id)
        .all()
    )
    tr_in = (
        db.query(AccountTransfer.to_account_id, func.sum(AccountTransfer.amount))
        .filter(AccountTransfer.transfer_date == target_date)
        .group_by(AccountTransfer.to_account_id)
        .all()
    )
    tr_out = (
        db.query(AccountTransfer.from_account_id, func.sum(AccountTransfer.amount))
        .filter(AccountTransfer.transfer_date == target_date)
        .group_by(AccountTransfer.from_account_id)
        .all()
    )
    recon_today = (
        db.query(CashReconciliation.financial_account_id, func.max(CashReconciliation.id))
        .filter(CashReconciliation.reconciliation_date == target_date)
        .group_by(CashReconciliation.financial_account_id)
        .all()
    )

    in_map = {int(row[0]): float(row[1] or 0) for row in tx_in}
    out_map = {int(row[0]): float(row[1] or 0) for row in tx_out}
    tr_in_map = {int(row[0]): float(row[1] or 0) for row in tr_in}
    tr_out_map = {int(row[0]): float(row[1] or 0) for row in tr_out}
    recon_ids = {int(row[0]): int(row[1]) for row in recon_today}

    recon_rows = {}
    if recon_ids:
        for row in db.query(CashReconciliation).filter(CashReconciliation.id.in_(list(recon_ids.values()))).all():
            recon_rows[row.id] = row

    result = []
    for row in rows:
        account = _serialize_account(row)
        today_in = float(in_map.get(row.id, 0)) + float(tr_in_map.get(row.id, 0))
        today_out = float(out_map.get(row.id, 0)) + float(tr_out_map.get(row.id, 0))
        account['today_in'] = round(today_in, 4)
        account['today_out'] = round(today_out, 4)

        recon_id = recon_ids.get(row.id)
        recon = recon_rows.get(recon_id) if recon_id else None
        account['reconciliation_date'] = recon.reconciliation_date if recon else None
        account['reconciliation_status'] = recon.status if recon else 'missing'
        account['reconciliation_variance'] = float(recon.variance or 0) if recon else None
        result.append(account)
    return result


def create_financial_account(db: Session, payload: FinancialAccountCreate):
    ensure_default_financial_accounts(db)
    account_type = _normalize(payload.account_type)
    if account_type not in FINANCIAL_ACCOUNT_TYPES:
        raise ValueError('Invalid account_type.')

    code = generate_code(db, 'financial_account', requested_code=payload.code)

    opening_balance = _as_float(payload.opening_balance)
    current_balance = _as_float(payload.current_balance, opening_balance)

    row = FinancialAccount(
        name=(payload.name or '').strip() or code,
        code=code,
        account_type=account_type,
        subtype=(payload.subtype or '').strip() or None,
        currency=_code(payload.currency or 'PHP') or 'PHP',
        is_active=bool(payload.is_active),
        requires_daily_reconciliation=bool(payload.requires_daily_reconciliation),
        opening_balance=opening_balance,
        current_balance=current_balance,
        department=(payload.department or '').strip() or None,
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_account(row)


def update_financial_account(db: Session, account_id: int, payload: FinancialAccountUpdate):
    row = db.get(FinancialAccount, int(account_id))
    if not row:
        raise ValueError('Financial account not found.')

    data = payload.model_dump(exclude_unset=True)
    opening_changed = False

    if 'account_type' in data:
        next_type = _normalize(data.get('account_type'))
        if next_type not in FINANCIAL_ACCOUNT_TYPES:
            raise ValueError('Invalid account_type.')
        data['account_type'] = next_type

    if 'code' in data:
        next_code = ensure_editable_after_create(
            db,
            'financial_account',
            row.code,
            data.get('code'),
            exclude_id=row.id,
        )
        data['code'] = next_code

    if 'currency' in data and data.get('currency'):
        data['currency'] = _code(data.get('currency'))

    if 'name' in data and isinstance(data.get('name'), str):
        data['name'] = data['name'].strip() or row.name

    if 'subtype' in data and isinstance(data.get('subtype'), str):
        data['subtype'] = data['subtype'].strip() or None

    if 'department' in data and isinstance(data.get('department'), str):
        data['department'] = data['department'].strip() or None

    if 'opening_balance' in data:
        data['opening_balance'] = _as_float(data.get('opening_balance'))
        opening_changed = True

    if 'current_balance' in data:
        data['current_balance'] = _as_float(data.get('current_balance'))

    for key, value in data.items():
        setattr(row, key, value)

    db.add(row)
    db.commit()

    if opening_changed and 'current_balance' not in data:
        recompute_all_financial_balances(db)

    db.refresh(row)
    return _serialize_account(row)


def _update_receivable_balance(db: Session, receivable_id: int):
    receivable = db.get(Receivable, int(receivable_id))
    if not receivable:
        raise ValueError('Linked receivable not found.')
    receivable.amount_collected = round(float(receivable.amount_collected or 0), 4)
    adjustment_total = db.query(func.coalesce(func.sum(ReceivableAdjustment.amount), 0)).filter(
        ReceivableAdjustment.receivable_id == receivable.id
    ).scalar() or 0
    receivable.balance_due = round(float(receivable.gross_amount or 0) + float(adjustment_total) - float(receivable.amount_collected or 0), 4)
    if receivable.balance_due <= 0.0001:
        receivable.balance_due = 0.0
        receivable.status = 'settled'
        receivable.closed_at = receivable.closed_at or _today()
    elif receivable.amount_collected > 0:
        receivable.status = 'partial'
        receivable.closed_at = None
    else:
        receivable.status = 'open'
        receivable.closed_at = None
    db.add(receivable)


def _update_payable_balance(db: Session, payable_id: int):
    payable = db.get(Payable, int(payable_id))
    if not payable:
        raise ValueError('Linked payable not found.')
    payable.amount_paid = round(float(payable.amount_paid or 0), 4)
    payable.balance_due = round(float(payable.gross_amount or 0) - float(payable.amount_paid or 0), 4)
    if payable.balance_due <= 0.0001:
        payable.balance_due = 0.0
        payable.status = 'settled'
        payable.closed_at = payable.closed_at or _today()
    elif payable.amount_paid > 0:
        payable.status = 'partial'
        payable.closed_at = None
    else:
        payable.status = 'open'
        payable.closed_at = None
    db.add(payable)


def _reverse_money_effect(db: Session, tx: MoneyTransaction):
    account = db.get(FinancialAccount, int(tx.financial_account_id))
    if not account:
        raise ValueError('Linked financial account not found.')
    amount = float(tx.amount or 0)
    if _normalize(tx.direction) == 'in':
        account.current_balance = round(float(account.current_balance or 0) - amount, 4)
    else:
        account.current_balance = round(float(account.current_balance or 0) + amount, 4)
    db.add(account)

    if tx.receivable_id:
        receivable = db.get(Receivable, int(tx.receivable_id))
        if receivable:
            receivable.amount_collected = round(float(receivable.amount_collected or 0) - amount, 4)
            if receivable.amount_collected < 0:
                receivable.amount_collected = 0.0
            db.add(receivable)
            _update_receivable_balance(db, receivable.id)

    if tx.payable_id:
        payable = db.get(Payable, int(tx.payable_id))
        if payable:
            payable.amount_paid = round(float(payable.amount_paid or 0) - amount, 4)
            if payable.amount_paid < 0:
                payable.amount_paid = 0.0
            db.add(payable)
            _update_payable_balance(db, payable.id)


def _apply_money_effect(db: Session, tx: MoneyTransaction, *, allow_overdraw: bool = False):
    account = db.get(FinancialAccount, int(tx.financial_account_id))
    if not account:
        raise ValueError('Linked financial account not found.')

    amount = float(tx.amount or 0)
    direction = _normalize(tx.direction)
    if direction == 'out' and not allow_overdraw and _normalize(account.account_type) in STRICT_CASH_TYPES:
        if float(account.current_balance or 0) < amount:
            raise ValueError('Insufficient account balance for this money-out transaction.')

    if direction == 'in':
        account.current_balance = round(float(account.current_balance or 0) + amount, 4)
    else:
        account.current_balance = round(float(account.current_balance or 0) - amount, 4)
    db.add(account)

    if tx.receivable_id:
        receivable = db.get(Receivable, int(tx.receivable_id))
        if not receivable:
            raise ValueError('Linked receivable not found.')
        receivable.amount_collected = round(float(receivable.amount_collected or 0) + amount, 4)
        db.add(receivable)
        _update_receivable_balance(db, receivable.id)

    if tx.payable_id:
        payable = db.get(Payable, int(tx.payable_id))
        if not payable:
            raise ValueError('Linked payable not found.')
        payable.amount_paid = round(float(payable.amount_paid or 0) + amount, 4)
        db.add(payable)
        _update_payable_balance(db, payable.id)


def _normalize_transaction_status(status: str | None) -> str:
    normalized = (status or 'posted').strip().lower()
    if normalized not in {'draft', 'pending_approval', 'approved', 'posted', 'reversed', 'cancelled'}:
        raise ValueError('Invalid transaction status.')
    return normalized


def _normalize_transfer_status(status: str | None) -> str:
    normalized = (status or 'posted').strip().lower()
    if normalized not in {'draft', 'pending_approval', 'approved', 'posted', 'reversed', 'cancelled'}:
        raise ValueError('Invalid transfer status.')
    return normalized


def _normalize_reconciliation_status(status: str | None) -> str:
    normalized = (status or 'counted').strip().lower()
    if normalized not in {'open', 'counted', 'reviewed', 'closed', 'discrepancy_flagged', 'reversed'}:
        raise ValueError('Invalid reconciliation status.')
    return normalized


def _is_posting_status(status: str | None) -> bool:
    return (status or '').strip().lower() in {'approved', 'posted'}


def _create_linked_record(
    db: Session,
    *,
    direction: str,
    account: FinancialAccount,
    module: str,
    category: str | None,
    subcategory: str | None,
    level3_item: str | None,
    amount: float,
    payment_method: str | None,
    counterparty_name: str | None,
    transaction_date: str,
    reference_no: str | None,
    notes: str | None,
    bir_include: bool,
    created_by: str | None,
):
    linked = create_approved_record(
        db,
        module_slug=module or 'finance',
        direction='income' if _normalize(direction) == 'in' else 'expense',
        amount=float(amount or 0),
        name=f'Cashflow {direction} {account.code}',
        transaction_date=transaction_date,
        payment_method=payment_method or _payment_method_default(account, direction),
        counterparty=counterparty_name,
        notes=notes,
        document_ref=reference_no,
        created_by=created_by,
        preferred_paths=_preferred_finance_paths(direction, category, subcategory, level3_item),
    )
    linked.bir_status = _resolve_bir_status(bool(bir_include))
    db.add(linked)
    db.flush()

    journal = db.query(JournalEntry).filter(JournalEntry.reference_no == f'REC-{linked.id}').first()
    return linked, (journal.id if journal else None)


def create_money_transaction(db: Session, payload: MoneyTransactionCreate, username: str | None = None):
    ensure_default_financial_accounts(db)
    external_source = (payload.external_source or '').strip() or None
    external_id = (payload.external_id or '').strip() or None
    if external_source and external_id:
        existing = db.query(MoneyTransaction).options(selectinload(MoneyTransaction.financial_account)).filter(
            MoneyTransaction.external_source == external_source,
            MoneyTransaction.external_id == external_id,
        ).first()
        if existing:
            return _serialize_money_transaction(existing)

    direction = _normalize(payload.direction)
    if direction not in {'in', 'out'}:
        raise ValueError('direction must be "in" or "out".')

    amount = _as_float(payload.amount)
    if amount <= 0:
        raise ValueError('amount must be greater than zero.')

    row_account = db.get(FinancialAccount, int(payload.financial_account_id))
    if not row_account:
        raise ValueError('financial_account_id not found.')

    tx_date = _safe_date(payload.transaction_date)
    ensure_date_unlocked(db, tx_date, scope='bir', action='create cashflow transaction in locked period')

    if direction == 'out' and not bool(payload.allow_overdraw) and _normalize(row_account.account_type) in STRICT_CASH_TYPES:
        if float(row_account.current_balance or 0) < amount:
            raise ValueError('Insufficient account balance for this money-out transaction.')

    linked_journal_id = None
    tx_status = _normalize_transaction_status(payload.status)
    if payload.receivable_id and direction != 'in':
        raise ValueError('receivable_id can only be used on money-in entries.')
    if payload.payable_id and direction != 'out':
        raise ValueError('payable_id can only be used on money-out entries.')

    tx = MoneyTransaction(
        transaction_date=tx_date,
        direction=direction,
        financial_account_id=row_account.id,
        module=(payload.module or 'finance').strip() or 'finance',
        category=(payload.category or '').strip() or None,
        subcategory=(payload.subcategory or '').strip() or None,
        level3_item=(payload.level3_item or '').strip() or None,
        amount=amount,
        payment_method=(payload.payment_method or '').strip() or _payment_method_default(row_account, direction),
        reference_no=(payload.reference_no or '').strip() or None,
        counterparty_name=(payload.counterparty_name or '').strip() or None,
        notes=payload.notes,
        linked_record_type=(payload.linked_record_type or '').strip() or None,
        linked_record_id=payload.linked_record_id,
        receivable_id=payload.receivable_id,
        payable_id=payload.payable_id,
        bir_include=bool(payload.bir_include),
        status=tx_status,
        reversed_from_id=None,
        is_reversed=False,
        posted_at=tx_date if tx_status == 'posted' else None,
        created_by=username,
        approved_by=username if tx_status in {'approved', 'posted'} else None,
        external_source=external_source,
        external_id=external_id,
    )

    db.add(tx)
    db.flush()

    if _is_posting_status(tx_status):
        _apply_money_effect(db, tx, allow_overdraw=bool(payload.allow_overdraw))

    if bool(payload.auto_post_accounting) and _is_posting_status(tx_status):
        _, linked_journal_id = _create_linked_record(
            db,
            direction=direction,
            account=row_account,
            module=(payload.module or 'finance'),
            category=payload.category,
            subcategory=payload.subcategory,
            level3_item=payload.level3_item,
            amount=amount,
            payment_method=payload.payment_method,
            counterparty_name=payload.counterparty_name,
            transaction_date=tx_date,
            reference_no=payload.reference_no,
            notes=payload.notes,
            bir_include=bool(payload.bir_include),
            created_by=username,
        )

    tx.journal_entry_id = linked_journal_id
    db.add(tx)
    db.commit()

    tx = (
        db.query(MoneyTransaction)
        .options(selectinload(MoneyTransaction.financial_account))
        .filter(MoneyTransaction.id == tx.id)
        .first()
    )
    return _serialize_money_transaction(tx)


def list_money_transactions(
    db: Session,
    *,
    account_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    direction: str | None = None,
    module: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = 200,
):
    query = db.query(MoneyTransaction).options(selectinload(MoneyTransaction.financial_account))
    if account_id:
        query = query.filter(MoneyTransaction.financial_account_id == int(account_id))
    if start_date:
        query = query.filter(MoneyTransaction.transaction_date >= start_date)
    if end_date:
        query = query.filter(MoneyTransaction.transaction_date <= end_date)
    if direction:
        query = query.filter(MoneyTransaction.direction == _normalize(direction))
    if module:
        query = query.filter(MoneyTransaction.module == (module or '').strip())
    if status:
        query = query.filter(MoneyTransaction.status == (status or '').strip())
    if q:
        like_q = f'%{q.strip()}%'
        query = query.filter(
            or_(
                MoneyTransaction.reference_no.like(like_q),
                MoneyTransaction.counterparty_name.like(like_q),
                MoneyTransaction.notes.like(like_q),
                MoneyTransaction.category.like(like_q),
                MoneyTransaction.subcategory.like(like_q),
                MoneyTransaction.level3_item.like(like_q),
            )
        )

    rows = query.order_by(MoneyTransaction.id.desc()).limit(max(1, min(int(limit or 200), 1000))).all()
    return [_serialize_money_transaction(row) for row in rows]


def get_money_transaction(db: Session, tx_id: int):
    row = (
        db.query(MoneyTransaction)
        .options(selectinload(MoneyTransaction.financial_account))
        .filter(MoneyTransaction.id == int(tx_id))
        .first()
    )
    if not row:
        raise ValueError('Money transaction not found.')
    return _serialize_money_transaction(row)


def update_money_transaction(db: Session, tx_id: int, payload: MoneyTransactionUpdate, username: str | None = None):
    row = (
        db.query(MoneyTransaction)
        .options(selectinload(MoneyTransaction.financial_account))
        .filter(MoneyTransaction.id == int(tx_id))
        .first()
    )
    if not row:
        raise ValueError('Money transaction not found.')
    if bool(row.is_reversed) or _normalize(row.status) == 'reversed':
        raise ValueError('Reversed money transaction cannot be edited.')
    if _normalize(row.status) == 'cancelled':
        raise ValueError('Cancelled money transaction cannot be edited.')

    data = payload.model_dump(exclude_unset=True)
    old_status = _normalize_transaction_status(row.status)
    old_posting = _is_posting_status(old_status)
    if old_posting:
        _reverse_money_effect(db, row)

    if 'financial_account_id' in data:
        account = db.get(FinancialAccount, int(data.get('financial_account_id')))
        if not account:
            raise ValueError('financial_account_id not found.')
        row.financial_account_id = account.id

    if 'direction' in data:
        direction = _normalize(data.get('direction'))
        if direction not in {'in', 'out'}:
            raise ValueError('direction must be "in" or "out".')
        row.direction = direction

    if 'amount' in data:
        amount = _as_float(data.get('amount'))
        if amount <= 0:
            raise ValueError('amount must be greater than zero.')
        row.amount = amount

    for key in (
        'module',
        'category',
        'subcategory',
        'level3_item',
        'payment_method',
        'reference_no',
        'counterparty_name',
        'notes',
        'linked_record_type',
        'linked_record_id',
        'receivable_id',
        'payable_id',
        'bir_include',
    ):
        if key in data:
            setattr(row, key, data.get(key))

    if 'transaction_date' in data:
        row.transaction_date = _safe_date(data.get('transaction_date'))
    if not row.transaction_date:
        row.transaction_date = _today()

    ensure_date_unlocked(db, row.transaction_date, scope='bir', action='update cashflow transaction in locked period')

    next_status = _normalize_transaction_status(data.get('status') or row.status)
    row.status = next_status
    row.approved_by = username if next_status in {'approved', 'posted'} else row.approved_by
    row.posted_at = row.transaction_date if next_status == 'posted' else None

    if row.receivable_id and _normalize(row.direction) != 'in':
        raise ValueError('receivable_id can only be linked to money-in transactions.')
    if row.payable_id and _normalize(row.direction) != 'out':
        raise ValueError('payable_id can only be linked to money-out transactions.')

    if _is_posting_status(next_status):
        _apply_money_effect(db, row, allow_overdraw=bool(payload.allow_overdraw))

    if bool(payload.auto_post_accounting) and _is_posting_status(next_status):
        account = db.get(FinancialAccount, int(row.financial_account_id))
        if account and not row.journal_entry_id:
            _, journal_id = _create_linked_record(
                db,
                direction=row.direction,
                account=account,
                module=row.module or 'finance',
                category=row.category,
                subcategory=row.subcategory,
                level3_item=row.level3_item,
                amount=float(row.amount or 0),
                payment_method=row.payment_method,
                counterparty_name=row.counterparty_name,
                transaction_date=row.transaction_date,
                reference_no=row.reference_no,
                notes=row.notes,
                bir_include=bool(row.bir_include),
                created_by=username,
            )
            row.journal_entry_id = journal_id

    db.add(row)
    db.commit()
    row = (
        db.query(MoneyTransaction)
        .options(selectinload(MoneyTransaction.financial_account))
        .filter(MoneyTransaction.id == row.id)
        .first()
    )
    return _serialize_money_transaction(row)


def cancel_money_transaction(db: Session, tx_id: int, payload: CashflowActionPayload, username: str | None = None):
    row = db.get(MoneyTransaction, int(tx_id))
    if not row:
        raise ValueError('Money transaction not found.')
    if bool(row.is_reversed) or _normalize(row.status) == 'reversed':
        raise ValueError('Reversed money transaction cannot be cancelled.')
    if _normalize(row.status) == 'cancelled':
        raise ValueError('Money transaction is already cancelled.')

    if _is_posting_status(row.status):
        _reverse_money_effect(db, row)
    row.status = 'cancelled'
    row.posted_at = None
    if payload.reason:
        row.notes = f"{row.notes or ''}\nCancelled: {payload.reason}".strip()
    db.add(row)
    db.commit()
    row = (
        db.query(MoneyTransaction)
        .options(selectinload(MoneyTransaction.financial_account))
        .filter(MoneyTransaction.id == row.id)
        .first()
    )
    return _serialize_money_transaction(row)


def approve_money_transaction(db: Session, tx_id: int, payload: CashflowActionPayload, username: str | None = None):
    row = db.get(MoneyTransaction, int(tx_id))
    if not row:
        raise ValueError('Money transaction not found.')
    if bool(row.is_reversed) or _normalize(row.status) in {'reversed', 'cancelled'}:
        raise ValueError('Only active transactions can be approved.')

    if not _is_posting_status(row.status):
        _apply_money_effect(db, row, allow_overdraw=True)
    row.status = 'approved'
    row.approved_by = username or row.approved_by
    if payload.action_date:
        row.posted_at = _safe_date(payload.action_date)
    elif not row.posted_at:
        row.posted_at = row.transaction_date or _today()
    if payload.reason:
        row.notes = f"{row.notes or ''}\nApproved: {payload.reason}".strip()
    db.add(row)
    db.commit()
    row = (
        db.query(MoneyTransaction)
        .options(selectinload(MoneyTransaction.financial_account))
        .filter(MoneyTransaction.id == row.id)
        .first()
    )
    return _serialize_money_transaction(row)


def reverse_money_transaction(db: Session, tx_id: int, payload: CashflowActionPayload, username: str | None = None):
    row = db.get(MoneyTransaction, int(tx_id))
    if not row:
        raise ValueError('Money transaction not found.')
    if bool(row.is_reversed) or _normalize(row.status) == 'reversed':
        raise ValueError('Money transaction has already been reversed.')
    if _normalize(row.status) == 'cancelled':
        raise ValueError('Cancelled transaction cannot be reversed.')

    reverse_date = _safe_date(payload.action_date or row.transaction_date)
    ensure_date_unlocked(db, reverse_date, scope='bir', action='reverse cashflow transaction in locked period')

    reversal_row = None
    if _is_posting_status(row.status):
        reverse_direction = 'out' if _normalize(row.direction) == 'in' else 'in'
        reversal_row = MoneyTransaction(
            transaction_date=reverse_date,
            direction=reverse_direction,
            financial_account_id=row.financial_account_id,
            module=row.module,
            category=row.category,
            subcategory=row.subcategory,
            level3_item=row.level3_item,
            amount=float(row.amount or 0),
            payment_method=row.payment_method,
            reference_no=f'REV-{row.id}',
            counterparty_name=row.counterparty_name,
            notes=f"Reversal of TX-{row.id}. {payload.reason or ''}".strip(),
            linked_record_type=row.linked_record_type,
            linked_record_id=row.linked_record_id,
            receivable_id=None,
            payable_id=None,
            bir_include=bool(row.bir_include),
            journal_entry_id=None,
            status='posted',
            reversed_from_id=row.id,
            is_reversed=False,
            posted_at=reverse_date,
            created_by=username,
            approved_by=username,
        )
        db.add(reversal_row)
        db.flush()
        _apply_money_effect(db, reversal_row, allow_overdraw=True)

        if row.receivable_id:
            receivable = db.get(Receivable, int(row.receivable_id))
            if receivable:
                receivable.amount_collected = round(float(receivable.amount_collected or 0) - float(row.amount or 0), 4)
                if receivable.amount_collected < 0:
                    receivable.amount_collected = 0
                db.add(receivable)
                _update_receivable_balance(db, receivable.id)
        if row.payable_id:
            payable = db.get(Payable, int(row.payable_id))
            if payable:
                payable.amount_paid = round(float(payable.amount_paid or 0) - float(row.amount or 0), 4)
                if payable.amount_paid < 0:
                    payable.amount_paid = 0
                db.add(payable)
                _update_payable_balance(db, payable.id)

    row.status = 'reversed'
    row.is_reversed = True
    row.approved_by = username or row.approved_by
    if payload.reason:
        row.notes = f"{row.notes or ''}\nReversed: {payload.reason}".strip()
    db.add(row)
    db.commit()

    response = {
        'original': _serialize_money_transaction(
            db.query(MoneyTransaction).options(selectinload(MoneyTransaction.financial_account)).filter(MoneyTransaction.id == row.id).first()
        )
    }
    if reversal_row:
        response['reversal'] = _serialize_money_transaction(
            db.query(MoneyTransaction).options(selectinload(MoneyTransaction.financial_account)).filter(MoneyTransaction.id == reversal_row.id).first()
        )
    return response


def delete_money_transaction(db: Session, tx_id: int):
    row = db.get(MoneyTransaction, int(tx_id))
    if not row:
        raise ValueError('Money transaction not found.')
    if _is_posting_status(row.status):
        raise ValueError('Posted/approved transactions cannot be deleted. Cancel or reverse instead.')
    if bool(row.is_reversed) or _normalize(row.status) == 'reversed':
        raise ValueError('Reversed transaction cannot be deleted.')
    db.delete(row)
    db.commit()
    return {'ok': True}


def create_transfer(db: Session, payload: AccountTransferCreate, username: str | None = None):
    ensure_default_financial_accounts(db)
    external_source = (payload.external_source or '').strip() or None
    external_id = (payload.external_id or '').strip() or None
    if external_source and external_id:
        existing = db.query(AccountTransfer).options(
            selectinload(AccountTransfer.from_account),
            selectinload(AccountTransfer.to_account),
        ).filter(
            AccountTransfer.external_source == external_source,
            AccountTransfer.external_id == external_id,
        ).first()
        if existing:
            return _serialize_transfer(existing)

    amount = _as_float(payload.amount)
    if amount <= 0:
        raise ValueError('amount must be greater than zero.')

    from_account = db.get(FinancialAccount, int(payload.from_account_id))
    to_account = db.get(FinancialAccount, int(payload.to_account_id))
    if not from_account or not to_account:
        raise ValueError('Invalid from_account_id or to_account_id.')
    if int(from_account.id) == int(to_account.id):
        raise ValueError('from_account_id and to_account_id cannot be the same.')

    transfer_date = _safe_date(payload.transfer_date)
    ensure_date_unlocked(db, transfer_date, scope='bir', action='create account transfer in locked period')

    if not bool(payload.allow_overdraw) and _normalize(from_account.account_type) in STRICT_CASH_TYPES:
        if float(from_account.current_balance or 0) < amount:
            raise ValueError('Insufficient source balance for transfer.')

    transfer_status = _normalize_transfer_status(payload.status)

    row = AccountTransfer(
        transfer_date=transfer_date,
        from_account_id=from_account.id,
        to_account_id=to_account.id,
        amount=amount,
        reference_no=(payload.reference_no or '').strip() or None,
        notes=payload.notes,
        status=transfer_status,
        reversed_from_id=None,
        is_reversed=False,
        posted_at=transfer_date if transfer_status == 'posted' else None,
        created_by=username,
        approved_by=username if transfer_status in {'approved', 'posted'} else None,
        external_source=external_source,
        external_id=external_id,
    )
    db.add(row)
    db.flush()

    if _is_posting_status(transfer_status):
        from_account.current_balance = round(float(from_account.current_balance or 0) - amount, 4)
        to_account.current_balance = round(float(to_account.current_balance or 0) + amount, 4)
        db.add(from_account)
        db.add(to_account)

    if bool(payload.auto_post_accounting) and _is_posting_status(transfer_status):
        linked, journal_id = _create_linked_record(
            db,
            direction='out',
            account=from_account,
            module='finance',
            category='Transfers and Adjustments',
            subcategory='Internal Transfers',
            level3_item='Account to Account',
            amount=amount,
            payment_method='transfer',
            counterparty_name=to_account.name,
            transaction_date=transfer_date,
            reference_no=payload.reference_no,
            notes=payload.notes,
            bir_include=False,
            created_by=username,
        )
        row.journal_entry_id = journal_id
        row.notes = (row.notes or '') + f'\nLinked record REC-{linked.id}'
        db.add(row)

    db.commit()
    row = (
        db.query(AccountTransfer)
        .options(
            selectinload(AccountTransfer.from_account),
            selectinload(AccountTransfer.to_account),
        )
        .filter(AccountTransfer.id == row.id)
        .first()
    )
    return _serialize_transfer(row)


def list_transfers(
    db: Session,
    *,
    account_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 200,
):
    query = db.query(AccountTransfer).options(
        selectinload(AccountTransfer.from_account),
        selectinload(AccountTransfer.to_account),
    )
    if account_id:
        query = query.filter(or_(AccountTransfer.from_account_id == int(account_id), AccountTransfer.to_account_id == int(account_id)))
    if start_date:
        query = query.filter(AccountTransfer.transfer_date >= start_date)
    if end_date:
        query = query.filter(AccountTransfer.transfer_date <= end_date)

    rows = query.order_by(AccountTransfer.id.desc()).limit(max(1, min(int(limit or 200), 1000))).all()
    return [_serialize_transfer(row) for row in rows]


def update_transfer(db: Session, transfer_id: int, payload: AccountTransferUpdate, username: str | None = None):
    row = db.get(AccountTransfer, int(transfer_id))
    if not row:
        raise ValueError('Transfer not found.')
    if bool(row.is_reversed) or _normalize(row.status) == 'reversed':
        raise ValueError('Reversed transfer cannot be edited.')
    if _normalize(row.status) == 'cancelled':
        raise ValueError('Cancelled transfer cannot be edited.')

    old_posting = _is_posting_status(row.status)
    old_amount = float(row.amount or 0)
    old_from = db.get(FinancialAccount, int(row.from_account_id))
    old_to = db.get(FinancialAccount, int(row.to_account_id))
    if old_posting and old_from and old_to:
        old_from.current_balance = round(float(old_from.current_balance or 0) + old_amount, 4)
        old_to.current_balance = round(float(old_to.current_balance or 0) - old_amount, 4)
        db.add(old_from)
        db.add(old_to)

    data = payload.model_dump(exclude_unset=True)
    if 'from_account_id' in data:
        from_account = db.get(FinancialAccount, int(data.get('from_account_id')))
        if not from_account:
            raise ValueError('from_account_id not found.')
        row.from_account_id = from_account.id
    if 'to_account_id' in data:
        to_account = db.get(FinancialAccount, int(data.get('to_account_id')))
        if not to_account:
            raise ValueError('to_account_id not found.')
        row.to_account_id = to_account.id
    if int(row.from_account_id) == int(row.to_account_id):
        raise ValueError('from_account_id and to_account_id cannot be the same.')

    if 'amount' in data:
        amount = _as_float(data.get('amount'))
        if amount <= 0:
            raise ValueError('amount must be greater than zero.')
        row.amount = amount
    if 'transfer_date' in data:
        row.transfer_date = _safe_date(data.get('transfer_date'))
    if not row.transfer_date:
        row.transfer_date = _today()

    ensure_date_unlocked(db, row.transfer_date, scope='bir', action='update transfer in locked period')
    for key in ('reference_no', 'notes'):
        if key in data:
            setattr(row, key, data.get(key))

    next_status = _normalize_transfer_status(data.get('status') or row.status)
    row.status = next_status
    row.approved_by = username if next_status in {'approved', 'posted'} else row.approved_by
    row.posted_at = row.transfer_date if next_status == 'posted' else None

    from_account = db.get(FinancialAccount, int(row.from_account_id))
    to_account = db.get(FinancialAccount, int(row.to_account_id))
    if not from_account or not to_account:
        raise ValueError('from_account_id or to_account_id not found.')
    if _is_posting_status(next_status):
        amount = float(row.amount or 0)
        if not bool(payload.allow_overdraw) and _normalize(from_account.account_type) in STRICT_CASH_TYPES:
            if float(from_account.current_balance or 0) < amount:
                raise ValueError('Insufficient source balance for transfer.')
        from_account.current_balance = round(float(from_account.current_balance or 0) - amount, 4)
        to_account.current_balance = round(float(to_account.current_balance or 0) + amount, 4)
        db.add(from_account)
        db.add(to_account)

    db.add(row)
    db.commit()
    row = (
        db.query(AccountTransfer)
        .options(selectinload(AccountTransfer.from_account), selectinload(AccountTransfer.to_account))
        .filter(AccountTransfer.id == row.id)
        .first()
    )
    return _serialize_transfer(row)


def approve_transfer(db: Session, transfer_id: int, payload: CashflowActionPayload, username: str | None = None):
    row = db.get(AccountTransfer, int(transfer_id))
    if not row:
        raise ValueError('Transfer not found.')
    if bool(row.is_reversed) or _normalize(row.status) in {'reversed', 'cancelled'}:
        raise ValueError('Only active transfers can be approved.')

    if not _is_posting_status(row.status):
        from_account = db.get(FinancialAccount, int(row.from_account_id))
        to_account = db.get(FinancialAccount, int(row.to_account_id))
        if not from_account or not to_account:
            raise ValueError('from_account_id or to_account_id not found.')
        amount = float(row.amount or 0)
        if _normalize(from_account.account_type) in STRICT_CASH_TYPES and float(from_account.current_balance or 0) < amount:
            raise ValueError('Insufficient source balance for transfer.')
        from_account.current_balance = round(float(from_account.current_balance or 0) - amount, 4)
        to_account.current_balance = round(float(to_account.current_balance or 0) + amount, 4)
        db.add(from_account)
        db.add(to_account)

    row.status = 'approved'
    row.approved_by = username or row.approved_by
    row.posted_at = _safe_date(payload.action_date or row.transfer_date)
    if payload.reason:
        row.notes = f"{row.notes or ''}\nApproved: {payload.reason}".strip()
    db.add(row)
    db.commit()
    row = (
        db.query(AccountTransfer)
        .options(selectinload(AccountTransfer.from_account), selectinload(AccountTransfer.to_account))
        .filter(AccountTransfer.id == row.id)
        .first()
    )
    return _serialize_transfer(row)


def cancel_transfer(db: Session, transfer_id: int, payload: CashflowActionPayload):
    row = db.get(AccountTransfer, int(transfer_id))
    if not row:
        raise ValueError('Transfer not found.')
    if bool(row.is_reversed) or _normalize(row.status) == 'reversed':
        raise ValueError('Reversed transfer cannot be cancelled.')
    if _normalize(row.status) == 'cancelled':
        raise ValueError('Transfer is already cancelled.')

    if _is_posting_status(row.status):
        from_account = db.get(FinancialAccount, int(row.from_account_id))
        to_account = db.get(FinancialAccount, int(row.to_account_id))
        amount = float(row.amount or 0)
        if from_account and to_account:
            from_account.current_balance = round(float(from_account.current_balance or 0) + amount, 4)
            to_account.current_balance = round(float(to_account.current_balance or 0) - amount, 4)
            db.add(from_account)
            db.add(to_account)

    row.status = 'cancelled'
    row.posted_at = None
    if payload.reason:
        row.notes = f"{row.notes or ''}\nCancelled: {payload.reason}".strip()
    db.add(row)
    db.commit()
    row = (
        db.query(AccountTransfer)
        .options(selectinload(AccountTransfer.from_account), selectinload(AccountTransfer.to_account))
        .filter(AccountTransfer.id == row.id)
        .first()
    )
    return _serialize_transfer(row)


def reverse_transfer(db: Session, transfer_id: int, payload: CashflowActionPayload, username: str | None = None):
    row = db.get(AccountTransfer, int(transfer_id))
    if not row:
        raise ValueError('Transfer not found.')
    if bool(row.is_reversed) or _normalize(row.status) == 'reversed':
        raise ValueError('Transfer has already been reversed.')
    if _normalize(row.status) == 'cancelled':
        raise ValueError('Cancelled transfer cannot be reversed.')

    reverse_date = _safe_date(payload.action_date or row.transfer_date)
    ensure_date_unlocked(db, reverse_date, scope='bir', action='reverse transfer in locked period')

    reversal = None
    if _is_posting_status(row.status):
        reversal = AccountTransfer(
            transfer_date=reverse_date,
            from_account_id=row.to_account_id,
            to_account_id=row.from_account_id,
            amount=float(row.amount or 0),
            reference_no=f'REV-{row.id}',
            notes=f"Reversal of transfer {row.id}. {payload.reason or ''}".strip(),
            journal_entry_id=None,
            status='posted',
            reversed_from_id=row.id,
            is_reversed=False,
            posted_at=reverse_date,
            created_by=username,
            approved_by=username,
        )
        db.add(reversal)
        db.flush()

        from_account = db.get(FinancialAccount, int(reversal.from_account_id))
        to_account = db.get(FinancialAccount, int(reversal.to_account_id))
        if from_account and to_account:
            amount = float(reversal.amount or 0)
            from_account.current_balance = round(float(from_account.current_balance or 0) - amount, 4)
            to_account.current_balance = round(float(to_account.current_balance or 0) + amount, 4)
            db.add(from_account)
            db.add(to_account)

    row.status = 'reversed'
    row.is_reversed = True
    if payload.reason:
        row.notes = f"{row.notes or ''}\nReversed: {payload.reason}".strip()
    db.add(row)
    db.commit()

    response = {
        'original': _serialize_transfer(
            db.query(AccountTransfer).options(selectinload(AccountTransfer.from_account), selectinload(AccountTransfer.to_account)).filter(AccountTransfer.id == row.id).first()
        )
    }
    if reversal:
        response['reversal'] = _serialize_transfer(
            db.query(AccountTransfer).options(selectinload(AccountTransfer.from_account), selectinload(AccountTransfer.to_account)).filter(AccountTransfer.id == reversal.id).first()
        )
    return response


def delete_transfer(db: Session, transfer_id: int):
    row = db.get(AccountTransfer, int(transfer_id))
    if not row:
        raise ValueError('Transfer not found.')
    if _is_posting_status(row.status):
        raise ValueError('Posted/approved transfers cannot be deleted. Cancel or reverse instead.')
    if bool(row.is_reversed) or _normalize(row.status) == 'reversed':
        raise ValueError('Reversed transfer cannot be deleted.')
    db.delete(row)
    db.commit()
    return {'ok': True}


def _account_day_expected_values(db: Session, account_id: int, target_date: str) -> tuple[float, float, float, float]:
    opening_balance = _account_opening_balance_at(db, account_id, target_date)

    tx_in = (
        db.query(func.sum(MoneyTransaction.amount))
        .filter(
            MoneyTransaction.financial_account_id == int(account_id),
            MoneyTransaction.transaction_date == target_date,
            MoneyTransaction.direction == 'in',
        )
        .scalar()
        or 0
    )
    tx_out = (
        db.query(func.sum(MoneyTransaction.amount))
        .filter(
            MoneyTransaction.financial_account_id == int(account_id),
            MoneyTransaction.transaction_date == target_date,
            MoneyTransaction.direction == 'out',
        )
        .scalar()
        or 0
    )
    transfer_in = (
        db.query(func.sum(AccountTransfer.amount))
        .filter(AccountTransfer.to_account_id == int(account_id), AccountTransfer.transfer_date == target_date)
        .scalar()
        or 0
    )
    transfer_out = (
        db.query(func.sum(AccountTransfer.amount))
        .filter(AccountTransfer.from_account_id == int(account_id), AccountTransfer.transfer_date == target_date)
        .scalar()
        or 0
    )

    expected_in = float(tx_in or 0) + float(transfer_in or 0)
    expected_out = float(tx_out or 0) + float(transfer_out or 0)
    expected_closing = opening_balance + expected_in - expected_out
    return round(opening_balance, 4), round(expected_in, 4), round(expected_out, 4), round(expected_closing, 4)


def create_cash_reconciliation(db: Session, payload: CashReconciliationCreate, username: str | None = None):
    ensure_default_financial_accounts(db)

    account = db.get(FinancialAccount, int(payload.financial_account_id))
    if not account:
        raise ValueError('financial_account_id not found.')

    recon_date = _safe_date(payload.reconciliation_date)
    ensure_date_unlocked(db, recon_date, scope='bir', action='create cash reconciliation in locked period')

    opening_balance, expected_in, expected_out, expected_closing = _account_day_expected_values(db, account.id, recon_date)
    actual_counted = _as_float(payload.actual_counted)
    variance = round(actual_counted - expected_closing, 4)

    row = (
        db.query(CashReconciliation)
        .filter(
            CashReconciliation.financial_account_id == account.id,
            CashReconciliation.reconciliation_date == recon_date,
            CashReconciliation.shift_name == ((payload.shift_name or '').strip() or None),
        )
        .first()
    )
    if not row:
        row = CashReconciliation(
            financial_account_id=account.id,
            reconciliation_date=recon_date,
            shift_name=(payload.shift_name or '').strip() or None,
        )
    else:
        for line in list(row.lines or []):
            db.delete(line)

    recon_status = _normalize_reconciliation_status(payload.status)
    if recon_status == 'closed' and abs(variance) >= 0.01 and not (payload.notes or '').strip():
        raise ValueError('Variance note is required when closing with non-zero variance.')

    row.opening_balance = opening_balance
    row.expected_in = expected_in
    row.expected_out = expected_out
    row.expected_closing = expected_closing
    row.actual_counted = actual_counted
    row.variance = variance
    row.status = recon_status
    row.counted_by = (payload.counted_by or username)
    row.approved_by = username if row.status in {'reviewed', 'closed'} else row.approved_by
    row.posted_at = recon_date if row.status in {'reviewed', 'closed'} else row.posted_at
    row.closed_at = recon_date if row.status == 'closed' else None
    row.locked_at = recon_date if row.status == 'closed' else None
    row.notes = payload.notes
    db.add(row)
    db.flush()

    for idx, line in enumerate(payload.lines or []):
        db.add(
            CashReconciliationLine(
                cash_reconciliation_id=row.id,
                line_label=(line.line_label or '').strip() or f'line_{idx + 1}',
                amount=_as_float(line.amount),
                notes=line.notes,
                sort_order=int(line.sort_order if line.sort_order is not None else idx),
            )
        )

    db.commit()

    row = (
        db.query(CashReconciliation)
        .options(
            selectinload(CashReconciliation.financial_account),
            selectinload(CashReconciliation.lines),
        )
        .filter(CashReconciliation.id == row.id)
        .first()
    )
    return _serialize_reconciliation(row)


def list_cash_reconciliations(
    db: Session,
    *,
    account_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    status: str | None = None,
    limit: int = 300,
):
    query = db.query(CashReconciliation).options(
        selectinload(CashReconciliation.financial_account),
        selectinload(CashReconciliation.lines),
    )
    if account_id:
        query = query.filter(CashReconciliation.financial_account_id == int(account_id))
    if start_date:
        query = query.filter(CashReconciliation.reconciliation_date >= start_date)
    if end_date:
        query = query.filter(CashReconciliation.reconciliation_date <= end_date)
    if status:
        query = query.filter(CashReconciliation.status == (status or '').strip())

    rows = query.order_by(CashReconciliation.reconciliation_date.desc(), CashReconciliation.id.desc()).limit(max(1, min(int(limit or 300), 1000))).all()
    return [_serialize_reconciliation(row) for row in rows]


def update_cash_reconciliation(db: Session, reconciliation_id: int, payload: CashReconciliationCreate, username: str | None = None):
    row = db.get(CashReconciliation, int(reconciliation_id))
    if not row:
        raise ValueError('Cash reconciliation not found.')

    recon_date = _safe_date(payload.reconciliation_date or row.reconciliation_date)
    ensure_date_unlocked(db, recon_date, scope='bir', action='update cash reconciliation in locked period')

    account_id = int(payload.financial_account_id or row.financial_account_id)
    account = db.get(FinancialAccount, account_id)
    if not account:
        raise ValueError('financial_account_id not found.')

    opening_balance, expected_in, expected_out, expected_closing = _account_day_expected_values(db, account_id, recon_date)
    actual_counted = _as_float(payload.actual_counted)
    variance = round(actual_counted - expected_closing, 4)
    next_status = _normalize_reconciliation_status(payload.status or row.status)
    if next_status == 'closed' and abs(variance) >= 0.01 and not (payload.notes or '').strip():
        raise ValueError('Variance note is required when closing with non-zero variance.')

    row.financial_account_id = account_id
    row.reconciliation_date = recon_date
    row.shift_name = (payload.shift_name or '').strip() or None
    row.opening_balance = opening_balance
    row.expected_in = expected_in
    row.expected_out = expected_out
    row.expected_closing = expected_closing
    row.actual_counted = actual_counted
    row.variance = variance
    row.status = next_status
    row.counted_by = payload.counted_by or row.counted_by or username
    row.approved_by = username if next_status in {'reviewed', 'closed'} else row.approved_by
    row.posted_at = recon_date if next_status in {'reviewed', 'closed'} else None
    row.closed_at = recon_date if next_status == 'closed' else None
    row.locked_at = recon_date if next_status == 'closed' else None
    row.notes = payload.notes
    db.add(row)
    db.flush()

    for old in list(row.lines or []):
        db.delete(old)
    for idx, line in enumerate(payload.lines or []):
        db.add(
            CashReconciliationLine(
                cash_reconciliation_id=row.id,
                line_label=(line.line_label or '').strip() or f'line_{idx + 1}',
                amount=_as_float(line.amount),
                notes=line.notes,
                sort_order=int(line.sort_order if line.sort_order is not None else idx),
            )
        )
    db.commit()
    row = (
        db.query(CashReconciliation)
        .options(selectinload(CashReconciliation.financial_account), selectinload(CashReconciliation.lines))
        .filter(CashReconciliation.id == row.id)
        .first()
    )
    return _serialize_reconciliation(row)


def approve_cash_reconciliation(db: Session, reconciliation_id: int, payload: CashflowActionPayload, username: str | None = None):
    row = db.get(CashReconciliation, int(reconciliation_id))
    if not row:
        raise ValueError('Cash reconciliation not found.')
    if _normalize(row.status) in {'closed', 'reversed'}:
        raise ValueError('Closed/reversed reconciliation cannot be approved.')
    row.status = 'reviewed'
    row.approved_by = username or row.approved_by
    row.posted_at = _safe_date(payload.action_date or row.reconciliation_date)
    if payload.reason:
        row.notes = f"{row.notes or ''}\nReviewed: {payload.reason}".strip()
    db.add(row)
    db.commit()
    return _serialize_reconciliation(
        db.query(CashReconciliation).options(selectinload(CashReconciliation.financial_account), selectinload(CashReconciliation.lines)).filter(CashReconciliation.id == row.id).first()
    )


def close_cash_reconciliation(db: Session, reconciliation_id: int, payload: CashflowActionPayload, username: str | None = None):
    row = db.get(CashReconciliation, int(reconciliation_id))
    if not row:
        raise ValueError('Cash reconciliation not found.')
    if _normalize(row.status) == 'reversed':
        raise ValueError('Reversed reconciliation cannot be closed.')
    if abs(float(row.variance or 0)) >= 0.01 and not (payload.reason or row.notes or '').strip():
        raise ValueError('Variance note is required when closing with non-zero variance.')
    close_date = _safe_date(payload.action_date or row.reconciliation_date)
    row.status = 'closed'
    row.approved_by = username or row.approved_by
    row.posted_at = close_date
    row.closed_at = close_date
    row.locked_at = close_date
    if payload.reason:
        row.notes = f"{row.notes or ''}\nClosed: {payload.reason}".strip()
    db.add(row)
    db.commit()
    return _serialize_reconciliation(
        db.query(CashReconciliation).options(selectinload(CashReconciliation.financial_account), selectinload(CashReconciliation.lines)).filter(CashReconciliation.id == row.id).first()
    )


def reverse_cash_reconciliation(db: Session, reconciliation_id: int, payload: CashflowActionPayload, username: str | None = None):
    row = db.get(CashReconciliation, int(reconciliation_id))
    if not row:
        raise ValueError('Cash reconciliation not found.')
    if _normalize(row.status) == 'reversed':
        raise ValueError('Reconciliation already reversed.')
    row.status = 'reversed'
    row.closed_at = None
    row.locked_at = None
    if payload.reason:
        row.notes = f"{row.notes or ''}\nReversed: {payload.reason}".strip()
    db.add(row)
    db.commit()
    return _serialize_reconciliation(
        db.query(CashReconciliation).options(selectinload(CashReconciliation.financial_account), selectinload(CashReconciliation.lines)).filter(CashReconciliation.id == row.id).first()
    )


def create_receivable(db: Session, payload: ReceivableCreate):
    gross_amount = _as_float(payload.gross_amount)
    amount_collected = max(_as_float(payload.amount_collected), 0)
    source_type = (payload.source_type or '').strip() or None
    external_source = (payload.external_source or '').strip() or None
    external_id = (payload.external_id or '').strip() or None
    if external_source and external_id:
        existing = db.query(Receivable).filter(
            Receivable.external_source == external_source,
            Receivable.external_id == external_id,
        ).first()
        if existing:
            return _serialize_receivable(existing)
        existing_adjustment = db.query(ReceivableAdjustment).filter(
            ReceivableAdjustment.external_source == external_source,
            ReceivableAdjustment.external_id == external_id,
        ).first()
        if existing_adjustment:
            return _serialize_receivable(existing_adjustment.receivable)

    if gross_amount < 0:
        reverse_type = (payload.reverses_source_type or '').strip()
        if not reverse_type or not payload.reverses_source_id:
            raise ValueError('Negative receivables require reverses_source_type and reverses_source_id.')
        if source_type != 'pos_room_charge_reversal' or reverse_type != 'pos_room_charge':
            raise ValueError('Negative receivables are only allowed for POS room-charge reversals.')
        original = db.query(Receivable).filter(
            Receivable.source_type == reverse_type,
            Receivable.source_id == int(payload.reverses_source_id),
        ).first()
        if not original:
            raise ValueError('Original receivable for reversal was not found.')
        duplicate = db.query(ReceivableAdjustment).filter(
            ReceivableAdjustment.source_type == source_type,
            ReceivableAdjustment.source_id == payload.source_id,
        ).first()
        if duplicate:
            return _serialize_receivable(duplicate.receivable)
        current_balance = float(original.balance_due or 0)
        if abs(gross_amount) - current_balance > 0.0001:
            raise ValueError('Receivable reversal exceeds the remaining balance.')
        adjustment = ReceivableAdjustment(
            receivable_id=original.id,
            adjustment_date=_safe_date(payload.transaction_date),
            amount=gross_amount,
            source_type=source_type,
            source_id=payload.source_id,
            external_source=external_source,
            external_id=external_id,
            notes=payload.notes,
        )
        db.add(adjustment)
        db.flush()
        _update_receivable_balance(db, original.id)
        db.commit()
        db.refresh(original)
        return _serialize_receivable(original)

    if gross_amount <= 0:
        raise ValueError('gross_amount must be greater than zero.')
    if amount_collected > gross_amount:
        raise ValueError('amount_collected cannot exceed gross_amount.')

    row = Receivable(
        source_type=source_type,
        source_id=payload.source_id,
        counterparty_name=(payload.counterparty_name or '').strip(),
        receivable_type=(payload.receivable_type or 'guest_balance').strip() or 'guest_balance',
        transaction_date=_safe_date(payload.transaction_date),
        due_date=(payload.due_date or '').strip() or None,
        gross_amount=gross_amount,
        amount_collected=amount_collected,
        status=(payload.status or 'open').strip() or 'open',
        posted_at=_safe_date(payload.transaction_date),
        closed_at=None,
        notes=payload.notes,
        bir_include=bool(payload.bir_include),
        external_source=external_source,
        external_id=external_id,
    )
    db.add(row)
    db.flush()
    _update_receivable_balance(db, row.id)
    db.commit()
    db.refresh(row)
    return _serialize_receivable(row)


def list_receivables(
    db: Session,
    *,
    status: str | None = None,
    receivable_type: str | None = None,
    overdue_only: bool = False,
    q: str | None = None,
    limit: int = 300,
):
    query = db.query(Receivable)
    if status:
        query = query.filter(Receivable.status == (status or '').strip())
    if receivable_type:
        query = query.filter(Receivable.receivable_type == (receivable_type or '').strip())
    if overdue_only:
        today = _today()
        query = query.filter(Receivable.balance_due > 0, Receivable.due_date.isnot(None), Receivable.due_date < today)
    if q:
        like_q = f'%{q.strip()}%'
        query = query.filter(
            or_(
                Receivable.counterparty_name.like(like_q),
                Receivable.notes.like(like_q),
                Receivable.receivable_type.like(like_q),
            )
        )

    rows = query.order_by(Receivable.id.desc()).limit(max(1, min(int(limit or 300), 1000))).all()
    return [_serialize_receivable(row) for row in rows]


def collect_receivable(db: Session, receivable_id: int, payload: ReceivableCollectPayload, username: str | None = None):
    receivable = db.get(Receivable, int(receivable_id))
    if not receivable:
        raise ValueError('Receivable not found.')
    if float(receivable.balance_due or 0) <= 0:
        raise ValueError('Receivable is already settled.')

    amount = _as_float(payload.amount)
    if amount <= 0:
        raise ValueError('Collection amount must be greater than zero.')
    if amount > float(receivable.balance_due or 0):
        raise ValueError('Collection amount cannot exceed receivable balance.')

    tx = create_money_transaction(
        db,
        MoneyTransactionCreate(
            transaction_date=payload.collection_date,
            direction='in',
            financial_account_id=int(payload.financial_account_id),
            module=payload.module,
            category=payload.category,
            subcategory=payload.subcategory,
            level3_item=payload.level3_item,
            amount=amount,
            payment_method=payload.payment_method,
            reference_no=payload.reference_no,
            counterparty_name=receivable.counterparty_name,
            notes=payload.notes,
            linked_record_type=receivable.source_type,
            linked_record_id=receivable.source_id,
            receivable_id=receivable.id,
            bir_include=bool(receivable.bir_include),
            status='posted',
            auto_post_accounting=bool(payload.auto_post_accounting),
            allow_overdraw=False,
        ),
        username=username,
    )
    receivable = db.get(Receivable, int(receivable_id))
    return {
        'receivable': _serialize_receivable(receivable),
        'transaction': tx,
    }


def create_payable(db: Session, payload: PayableCreate):
    gross_amount = _as_float(payload.gross_amount)
    amount_paid = max(_as_float(payload.amount_paid), 0)
    if gross_amount <= 0:
        raise ValueError('gross_amount must be greater than zero.')
    if amount_paid > gross_amount:
        raise ValueError('amount_paid cannot exceed gross_amount.')

    row = Payable(
        source_type=(payload.source_type or '').strip() or None,
        source_id=payload.source_id,
        supplier_name=(payload.supplier_name or '').strip(),
        payable_type=(payload.payable_type or 'supplier_bill').strip() or 'supplier_bill',
        bill_date=_safe_date(payload.bill_date),
        due_date=(payload.due_date or '').strip() or None,
        gross_amount=gross_amount,
        amount_paid=amount_paid,
        status=(payload.status or 'open').strip() or 'open',
        posted_at=_safe_date(payload.bill_date),
        closed_at=None,
        notes=payload.notes,
        bir_include=bool(payload.bir_include),
    )
    db.add(row)
    db.flush()
    _update_payable_balance(db, row.id)
    db.commit()
    db.refresh(row)
    return _serialize_payable(row)


def list_payables(
    db: Session,
    *,
    status: str | None = None,
    payable_type: str | None = None,
    overdue_only: bool = False,
    q: str | None = None,
    limit: int = 300,
):
    query = db.query(Payable)
    if status:
        query = query.filter(Payable.status == (status or '').strip())
    if payable_type:
        query = query.filter(Payable.payable_type == (payable_type or '').strip())
    if overdue_only:
        today = _today()
        query = query.filter(Payable.balance_due > 0, Payable.due_date.isnot(None), Payable.due_date < today)
    if q:
        like_q = f'%{q.strip()}%'
        query = query.filter(
            or_(
                Payable.supplier_name.like(like_q),
                Payable.notes.like(like_q),
                Payable.payable_type.like(like_q),
            )
        )

    rows = query.order_by(Payable.id.desc()).limit(max(1, min(int(limit or 300), 1000))).all()
    return [_serialize_payable(row) for row in rows]


def pay_payable(db: Session, payable_id: int, payload: PayablePayPayload, username: str | None = None):
    payable = db.get(Payable, int(payable_id))
    if not payable:
        raise ValueError('Payable not found.')
    if float(payable.balance_due or 0) <= 0:
        raise ValueError('Payable is already settled.')

    amount = _as_float(payload.amount)
    if amount <= 0:
        raise ValueError('Payment amount must be greater than zero.')
    if amount > float(payable.balance_due or 0):
        raise ValueError('Payment amount cannot exceed payable balance.')

    tx = create_money_transaction(
        db,
        MoneyTransactionCreate(
            transaction_date=payload.payment_date,
            direction='out',
            financial_account_id=int(payload.financial_account_id),
            module=payload.module,
            category=payload.category,
            subcategory=payload.subcategory,
            level3_item=payload.level3_item,
            amount=amount,
            payment_method=payload.payment_method,
            reference_no=payload.reference_no,
            counterparty_name=payable.supplier_name,
            notes=payload.notes,
            linked_record_type=payable.source_type,
            linked_record_id=payable.source_id,
            payable_id=payable.id,
            bir_include=bool(payable.bir_include),
            status='posted',
            auto_post_accounting=bool(payload.auto_post_accounting),
            allow_overdraw=False,
        ),
        username=username,
    )
    payable = db.get(Payable, int(payable_id))
    return {
        'payable': _serialize_payable(payable),
        'transaction': tx,
    }


def update_receivable(db: Session, receivable_id: int, payload: ReceivableCreate):
    row = db.get(Receivable, int(receivable_id))
    if not row:
        raise ValueError('Receivable not found.')
    row.source_type = (payload.source_type or '').strip() or None
    row.source_id = payload.source_id
    row.counterparty_name = (payload.counterparty_name or '').strip()
    row.receivable_type = (payload.receivable_type or 'guest_balance').strip() or 'guest_balance'
    row.transaction_date = _safe_date(payload.transaction_date)
    row.due_date = (payload.due_date or '').strip() or None
    row.gross_amount = max(_as_float(payload.gross_amount), 0)
    row.amount_collected = max(_as_float(payload.amount_collected), 0)
    row.notes = payload.notes
    row.bir_include = bool(payload.bir_include)
    row.status = (payload.status or row.status or 'open').strip() or 'open'
    row.posted_at = row.posted_at or row.transaction_date
    db.add(row)
    db.flush()
    _update_receivable_balance(db, row.id)
    db.commit()
    db.refresh(row)
    return _serialize_receivable(row)


def write_off_receivable(db: Session, receivable_id: int, payload: CashflowActionPayload):
    row = db.get(Receivable, int(receivable_id))
    if not row:
        raise ValueError('Receivable not found.')
    if float(row.balance_due or 0) <= 0:
        raise ValueError('Receivable has no remaining balance.')
    row.status = 'written_off'
    row.amount_collected = float(row.gross_amount or 0)
    row.balance_due = 0
    row.closed_at = _safe_date(payload.action_date or _today())
    if payload.reason:
        row.notes = f"{row.notes or ''}\nWrite-off: {payload.reason}".strip()
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_receivable(row)


def reopen_receivable(db: Session, receivable_id: int, payload: CashflowActionPayload):
    row = db.get(Receivable, int(receivable_id))
    if not row:
        raise ValueError('Receivable not found.')
    if row.status not in {'settled', 'written_off'}:
        raise ValueError('Only settled/written-off receivables can be reopened.')
    row.status = 'open'
    row.amount_collected = max(0.0, min(float(row.amount_collected or 0), float(row.gross_amount or 0)))
    row.closed_at = None
    _update_receivable_balance(db, row.id)
    if payload.reason:
        row.notes = f"{row.notes or ''}\nReopened: {payload.reason}".strip()
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_receivable(row)


def reverse_receivable_collection(db: Session, receivable_id: int, transaction_id: int, payload: CashflowActionPayload, username: str | None = None):
    receivable = db.get(Receivable, int(receivable_id))
    if not receivable:
        raise ValueError('Receivable not found.')
    tx = db.get(MoneyTransaction, int(transaction_id))
    if not tx:
        raise ValueError('Money transaction not found.')
    if int(tx.receivable_id or 0) != int(receivable.id):
        raise ValueError('Transaction is not linked to this receivable.')
    if _normalize(tx.direction) != 'in':
        raise ValueError('Only money-in transaction can reverse receivable collection.')
    return reverse_money_transaction(db, tx.id, payload, username=username)


def update_payable(db: Session, payable_id: int, payload: PayableCreate):
    row = db.get(Payable, int(payable_id))
    if not row:
        raise ValueError('Payable not found.')
    row.source_type = (payload.source_type or '').strip() or None
    row.source_id = payload.source_id
    row.supplier_name = (payload.supplier_name or '').strip()
    row.payable_type = (payload.payable_type or 'supplier_bill').strip() or 'supplier_bill'
    row.bill_date = _safe_date(payload.bill_date)
    row.due_date = (payload.due_date or '').strip() or None
    row.gross_amount = max(_as_float(payload.gross_amount), 0)
    row.amount_paid = max(_as_float(payload.amount_paid), 0)
    row.notes = payload.notes
    row.bir_include = bool(payload.bir_include)
    row.status = (payload.status or row.status or 'open').strip() or 'open'
    row.posted_at = row.posted_at or row.bill_date
    db.add(row)
    db.flush()
    _update_payable_balance(db, row.id)
    db.commit()
    db.refresh(row)
    return _serialize_payable(row)


def write_off_payable(db: Session, payable_id: int, payload: CashflowActionPayload):
    row = db.get(Payable, int(payable_id))
    if not row:
        raise ValueError('Payable not found.')
    if float(row.balance_due or 0) <= 0:
        raise ValueError('Payable has no remaining balance.')
    row.status = 'written_off'
    row.amount_paid = float(row.gross_amount or 0)
    row.balance_due = 0
    row.closed_at = _safe_date(payload.action_date or _today())
    if payload.reason:
        row.notes = f"{row.notes or ''}\nWrite-off: {payload.reason}".strip()
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_payable(row)


def reopen_payable(db: Session, payable_id: int, payload: CashflowActionPayload):
    row = db.get(Payable, int(payable_id))
    if not row:
        raise ValueError('Payable not found.')
    if row.status not in {'settled', 'written_off'}:
        raise ValueError('Only settled/written-off payables can be reopened.')
    row.status = 'open'
    row.amount_paid = max(0.0, min(float(row.amount_paid or 0), float(row.gross_amount or 0)))
    row.closed_at = None
    _update_payable_balance(db, row.id)
    if payload.reason:
        row.notes = f"{row.notes or ''}\nReopened: {payload.reason}".strip()
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_payable(row)


def reverse_payable_payment(db: Session, payable_id: int, transaction_id: int, payload: CashflowActionPayload, username: str | None = None):
    payable = db.get(Payable, int(payable_id))
    if not payable:
        raise ValueError('Payable not found.')
    tx = db.get(MoneyTransaction, int(transaction_id))
    if not tx:
        raise ValueError('Money transaction not found.')
    if int(tx.payable_id or 0) != int(payable.id):
        raise ValueError('Transaction is not linked to this payable.')
    if _normalize(tx.direction) != 'out':
        raise ValueError('Only money-out transaction can reverse payable payment.')
    return reverse_money_transaction(db, tx.id, payload, username=username)


def create_template(db: Session, payload: CashflowTemplateCreate):
    direction = _normalize(payload.direction)
    if direction not in {'in', 'out'}:
        raise ValueError('direction must be "in" or "out".')

    row = CashflowTemplate(
        name=(payload.name or '').strip(),
        direction=direction,
        default_module=(payload.default_module or 'finance').strip() or 'finance',
        default_category=(payload.default_category or '').strip() or None,
        default_subcategory=(payload.default_subcategory or '').strip() or None,
        default_level3_item=(payload.default_level3_item or '').strip() or None,
        default_account_id=payload.default_account_id,
        default_payment_method=(payload.default_payment_method or '').strip() or None,
        default_bir_include=bool(payload.default_bir_include),
        default_notes=payload.default_notes,
        is_active=bool(payload.is_active),
    )
    db.add(row)
    db.commit()
    row = db.query(CashflowTemplate).options(selectinload(CashflowTemplate.default_account)).filter(CashflowTemplate.id == row.id).first()
    return _serialize_template(row)


def update_template(db: Session, template_id: int, payload: CashflowTemplateUpdate):
    row = db.get(CashflowTemplate, int(template_id))
    if not row:
        raise ValueError('Template not found.')

    data = payload.model_dump(exclude_unset=True)
    if 'direction' in data:
        direction = _normalize(data.get('direction'))
        if direction not in {'in', 'out'}:
            raise ValueError('direction must be "in" or "out".')
        data['direction'] = direction

    for key, value in data.items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(row, key, value)

    if row.default_module is None:
        row.default_module = 'finance'

    db.add(row)
    db.commit()
    row = db.query(CashflowTemplate).options(selectinload(CashflowTemplate.default_account)).filter(CashflowTemplate.id == row.id).first()
    return _serialize_template(row)


def list_templates(db: Session, active_only: bool = False):
    query = db.query(CashflowTemplate).options(selectinload(CashflowTemplate.default_account))
    if active_only:
        query = query.filter(CashflowTemplate.is_active == True)
    rows = query.order_by(CashflowTemplate.name.asc(), CashflowTemplate.id.asc()).all()
    return [_serialize_template(row) for row in rows]


def delete_template(db: Session, template_id: int):
    row = db.get(CashflowTemplate, int(template_id))
    if not row:
        raise ValueError('Template not found.')
    db.delete(row)
    db.commit()
    return {'ok': True}


def launch_template(db: Session, template_id: int, overrides: dict, username: str | None = None):
    row = db.get(CashflowTemplate, int(template_id))
    if not row:
        raise ValueError('Template not found.')
    if not row.is_active:
        raise ValueError('Template is inactive.')

    payload = {
        'transaction_date': overrides.get('transaction_date'),
        'direction': overrides.get('direction') or row.direction,
        'financial_account_id': overrides.get('financial_account_id') or row.default_account_id,
        'module': overrides.get('module') or row.default_module or 'finance',
        'category': overrides.get('category') or row.default_category,
        'subcategory': overrides.get('subcategory') or row.default_subcategory,
        'level3_item': overrides.get('level3_item') or row.default_level3_item,
        'amount': overrides.get('amount'),
        'payment_method': overrides.get('payment_method') or row.default_payment_method,
        'reference_no': overrides.get('reference_no'),
        'counterparty_name': overrides.get('counterparty_name'),
        'notes': overrides.get('notes') or row.default_notes,
        'linked_record_type': overrides.get('linked_record_type'),
        'linked_record_id': overrides.get('linked_record_id'),
        'receivable_id': overrides.get('receivable_id'),
        'payable_id': overrides.get('payable_id'),
        'bir_include': overrides.get('bir_include', row.default_bir_include),
        'status': overrides.get('status', 'posted'),
        'auto_post_accounting': bool(overrides.get('auto_post_accounting', False)),
        'allow_overdraw': bool(overrides.get('allow_overdraw', False)),
    }
    if not payload['financial_account_id']:
        raise ValueError('Template launch requires financial_account_id.')
    if _as_float(payload['amount']) <= 0:
        raise ValueError('Template launch amount must be greater than zero.')

    return create_money_transaction(db, MoneyTransactionCreate(**payload), username=username)


def cashflow_summary(db: Session, target_date: str | None = None):
    ensure_default_financial_accounts(db)
    date_key = _safe_date(target_date)

    accounts = list_financial_accounts(db, on_date=date_key)
    tx_today = list_money_transactions(db, start_date=date_key, end_date=date_key, limit=300)
    transfer_today = list_transfers(db, start_date=date_key, end_date=date_key, limit=200)

    total_cash = sum(float(row.get('current_balance') or 0) for row in accounts if row.get('account_type') != 'bank')
    total_bank = sum(float(row.get('current_balance') or 0) for row in accounts if row.get('account_type') == 'bank')

    today_in = sum(float(row.get('amount') or 0) for row in tx_today if _normalize(row.get('direction')) == 'in')
    today_out = sum(float(row.get('amount') or 0) for row in tx_today if _normalize(row.get('direction')) == 'out')

    receivables_due = (
        db.query(func.sum(Receivable.balance_due))
        .filter(Receivable.balance_due > 0)
        .scalar()
        or 0
    )
    payables_due = (
        db.query(func.sum(Payable.balance_due))
        .filter(Payable.balance_due > 0)
        .scalar()
        or 0
    )

    unreconciled_accounts = 0
    variance_alerts = 0
    for row in accounts:
        if row.get('requires_daily_reconciliation') and row.get('reconciliation_status') == 'missing':
            unreconciled_accounts += 1
        if row.get('reconciliation_variance') is not None and abs(float(row.get('reconciliation_variance') or 0)) >= 0.01:
            variance_alerts += 1

    overdue_receivables = (
        db.query(Receivable)
        .filter(Receivable.balance_due > 0, Receivable.due_date.isnot(None), Receivable.due_date < date_key)
        .order_by(Receivable.due_date.asc(), Receivable.id.desc())
        .limit(20)
        .all()
    )
    overdue_payables = (
        db.query(Payable)
        .filter(Payable.balance_due > 0, Payable.due_date.isnot(None), Payable.due_date < date_key)
        .order_by(Payable.due_date.asc(), Payable.id.desc())
        .limit(20)
        .all()
    )

    recent_variances = (
        db.query(CashReconciliation)
        .options(selectinload(CashReconciliation.financial_account))
        .filter(func.abs(CashReconciliation.variance) >= 0.01)
        .order_by(CashReconciliation.reconciliation_date.desc(), CashReconciliation.id.desc())
        .limit(20)
        .all()
    )

    journal_post_failures = [
        row for row in tx_today if _normalize(row.get('status')) in {'posted', 'approved'} and row.get('journal_entry_id') is None and bool(row.get('module'))
    ]

    return {
        'date': date_key,
        'summary_cards': {
            'total_cash_on_hand': round(float(total_cash), 4),
            'total_bank_balance': round(float(total_bank), 4),
            'receivables_due': round(float(receivables_due or 0), 4),
            'payables_due': round(float(payables_due or 0), 4),
            'todays_money_in': round(float(today_in), 4),
            'todays_money_out': round(float(today_out), 4),
            'unreconciled_accounts': int(unreconciled_accounts),
            'variance_alerts': int(variance_alerts),
        },
        'recent_transactions': tx_today[:50],
        'recent_transfers': transfer_today[:50],
        'accounts_requiring_reconciliation': [row for row in accounts if row.get('requires_daily_reconciliation') and row.get('reconciliation_status') == 'missing'],
        'overdue_receivables': [_serialize_receivable(row) for row in overdue_receivables],
        'overdue_payables': [_serialize_payable(row) for row in overdue_payables],
        'recent_variances': [_serialize_reconciliation(row) for row in recent_variances],
        'journal_posting_failures': journal_post_failures,
    }


def account_ledger(
    db: Session,
    account_id: int,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    include_reconciliations: bool = True,
    limit: int = 500,
):
    ensure_default_financial_accounts(db)
    account = db.get(FinancialAccount, int(account_id))
    if not account:
        raise ValueError('Financial account not found.')

    query_tx = db.query(MoneyTransaction).filter(MoneyTransaction.financial_account_id == account.id)
    query_tr = db.query(AccountTransfer).filter(or_(AccountTransfer.from_account_id == account.id, AccountTransfer.to_account_id == account.id))
    query_re = db.query(CashReconciliation).filter(CashReconciliation.financial_account_id == account.id)

    if start_date:
        query_tx = query_tx.filter(MoneyTransaction.transaction_date >= start_date)
        query_tr = query_tr.filter(AccountTransfer.transfer_date >= start_date)
        query_re = query_re.filter(CashReconciliation.reconciliation_date >= start_date)
    if end_date:
        query_tx = query_tx.filter(MoneyTransaction.transaction_date <= end_date)
        query_tr = query_tr.filter(AccountTransfer.transfer_date <= end_date)
        query_re = query_re.filter(CashReconciliation.reconciliation_date <= end_date)

    tx_rows = query_tx.order_by(MoneyTransaction.transaction_date.asc(), MoneyTransaction.id.asc()).limit(limit).all()
    tr_rows = query_tr.order_by(AccountTransfer.transfer_date.asc(), AccountTransfer.id.asc()).limit(limit).all()
    re_rows = query_re.order_by(CashReconciliation.reconciliation_date.asc(), CashReconciliation.id.asc()).limit(limit).all() if include_reconciliations else []

    if start_date:
        opening_balance = _account_opening_balance_at(db, account.id, start_date)
    else:
        opening_balance = float(account.opening_balance or 0)

    rows = [
        {
            'entry_type': 'opening_balance',
            'entry_id': 0,
            'date': start_date or 'opening',
            'description': 'Opening Balance',
            'reference_no': None,
            'debit': round(opening_balance, 4) if opening_balance >= 0 else 0.0,
            'credit': round(abs(opening_balance), 4) if opening_balance < 0 else 0.0,
            'signed_amount': round(opening_balance, 4),
            'meta': {},
        }
    ]

    for row in tx_rows:
        signed = float(row.amount or 0) if _normalize(row.direction) == 'in' else -float(row.amount or 0)
        rows.append(
            {
                'entry_type': 'money_transaction',
                'entry_id': row.id,
                'date': row.transaction_date,
                'description': f"{row.direction.upper()} · {row.category or '-'} / {row.subcategory or '-'}",
                'reference_no': row.reference_no,
                'debit': round(max(signed, 0), 4),
                'credit': round(abs(min(signed, 0)), 4),
                'signed_amount': round(signed, 4),
                'meta': _serialize_money_transaction(
                    db.query(MoneyTransaction).options(selectinload(MoneyTransaction.financial_account)).filter(MoneyTransaction.id == row.id).first()
                ),
            }
        )

    for row in tr_rows:
        signed = float(row.amount or 0)
        if int(row.from_account_id) == int(account.id):
            signed = -signed
        rows.append(
            {
                'entry_type': 'account_transfer',
                'entry_id': row.id,
                'date': row.transfer_date,
                'description': 'Transfer',
                'reference_no': row.reference_no,
                'debit': round(max(signed, 0), 4),
                'credit': round(abs(min(signed, 0)), 4),
                'signed_amount': round(signed, 4),
                'meta': _serialize_transfer(
                    db.query(AccountTransfer)
                    .options(selectinload(AccountTransfer.from_account), selectinload(AccountTransfer.to_account))
                    .filter(AccountTransfer.id == row.id)
                    .first()
                ),
            }
        )

    if include_reconciliations:
        for row in re_rows:
            rows.append(
                {
                    'entry_type': 'cash_reconciliation',
                    'entry_id': row.id,
                    'date': row.reconciliation_date,
                    'description': f"Reconciliation ({row.shift_name or 'day'})",
                    'reference_no': None,
                    'debit': 0.0,
                    'credit': 0.0,
                    'signed_amount': 0.0,
                    'meta': _serialize_reconciliation(
                        db.query(CashReconciliation)
                        .options(selectinload(CashReconciliation.financial_account), selectinload(CashReconciliation.lines))
                        .filter(CashReconciliation.id == row.id)
                        .first()
                    ),
                }
            )

    def _sort_key(item):
        date_value = item.get('date') or ''
        return (date_value, str(item.get('entry_type') or ''), int(item.get('entry_id') or 0))

    ordered = sorted(rows, key=_sort_key)

    running_balance = 0.0
    result_rows = []
    for row in ordered:
        running_balance += float(row.get('signed_amount') or 0)
        out = dict(row)
        out['running_balance'] = round(running_balance, 4)
        result_rows.append(out)

    return {
        'account': _serialize_account(account),
        'opening_balance': round(opening_balance, 4),
        'rows': result_rows,
        'closing_balance': round(running_balance, 4),
    }

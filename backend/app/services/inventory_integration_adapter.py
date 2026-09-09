from __future__ import annotations

from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from sqlalchemy.orm import Session

from app.schemas.integration_review import IntegrationReviewCreate
from app.services.account_mapping_service import resolve_record_accounts


STAFF_MEAL_TYPES = {'staff_meal', 'staff_meal_reversal'}
STAFF_MEAL_CATEGORY = 'Staff Meals'
POS_COGS_EVENTS = {'inventory.pos_sale_consumed', 'inventory.pos_sale_reversed'}
POS_COGS_CATEGORY = 'Cost of goods sold'


def _money(value) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0')


def _staff_meal_value(lines) -> Decimal:
    if not isinstance(lines, list):
        return Decimal('0')
    return sum(
        (abs(_money(line.get('quantity')) * _money(line.get('unit_cost'))) for line in lines if isinstance(line, dict)),
        Decimal('0'),
    ).quantize(Decimal('0.01'))


def _posting_accounts(db: Session, category: str):
    mapping_record = SimpleNamespace(
        module_slug='inventory',
        category=category,
        bucket=None,
        item=None,
        direction='out',
        payment_method=None,
    )
    debit_account, credit_account = resolve_record_accounts(db, mapping_record, None, None)
    if not debit_account or not credit_account:
        raise ValueError(
            f'Accounting posting rule required for module inventory, category {category}, direction out.'
        )
    return debit_account, credit_account


def _journal(amount: Decimal, debit_account, credit_account, description: str, memo: str | None = None) -> dict:
    return {
        'description': description,
        'lines': [
            {
                'account_code': debit_account[0],
                'account_name': debit_account[1],
                'debit': float(amount),
                'credit': 0,
                'memo': memo or description,
            },
            {
                'account_code': credit_account[0],
                'account_name': credit_account[1],
                'debit': 0,
                'credit': float(amount),
                'memo': memo or description,
            },
        ],
    }


def _normalize_staff_meal(db: Session, payload: IntegrationReviewCreate, data: dict) -> IntegrationReviewCreate:
    document_type = str(data.get('document_type') or '').strip().lower()
    if document_type not in STAFF_MEAL_TYPES:
        return payload

    amount = _staff_meal_value(data.get('lines'))
    if amount <= 0:
        raise ValueError('Inventory Staff Meals event must contain a positive costed stock value.')

    debit_account, credit_account = _posting_accounts(db, STAFF_MEAL_CATEGORY)
    reversal = document_type == 'staff_meal_reversal'
    if reversal:
        debit_account, credit_account = credit_account, debit_account

    document_number = str(data.get('document_number') or '').strip()
    reference = str(data.get('reference') or '').strip()
    label = document_number or reference or str(payload.source_entity_id or '')
    description = f'Staff meal reversal {label}' if reversal else f'Staff meal {label}'
    links = {
        **(payload.proposed_links or {}),
        'target_type': 'stock_document',
        'target_id': str(data.get('document_id') or payload.source_entity_id or ''),
        'document_type': document_type,
        'document_number': data.get('document_number'),
        'category': STAFF_MEAL_CATEGORY,
        'reversal': reversal,
    }
    return payload.model_copy(
        update={
            'financial_effect': 'journal_only',
            'amount': float(amount),
            'proposed_journal': _journal(amount, debit_account, credit_account, description.strip(), reference or None),
            'proposed_links': links,
        }
    )


def _normalize_pos_cogs(db: Session, payload: IntegrationReviewCreate, event_type: str, data: dict) -> IntegrationReviewCreate:
    amount = _money(data.get('total_cost')).quantize(Decimal('0.01'))
    if amount <= 0:
        raise ValueError('Inventory POS COGS event must contain a positive total_cost.')

    debit_account, credit_account = _posting_accounts(db, POS_COGS_CATEGORY)
    reversal = event_type == 'inventory.pos_sale_reversed'
    if reversal:
        debit_account, credit_account = credit_account, debit_account

    sale_id = str(data.get('sale_id') or payload.source_entity_id or '').strip()
    description = f'POS COGS reversal {sale_id}' if reversal else f'POS COGS {sale_id}'
    links = {
        **(payload.proposed_links or {}),
        'target_type': 'pos_sale',
        'target_id': sale_id,
        'sale_id': data.get('sale_id'),
        'stock_document_id': data.get('stock_document_id'),
        'reverses_stock_document_id': data.get('reverses_stock_document_id'),
        'category': POS_COGS_CATEGORY,
        'reversal': reversal,
    }
    return payload.model_copy(
        update={
            'financial_effect': 'journal_only',
            'amount': float(amount),
            'proposed_journal': _journal(amount, debit_account, credit_account, description),
            'proposed_links': links,
        }
    )


def normalize_inventory_review_payload(db: Session, payload: IntegrationReviewCreate) -> IntegrationReviewCreate:
    """Convert costed Inventory events into Accounting-owned journal proposals.

    Inventory owns quantities and weighted-average costs. Accounting owns the chart of
    accounts through AccountMappingRule. No GL account codes are embedded in Inventory.
    """
    if payload.source_app.strip().lower() != 'inventory':
        return payload

    envelope = payload.payload if isinstance(payload.payload, dict) else {}
    event_type = str(envelope.get('event_type') or '').strip()
    data = envelope.get('data') if isinstance(envelope.get('data'), dict) else {}

    if event_type == 'inventory.stock_document.posted':
        return _normalize_staff_meal(db, payload, data)
    if event_type in POS_COGS_EVENTS:
        return _normalize_pos_cogs(db, payload, event_type, data)
    return payload

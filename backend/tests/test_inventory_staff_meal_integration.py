import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.entities import AccountMappingRule, ChartAccount, JournalEntry, JournalLine
from app.schemas.integration_review import IntegrationReviewCreate, IntegrationReviewDecision
from app.services.integration_review_service import accept_item, create_review_item
from app.services.inventory_integration_adapter import normalize_inventory_review_payload


def make_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def seed_staff_meal_mapping(db):
    db.add_all([
        ChartAccount(code='6100-SM', name='Staff Meals Expense', account_type='expense', is_active=True),
        ChartAccount(code='1200-INV', name='Inventory', account_type='asset', is_active=True),
    ])
    db.flush()
    db.add(AccountMappingRule(
        module_slug='inventory',
        category='Staff Meals',
        direction='out',
        debit_account_code='6100-SM',
        credit_account_code='1200-INV',
        priority=10,
        is_active=True,
    ))
    db.commit()


def stock_event(document_type='staff_meal'):
    return IntegrationReviewCreate(
        source_app='inventory',
        source_event_id=f'evt-{document_type}',
        source_entity_type='stock_document',
        source_entity_id=f'doc-{document_type}',
        source_revision=1,
        financial_effect='reference_only',
        amount=0,
        proposed_links={'target_type': 'stock_document', 'target_id': f'doc-{document_type}'},
        payload={
            'event_type': 'inventory.stock_document.posted',
            'aggregate_type': 'stock_document',
            'aggregate_id': f'doc-{document_type}',
            'data': {
                'document_id': f'doc-{document_type}',
                'document_number': 'SM-0001' if document_type == 'staff_meal' else 'SMR-0001',
                'document_type': document_type,
                'reference': 'Chicken adobo',
                'lines': [
                    {'item_id': 'chicken', 'quantity': '-2.0' if document_type == 'staff_meal' else '2.0', 'unit_cost': '80.00'},
                    {'item_id': 'soy', 'quantity': '-0.5' if document_type == 'staff_meal' else '0.5', 'unit_cost': '20.00'},
                ],
            },
        },
        idempotency_key=f'stock-document:doc-{document_type}',
    )


def test_staff_meal_becomes_costed_journal_using_accounting_mapping():
    db = make_session()
    seed_staff_meal_mapping(db)

    adapted = normalize_inventory_review_payload(db, stock_event('staff_meal'))

    assert adapted.financial_effect == 'journal_only'
    assert adapted.amount == 170.0
    assert adapted.proposed_links['category'] == 'Staff Meals'
    assert adapted.proposed_links['reversal'] is False
    lines = adapted.proposed_journal['lines']
    assert lines[0]['account_code'] == '6100-SM'
    assert lines[0]['debit'] == 170.0
    assert lines[1]['account_code'] == '1200-INV'
    assert lines[1]['credit'] == 170.0


def test_staff_meal_reversal_swaps_debit_and_credit_from_same_rule():
    db = make_session()
    seed_staff_meal_mapping(db)

    adapted = normalize_inventory_review_payload(db, stock_event('staff_meal_reversal'))

    assert adapted.financial_effect == 'journal_only'
    assert adapted.amount == 170.0
    assert adapted.proposed_links['reversal'] is True
    lines = adapted.proposed_journal['lines']
    assert lines[0]['account_code'] == '1200-INV'
    assert lines[0]['debit'] == 170.0
    assert lines[1]['account_code'] == '6100-SM'
    assert lines[1]['credit'] == 170.0


def test_staff_meal_missing_posting_rule_fails_loudly():
    db = make_session()
    with pytest.raises(ValueError, match='posting rule required'):
        normalize_inventory_review_payload(db, stock_event('staff_meal'))


def test_non_staff_stock_document_remains_reference_only():
    db = make_session()
    payload = stock_event('issue')
    adapted = normalize_inventory_review_payload(db, payload)
    assert adapted is payload
    assert adapted.financial_effect == 'reference_only'


def test_staff_meal_review_acceptance_posts_balanced_journal_and_replay_is_idempotent():
    db = make_session()
    seed_staff_meal_mapping(db)
    adapted = normalize_inventory_review_payload(db, stock_event('staff_meal'))

    created = create_review_item(db, adapted)
    replay = create_review_item(db, adapted)
    assert replay['id'] == created['id']
    assert created['status'] == 'ready_for_review'

    accepted = accept_item(
        db,
        created['id'],
        IntegrationReviewDecision(transaction_date='2026-09-09'),
        'integration-reviewer',
    )
    accepted_replay = accept_item(
        db,
        created['id'],
        IntegrationReviewDecision(transaction_date='2026-09-09'),
        'integration-reviewer',
    )

    assert accepted_replay['accepted_journal_entry_id'] == accepted['accepted_journal_entry_id']
    assert db.query(JournalEntry).count() == 1
    lines = db.query(JournalLine).order_by(JournalLine.id).all()
    assert len(lines) == 2
    assert float(lines[0].debit) == 170.0
    assert float(lines[1].credit) == 170.0

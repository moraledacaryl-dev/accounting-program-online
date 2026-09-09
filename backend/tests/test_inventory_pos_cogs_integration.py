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


def seed_cogs_mapping(db):
    db.add_all([
        ChartAccount(code='5100-COGS', name='Cost of Goods Sold', account_type='expense', is_active=True),
        ChartAccount(code='1200-INV', name='Inventory', account_type='asset', is_active=True),
    ])
    db.flush()
    db.add(AccountMappingRule(
        module_slug='inventory',
        category='Cost of goods sold',
        direction='out',
        debit_account_code='5100-COGS',
        credit_account_code='1200-INV',
        priority=10,
        is_active=True,
    ))
    db.commit()


def pos_event(event_type='inventory.pos_sale_consumed', total_cost='20.00'):
    reversal = event_type == 'inventory.pos_sale_reversed'
    data = {
        'sale_id': 'sale-001',
        'stock_document_id': 'doc-reversal' if reversal else 'doc-sale',
        'total_cost': total_cost,
    }
    if reversal:
        data.update({
            'event_type': 'sale_refunded',
            'reverses_stock_document_id': 'doc-sale',
        })
    else:
        data['lines'] = [{'external_product_id': 'CAFE-001', 'quantity': '2', 'cost': total_cost}]
    return IntegrationReviewCreate(
        source_app='inventory',
        source_event_id='evt-reversal' if reversal else 'evt-sale',
        source_entity_type='pos_sale_event',
        source_entity_id='pos-row-2' if reversal else 'pos-row-1',
        source_revision=1,
        financial_effect='reference_only',
        amount=0,
        proposed_links={'target_type': 'pos_sale', 'target_id': 'sale-001'},
        payload={
            'event_type': event_type,
            'aggregate_type': 'pos_sale_event',
            'aggregate_id': 'pos-row-2' if reversal else 'pos-row-1',
            'data': data,
        },
        idempotency_key='accounting-pos:evt-002' if reversal else 'accounting-pos:evt-001',
    )


def test_pos_sale_consumption_becomes_cogs_journal_using_accounting_mapping():
    db = make_session()
    seed_cogs_mapping(db)

    adapted = normalize_inventory_review_payload(db, pos_event())

    assert adapted.financial_effect == 'journal_only'
    assert adapted.amount == 20.0
    assert adapted.proposed_links['category'] == 'Cost of goods sold'
    assert adapted.proposed_links['reversal'] is False
    lines = adapted.proposed_journal['lines']
    assert lines[0]['account_code'] == '5100-COGS'
    assert lines[0]['debit'] == 20.0
    assert lines[1]['account_code'] == '1200-INV'
    assert lines[1]['credit'] == 20.0


def test_pos_sale_reversal_swaps_cogs_and_inventory_accounts():
    db = make_session()
    seed_cogs_mapping(db)

    adapted = normalize_inventory_review_payload(db, pos_event('inventory.pos_sale_reversed'))

    assert adapted.financial_effect == 'journal_only'
    assert adapted.amount == 20.0
    assert adapted.proposed_links['reversal'] is True
    assert adapted.proposed_links['reverses_stock_document_id'] == 'doc-sale'
    lines = adapted.proposed_journal['lines']
    assert lines[0]['account_code'] == '1200-INV'
    assert lines[0]['debit'] == 20.0
    assert lines[1]['account_code'] == '5100-COGS'
    assert lines[1]['credit'] == 20.0


def test_pos_cogs_missing_or_zero_cost_fails_loudly():
    db = make_session()
    seed_cogs_mapping(db)
    with pytest.raises(ValueError, match='positive total_cost'):
        normalize_inventory_review_payload(db, pos_event(total_cost='0'))


def test_pos_cogs_missing_posting_rule_fails_loudly():
    db = make_session()
    with pytest.raises(ValueError, match='posting rule required'):
        normalize_inventory_review_payload(db, pos_event())


def test_unrelated_inventory_event_remains_unchanged():
    db = make_session()
    payload = pos_event()
    payload = payload.model_copy(update={
        'payload': {**payload.payload, 'event_type': 'inventory.production.completed'}
    })
    adapted = normalize_inventory_review_payload(db, payload)
    assert adapted is payload
    assert adapted.financial_effect == 'reference_only'


def test_pos_cogs_review_acceptance_posts_one_balanced_journal_and_replay_is_idempotent():
    db = make_session()
    seed_cogs_mapping(db)
    adapted = normalize_inventory_review_payload(db, pos_event())

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
    assert float(lines[0].debit) == 20.0
    assert float(lines[1].credit) == 20.0

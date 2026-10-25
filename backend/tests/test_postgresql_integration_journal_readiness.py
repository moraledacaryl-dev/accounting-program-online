"""Real PostgreSQL ledger guards and duplicate-review serialization."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest

from app.db.database import SessionLocal, engine
from app.models.entities import ChartAccount, JournalEntry, JournalLine
from app.schemas.integration_review import IntegrationReviewCreate, IntegrationReviewDecision
from app.services.integration_review_service import accept_item, create_review_item

pytestmark = pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='PostgreSQL CI lane only')


def review(db, *, credit='100.0040'):
    marker = uuid4().hex[:12]
    codes = [f'JR-{marker}-DR', f'JR-{marker}-CR']
    db.add_all([ChartAccount(code=code, name=code, account_type='asset', is_active=True) for code in codes])
    db.commit()
    item = create_review_item(db, IntegrationReviewCreate(
        source_app='inventory', source_event_id=f'isolated-{marker}',
        source_entity_type='stock_document', financial_effect='journal_only', amount=100.004,
        proposed_journal={'lines': [
            {'account_code': codes[0], 'debit': '100.0040', 'credit': 0},
            {'account_code': codes[1], 'debit': 0, 'credit': credit},
        ]},
    ))
    return item, codes


def test_postgresql_subcent_imbalance_has_no_posted_effect():
    with SessionLocal() as db:
        item, _ = review(db, credit='100.0000')
        assert item['status'] == 'validation_failed'
        with pytest.raises(ValueError, match='ready for review'):
            accept_item(db, item['id'], IntegrationReviewDecision(transaction_date='2026-10-25'), 'isolated-reviewer')
        assert db.query(JournalEntry).filter_by(reference_no=f"inventory:{item['source_event_id']}").count() == 0


def test_postgresql_deactivated_proposal_cannot_post():
    with SessionLocal() as db:
        item, codes = review(db)
        db.query(ChartAccount).filter_by(code=codes[1]).one().is_active = False
        db.commit()
        with pytest.raises(ValueError, match='active chart accounts'):
            accept_item(db, item['id'], IntegrationReviewDecision(transaction_date='2026-10-25'), 'isolated-reviewer')
        db.rollback()
        assert db.query(JournalEntry).filter_by(reference_no=f"inventory:{item['source_event_id']}").count() == 0


def test_postgresql_simultaneous_acceptance_posts_one_exact_journal():
    with SessionLocal() as db:
        item, _ = review(db)
    barrier = Barrier(2)

    def accept():
        with SessionLocal() as db:
            barrier.wait(timeout=10)
            return accept_item(db, item['id'], IntegrationReviewDecision(transaction_date='2026-10-25'), 'isolated-reviewer')['accepted_journal_entry_id']

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(accept) for _ in range(2)]
        ids = [future.result(timeout=20) for future in futures]
    assert ids[0] == ids[1]
    with SessionLocal() as db:
        assert db.query(JournalEntry).filter_by(reference_no=f"inventory:{item['source_event_id']}").count() == 1
        lines = db.query(JournalLine).filter_by(journal_entry_id=ids[0]).all()
        assert len(lines) == 2
        assert sum(line.debit for line in lines) == sum(line.credit for line in lines) == Decimal('100.0040')

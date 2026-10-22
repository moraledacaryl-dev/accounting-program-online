import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.entities import IntegrationReviewItem
from app.services.integration_review_service import list_review_items, paginated_review_items


@pytest.fixture()
def db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session
    engine.dispose()


def add(db, event, *, source='pos', entity=None, status='ready_for_review', payload=None):
    row = IntegrationReviewItem(
        source_app=source,
        source_event_id=event,
        source_entity_type='sale' if source == 'pos' else 'Payroll Run',
        source_entity_id=str(entity) if entity is not None else event,
        source_revision=1,
        financial_effect='journal_only',
        amount=100,
        currency='PHP',
        status=status,
        payload_json=json.dumps(payload or {}),
        idempotency_key='fixture-' + event,
    )
    db.add(row)
    db.flush()
    return row


def test_pages_cover_every_visible_item_once_without_losing_rows_after_staff_hiding(db):
    for index in range(56):
        add(db, 'pos-' + str(index), status='ready_for_review' if index % 2 else 'accepted')

    # Approved + original Paid remain in immutable history, but should not
    # consume slots after a later Paid revision supersedes the original.
    approved = add(db, 'payroll:10:Approved', source='staff', entity=10)
    old_paid = add(db, 'payroll:10:Paid', source='staff', entity=10,
                   payload={'run': {'id': 10}})
    revised_paid = add(db, 'payroll:11:Paid', source='staff', entity=11,
                       payload={'run': {'id': 11, 'revision_of_run_id': 10}})
    independent = add(db, 'payroll:15:Approved', source='staff', entity=15)
    db.commit()
    hidden = {approved.id, old_paid.id}
    expected = set(row.id for row in db.query(IntegrationReviewItem).all()) - hidden

    pages = [paginated_review_items(db, page=n, page_size=25) for n in (1, 2, 3)]
    ids = [row['id'] for page in pages for row in page['items']]
    assert pages[0]['total'] == len(expected) == 58
    assert pages[0]['total_pages'] == 3
    assert [len(page['items']) for page in pages] == [25, 25, 8]
    assert set(ids) == expected
    assert len(set(ids)) == len(ids)
    assert ids == sorted(ids, reverse=True)
    assert revised_paid.id in ids and independent.id in ids
    assert pages[0]['has_next'] is True and pages[0]['has_previous'] is False
    assert pages[2]['has_next'] is False and pages[2]['has_previous'] is True
    assert db.query(IntegrationReviewItem).count() == 60


def test_filters_and_legacy_list_exclude_hidden_rows_before_count_and_limit(db):
    add(db, 'payroll:25:Approved', source='staff', entity=25)
    add(db, 'payroll:25:Paid', source='staff', entity=25)
    for index in range(34):
        add(db, 'pos-' + str(index), status='accepted' if index % 3 == 0 else 'ready_for_review')
    db.commit()
    first = paginated_review_items(db, source_app='pos', status='ready_for_review', page=1, page_size=10)
    second = paginated_review_items(db, source_app='pos', status='ready_for_review', page=2, page_size=10)
    assert first['total'] == second['total'] == 22
    assert len(first['items']) == len(second['items']) == 10
    assert len(list_review_items(db, source_app='staff', limit=5)) == 1
    assert paginated_review_items(db, source_app='staff', page_size=25)['total'] == 1
    assert paginated_review_items(db, q='pos-3', page_size=25)['total'] == 5
    assert paginated_review_items(db, page=200, page_size=25)['items'] == []


@pytest.mark.parametrize(('page', 'size'), [(0, 25), (1, 0), (1, 101)])
def test_invalid_pagination_bounds_rejected(db, page, size):
    with pytest.raises(ValueError, match='Invalid page or page_size'):
        paginated_review_items(db, page=page, page_size=size)

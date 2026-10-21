"""Owner-only journal exception review: scoped evidence and authorization."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import deps, journal_review
from app.db.database import Base, get_db
from app.models.entities import FinancialAccount, MoneyTransaction, JournalEntry
from app.models.journal_linkage_review import JournalLinkageReview


@pytest.fixture
def client_and_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        acc = FinancialAccount(name='Primary Cash', code='AUDIT-JOURNAL-REVIEW', account_type='cash_drawer')
        db.add(acc)
        db.flush()
        for i, source, day, journal_id in [
            (1, 'legacy_import', '2025-01-10', None),
            (2, 'legacy_import', '2025-02-10', None),
            (3, 'beds24', '2026-04-01', None),
            (4, 'legacy_import', '2026-04-01', None),
            (5, 'legacy_import', '2025-01-10', None),
        ]:
            db.add(MoneyTransaction(
                id=i, financial_account_id=acc.id, transaction_date=day,
                direction='in', amount=100 + i, status='posted',
                module='cashbook', category='historic receipt',
                external_source=source, external_id=f'ext-{i}',
                reference_no=f'PAY-{i}', journal_entry_id=journal_id,
            ))
        db.add(MoneyTransaction(
            financial_account_id=acc.id, transaction_date='2025-01-10',
            direction='out', amount=9, status='draft', module='finance',
            external_source='legacy_import', external_id='draft-7',
        ))
        db.commit()
        actor = SimpleNamespace(username='owner', role='owner')
        app = FastAPI()
        app.include_router(journal_review.router, prefix='/reports')
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[deps.get_current_user] = lambda: actor
        with TestClient(app) as client:
            yield client, db, actor
    engine.dispose()


def test_owner_can_page_and_filter_journal_linkage_without_edits(client_and_db):
    client, db, actor = client_and_db
    response = client.get('/reports/journal-linkage-review?limit=2')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'private, no-store'
    body = response.json()
    assert body['count'] == 5
    assert body['review_summary'] == {
        'missing_journal_links': 5,
        'never_reviewed': 5,
        'evidence_recorded': 0,
        'classifications': {
            'needs_evidence': 0, 'cashflow_only_documented': 0,
            'journal_candidate_identified': 0, 'requires_accounting_review': 0,
        },
        'journal_links_resolved_by_review': 0,
        'is_financially_reconciled': False,
    }
    assert body['total_pages'] == 3
    assert [row['id'] for row in body['items']] == [1, 5]
    assert {row['source']: row['count'] for row in body['source_counts']} == {
        'legacy_import': 4, 'beds24': 1,
    }
    assert body['classification'] == 'unverified_journal_linkage'
    assert all(row['review_status'] == 'unverified' and row['journal_entry_id'] is None
               for row in body['items'])
    assert client.get('/reports/journal-linkage-review?year=2026&source=beds24').json()['count'] == 1
    assert client.get('/reports/journal-linkage-review?year=2025&source=beds24').json()['count'] == 0
    assert len(client.get('/reports/journal-linkage-review?page=3&limit=2').json()['items']) == 1

    all_rows = db.query(MoneyTransaction).order_by(MoneyTransaction.id).all()
    assert len(all_rows) == 6
    assert sum(row.status == 'posted' and row.journal_entry_id is None for row in all_rows) == 5
    assert all(row.journal_entry_id is None for row in all_rows)


def test_review_access_denied_to_non_owner_even_if_reports_view_permission(client_and_db):
    client, _, actor = client_and_db
    actor.role = 'front_desk'
    assert client.get('/reports/journal-linkage-review').status_code == 403
    actor.role = 'accountant'
    assert client.get('/reports/journal-linkage-review').status_code == 403
    actor.role = 'admin'
    assert client.get('/reports/journal-linkage-review').status_code == 200


@pytest.mark.parametrize('query', ['year=20x5', 'page=0', 'limit=0', 'limit=101', 'page=10001', 'queue=cleared'])
def test_journal_review_rejects_invalid_queries(client_and_db, query):
    client, _, _ = client_and_db
    assert client.get('/reports/journal-linkage-review?' + query).status_code == 422


def test_review_router_limits_mutations_to_append_only_evidence():
    assert [route.methods for route in journal_review.router.routes] == [{'GET'}, {'GET'}, {'POST'}]


def _decision(decision='needs_evidence', reference=None, journal_id=None, expected=None, key='idempotency-review-001'):
    return {
        'decision': decision,
        'supporting_reference': reference,
        'notes': 'Review source receipts and original cashbook before any journal correction.',
        'suggested_journal_entry_id': journal_id,
        'expected_latest_review_id': expected,
        'idempotency_key': key,
    }


def test_append_only_reviews_do_not_mutate_money_or_post_journals(client_and_db):
    client, db, actor = client_and_db
    before = [(row.id, row.amount, row.status, row.journal_entry_id)
              for row in db.query(MoneyTransaction).order_by(MoneyTransaction.id)]
    response = client.post('/reports/journal-linkage-review/1/decisions',
                           json=_decision())
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['id'] > 0
    assert result['accounting_posting_created'] is False
    assert result['journal_link_changed'] is False
    assert result['decision'] == 'needs_evidence'
    assert response.headers['cache-control'] == 'private, no-store'

    repeated = client.post('/reports/journal-linkage-review/1/decisions',
                           json=_decision())
    assert repeated.status_code == 200
    assert repeated.json()['id'] == result['id']
    assert db.query(JournalLinkageReview).count() == 1
    initial_summary = client.get('/reports/journal-linkage-review').json()['review_summary']
    assert initial_summary['missing_journal_links'] == 5
    assert initial_summary['never_reviewed'] == 4
    assert initial_summary['evidence_recorded'] == 1
    assert initial_summary['classifications']['needs_evidence'] == 1
    assert initial_summary['journal_links_resolved_by_review'] == 0
    assert initial_summary['is_financially_reconciled'] is False
    assert client.get('/reports/journal-linkage-review').json()['items'][0]['review_status'] == 'evidence_recorded'
    history = client.get('/reports/journal-linkage-review/1/history')
    assert history.status_code == 200
    assert history.json()['items'][0]['id'] == result['id']

    duplicate_without_new_expected = client.post(
        '/reports/journal-linkage-review/1/decisions',
        json=_decision(key='idempotency-review-002'),
    )
    assert duplicate_without_new_expected.status_code == 409
    second = client.post(
        '/reports/journal-linkage-review/1/decisions',
        json=_decision(decision='requires_accounting_review', reference='Receipt book page 21',
                       expected=result['id'], key='idempotency-review-003'),
    )
    assert second.status_code == 200, second.text
    assert second.json()['id'] > result['id']
    assert db.query(JournalLinkageReview).count() == 2
    latest_summary = client.get('/reports/journal-linkage-review').json()['review_summary']
    # Re-reviewing an item never increments the number of reviewed transactions.
    assert latest_summary['evidence_recorded'] == 1
    assert latest_summary['never_reviewed'] == 4
    assert latest_summary['classifications']['needs_evidence'] == 0
    assert latest_summary['classifications']['requires_accounting_review'] == 1
    assert latest_summary['journal_links_resolved_by_review'] == 0
    assert [r['id'] for r in client.get('/reports/journal-linkage-review/1/history').json()['items']] == [
        second.json()['id'], result['id'],
    ]
    after = [(row.id, row.amount, row.status, row.journal_entry_id)
             for row in db.query(MoneyTransaction).order_by(MoneyTransaction.id)]
    assert after == before
    assert db.query(JournalEntry).count() == 0



def test_idempotent_retry_rejects_different_evidence_or_reviewer(client_and_db):
    client, db, actor = client_and_db
    original = _decision(
        decision='cashflow_only_documented',
        reference=' Receipt book page 21 ',
        key='idempotency-evidence-guard-001',
    )
    original['notes'] = ' Original receipt and source cashbook verified. '
    saved = client.post('/reports/journal-linkage-review/1/decisions', json=original)
    assert saved.status_code == 200, saved.text
    saved_id = saved.json()['id']

    # Harmless whitespace normalization must not break a legitimate network retry.
    same = dict(original, supporting_reference='Receipt book page 21',
                notes='Original receipt and source cashbook verified.')
    retry = client.post('/reports/journal-linkage-review/1/decisions', json=same)
    assert retry.status_code == 200
    assert retry.json()['id'] == saved_id

    different_payloads = (
        dict(same, decision='requires_accounting_review'),
        dict(same, supporting_reference='Different physical receipt'),
        dict(same, notes='A different review rationale requiring separate history.'),
        dict(same, suggested_journal_entry_id=25),
    )
    for changed in different_payloads:
        response = client.post('/reports/journal-linkage-review/1/decisions', json=changed)
        assert response.status_code == 409, response.text
        assert 'different review evidence' in response.json()['detail']

    actor.username = 'another-owner'
    changed_reviewer = client.post('/reports/journal-linkage-review/1/decisions', json=same)
    assert changed_reviewer.status_code == 409
    actor.username = 'owner'

    reused_other_transaction = client.post('/reports/journal-linkage-review/2/decisions', json=same)
    assert reused_other_transaction.status_code == 409
    assert db.query(JournalLinkageReview).count() == 1
    assert db.query(JournalLinkageReview).one().id == saved_id
    assert db.query(JournalEntry).count() == 0
    assert all(row.journal_entry_id is None for row in db.query(MoneyTransaction))

def test_evidence_policy_and_journal_candidate_must_reference_existing_posted_journal(client_and_db):
    client, db, _ = client_and_db
    assert client.post('/reports/journal-linkage-review/1/decisions',
        json=_decision(decision='cashflow_only_documented')).status_code == 422
    assert client.post('/reports/journal-linkage-review/1/decisions',
        json=_decision(decision='journal_candidate_identified', reference='Manual review proof')).status_code == 422
    assert client.post('/reports/journal-linkage-review/1/decisions',
        json=_decision(decision='journal_candidate_identified', reference='Manual review proof',
                       journal_id=444)).status_code == 422
    assert db.query(JournalLinkageReview).count() == 0

    draft = JournalEntry(entry_date='2026-02-02', status='draft', reference_no='DRAFT')
    posted = JournalEntry(entry_date='2026-02-02', status='posted', reference_no='POSTED')
    db.add_all([draft, posted]); db.commit()
    assert client.post('/reports/journal-linkage-review/1/decisions',
        json=_decision(decision='journal_candidate_identified', reference='Evidence', 
                       journal_id=draft.id)).status_code == 422
    success = client.post('/reports/journal-linkage-review/1/decisions',
        json=_decision(decision='journal_candidate_identified', reference='Original source and journal reviewed',
                       journal_id=posted.id, key='idempotency-review-004'))
    assert success.status_code == 200, success.text
    assert success.json()['suggested_journal_entry_id'] == posted.id
    assert db.query(MoneyTransaction).filter_by(id=1).one().journal_entry_id is None


def test_append_only_review_denied_to_non_owner(client_and_db):
    client, db, actor = client_and_db
    actor.role = 'front_desk'
    assert client.post('/reports/journal-linkage-review/1/decisions', json=_decision()).status_code == 403
    assert client.get('/reports/journal-linkage-review/1/history').status_code == 403
    actor.role = 'admin'
    assert client.post('/reports/journal-linkage-review/1/decisions', json=_decision()).status_code == 200
    assert db.query(JournalLinkageReview).count() == 1


def test_review_progress_tracks_latest_decision_across_filtered_sources(client_and_db):
    client, db, _ = client_and_db
    review_1 = client.post(
        '/reports/journal-linkage-review/1/decisions',
        json=_decision(decision='cashflow_only_documented', reference='Folio receipt #1',
                       key='evidence-progress-001'),
    )
    assert review_1.status_code == 200, review_1.text
    review_2 = client.post(
        '/reports/journal-linkage-review/3/decisions',
        json=_decision(decision='requires_accounting_review', reference='Source B proof',
                       key='evidence-progress-002'),
    )
    assert review_2.status_code == 200, review_2.text

    all_summary = client.get('/reports/journal-linkage-review?limit=2').json()['review_summary']
    assert all_summary['missing_journal_links'] == 5
    assert all_summary['evidence_recorded'] == 2
    assert all_summary['never_reviewed'] == 3
    assert all_summary['classifications']['cashflow_only_documented'] == 1
    assert all_summary['classifications']['requires_accounting_review'] == 1
    assert all_summary['journal_links_resolved_by_review'] == 0

    source_a = client.get('/reports/journal-linkage-review?source=legacy_import').json()
    assert source_a['count'] == 4
    assert source_a['review_summary']['evidence_recorded'] == 1
    assert source_a['review_summary']['never_reviewed'] == 3

    source_b = client.get('/reports/journal-linkage-review?year=2026&source=beds24').json()
    assert source_b['count'] == 1
    assert source_b['review_summary']['evidence_recorded'] == 1
    assert source_b['review_summary']['never_reviewed'] == 0
    assert source_b['review_summary']['is_financially_reconciled'] is False
    assert db.query(MoneyTransaction).filter(MoneyTransaction.journal_entry_id.isnot(None)).count() == 0


def test_work_queue_selection_excludes_reviewed_only_from_list_not_scope(client_and_db):
    client, db, _ = client_and_db
    original = client.get('/reports/journal-linkage-review?queue=unreviewed&limit=2').json()
    assert original['count'] == 5
    assert original['scope_count'] == 5
    assert original['review_summary']['missing_journal_links'] == 5
    assert original['review_summary']['never_reviewed'] == 5
    assert original['queue'] == 'unreviewed'
    assert original['total_pages'] == 3

    decision = client.post('/reports/journal-linkage-review/1/decisions',
        json=_decision(decision='needs_evidence', key='queue-review-idempotency-key-001'))
    assert decision.status_code == 200, decision.text
    pending = client.get('/reports/journal-linkage-review?queue=unreviewed&limit=2').json()
    assert pending['count'] == 4
    assert pending['scope_count'] == 5
    assert pending['total_pages'] == 2
    assert pending['review_summary']['missing_journal_links'] == 5
    assert pending['review_summary']['never_reviewed'] == 4
    assert pending['review_summary']['evidence_recorded'] == 1
    assert all(item['id'] != 1 for item in pending['items'])

    reviewed = client.get('/reports/journal-linkage-review?queue=reviewed&limit=2').json()
    assert reviewed['count'] == 1
    assert reviewed['scope_count'] == 5
    assert [item['id'] for item in reviewed['items']] == [1]
    assert reviewed['items'][0]['latest_review']['decision'] == 'needs_evidence'
    assert reviewed['review_summary'] == pending['review_summary']

    updated = client.post('/reports/journal-linkage-review/1/decisions',
        json=_decision(decision='requires_accounting_review', reference='Source record proof',
                       expected=decision.json()['id'], key='queue-review-idempotency-key-002'))
    assert updated.status_code == 200, updated.text
    rechecked = client.get('/reports/journal-linkage-review?queue=reviewed').json()
    assert rechecked['count'] == 1
    assert rechecked['review_summary']['evidence_recorded'] == 1
    assert rechecked['review_summary']['classifications']['requires_accounting_review'] == 1
    assert rechecked['review_summary']['classifications']['needs_evidence'] == 0

    year_pending = client.get('/reports/journal-linkage-review?queue=unreviewed&year=2025').json()
    assert year_pending['count'] == 2
    assert year_pending['scope_count'] == 3
    assert year_pending['review_summary']['missing_journal_links'] == 3

    assert client.get('/reports/journal-linkage-review?queue=reviewed&source=beds24').json()['count'] == 0
    assert db.query(MoneyTransaction).filter(MoneyTransaction.journal_entry_id.isnot(None)).count() == 0
    assert db.query(JournalEntry).count() == 0

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from app.api.journals import reverse_entry
from app.db.database import SessionLocal, engine
from app.models.entities import JournalEntry, JournalLine

pytestmark = pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='PostgreSQL CI lane only')


def test_concurrent_journal_reversal_has_one_economic_effect():
    with SessionLocal() as db:
        entry = JournalEntry(entry_date='2026-09-07', status='posted', reference_no=f'REVIEW-{uuid4().hex}')
        db.add(entry); db.flush()
        db.add_all([JournalLine(journal_entry_id=entry.id, account_code='1000', account_name='Cash', debit=100, credit=0), JournalLine(journal_entry_id=entry.id, account_code='4000', account_name='Income', debit=0, credit=100)])
        db.commit(); entry_id = entry.id
    barrier = Barrier(2)
    def run():
        with SessionLocal() as db:
            barrier.wait(timeout=10)
            try:
                reverse_entry(entry_id, db=db, user=SimpleNamespace(username='race-auditor'))
                return 'posted'
            except HTTPException as exc:
                db.rollback()
                assert exc.status_code in {400, 409}
                return 'rejected'
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run), pool.submit(run)]
        results = [future.result(timeout=20) for future in futures]
    assert sorted(results) == ['posted', 'rejected']
    with SessionLocal() as db:
        assert db.query(JournalEntry).filter_by(reversed_from_id=entry_id).count() == 1

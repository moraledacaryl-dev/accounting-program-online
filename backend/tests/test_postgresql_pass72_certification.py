from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func

from app.db.database import SessionLocal, engine
from app.models.entities import JournalEntry, JournalLine


pytestmark = pytest.mark.skipif(
    engine.dialect.name != 'postgresql',
    reason='PostgreSQL CI lane only',
)


def test_postgresql_trial_balance_remains_exact_at_dense_ledger_volume():
    marker = uuid4().hex[:12]
    entry_count = 1000

    with SessionLocal() as db:
        entries = [
            JournalEntry(
                entry_date='2026-08-29',
                reference_no=f'P72-SCALE-{marker}-{index}',
                description='Pass 72 dense-ledger certification',
                source_module='pass72_certification',
                status='posted',
            )
            for index in range(entry_count)
        ]
        db.add_all(entries)
        db.flush()

        lines = []
        for index, entry in enumerate(entries, start=1):
            amount = float((index % 97) + 1)
            lines.extend([
                JournalLine(journal_entry_id=entry.id, account_code='1000', account_name='Cash', debit=amount, credit=0),
                JournalLine(journal_entry_id=entry.id, account_code='4000', account_name='Revenue', debit=0, credit=amount),
                JournalLine(journal_entry_id=entry.id, account_code='5000', account_name='Operating Expense', debit=amount / 2, credit=0),
                JournalLine(journal_entry_id=entry.id, account_code='1000', account_name='Cash', debit=0, credit=amount / 2),
            ])
        db.add_all(lines)
        db.flush()

        debit, credit, line_count = db.query(
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
            func.count(JournalLine.id),
        ).join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id).filter(
            JournalEntry.source_module == 'pass72_certification',
            JournalEntry.reference_no.like(f'P72-SCALE-{marker}-%'),
        ).one()

        assert line_count == entry_count * 4
        assert round(float(debit), 4) == round(float(credit), 4)

        account_rows = db.query(
            JournalLine.account_code,
            func.sum(JournalLine.debit),
            func.sum(JournalLine.credit),
        ).join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id).filter(
            JournalEntry.source_module == 'pass72_certification',
            JournalEntry.reference_no.like(f'P72-SCALE-{marker}-%'),
        ).group_by(JournalLine.account_code).all()

        assert {row[0] for row in account_rows} == {'1000', '4000', '5000'}
        db.rollback()

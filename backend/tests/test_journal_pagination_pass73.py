from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.journals import entries
from app.db.database import Base
from app.models.entities import JournalEntry


def make_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return TestingSession()


def test_journal_register_is_bounded_and_supports_stable_offset_paging():
    db = make_session()
    db.add_all([
        JournalEntry(entry_date='2026-08-30', reference_no=f'P73-{index:03d}', description='Pass 73 pagination fixture', source_module='finance', status='posted')
        for index in range(250)
    ])
    db.commit()

    first = entries(db=db, user=SimpleNamespace(username='auditor'), limit=100, offset=0)
    second = entries(db=db, user=SimpleNamespace(username='auditor'), limit=100, offset=100)
    third = entries(db=db, user=SimpleNamespace(username='auditor'), limit=100, offset=200)

    assert len(first) == 100
    assert len(second) == 100
    assert len(third) == 50
    assert first[0].reference_no == 'P73-249'
    assert first[-1].reference_no == 'P73-150'
    assert second[0].reference_no == 'P73-149'
    assert third[-1].reference_no == 'P73-000'


def test_journal_register_default_page_does_not_return_entire_history():
    db = make_session()
    db.add_all([
        JournalEntry(entry_date='2026-08-30', reference_no=f'P73-DEFAULT-{index:03d}', description='Pass 73 default bound fixture', source_module='finance', status='posted')
        for index in range(140)
    ])
    db.commit()

    page = entries(db=db, user=SimpleNamespace(username='auditor'))
    assert len(page) == 100

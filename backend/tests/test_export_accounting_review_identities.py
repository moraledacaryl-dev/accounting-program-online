import importlib.util
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.entities import IntegrationReviewItem

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'export_accounting_review_identities.py'
spec = importlib.util.spec_from_file_location('export_accounting_review_identities', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session
    engine.dispose()


def add(db, source, identifier, revision=1):
    row = IntegrationReviewItem(
        source_app=source, source_event_id=identifier,
        source_entity_type='test', source_entity_id='123',
        source_revision=revision, financial_effect='reference_only',
        amount=0, currency='PHP', status='ready_for_review',
        idempotency_key=f'{source}-{identifier}-{revision}',
    )
    db.add(row)
    db.flush()
    return row


def test_export_all_statuses_and_revisions_without_financial_or_payroll_payloads(db):
    add(db, 'inventory', 'receipt-a', 1)
    add(db, 'staff', 'payroll-a:Paid', 2)
    add(db, 'pos', 'payment-a', 1)
    db.commit()
    report = module.export_intake_identities(db)
    assert report['no_pagination_cutoff'] is True
    assert report['sources'] == ['inventory', 'staff']
    assert report['accounting_review'] == [
        {'source_app': 'inventory', 'source_event_id': 'receipt-a', 'source_revision': 1},
        {'source_app': 'staff', 'source_event_id': 'payroll-a:Paid', 'source_revision': 2},
    ]
    assert not any(word in json.dumps(report) for word in (
        'gross_amount', 'cashflow', 'employee_name', 'payload_json', 'account_number',
    ))
    assert module.export_intake_identities(db, ['staff'])['accounting_review'][0]['source_app'] == 'staff'


def test_export_runs_select_only_without_creating_records(db):
    add(db, 'staff', 'payroll-b:Approved')
    db.commit()
    statements = []
    def observe(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split(None, 1)[0].upper())
    engine = db.get_bind()
    event.listen(engine, 'before_cursor_execute', observe)
    try:
        result = module.export_intake_identities(db, ['staff'])
    finally:
        event.remove(engine, 'before_cursor_execute', observe)
    assert len(result['accounting_review']) == 1
    assert statements and set(statements) == {'SELECT'}
    assert not db.dirty and not db.new and not db.deleted


@pytest.mark.parametrize('bad', [[], ['pos'], ['inventory', 'pos'], ['unknown']])
def test_refuse_unsupported_or_empty_source_scopes(db, bad):
    with pytest.raises(ValueError):
        module.export_intake_identities(db, bad)


def test_restricted_export_does_not_overwrite_and_file_contains_only_ids(tmp_path):
    dest = tmp_path / 'receipt-identities.json'
    data = {'accounting_review': [{'source_app': 'inventory', 'source_event_id': 'a', 'source_revision': 1}]}
    module.write_restricted_json(dest, data)
    assert json.loads(dest.read_text()) == data
    assert dest.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        module.write_restricted_json(dest, {'accounting_review': []})
    assert json.loads(dest.read_text()) == data


def test_restricted_export_rejects_symlink_destination(tmp_path):
    target = tmp_path / 'target.json'
    target.write_text('unchanged')
    alias = tmp_path / 'alias.json'
    alias.symlink_to(target)
    with pytest.raises(FileExistsError, OSError):
        module.write_restricted_json(alias, {'accounting_review': []})
    assert target.read_text() == 'unchanged'

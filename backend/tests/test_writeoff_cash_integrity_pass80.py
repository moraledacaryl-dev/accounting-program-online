from pathlib import Path
from types import SimpleNamespace

from app.models.entities import Payable, Receivable
from app.schemas.cashflow import CashflowActionPayload
from app.services import writeoff_service


ROOT = Path(__file__).resolve().parents[2]


class FakeQuery:
    def __init__(self, db, model):
        self.db = db
        self.model = model
        self.locked = False

    def filter(self, *_args, **_kwargs):
        return self

    def populate_existing(self):
        return self

    def with_for_update(self):
        self.locked = True
        self.db.locked_models.append(self.model)
        return self

    def first(self):
        if self.model is self.db.model:
            return self.db.row
        return None


class FakeDb:
    def __init__(self, model, row):
        self.model = model
        self.row = row
        self.commits = 0
        self.refreshed = []
        self.locked_models = []

    def query(self, model):
        return FakeQuery(self, model)

    def get(self, model, row_id):
        if model is self.model and int(row_id) == int(self.row.id):
            return self.row
        return None

    def commit(self):
        self.commits += 1

    def refresh(self, row):
        self.refreshed.append(row)


def test_receivable_writeoff_preserves_actual_collection(monkeypatch):
    row = SimpleNamespace(
        id=41,
        gross_amount=1000.0,
        amount_collected=250.0,
        balance_due=750.0,
        status='open',
        closed_at=None,
        notes='Partial collection retained',
    )
    db = FakeDb(Receivable, row)
    monkeypatch.setattr(writeoff_service, '_serialize_receivable', lambda item: item)

    result = writeoff_service.write_off_receivable_preserving_cash(
        db,
        41,
        CashflowActionPayload(action_date='2026-09-01', reason='Uncollectible remainder'),
    )

    assert result is row
    assert row.amount_collected == 250.0
    assert row.gross_amount == 1000.0
    assert row.balance_due == 0
    assert row.status == 'written_off'
    assert row.closed_at == '2026-09-01'
    assert 'Write-off: Uncollectible remainder' in row.notes
    assert db.commits == 1
    assert db.refreshed == [row]
    assert db.locked_models == [Receivable]


def test_payable_writeoff_preserves_actual_payment(monkeypatch):
    row = SimpleNamespace(
        id=52,
        gross_amount=1000.0,
        amount_paid=300.0,
        balance_due=700.0,
        status='open',
        closed_at=None,
        notes='Partial payment retained',
    )
    db = FakeDb(Payable, row)
    monkeypatch.setattr(writeoff_service, '_serialize_payable', lambda item: item)

    result = writeoff_service.write_off_payable_preserving_cash(
        db,
        52,
        CashflowActionPayload(action_date='2026-09-01', reason='Forgiven remainder'),
    )

    assert result is row
    assert row.amount_paid == 300.0
    assert row.gross_amount == 1000.0
    assert row.balance_due == 0
    assert row.status == 'written_off'
    assert row.closed_at == '2026-09-01'
    assert 'Write-off: Forgiven remainder' in row.notes
    assert db.commits == 1
    assert db.refreshed == [row]
    assert db.locked_models == [Payable]


def test_writeoff_rejects_zero_balance_without_mutation(monkeypatch):
    receivable = SimpleNamespace(
        id=61,
        gross_amount=500.0,
        amount_collected=500.0,
        balance_due=0.0,
        status='closed',
        closed_at='2026-08-31',
        notes=None,
    )
    db = FakeDb(Receivable, receivable)
    monkeypatch.setattr(writeoff_service, '_serialize_receivable', lambda item: item)

    try:
        writeoff_service.write_off_receivable_preserving_cash(
            db,
            61,
            CashflowActionPayload(action_date='2026-09-01'),
        )
    except ValueError as exc:
        assert str(exc) == 'Receivable has no remaining balance.'
    else:
        raise AssertionError('zero-balance receivable was written off')

    assert receivable.status == 'closed'
    assert receivable.amount_collected == 500.0
    assert db.commits == 0
    assert db.locked_models == [Receivable]


def test_public_writeoff_routes_use_cash_preserving_service_only():
    receivables_api = (ROOT / 'backend/app/api/receivables.py').read_text()
    payables_api = (ROOT / 'backend/app/api/payables.py').read_text()

    assert 'write_off_receivable_preserving_cash' in receivables_api
    assert 'return write_off_receivable_preserving_cash(' in receivables_api
    assert 'write_off_receivable,' not in receivables_api
    assert 'return write_off_receivable(' not in receivables_api

    assert 'write_off_payable_preserving_cash' in payables_api
    assert 'return write_off_payable_preserving_cash(' in payables_api
    assert 'write_off_payable,' not in payables_api
    assert 'return write_off_payable(' not in payables_api


def test_cash_preserving_service_never_fabricates_settlement_totals():
    source = (ROOT / 'backend/app/services/writeoff_service.py').read_text()

    assert 'row.amount_collected =' not in source
    assert 'row.amount_paid =' not in source
    assert "row.status = 'written_off'" in source
    assert 'row.balance_due = 0' in source

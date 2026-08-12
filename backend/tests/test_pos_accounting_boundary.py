from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.entities import Receivable
from app.services import pos_accounting_boundary as boundary


def test_dedicated_pos_sale_bypasses_legacy_accounting_inventory(monkeypatch):
    monkeypatch.setattr(boundary, '_base_consume_inventory', lambda *args, **kwargs: 125.50)
    monkeypatch.setattr(
        boundary,
        '_base_create_sale',
        lambda db, payload, username=None: boundary._guarded_consume_inventory(),
    )

    pos_payload = SimpleNamespace(external_source='dedicated_pos_cloud')
    manual_payload = SimpleNamespace(external_source=None)

    assert boundary.create_sale_order_with_pos_boundary(None, pos_payload) == 0.0
    assert boundary.create_sale_order_with_pos_boundary(None, manual_payload) == 125.50


def test_dedicated_pos_void_cannot_reverse_legacy_accounting_inventory(monkeypatch):
    monkeypatch.setattr(
        boundary,
        '_base_void_sale',
        lambda db, order, payload, username=None: payload.reverse_inventory,
    )

    payload = SimpleNamespace(reverse_inventory=True)
    pos_order = SimpleNamespace(external_source='dedicated_pos_cloud')
    manual_order = SimpleNamespace(external_source=None)

    assert boundary.void_sale_order_with_pos_boundary(None, pos_order, payload) is False

    manual_payload = SimpleNamespace(reverse_inventory=True)
    assert boundary.void_sale_order_with_pos_boundary(None, manual_order, manual_payload) is True


def test_pos_room_charge_receivable_retry_is_idempotent(monkeypatch):
    engine = create_engine('sqlite:///:memory:', future=True)
    Receivable.__table__.create(engine)
    Session = sessionmaker(bind=engine, future=True)

    with Session() as db:
        existing = Receivable(
            source_type='pos_room_charge',
            source_id=44,
            counterparty_name='Room 201',
            receivable_type='guest_balance',
            transaction_date='2026-08-12',
            gross_amount=850,
            amount_collected=0,
            balance_due=850,
            status='open',
            bir_include=False,
        )
        db.add(existing)
        db.commit()
        db.refresh(existing)

        monkeypatch.setattr(
            boundary,
            '_base_create_receivable',
            lambda db, payload: (_ for _ in ()).throw(AssertionError('duplicate receivable created')),
        )

        replay = SimpleNamespace(source_type='pos_room_charge', source_id=44)
        result = boundary.create_receivable_with_pos_idempotency(db, replay)

        assert result['id'] == existing.id
        assert db.query(Receivable).count() == 1


def test_non_pos_receivable_uses_normal_accounting_flow(monkeypatch):
    sentinel = {'ok': True}
    monkeypatch.setattr(boundary, '_base_create_receivable', lambda db, payload: sentinel)
    payload = SimpleNamespace(source_type='event_balance', source_id=99)
    assert boundary.create_receivable_with_pos_idempotency(None, payload) is sentinel

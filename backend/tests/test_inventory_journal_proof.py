from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.integration_review import inventory_service_status, require_service_integration_key
from app.db.database import Base
from app.models.entities import AccountMappingRule, ChartAccount, JournalEntry
from app.schemas.integration_review import IntegrationReviewCreate, IntegrationReviewDecision
from app.services.integration_review_service import accept_item, create_review_item
from app.services.inventory_integration_adapter import normalize_inventory_review_payload
from app.services.inventory_journal_proof import inventory_journal_proof


def make_db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def cogs_review(db, source_id="inventory-proof-1"):
    db.add_all([
        ChartAccount(code="5100", name="COGS", account_type="expense", is_active=True),
        ChartAccount(code="1200", name="Inventory Asset", account_type="asset", is_active=True),
    ])
    db.flush()
    db.add(AccountMappingRule(
        module_slug="inventory", category="Cost of goods sold", direction="out",
        debit_account_code="5100", credit_account_code="1200",
        priority=10, is_active=True,
    ))
    db.commit()
    payload = IntegrationReviewCreate(
        source_app="inventory", source_event_id=source_id,
        source_entity_type="pos_sale_event", source_entity_id="sale-1",
        source_revision=1, financial_effect="reference_only",
        amount=0,
        proposed_links={"target_type": "pos_sale", "target_id": "sale-1"},
        payload={
            "event_type": "inventory.pos_sale_consumed",
            "aggregate_type": "pos_sale_event", "aggregate_id": "sale-1",
            "data": {"sale_id": "sale-1", "total_cost": "80.00",
                     "lines": [{"quantity": "2", "cost": "80.00"}]},
        }, idempotency_key=f"source:{source_id}",
    )
    return create_review_item(db, normalize_inventory_review_payload(db, payload))


def test_inventory_proof_transitions_only_after_real_balanced_posted_journal():
    db = make_db()
    with db:
        item = cogs_review(db)
        initial = inventory_journal_proof(db, "inventory-proof-1")
        assert initial["review_status"] == "ready_for_review"
        assert initial["journal_status"] is None
        assert initial["ledger_posting_confirmed"] is False
        assert inventory_journal_proof(db, "not-an-inventory-event") is None

        result = accept_item(db, item["id"], IntegrationReviewDecision(
            transaction_date="2026-10-21"
        ), "reviewer")
        accepted = inventory_journal_proof(db, "inventory-proof-1")
        assert accepted["review_status"] == "accepted"
        assert accepted["accepted_journal_entry_id"] == result["accepted_journal_entry_id"]
        assert accepted["journal_status"] == "posted"
        assert accepted["journal_debit"] == accepted["journal_credit"] == "80.0000"
        assert accepted["ledger_posting_confirmed"] is True

        journal = db.get(JournalEntry, accepted["accepted_journal_entry_id"])
        journal.is_reversed = True
        db.commit()
        assert inventory_journal_proof(db, "inventory-proof-1")["ledger_posting_confirmed"] is False


def test_reference_only_acceptance_does_not_manufacture_journal_proof():
    db = make_db()
    with db:
        payload = IntegrationReviewCreate(
            source_app="inventory", source_event_id="opening-ref",
            source_entity_type="stock_document", source_entity_id="doc-1",
            financial_effect="reference_only", amount=0,
            proposed_links={"target_type": "stock_document", "target_id": "doc-1"},
            idempotency_key="reference-only-1",
        )
        item = create_review_item(db, payload)
        accept_item(db, item["id"], IntegrationReviewDecision(transaction_date="2026-10-21"), "reviewer")
        proof = inventory_journal_proof(db, "opening-ref")
        assert proof["review_status"] == "accepted"
        assert proof["accepted_journal_entry_id"] is None
        assert proof["ledger_posting_confirmed"] is False


def test_service_route_is_read_only_and_missing_source_is_404():
    db = make_db()
    with db:
        try:
            inventory_service_status(source_event_id="unknown-source", db=db, _service=True)
        except HTTPException as exc:
            assert exc.status_code == 404
        else:
            raise AssertionError("Unknown Inventory event must return 404")


def test_posting_proof_endpoint_uses_production_integration_auth(monkeypatch):
    from app.core.settings import settings

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "integration_api_key", "correct-integration-secret")
    monkeypatch.setattr(settings, "integration_secret", "unused")
    try:
        require_service_integration_key("incorrect")
    except HTTPException as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("Status lookup must require the integration secret")

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_source_outbox_parity.py"
spec = importlib.util.spec_from_file_location("source_outbox_parity_assembler", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def accounting():
    return {
        "export_type": "accounting_review_identities",
        "sources": ["inventory", "staff"],
        "no_pagination_cutoff": True,
        "accounting_review": [
            {"source_app": "inventory", "source_event_id": "inv-uuid-1", "source_revision": 1},
            {"source_app": "staff", "source_event_id": "staff-finance:1", "source_revision": 3},
        ],
    }


def staff():
    return {
        "source": "staff", "export_type": "staff_financial_outbox_identities",
        "full_source_scan": True, "complete_for_window": False,
        "events": [{
            "destination": "accounting", "event_type": "payroll.run.paid",
            "external_id": "staff-finance:1", "source_revision": 3, "status": "Completed",
        }],
    }


def inventory():
    return {
        "source": "inventory", "export_type": "inventory_accounting_outbox_identities",
        "full_source_scan": True, "complete_for_window": False,
        "events": [{"id": "inv-uuid-1", "destination_system": "accounting", "status": "completed"}],
    }


def test_private_export_assembly_checks_exact_source_identity_without_claiming_cross_db_completeness():
    merged = audit.build_private_parity_snapshot(accounting(), staff_export=staff(),
                                                 inventory_export=inventory())
    assert merged["schema_version"] == 1
    assert set(merged["producers"]) == {"inventory", "staff"}
    assert merged["producers"]["inventory"]["complete_for_window"] is False
    assert merged["producers"]["staff"]["complete_for_window"] is False
    outcome = audit.compare_snapshots(merged)
    assert outcome["sources"]["staff"]["counts"]["present_in_accounting"] == 1
    assert outcome["sources"]["inventory"]["counts"]["present_in_accounting"] == 1
    assert outcome["finding_count"] == 0
    assert outcome["fully_certified"] is False


def test_incomplete_source_no_receiver_orphan_claims_even_if_accounting_has_other_events():
    local = inventory()
    local["events"] = []
    merged = audit.build_private_parity_snapshot(accounting(), inventory_export=local)
    report = audit.compare_snapshots(merged)
    assert report["sources"]["inventory"]["counts"]["source_side_orphan_check_unknown"] == 1
    assert "accounting_receipt_not_in_source_export" not in report["sources"]["inventory"]["counts"]


@pytest.mark.parametrize('mutator', [
    lambda a, s, i: a.update(export_type="wrong"),
    lambda a, s, i: a.update(no_pagination_cutoff=False),
    lambda a, s, i: s.update(source="inventory"),
    lambda a, s, i: s.update(export_type="wrong"),
    lambda a, s, i: s.update(full_source_scan=False),
    lambda a, s, i: s.update(complete_for_window=True),
    lambda a, s, i: s["events"][0].update(employee_name="DO NOT EXPORT"),
    lambda a, s, i: i.update(source="staff"),
    lambda a, s, i: i["events"][0].update(account_number="DO NOT EXPORT"),
])
def test_invalid_or_privacy_unsafe_export_schema_is_rejected(mutator):
    a, s, i = accounting(), staff(), inventory()
    mutator(a, s, i)
    with pytest.raises(ValueError):
        audit.build_private_parity_snapshot(a, staff_export=s, inventory_export=i)


def test_cli_private_sources_emits_aggregates_and_fingerprints_not_external_id(tmp_path, capsys):
    a = tmp_path / "accounting.json"
    s = tmp_path / "staff.json"
    i = tmp_path / "inventory.json"
    a.write_text(json.dumps(accounting()))
    s.write_text(json.dumps(staff()))
    i.write_text(json.dumps(inventory()))
    assert audit.main(["--accounting", str(a), "--staff", str(s), "--inventory", str(i)]) == 0
    text = capsys.readouterr().out
    result = json.loads(text)
    assert result["finding_count"] == 0
    assert "staff-finance:1" not in text
    assert "inv-uuid-1" not in text
    assert "accounting_review" not in result

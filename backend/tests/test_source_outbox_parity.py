import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'audit_source_outbox_parity.py'
spec = importlib.util.spec_from_file_location('audit_source_outbox_parity', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
compare = module.compare_snapshots


def example(*, complete=True):
    return {
        'schema_version': 1,
        'producers': {
            'inventory': {'complete_for_window': complete, 'events': [
                {'destination_system': 'accounting', 'id': 'inventory-1', 'status': 'completed'},
                {'destination_system': 'accounting', 'id': 'inventory-2', 'status': 'failed'},
                {'destination_system': 'operations', 'id': 'not-accounting', 'status': 'completed'},
            ]},
            'staff': {'complete_for_window': complete, 'events': [
                {'destination': 'accounting', 'event_type': 'payroll.run.paid',
                 'external_id': 'staff:77:Paid', 'source_revision': 2, 'status': 'Completed'},
                {'destination': 'accounting', 'event_type': 'employee.sync',
                 'external_id': 'employee-sync', 'status': 'Completed'},
                {'destination': 'operations', 'event_type': 'payroll.run.paid',
                 'external_id': 'not-accounting', 'status': 'Completed'},
            ]},
            'pos': {'complete_for_window': complete, 'events': [
                {'event_type': 'payment.collected', 'status': 'synced'},
                {'event_type': 'payment.refunded', 'status': 'failed'},
            ]},
        },
        'accounting_review': [
            {'source_app': 'inventory', 'source_event_id': 'inventory-1', 'source_revision': 1},
            {'source_app': 'staff', 'source_event_id': 'staff:77:Paid', 'source_revision': 2},
        ],
    }


def test_source_identity_rules_and_noncomparable_pos_legacy():
    report = compare(example())
    inv = report['sources']['inventory']['counts']
    staff = report['sources']['staff']['counts']
    pos = report['sources']['pos']['counts']
    assert inv['eligible_financial_events'] == 2
    assert inv['present_in_accounting'] == 1
    assert inv['source_pending_without_receipt'] == 1
    assert staff['eligible_financial_events'] == 1
    assert staff['present_in_accounting'] == 1
    assert pos['legacy_direct_pos_not_review_comparable'] == 2
    assert pos['legacy_direct_pos_unsynced'] == 1
    assert report['fully_certified'] is False
    assert report['live_connectivity_checked'] is False
    assert report['finding_count'] == 0


def test_complete_export_flags_missing_completed_and_source_orphan():
    data = example()
    data['producers']['inventory']['events'].append({
        'destination_system': 'accounting', 'id': 'not-received', 'status': 'completed',
    })
    data['accounting_review'].append({
        'source_app': 'inventory', 'source_event_id': 'not-in-source', 'source_revision': 1,
    })
    report = compare(data)
    inv = report['sources']['inventory']
    assert inv['counts']['source_completed_without_accounting_receipt'] == 1
    assert inv['counts']['accounting_receipt_not_in_source_export'] == 1
    assert {row['state'] for row in inv['findings']} == {
        'completed_missing_receipt', 'receipt_absent_from_complete_source_window',
    }
    assert all('not-received' not in json.dumps(row) for row in inv['findings'])


def test_incomplete_source_export_never_claims_orphan():
    data = example(complete=False)
    data['accounting_review'].append({
        'source_app': 'inventory', 'source_event_id': 'extra', 'source_revision': 1,
    })
    report = compare(data)
    inv = report['sources']['inventory']
    assert inv['counts']['source_side_orphan_check_unknown'] == 1
    assert 'accounting_receipt_not_in_source_export' not in inv['counts']
    assert not any(item['state'] == 'receipt_absent_from_complete_source_window'
                   for item in inv['findings'])


def test_source_and_accounting_duplicate_revisions_detected_without_raw_payloads():
    data = example()
    data['producers']['inventory']['events'].append({
        'destination_system': 'accounting', 'id': 'inventory-1', 'status': 'completed',
    })
    data['accounting_review'].append({
        'source_app': 'staff', 'source_event_id': 'staff:77:Paid', 'source_revision': 2,
    })
    result = compare(data)
    assert result['sources']['inventory']['counts']['duplicate_source_identity'] == 1
    assert result['sources']['staff']['counts']['duplicate_accounting_identity'] == 1
    assert all('event_fingerprint' in entry for entry in result['findings'])
    assert all('source_event_id' not in entry for entry in result['findings'])


@pytest.mark.parametrize('input_value', [
    {}, {'schema_version': 2, 'producers': {}, 'accounting_review': []},
    {'schema_version': 1, 'producers': {}, 'accounting_review': []},
    {'schema_version': 1, 'producers': {'inventory': {'events': []}}, 'accounting_review': []},
    {'schema_version': 1, 'producers': {'inventory': {'complete_for_window': True, 'events': {}}}, 'accounting_review': []},
    {'schema_version': 1, 'producers': {'mystery': {'complete_for_window': True, 'events': []}}, 'accounting_review': []},
])
def test_invalid_incomplete_or_unrecognized_snapshot_fails_closed(input_value):
    with pytest.raises(ValueError):
        compare(input_value)


def test_cli_outputs_read_only_report(tmp_path, capsys):
    path = tmp_path / 'sanitized.json'
    path.write_text(json.dumps(example()), encoding='utf-8')
    assert module.main(['--snapshot', str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['scope'] == 'user_supplied_point_in_time_export'
    assert report['read_only'] is True
    assert report['finding_count'] == 0

"""Offline, read-only comparison of sanitized producer outboxes with Accounting intake.

No network, credentials, database writes, journal posting or automatic retries.
Input is an explicit point-in-time export; no claims beyond the supplied scope.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

STAFF_FINANCIAL_EVENTS = frozenset({
    'payroll.run.approved', 'payroll.run.paid', 'payroll.13th_month.paid',
    'cash_advance.released', 'cash_advance.repaid',
})
INVENTORY_COMPLETED = frozenset({'completed'})
STAFF_COMPLETED = frozenset({'completed', 'sent'})
POS_LEGACY_EVENTS = frozenset({
    'cash_movement.created', 'transfer.created', 'payment.collected',
    'payment.folio_pending', 'payment.refunded', 'room_charge.request_created',
    'order.finalized', 'order.voided', 'session.closed',
})
SOURCES = ('inventory', 'staff', 'pos')


def _event_key(source, identifier, revision):
    if not isinstance(identifier, (str, int)) or isinstance(identifier, bool):
        raise ValueError('Source event ID must be a non-empty string or integer.')
    identity = str(identifier).strip()
    if not identity:
        raise ValueError('Source event ID cannot be empty.')
    if type(revision) is not int or revision < 1:
        raise ValueError('Source revision must be a positive integer.')
    return (source, identity, revision)


def _fingerprint(key):
    return hashlib.sha256('|'.join(map(str, key)).encode('utf-8')).hexdigest()[:14]


def _source_rows(source, rows):
    """Return only financial-intake events with producer-specific identity rules."""
    if not isinstance(rows, list):
        raise ValueError(f'{source}.events must be a list.')
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f'{source}.events must contain objects.')
        if source == 'inventory':
            if row.get('destination_system') != 'accounting':
                continue
            key = _event_key('inventory', row.get('id'), 1)
            finished = str(row.get('status') or '').lower() in INVENTORY_COMPLETED
            yield key, finished, str(row.get('status') or 'unknown')
        elif source == 'staff':
            if row.get('destination') != 'accounting' or row.get('event_type') not in STAFF_FINANCIAL_EVENTS:
                continue
            key = _event_key('staff', row.get('external_id'), row.get('source_revision', 1))
            finished = str(row.get('status') or '').lower() in STAFF_COMPLETED
            yield key, finished, str(row.get('status') or 'unknown')
        elif source == 'pos':
            # POS's ordinary outbox does not use Integration Review: it posts to
            # dedicated POS/ERP endpoints. Do NOT invent a source_event_id
            # mapping from its outbox row id or claim a missing Review Inbox row.
            if row.get('event_type') in POS_LEGACY_EVENTS:
                yield None, str(row.get('status') or '').lower() == 'synced', str(row.get('status') or 'unknown')
        else:
            raise ValueError(f'Unsupported source: {source}')


def compare_snapshots(snapshot):
    if not isinstance(snapshot, dict):
        raise ValueError('Snapshot must be a JSON object.')
    if snapshot.get('schema_version') != 1:
        raise ValueError('Snapshot schema_version must be 1.')
    producers = snapshot.get('producers')
    incoming = snapshot.get('accounting_review')
    if not isinstance(producers, dict) or not isinstance(incoming, list):
        raise ValueError('Provide producers object and accounting_review array.')
    if not producers:
        raise ValueError('At least one source export is required.')
    for source in producers:
        if source not in SOURCES:
            raise ValueError(f'Unsupported producer: {source}')
    for source, data in producers.items():
        if not isinstance(data, dict) or type(data.get('complete_for_window')) is not bool:
            raise ValueError(f'{source} needs events and explicit complete_for_window boolean.')
        if not isinstance(data.get('events'), list):
            raise ValueError(f'{source}.events must be a list.')

    received = Counter()
    for item in incoming:
        if not isinstance(item, dict):
            raise ValueError('Accounting review rows must be objects.')
        source = str(item.get('source_app') or '').strip().lower()
        if source not in producers or source == 'pos':
            continue
        key = _event_key(source, item.get('source_event_id'), item.get('source_revision', 1))
        received[key] += 1

    reports = {}
    overall_findings = []
    for source, data in sorted(producers.items()):
        counts = Counter()
        seen = Counter()
        findings = []
        for key, finished, status in _source_rows(source, data['events']):
            if key is None:
                counts['legacy_direct_pos_not_review_comparable'] += 1
                if not finished:
                    counts['legacy_direct_pos_unsynced'] += 1
                continue
            counts['eligible_financial_events'] += 1
            seen[key] += 1
            if seen[key] > 1:
                counts['duplicate_source_identity'] += 1
                findings.append({'state': 'duplicate_source_identity', 'event_fingerprint': _fingerprint(key)})
                continue
            observed = received[key]
            if observed:
                counts['present_in_accounting'] += 1
                if observed > 1:
                    counts['duplicate_accounting_identity'] += 1
                    findings.append({'state': 'duplicate_accounting_identity', 'event_fingerprint': _fingerprint(key)})
                if not finished:
                    counts['sender_not_marked_complete_but_received'] += 1
            elif finished:
                counts['source_completed_without_accounting_receipt'] += 1
                findings.append({'state': 'completed_missing_receipt', 'event_fingerprint': _fingerprint(key)})
            else:
                counts['source_pending_without_receipt'] += 1

        # Absence of upstream export is never proof of an orphan when a
        # producer supplied only a sample or truncated paginated response.
        if data['complete_for_window'] and source != 'pos':
            extras = [key for key in received if key[0] == source and key not in seen]
            counts['accounting_receipt_not_in_source_export'] = len(extras)
            findings.extend({'state': 'receipt_absent_from_complete_source_window',
                             'event_fingerprint': _fingerprint(key)} for key in extras)
        else:
            counts['source_side_orphan_check_unknown'] = 1
        reports[source] = {
            'complete_for_window': data['complete_for_window'],
            'counts': dict(sorted(counts.items())),
            'findings': findings,
            'interpretation': (
                'POS legacy direct sync is not comparable to Integration Review IDs.'
                if source == 'pos' else
                'A completed source event with no retained Accounting review record requires investigation; '
                'this snapshot alone cannot prove network transport failure.'
            ),
        }
        overall_findings.extend({'source': source, **row} for row in findings)

    return {
        'scope': 'user_supplied_point_in_time_export',
        'fully_certified': False,
        'live_connectivity_checked': False,
        'read_only': True,
        'sources': reports,
        'finding_count': len(overall_findings),
        'findings': overall_findings[:100],
        'findings_truncated': len(overall_findings) > 100,
        'limitations': (
            'Only supplied producer events and Accounting Review Inbox rows are compared. '
            'Completeness cannot be inferred from paginated/truncated exports; '
            'POS legacy direct cashflow/journal/receivable sync requires separate endpoint-specific matching. '
            'An accepted review is not proof of a posted journal, bank receipt, or end-to-end financial correctness.'
        ),
    }




def build_private_parity_snapshot(accounting_export, *, staff_export=None, inventory_export=None):
    """Combine protected source exports without writing or echoing identifiers.

    No implicit complete-for-window claims: each independent database was read
    at a different instant and there is no shared cross-app snapshot lock.
    """
    if not isinstance(accounting_export, dict):
        raise ValueError('Accounting export must be an object.')
    if accounting_export.get('export_type') != 'accounting_review_identities':
        raise ValueError('Unexpected Accounting receipt export type.')
    if accounting_export.get('no_pagination_cutoff') is not True:
        raise ValueError('Accounting receipt export must certify unpaginated coverage.')
    receipts = accounting_export.get('accounting_review')
    if not isinstance(receipts, list):
        raise ValueError('Accounting export has no review identity array.')

    supplied = {'staff': staff_export, 'inventory': inventory_export}
    producers = {}
    expected_export_types = {
        'staff': 'staff_financial_outbox_identities',
        'inventory': 'inventory_accounting_outbox_identities',
    }
    for name, data in supplied.items():
        if data is None:
            continue
        if not isinstance(data, dict) or data.get('source') != name:
            raise ValueError(f'{name} source export identity was not verified.')
        if data.get('export_type') != expected_export_types[name]:
            raise ValueError(f'{name} source export type is unexpected.')
        if data.get('full_source_scan') is not True or data.get('complete_for_window') is not False:
            raise ValueError(f'{name} source export must be an unpaginated uncoordinated snapshot.')
        if not isinstance(data.get('events'), list):
            raise ValueError(f'{name} source events missing.')
        # Revalidate the only identity/status fields allowed by the contract,
        # dropping sender-export metadata that is not part of the comparison.
        permitted = (
            {'destination', 'event_type', 'external_id', 'source_revision', 'status'}
            if name == 'staff' else {'id', 'destination_system', 'status'}
        )
        for event in data['events']:
            if not isinstance(event, dict) or set(event) != permitted:
                raise ValueError(f'{name} source event schema mismatch.')
        producers[name] = {
            # A non-atomic source/receiver export cannot prove both databases
            # covered the same instant; absence of any event stays UNKNOWN.
            'complete_for_window': False,
            'events': data['events'],
        }
    if not producers:
        raise ValueError('At least one Staff or Inventory export is required.')
    return {'schema_version': 1, 'producers': producers, 'accounting_review': receipts}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--snapshot', help='Legacy combined sanitized JSON snapshot')
    mode.add_argument('--accounting', help='Restricted Accounting identity exporter JSON')
    parser.add_argument('--staff', help='Restricted Staff source exporter JSON')
    parser.add_argument('--inventory', help='Restricted Inventory source exporter JSON')
    args = parser.parse_args(argv)
    if args.snapshot:
        if args.staff or args.inventory:
            parser.error('--snapshot cannot be combined with individual source exports')
        payload = json.loads(Path(args.snapshot).read_text(encoding='utf-8'))
    else:
        if not args.staff and not args.inventory:
            parser.error('--accounting requires --staff and/or --inventory')
        payload = build_private_parity_snapshot(
            json.loads(Path(args.accounting).read_text(encoding='utf-8')),
            staff_export=json.loads(Path(args.staff).read_text(encoding='utf-8')) if args.staff else None,
            inventory_export=json.loads(Path(args.inventory).read_text(encoding='utf-8')) if args.inventory else None,
        )
    # The comparison prints only aggregate counts and short fingerprints,
    # never the raw Staff/Inventory/Accounting event identities.
    print(json.dumps(compare_snapshots(payload), indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, help='Sanitized exported JSON snapshot; read only')
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.snapshot).read_text(encoding='utf-8'))
    print(json.dumps(compare_snapshots(payload), indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

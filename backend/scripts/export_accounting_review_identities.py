"""Safely export Accounting intake identity columns for offline outbox parity.

READ ONLY against Accounting SQL: no producer calls, postings, retries,
financial mutations, credentials, raw payloads, or privileged service APIs.
Treat the resulting file as sensitive because source event identifiers may
refer to employees/other source records.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.entities import IntegrationReviewItem

ALLOWED_SOURCES = frozenset({'inventory', 'staff'})


def export_intake_identities(db: Session, sources=('inventory', 'staff')) -> dict:
    sources = tuple(sorted(set(sources)))
    if not sources or any(s not in ALLOWED_SOURCES for s in sources):
        raise ValueError('Only inventory and staff financial review sources are supported.')

    rows = (
        db.query(
            IntegrationReviewItem.source_app,
            IntegrationReviewItem.source_event_id,
            IntegrationReviewItem.source_revision,
        )
        .filter(IntegrationReviewItem.source_app.in_(sources))
        .order_by(IntegrationReviewItem.id.asc())
        .all()
    )
    return {
        'export_type': 'accounting_review_identities',
        'sources': list(sources),
        'no_pagination_cutoff': True,
        'accounting_review': [
            {'source_app': row.source_app,
             'source_event_id': row.source_event_id,
             'source_revision': row.source_revision}
            for row in rows
        ],
        'limitations': (
            'A full unpaginated Accounting intake scan is not a producer outbox '
            'completeness certificate. Freeze/scope both producer and Accounting '
            'exports to the same time window before interpreting missing events.'
        ),
    }


def write_restricted_json(path: str | Path, report: dict):
    destination = Path(path).expanduser()
    # Never follow symlinks or overwrite a prior export; raw event identities
    # should not accidentally leak via an existing shared/world-readable file.
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    fd = os.open(destination, flags, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            fd = None
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
    finally:
        if fd is not None:
            os.close(fd)
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='NEW protected JSON file path; no overwrite')
    parser.add_argument('--source', action='append', choices=sorted(ALLOWED_SOURCES),
                        help='May repeat; defaults to Inventory and Staff')
    args = parser.parse_args(argv)
    with SessionLocal() as db:
        result = export_intake_identities(db, sources=args.source or sorted(ALLOWED_SOURCES))
    destination = write_restricted_json(args.output, result)
    # No IDs or sensitive payload contents are printed to stdout.
    print(f"Exported {len(result['accounting_review'])} Accounting review identities to a restricted file.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

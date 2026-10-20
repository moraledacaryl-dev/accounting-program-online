"""Owner-only, read-only review of posted money movements lacking journal links.

A missing journal foreign key is not evidence that money or revenue is missing.
No endpoint in this module creates journals, updates links, or writes decisions.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.database import get_db
from app.models.entities import MoneyTransaction


router = APIRouter()


def _unlinked(db: Session):
    return db.query(MoneyTransaction).filter(
        MoneyTransaction.status == 'posted',
        MoneyTransaction.journal_entry_id.is_(None),
    )


def review_journal_linkage(db: Session, *, year=None, source=None, page=1, limit=25):
    """Read at most one page of transaction-level evidence; never mutate rows."""
    base = _unlinked(db)
    if year:
        base = base.filter(MoneyTransaction.transaction_date.like(f'{year}-%'))

    totals = (
        base.with_entities(MoneyTransaction.external_source, func.count(MoneyTransaction.id))
        .group_by(MoneyTransaction.external_source)
        .order_by(func.count(MoneyTransaction.id).desc(), MoneyTransaction.external_source.asc())
        .all()
    )
    source_counts = [
        {'source': name if name else '(unspecified)', 'count': int(count)}
        for name, count in totals
    ]
    if source:
        if source == '(unspecified)':
            base = base.filter((MoneyTransaction.external_source.is_(None)) | (MoneyTransaction.external_source == ''))
        else:
            base = base.filter(MoneyTransaction.external_source == source)

    count = base.count()
    rows = (
        base.order_by(MoneyTransaction.transaction_date.asc(), MoneyTransaction.id.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return {
        'count': int(count),
        'page': page,
        'page_size': limit,
        'total_pages': (count + limit - 1) // limit,
        'source_counts': source_counts,
        'classification': 'unverified_journal_linkage',
        'notes': [
            'A missing journal link does not prove a missing journal or missing revenue.',
            'Compare external source evidence, folios, and existing ledger postings before any correction.',
            'No automatic journalization or reconciliation is available from this review.',
        ],
        'items': [
            {
                'id': row.id,
                'transaction_date': row.transaction_date,
                'direction': row.direction,
                'module': row.module,
                'category': row.category,
                'amount': row.amount,
                'payment_method': row.payment_method,
                'reference_no': row.reference_no,
                'external_source': row.external_source,
                'external_id': row.external_id,
                'financial_account_id': row.financial_account_id,
                'linked_record_id': row.linked_record_id,
                'journal_entry_id': row.journal_entry_id,
                'review_status': 'unverified',
            }
            for row in rows
        ],
    }


@router.get('/journal-linkage-review')
def journal_linkage_review(
    response: Response,
    year: str | None = Query(None, pattern=r'^\d{4}$'),
    source: str | None = Query(None, max_length=40),
    page: int = Query(1, ge=1, le=10000),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(require_roles('owner', 'admin')),
):
    response.headers['Cache-Control'] = 'private, no-store'
    return review_journal_linkage(db, year=year, source=source, page=page, limit=limit)

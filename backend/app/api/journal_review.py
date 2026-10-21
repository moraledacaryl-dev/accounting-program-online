"""Owner-only journal linkage evidence review with append-only review decisions.

A missing journal foreign key is not evidence that money or revenue is missing.
Decisions append private review history only; monetary data and journals remain unchanged.
"""
from __future__ import annotations

import csv
from decimal import Decimal
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from typing import Literal
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.database import get_db
from app.models.entities import JournalEntry, MoneyTransaction
from app.models.journal_linkage_review import JournalLinkageReview
from app.services.audit_service import record_audit


router = APIRouter()

# A private CSV is a finite, owner/admin-only worklist, never a public CI artifact.
JOURNAL_REVIEW_EXPORT_MAX_ROWS = 10000


def _unlinked(db: Session):
    return db.query(MoneyTransaction).filter(
        MoneyTransaction.status == 'posted',
        MoneyTransaction.journal_entry_id.is_(None),
    )


def _filtered_unlinked(db: Session, *, year=None, source=None):
    """Same date/source selection as the private review UI, without pagination."""
    base = _unlinked(db)
    if year:
        base = base.filter(MoneyTransaction.transaction_date.like(f'{year}-%'))
    if source:
        if source == '(unspecified)':
            base = base.filter(
                (MoneyTransaction.external_source.is_(None)) |
                (MoneyTransaction.external_source == '')
            )
        else:
            base = base.filter(MoneyTransaction.external_source == source)
    return base


def _protect_csv_text(value):
    """Avoid spreadsheet formula execution from untrusted external references or notes."""
    if value is None:
        return ''
    raw = str(value)
    if raw.lstrip().startswith(('=', '+', '-', '@')) and not isinstance(value, (int, float, Decimal)):
        return "'" + raw
    return raw


def journal_review_csv(db: Session, *, year=None, source=None, queue='all', page=None, limit=25, expected_page_ids=None):
    """Build an evidence worklist without altering journal or transaction records."""
    base = _filtered_unlinked(db, year=year, source=source)
    latest_review = (
        db.query(
            JournalLinkageReview.money_transaction_id.label('transaction_id'),
            func.max(JournalLinkageReview.id).label('review_id'),
        )
        .group_by(JournalLinkageReview.money_transaction_id)
        .subquery()
    )
    query = (
        base.outerjoin(latest_review, latest_review.c.transaction_id == MoneyTransaction.id)
        .outerjoin(JournalLinkageReview, JournalLinkageReview.id == latest_review.c.review_id)
    )
    if queue == 'unreviewed':
        query = query.filter(latest_review.c.review_id.is_(None))
    elif queue == 'reviewed':
        query = query.filter(latest_review.c.review_id.isnot(None))
    query = (
        query.with_entities(MoneyTransaction, JournalLinkageReview)
        .order_by(MoneyTransaction.transaction_date.asc(), MoneyTransaction.id.asc())
    )
    if page is None:
        # Refuse truncation for an entire filtered worklist.
        rows = query.limit(JOURNAL_REVIEW_EXPORT_MAX_ROWS + 1).all()
        if len(rows) > JOURNAL_REVIEW_EXPORT_MAX_ROWS:
            raise HTTPException(status_code=413, detail='Review worklist exceeds the private export row limit.')
    else:
        # Precisely mirror the on-screen review queue's ordered page.
        rows = query.offset((page - 1) * limit).limit(limit).all()

    # If the queue changed since the reviewer viewed the page, refuse to
    # substitute other transactions in an apparently identical batch export.
    if expected_page_ids is not None:
        if page is None:
            raise HTTPException(status_code=422, detail='Page IDs require a specific page.')
        expected = [int(value) for value in expected_page_ids.split(',')]
        if len(expected) > limit or len(expected) != len(set(expected)):
            raise HTTPException(status_code=422, detail='Invalid displayed-page transaction IDs.')
        if [tx.id for tx, _ in rows] != expected:
            raise HTTPException(
                status_code=409,
                detail='Journal review queue changed. Refresh before exporting the displayed page.',
            )

    header = [
        'money_transaction_id', 'transaction_date', 'financial_account_id',
        'direction', 'amount_php', 'payment_method', 'module', 'category',
        'external_source', 'external_event_id', 'payment_reference',
        'linked_record_id', 'journal_link_status', 'latest_review_classification',
        'evidence_reference', 'review_rationale', 'suggested_journal_entry_id',
        'reviewed_by', 'reviewed_at',
        'subcategory', 'linked_record_type', 'receivable_id', 'payable_id',
        'reversed_from_id', 'is_reversed', 'posted_at', 'bir_include',
    ]
    output = StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(header)
    for tx, review in rows:
        writer.writerow([_protect_csv_text(cell) for cell in (
            tx.id, tx.transaction_date, tx.financial_account_id,
            tx.direction, tx.amount, tx.payment_method, tx.module, tx.category,
            tx.external_source, tx.external_id, tx.reference_no,
            tx.linked_record_id, 'missing_direct_journal_link',
            review.decision if review else 'never_reviewed',
            review.supporting_reference if review else None,
            review.notes if review else None,
            review.suggested_journal_entry_id if review else None,
            review.reviewed_by if review else None,
            review.created_at.isoformat() if review and review.created_at else None,
            tx.subcategory, tx.linked_record_type, tx.receivable_id, tx.payable_id,
            tx.reversed_from_id, tx.is_reversed, tx.posted_at, tx.bir_include,
        )])
    return output.getvalue()


def review_journal_linkage(db: Session, *, year=None, source=None, queue='all', page=1, limit=25):
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

    scope_count = base.count()
    # Count latest review classifications across the *filtered population*,
    # not just this page. Recording evidence is not financial reconciliation.
    latest_review = (
        db.query(
            JournalLinkageReview.money_transaction_id.label('transaction_id'),
            func.max(JournalLinkageReview.id).label('review_id'),
        )
        .group_by(JournalLinkageReview.money_transaction_id)
        .subquery()
    )
    review_group_rows = (
        base.with_entities(
            JournalLinkageReview.decision,
            func.count(MoneyTransaction.id),
        )
        .outerjoin(
            latest_review,
            latest_review.c.transaction_id == MoneyTransaction.id,
        )
        .outerjoin(
            JournalLinkageReview,
            JournalLinkageReview.id == latest_review.c.review_id,
        )
        .group_by(JournalLinkageReview.decision)
        .all()
    )
    review_counts = {
        'never_reviewed': 0,
        'needs_evidence': 0,
        'cashflow_only_documented': 0,
        'journal_candidate_identified': 0,
        'requires_accounting_review': 0,
    }
    for decision, total in review_group_rows:
        key = decision if decision is not None else 'never_reviewed'
        if key in review_counts:
            review_counts[key] = int(total)
        else:
            # Keep any future classification visible in overall review coverage
            # without wrongly treating it as reconciled.
            review_counts['requires_accounting_review'] += int(total)
    evidence_recorded = scope_count - review_counts['never_reviewed']

    # The work queue filters rows, never the scope-wide review progress.
    # Otherwise choosing "awaiting review" would make pending journals appear
    # to disappear from the financial exception summary.
    if queue == 'unreviewed':
        base = base.outerjoin(
            latest_review,
            latest_review.c.transaction_id == MoneyTransaction.id,
        ).filter(latest_review.c.review_id.is_(None))
    elif queue == 'reviewed':
        base = base.join(
            latest_review,
            latest_review.c.transaction_id == MoneyTransaction.id,
        )
    count = base.count()

    rows = (
        base.order_by(MoneyTransaction.transaction_date.asc(), MoneyTransaction.id.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    latest_by_tx = {}
    ids = [row.id for row in rows]
    if ids:
        reviews = (
            db.query(JournalLinkageReview)
            .filter(JournalLinkageReview.money_transaction_id.in_(ids))
            .order_by(JournalLinkageReview.id.desc())
            .all()
        )
        for review in reviews:
            latest_by_tx.setdefault(review.money_transaction_id, review)

    return {
        'count': int(count),
        'review_summary': {
            'missing_journal_links': int(scope_count),
            'never_reviewed': review_counts['never_reviewed'],
            'evidence_recorded': evidence_recorded,
            'classifications': {
                key: value for key, value in review_counts.items()
                if key != 'never_reviewed'
            },
            'journal_links_resolved_by_review': 0,
            'is_financially_reconciled': False,
        },
        'page': page,
        'queue': queue,
        'scope_count': int(scope_count),
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
                # A review classification never settles a journal mismatch.
                'review_status': 'evidence_recorded' if row.id in latest_by_tx else 'unverified',
                'latest_review': _serialize_review(latest_by_tx.get(row.id)),
            }
            for row in rows
        ],
    }


@router.get('/journal-linkage-review')
def journal_linkage_review(
    response: Response,
    year: str | None = Query(None, pattern=r'^\d{4}$'),
    source: str | None = Query(None, max_length=40),
    queue: Literal['all', 'unreviewed', 'reviewed'] = Query('all'),
    page: int = Query(1, ge=1, le=10000),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(require_roles('owner', 'admin')),
):
    response.headers['Cache-Control'] = 'private, no-store'
    return review_journal_linkage(db, year=year, source=source, queue=queue, page=page, limit=limit)


@router.get('/journal-linkage-review/export.csv')
def export_journal_linkage_review(
    year: str | None = Query(None, pattern=r'^\d{4}$'),
    source: str | None = Query(None, max_length=40),
    queue: Literal['all', 'unreviewed', 'reviewed'] = Query('all'),
    page: int | None = Query(None, ge=1, le=10000),
    limit: int = Query(25, ge=1, le=100),
    expected_page_ids: str | None = Query(
        None, min_length=1, max_length=2100, pattern=r'^[1-9][0-9]*(,[1-9][0-9]*)*$'
    ),
    db: Session = Depends(get_db),
    user=Depends(require_roles('owner', 'admin')),
):
    # Never emit private receipt references or amounts into public build logs.
    content = journal_review_csv(
        db, year=year, source=source, queue=queue, page=page, limit=limit,
        expected_page_ids=expected_page_ids,
    )
    filename = (
        f"journal-review-private-{year or 'all'}-{queue}"
        f"{f'-page-{page}' if page is not None else ''}.csv"
    )
    return Response(
        content=content,
        media_type='text/csv; charset=utf-8',
        headers={
            'Cache-Control': 'private, no-store',
            'X-Content-Type-Options': 'nosniff',
            'Content-Disposition': f'attachment; filename="{filename}"',
        },
    )


class JournalLinkageReviewCreate(BaseModel):
    decision: Literal[
        'needs_evidence', 'cashflow_only_documented',
        'journal_candidate_identified', 'requires_accounting_review',
    ]
    supporting_reference: str | None = Field(default=None, max_length=255)
    notes: str = Field(min_length=10, max_length=2000)
    suggested_journal_entry_id: int | None = Field(default=None, gt=0)
    expected_latest_review_id: int | None = Field(default=None, gt=0)
    idempotency_key: str = Field(min_length=16, max_length=128)


def _serialize_review(row: JournalLinkageReview | None):
    if row is None:
        return None
    return {
        'id': row.id,
        'transaction_id': row.money_transaction_id,
        'decision': row.decision,
        'supporting_reference': row.supporting_reference,
        'notes': row.notes,
        'suggested_journal_entry_id': row.suggested_journal_entry_id,
        'reviewed_by': row.reviewed_by,
        'reviewed_at': row.created_at.isoformat() if row.created_at else None,
        'accounting_posting_created': False,
        'journal_link_changed': False,
    }


def _same_review_retry(row: JournalLinkageReview, payload: JournalLinkageReviewCreate, user) -> bool:
    """Only return an existing decision for an identical retry by its original reviewer."""
    return (
        row.decision == payload.decision
        and row.supporting_reference == ((payload.supporting_reference or '').strip() or None)
        and row.notes == payload.notes.strip()
        and row.suggested_journal_entry_id == payload.suggested_journal_entry_id
        and row.reviewed_by == getattr(user, 'username', None)
    )


def record_review_decision(db: Session, transaction_id: int, payload: JournalLinkageReviewCreate, user):
    """Append decision evidence only; lock the money row to prevent review races."""
    prior_key = db.query(JournalLinkageReview).filter(
        JournalLinkageReview.idempotency_key == payload.idempotency_key
    ).one_or_none()
    if prior_key:
        if prior_key.money_transaction_id != transaction_id:
            raise HTTPException(status_code=409, detail='Idempotency key already used on another transaction.')
        if not _same_review_retry(prior_key, payload, user):
            raise HTTPException(status_code=409, detail='Idempotency key already used with different review evidence or reviewer.')
        return _serialize_review(prior_key)
    tx = _unlinked(db).filter(MoneyTransaction.id == transaction_id).with_for_update().one_or_none()
    if tx is None:
        raise HTTPException(status_code=409, detail='Transaction no longer qualifies for unlinked journal review.')
    previous = db.query(JournalLinkageReview).filter(
        JournalLinkageReview.money_transaction_id == transaction_id
    ).order_by(JournalLinkageReview.id.desc()).first()
    if (previous.id if previous else None) != payload.expected_latest_review_id:
        raise HTTPException(status_code=409, detail='Review history changed. Refresh before submitting.')

    reference = (payload.supporting_reference or '').strip() or None
    notes = payload.notes.strip()
    if len(notes) < 10:
        raise HTTPException(status_code=422, detail='A specific review rationale is required.')
    if payload.decision != 'needs_evidence' and not reference:
        raise HTTPException(status_code=422, detail='Evidence reference is required for this classification.')
    journal = None
    if payload.decision == 'journal_candidate_identified':
        if not payload.suggested_journal_entry_id:
            raise HTTPException(status_code=422, detail='An existing posted journal ID is required.')
        journal = db.query(JournalEntry).filter(
            JournalEntry.id == payload.suggested_journal_entry_id,
            JournalEntry.status == 'posted',
        ).one_or_none()
        if journal is None:
            raise HTTPException(status_code=422, detail='Suggested journal must already be posted.')
    elif payload.suggested_journal_entry_id is not None:
        raise HTTPException(status_code=422, detail='Journal ID only allowed for journal candidate review.')

    reviewer = getattr(user, 'username', None)
    if not reviewer:
        raise HTTPException(status_code=403, detail='Reviewer identity unavailable.')
    row = JournalLinkageReview(
        money_transaction_id=transaction_id,
        decision=payload.decision,
        supporting_reference=reference,
        notes=notes,
        suggested_journal_entry_id=journal.id if journal else None,
        reviewed_by=reviewer,
        idempotency_key=payload.idempotency_key,
    )
    db.add(row)
    db.flush()
    record_audit(db, entity_type='journal_linkage_review', entity_id=row.id,
                 action='evidence_classified', user=user, after={
                     'money_transaction_id': transaction_id,
                     'decision': row.decision,
                     'suggested_journal_entry_id': row.suggested_journal_entry_id,
                     'supporting_reference': row.supporting_reference,
                 })
    db.commit()
    db.refresh(row)
    return _serialize_review(row)


@router.get('/journal-linkage-review/{transaction_id}/history')
def journal_linkage_review_history(
    transaction_id: int,
    response: Response,
    db: Session = Depends(get_db),
    user=Depends(require_roles('owner', 'admin')),
):
    response.headers['Cache-Control'] = 'private, no-store'
    tx = db.query(MoneyTransaction.id).filter(MoneyTransaction.id == transaction_id).one_or_none()
    if tx is None:
        raise HTTPException(status_code=404, detail='Money transaction not found.')
    rows = db.query(JournalLinkageReview).filter(
        JournalLinkageReview.money_transaction_id == transaction_id,
    ).order_by(JournalLinkageReview.id.desc()).limit(100).all()
    return {'transaction_id': transaction_id, 'items': [_serialize_review(r) for r in rows]}


@router.post('/journal-linkage-review/{transaction_id}/decisions')
def journal_linkage_record_review(
    transaction_id: int,
    payload: JournalLinkageReviewCreate,
    response: Response,
    db: Session = Depends(get_db),
    user=Depends(require_roles('owner', 'admin')),
):
    response.headers['Cache-Control'] = 'private, no-store'
    return record_review_decision(db, transaction_id, payload, user)

"""Owner-only, read-only review of posted money movements lacking journal links.

A missing journal foreign key is not evidence that money or revenue is missing.
No endpoint in this module creates journals, updates links, or writes decisions.
"""
from __future__ import annotations

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
    page: int = Query(1, ge=1, le=10000),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(require_roles('owner', 'admin')),
):
    response.headers['Cache-Control'] = 'private, no-store'
    return review_journal_linkage(db, year=year, source=source, page=page, limit=limit)


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


def record_review_decision(db: Session, transaction_id: int, payload: JournalLinkageReviewCreate, user):
    """Append decision evidence only; lock the money row to prevent review races."""
    prior_key = db.query(JournalLinkageReview).filter(
        JournalLinkageReview.idempotency_key == payload.idempotency_key
    ).one_or_none()
    if prior_key:
        if prior_key.money_transaction_id != transaction_id:
            raise HTTPException(status_code=409, detail='Idempotency key already used on another transaction.')
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

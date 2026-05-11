from __future__ import annotations
from sqlalchemy.orm import Session
from app.models.entities import BIRBookEntry, BIRSelectionEntry, JournalEntry, PeriodLock, Record

def period_locked(db: Session, period_key: str, scope: str = 'bir') -> bool:
    lock = db.query(PeriodLock).filter(PeriodLock.period_key == period_key, PeriodLock.scope == scope).first()
    return bool(lock and lock.is_locked)

def period_key_from_date(date_value: str | None) -> str | None:
    if not date_value:
        return None
    value = date_value.strip()
    if len(value) < 7:
        return None
    return value[:7]

def ensure_period_unlocked(db: Session, period_key: str | None, scope: str = 'bir', action: str = 'write') -> None:
    if not period_key:
        return
    if period_locked(db, period_key, scope):
        raise ValueError(f'Cannot {action}. Period {period_key} is locked for scope "{scope}".')

def ensure_date_unlocked(db: Session, date_value: str | None, scope: str = 'bir', action: str = 'write') -> None:
    ensure_period_unlocked(db, period_key_from_date(date_value), scope=scope, action=action)


def _derive_record_book_type(record: Record) -> str:
    if record.direction == 'income':
        return 'sales_book' if record.module_slug in {'rooms', 'restaurant', 'breakfast', 'cafe', 'bar', 'events', 'other-income', 'other_income'} else 'cash_receipts_book'
    return 'purchase_book' if record.module_slug in {'procurement', 'inventory', 'utilities', 'assets'} else 'cash_disbursements_book'


def _record_candidates(db: Session, period_key: str) -> list[Record]:
    return db.query(Record).filter(
        Record.transaction_date.like(f"{period_key}%"),
        Record.direction.in_(['income', 'expense']),
        Record.workflow_status == 'approved',
    ).order_by(Record.id.asc()).all()


def _journal_candidates(db: Session, period_key: str) -> list[JournalEntry]:
    return db.query(JournalEntry).filter(
        JournalEntry.entry_date.like(f"{period_key}%"),
        JournalEntry.status == 'posted',
    ).order_by(JournalEntry.id.asc()).all()


def list_bir_candidates(db: Session, period_key: str):
    selections = db.query(BIRSelectionEntry).filter(BIRSelectionEntry.period_key == period_key).all()
    sel_map = {(s.source_type, int(s.source_id)): s for s in selections}

    records = []
    for row in _record_candidates(db, period_key):
        sel = sel_map.get(('record', int(row.id)))
        default_include = row.bir_status == 'posted_to_bir'
        include = bool(sel.include_in_bir) if sel else default_include
        records.append({
            'source_type': 'record',
            'source_id': row.id,
            'module_slug': row.module_slug,
            'name': row.name,
            'entry_date': row.transaction_date,
            'raw_reference_no': row.document_ref,
            'reference_no': row.document_ref,
            'display_reference_no': row.document_ref or f'REC-{row.id}',
            'direction': row.direction,
            'amount': float(row.amount or 0),
            'bir_status': row.bir_status,
            'include_in_bir': include,
            'book_type': (sel.book_type if sel and sel.book_type else _derive_record_book_type(row)),
            'tax_type': (sel.tax_type if sel and sel.tax_type else 'unassigned'),
            'notes': (sel.notes if sel else None),
        })

    journals = []
    for row in _journal_candidates(db, period_key):
        sel = sel_map.get(('journal_entry', int(row.id)))
        journals.append({
            'source_type': 'journal_entry',
            'source_id': row.id,
            'source_module': row.source_module,
            'name': row.description,
            'entry_date': row.entry_date,
            'raw_reference_no': row.reference_no,
            'reference_no': row.reference_no,
            'display_reference_no': row.reference_no or f'JE-{row.id}',
            'amount': 0.0,
            'include_in_bir': bool(sel.include_in_bir) if sel else False,
            'book_type': (sel.book_type if sel and sel.book_type else 'general_journal'),
            'tax_type': (sel.tax_type if sel and sel.tax_type else 'unassigned'),
            'notes': (sel.notes if sel else None),
        })

    return {
        'period_key': period_key,
        'records': records,
        'journal_entries': journals,
        'summary': {
            'record_candidates': len(records),
            'record_included': len([x for x in records if x['include_in_bir']]),
            'journal_candidates': len(journals),
            'journal_included': len([x for x in journals if x['include_in_bir']]),
        },
    }


def save_bir_selections(db: Session, period_key: str, selections: list, username: str | None = None):
    ensure_period_unlocked(db, period_key, 'bir', action='update BIR inclusion selections')
    for item in selections:
        source_type = (item.source_type or '').strip().lower()
        source_id = int(item.source_id)
        if source_type not in {'record', 'journal_entry'}:
            raise ValueError('source_type must be "record" or "journal_entry".')

        if source_type == 'record':
            row = db.get(Record, source_id)
            if not row:
                raise ValueError(f'Record {source_id} not found.')
            if not (row.transaction_date or '').startswith(period_key):
                raise ValueError(f'Record {source_id} does not belong to period {period_key}.')
            row.bir_status = 'posted_to_bir' if item.include_in_bir else ('ready_for_bir' if row.bir_status == 'posted_to_bir' else row.bir_status)
            db.add(row)
        else:
            row = db.get(JournalEntry, source_id)
            if not row:
                raise ValueError(f'Journal entry {source_id} not found.')
            if not (row.entry_date or '').startswith(period_key):
                raise ValueError(f'Journal entry {source_id} does not belong to period {period_key}.')

        sel = db.query(BIRSelectionEntry).filter(
            BIRSelectionEntry.period_key == period_key,
            BIRSelectionEntry.source_type == source_type,
            BIRSelectionEntry.source_id == source_id,
        ).first()
        if not sel:
            sel = BIRSelectionEntry(period_key=period_key, source_type=source_type, source_id=source_id)
        sel.include_in_bir = bool(item.include_in_bir)
        sel.book_type = item.book_type
        sel.tax_type = item.tax_type
        sel.notes = item.notes
        sel.selected_by = username
        db.add(sel)
    db.commit()
    return list_bir_candidates(db, period_key)


def generate_books(db: Session, period_key: str):
    ensure_period_unlocked(db, period_key, 'bir', action='generate BIR books')
    db.query(BIRBookEntry).filter(BIRBookEntry.period_key == period_key).delete()

    selections = db.query(BIRSelectionEntry).filter(BIRSelectionEntry.period_key == period_key).all()
    sel_map = {(s.source_type, int(s.source_id)): s for s in selections}

    entries = []

    for r in _record_candidates(db, period_key):
        sel = sel_map.get(('record', int(r.id)))
        include = bool(sel.include_in_bir) if sel else (r.bir_status == 'posted_to_bir')
        if not include:
            continue
        entries.append(BIRBookEntry(
            book_type=(sel.book_type if sel and sel.book_type else _derive_record_book_type(r)),
            period_key=period_key,
            source_type='record',
            source_id=r.id,
            entry_date=r.transaction_date,
            reference_no=r.document_ref or f"REC-{r.id}",
            description=r.name,
            amount=float(r.amount or 0),
            tax_type=(sel.tax_type if sel and sel.tax_type else 'unassigned'),
        ))

    for j in _journal_candidates(db, period_key):
        sel = sel_map.get(('journal_entry', int(j.id)))
        if not (sel and sel.include_in_bir):
            continue
        entries.append(BIRBookEntry(
            book_type=(sel.book_type if sel.book_type else 'general_journal'),
            period_key=period_key,
            source_type='journal_entry',
            source_id=j.id,
            entry_date=j.entry_date,
            reference_no=j.reference_no,
            description=j.description,
            amount=0,
            tax_type=(sel.tax_type if sel.tax_type else 'unassigned'),
        ))

    for e in entries:
        db.add(e)
    db.commit()
    return {'generated': len(entries), 'period_key': period_key}

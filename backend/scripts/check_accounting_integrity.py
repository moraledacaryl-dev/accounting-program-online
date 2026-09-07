"""Read-only release preflight. Reports record IDs, never credentials or notes."""
import json
import re
import sys
from pathlib import Path
from datetime import date
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import func
from app.db.database import SessionLocal
from app.models.entities import JournalEntry, JournalLine, Record
from app.services.journal_integrity_service import money


def inspect_integrity(db):
    issues = []
    for entry in db.query(JournalEntry).yield_per(200):
        if entry.status not in {'draft', 'posted', 'cancelled', 'voided', 'reversed'}:
            issues.append({'type': 'unknown_journal_status', 'journal_id': entry.id})
        if entry.status != 'posted':
            continue
        try:
            if not entry.entry_date or date.fromisoformat(entry.entry_date).isoformat() != entry.entry_date:
                raise ValueError()
        except (TypeError, ValueError):
            issues.append({'type': 'invalid_posted_date', 'journal_id': entry.id})
        lines = db.query(JournalLine).filter_by(journal_entry_id=entry.id).all()
        dr = cr = Decimal(0)
        try:
            for line in lines:
                debit, credit = money(line.debit), money(line.credit)
                dr += debit; cr += credit
                if debit < 0 or credit < 0 or (debit > 0 and credit > 0):
                    issues.append({'type': 'invalid_journal_line', 'journal_id': entry.id, 'line_id': line.id})
            if len(lines) < 2 or dr == 0 or dr != cr:
                issues.append({'type': 'empty_or_unbalanced_journal', 'journal_id': entry.id})
        except ValueError:
            issues.append({'type': 'nonfinite_amount', 'journal_id': entry.id})
        match = re.fullmatch(r'REC-(\d+)', entry.reference_no or '')
        if match:
            record = db.get(Record, int(match.group(1)))
            if record is None:
                issues.append({'type': 'missing_source_record', 'journal_id': entry.id})
            else:
                try:
                    mismatch = abs(money(record.amount)) != dr or record.transaction_date != entry.entry_date or record.workflow_status != 'approved'
                except ValueError:
                    mismatch = True
                if mismatch:
                    issues.append({'type': 'source_journal_mismatch', 'journal_id': entry.id, 'record_id': record.id})
    for source_id, count in db.query(JournalEntry.reversed_from_id, func.count()).filter(JournalEntry.reversed_from_id.is_not(None)).group_by(JournalEntry.reversed_from_id).having(func.count() > 1):
        issues.append({'type': 'duplicate_reversal', 'journal_id': source_id, 'count': count})
    return issues


if __name__ == '__main__':
    with SessionLocal() as db:
        issues = inspect_integrity(db)
        db.rollback()
    print(json.dumps({'ok': not issues, 'issue_count': len(issues), 'issues': issues}, indent=2))
    raise SystemExit(bool(issues))

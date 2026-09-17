from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.models.entities import Booking, BookingFolio, BookingFolioLine, Receivable


CANCELLED_BOOKING_STATUSES = {'cancelled', 'canceled'}


def neutralize_cancelled_beds24_bookings(
    db: Session,
    *,
    beds24_booking_ids: Iterable[str] | None = None,
) -> dict[str, int]:
    """Keep cancelled Beds24 reservations for audit, but remove their financial effect.

    Beds24 remains the source of the cancellation status and raw booking snapshot.  The
    local Booking row is retained so the cancellation is auditable.  Only Beds24-owned
    financial mirrors are removed/zeroed; locally entered folio lines are deliberately
    left untouched because they may represent a real cancellation fee or other manual
    adjustment that accounting intends to keep.
    """
    query = db.query(Booking).filter(Booking.external_source == 'beds24')
    ids = [str(value).strip() for value in (beds24_booking_ids or []) if str(value).strip()]
    if ids:
        query = query.filter(Booking.external_booking_id.in_(ids))

    bookings = [
        row
        for row in query.all()
        if str(row.status or '').strip().lower() in CANCELLED_BOOKING_STATUSES
    ]

    removed_folio_lines = 0
    closed_receivables = 0
    for booking in bookings:
        # Booking gross/deposit fields feed several summaries directly.  The original
        # Beds24 amounts remain preserved in Beds24BookingMap/raw_snapshot for audit.
        booking.gross_amount = 0.0
        booking.deposit_amount = 0.0
        db.add(booking)

        folio_ids = [
            row.id
            for row in db.query(BookingFolio.id).filter(BookingFolio.booking_id == booking.id).all()
        ]
        if folio_ids:
            mirror_lines = (
                db.query(BookingFolioLine)
                .filter(BookingFolioLine.folio_id.in_(folio_ids))
                .filter(BookingFolioLine.external_source == 'beds24')
                .all()
            )
            removed_folio_lines += len(mirror_lines)
            for line in mirror_lines:
                db.delete(line)

        receivables = (
            db.query(Receivable)
            .filter(
                Receivable.source_type == 'booking',
                Receivable.source_id == booking.id,
                Receivable.receivable_type == 'guest_balance',
            )
            .all()
        )
        for receivable in receivables:
            receivable.gross_amount = 0.0
            receivable.amount_collected = 0.0
            receivable.balance_due = 0.0
            receivable.status = 'closed'
            receivable.closed_at = booking.check_out or receivable.closed_at
            marker = 'Cancelled Beds24 reservation; financial mirror neutralized.'
            notes = str(receivable.notes or '').strip()
            if marker.lower() not in notes.lower():
                receivable.notes = f'{notes}\n{marker}'.strip()
            db.add(receivable)
            closed_receivables += 1

    if bookings:
        db.commit()

    return {
        'cancelled_bookings_neutralized': len(bookings),
        'beds24_folio_lines_removed': removed_folio_lines,
        'receivables_closed': closed_receivables,
    }

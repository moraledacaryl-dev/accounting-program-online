"""Safely repair only the two Beds24 cancellations verified by historical audit.

Not a generic booking sync: exact source IDs, exact local IDs, fresh API proof,
locked booking row and strict financial/folio guard are mandatory.
"""
from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path

from app.db.database import SessionLocal
from app.models.entities import Beds24BookingMap, Booking, BookingFolio, Receivable
from app.services.beds24_cancellation_service import apply_beds24_cancellation
from app.services.beds24_service import fetch_beds24_bookings

TARGETS = {"86810780": 567, "87953694": 637}
CANCELLED = {"cancelled", "canceled"}


def verify_remote_cancellation(booking_id: str, bookings: list[dict]) -> dict:
    matches = [
        item for item in bookings
        if str(item.get("id") or item.get("bookingId") or "").strip() == booking_id
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Beds24 {booking_id}: expected exactly one remote booking; found {len(matches)}")
    item = matches[0]
    if str(item.get("status") or "").strip().lower() not in CANCELLED:
        raise RuntimeError(f"Beds24 {booking_id}: upstream status is not cancelled; refuse to change Accounting")
    return item


def check_local_safety(booking_id: str, rows: list, maps: list, receivables: list, folios: list) -> str:
    expected_id = TARGETS[booking_id]
    if len(rows) != 1:
        raise RuntimeError(f"Beds24 {booking_id}: non-unique Accounting link ({len(rows)})")
    booking = rows[0]
    if booking.id != expected_id or booking.external_source != "beds24" or str(booking.external_booking_id) != booking_id:
        raise RuntimeError(f"Beds24 {booking_id}: Accounting ID/source has changed")
    if len(maps) != 1 or maps[0].local_booking_id != expected_id:
        raise RuntimeError(f"Beds24 {booking_id}: exact booking map missing or conflicting")
    if receivables:
        raise RuntimeError(f"Beds24 {booking_id}: linked receivables exist; financial review required")
    if abs(float(booking.deposit_amount or 0)) > 0.0001:
        raise RuntimeError(f"Beds24 {booking_id}: deposit recorded; financial review required")
    if len(folios) != 1:
        raise RuntimeError(f"Beds24 {booking_id}: unexpected folio count ({len(folios)})")
    current = str(booking.status or "").lower()
    if current in CANCELLED:
        return "already_cancelled"
    if current != "confirmed":
        raise RuntimeError(f"Beds24 {booking_id}: unexpected local status ({current})")
    return "eligible"


def repair_booking(booking_id: str) -> str:
    if booking_id not in TARGETS:
        raise ValueError("Unapproved Beds24 booking ID")
    db = SessionLocal()
    try:
        # The network request occurs before locking the Accounting booking row.
        remote, _, _ = fetch_beds24_bookings(db, booking_id=booking_id, include_invoice_items=False)
        payload = verify_remote_cancellation(booking_id, remote)
        rows = db.query(Booking).filter(
            Booking.external_source == "beds24",
            Booking.external_booking_id == booking_id,
        ).populate_existing().with_for_update().all()
        maps = db.query(Beds24BookingMap).filter(
            Beds24BookingMap.beds24_booking_id == booking_id
        ).all()
        receivables = db.query(Receivable).filter(
            Receivable.source_type == "booking",
            Receivable.source_id == TARGETS[booking_id],
        ).all()
        folios = db.query(BookingFolio).filter(
            BookingFolio.booking_id == TARGETS[booking_id]
        ).all()
        decision = check_local_safety(booking_id, rows, maps, receivables, folios)
        if decision == "already_cancelled":
            db.rollback()
            return decision
        result = apply_beds24_cancellation(db, payload, source_type="historical_verified_backfill")
        if result.get("action") != "cancelled" or int(result.get("receivables_closed") or 0):
            raise RuntimeError(f"Beds24 {booking_id}: unexpected status-only cancellation outcome")
        db.commit()
        print(f"BACKFILL: beds24_id={booking_id} accounting_id={TARGETS[booking_id]} status=cancelled")
        return "cancelled"
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def sync_protected_csv(path: Path) -> None:
    """Reflect committed status-only corrections after the shared audit lock is held."""
    if not path.is_file():
        return
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        names = reader.fieldnames
        if not names:
            raise RuntimeError("Audit report is empty")
        rows = list(reader)
    db = SessionLocal()
    try:
        updated = set()
        for bid, accounting_id in TARGETS.items():
            booking = db.query(Booking).filter(Booking.id == accounting_id).one()
            if booking.status not in CANCELLED:
                continue
            for row in rows:
                if str(row.get("beds24_booking_id") or "") == bid and str(row.get("beds24_status") or "").lower() in CANCELLED:
                    row["accounting_status"] = "cancelled"
                    row["classification"] = "MATCHED"
                    updated.add(bid)
        if not updated:
            return
    finally:
        db.close()
    descriptor, temp_path = tempfile.mkstemp(prefix=".statuses-", suffix=".csv", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=names)
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, path)
        print(f"BACKFILL: protected_audit_report_updated={len(updated)}")
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def main() -> int:
    results = {}
    for booking_id in TARGETS:
        results[booking_id] = repair_booking(booking_id)
    sync_protected_csv(Path("/var/lib/hiddenoasis/accounting-beds24-audit/statuses.csv"))
    print(
        "BACKFILL: verified_cancelled=" +
        str(sum(state in {"cancelled", "already_cancelled"} for state in results.values()))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

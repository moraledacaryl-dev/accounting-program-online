"""Read-only, resumable Beds24 booking status audit. Run where Accounting DB is accessible."""
import argparse
import csv
import time
from collections import Counter
from pathlib import Path

from sqlalchemy import text
from app.db.database import SessionLocal
from app.services.beds24_service import Beds24ApiError, load_beds24_settings, _api_get, extract_bookings_from_payload

FIELDS = ["beds24_booking_id", "accounting_booking_id", "accounting_status", "beds24_status", "classification"]
CANCELLED = {"cancelled", "canceled"}


def classify_booking(local, matches):
    """Classify one Beds24 ID without changing accounting records."""
    if len(local) > 1:
        return "DUPLICATE_LINK", ""
    if not matches:
        return "MISSING_IN_BEDS24", ""
    if len(matches) > 1:
        return "DUPLICATE_REMOTE", ""
    remote_status = str(matches[0].get("status") or "").strip().lower()
    local_status = str(local[0]["status"] or "").strip().lower()
    if not remote_status:
        return "API_ERROR", ""
    if remote_status in CANCELLED and local_status not in CANCELLED:
        return "CANCELLATION_MISMATCH", remote_status
    if remote_status == local_status or (remote_status in CANCELLED and local_status in CANCELLED):
        return "MATCHED", remote_status
    return "OTHER_STATUS_MISMATCH", remote_status


def run(output: Path, delay: float, max_requests: int, start_after_id: str = ""):
    output.parent.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        db.execute(text("SET TRANSACTION READ ONLY"))
        rows = db.execute(text("""
            SELECT id, external_booking_id, status FROM bookings
            WHERE external_source = 'beds24' AND external_booking_id IS NOT NULL
            ORDER BY id
        """)).mappings().all()
        grouped = {}
        for row in rows:
            bid = str(row["external_booking_id"]).strip()
            if bid:
                grouped.setdefault(bid, []).append(row)
        completed = {}
        if output.exists():
            with output.open(newline="") as file:
                for row in csv.DictReader(file):
                    if row["classification"] != "API_ERROR":
                        completed[row["beds24_booking_id"]] = row
        settings = load_beds24_settings(db)
        if not settings.get("enabled"):
            raise RuntimeError("Beds24 integration disabled")
        token = str(settings.get("access_token") or "").strip()
        if not token:
            raise RuntimeError("Audit requires an existing access token; refresh is intentionally disabled")
        base_url = str(settings.get("api_base_url") or "https://beds24.com/api/v2").rstrip("/")
        count = 0
        batch_last_id = ""
        if start_after_id and start_after_id not in grouped:
            raise ValueError(f"Start-after ID {start_after_id} is not present in Accounting booking links")
        start_reached = not start_after_id
        with output.open("a", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            if file.tell() == 0:
                writer.writeheader()
            for bid, local in grouped.items():
                if not start_reached:
                    if bid == start_after_id:
                        start_reached = True
                    continue
                if bid in completed:
                    continue
                if count >= max_requests:
                    break
                if len(local) > 1:
                    classification, remote_status = "DUPLICATE_LINK", ""
                else:
                    for attempt in range(5):
                        try:
                            payload = _api_get(base_url, "/bookings", headers={"token": token}, params={"id": bid, "includeInvoiceItems": "false"})
                            bookings = extract_bookings_from_payload(payload)
                            matches = [b for b in bookings if str(b.get("id") or b.get("bookingId") or "") == bid]
                            classification, remote_status = classify_booking(local, matches)
                            break
                        except Beds24ApiError as exc:
                            db.rollback()
                            db.execute(text("SET TRANSACTION READ ONLY"))
                            if exc.status_code == 429 and attempt < 4:
                                wait = max(65, int(exc.retry_after_seconds or 65) + 5)
                                print(f"Rate limited; waiting {wait}s before retry", flush=True)
                                time.sleep(wait)
                                continue
                            classification, remote_status = "API_ERROR", ""
                            print(f"API error for {bid}: {type(exc).__name__} (HTTP {exc.status_code})", flush=True)
                            if exc.status_code == 429:
                                print("Stopping batch: Beds24 rate limit persists after retries.", flush=True)
                                break
                            break
                        except Exception as exc:
                            db.rollback()
                            db.execute(text("SET TRANSACTION READ ONLY"))
                            classification, remote_status = "API_ERROR", ""
                            print(f"Error for {bid}: {type(exc).__name__}", flush=True)
                            break
                writer.writerow({
                    "beds24_booking_id": bid,
                    "accounting_booking_id": ",".join(str(r["id"]) for r in local),
                    "accounting_status": ",".join(str(r["status"]) for r in local),
                    "beds24_status": remote_status,
                    "classification": classification,
                })
                file.flush()
                batch_last_id = bid
                count += 1
                if count % 25 == 0:
                    print(f"Processed {count} new IDs", flush=True)
                if classification == "API_ERROR":
                    print("Stopping batch on API error; rerun to retry this booking.", flush=True)
                    break
                time.sleep(delay)
        latest = {}
        with output.open(newline="") as file:
            for row in csv.DictReader(file):
                latest[row["beds24_booking_id"]] = row
        current_rows = {bid: row for bid, row in latest.items() if bid in grouped}
        counts = Counter(r["classification"] for r in current_rows.values())
        processed = sum(1 for r in current_rows.values() if r["classification"] != "API_ERROR")
        pending = len(grouped) - processed
        issues = sum(value for key, value in counts.items() if key not in {"MATCHED", "API_ERROR"})
        print(f"Total linked IDs: {len(grouped)}; processed: {processed}; pending: {pending}; needs review: {issues}")
        for key, value in sorted(counts.items()):
            print(f"{key}: {value}")
        review_rows = [row for row in current_rows.values() if row["classification"] not in {"MATCHED", "API_ERROR"}]
        for row in review_rows[:50]:
            print(f"REVIEW_REQUIRED {row['classification']} Beds24={row['beds24_booking_id']} Accounting={row['accounting_booking_id']} AccountingStatus={row['accounting_status']} Beds24Status={row['beds24_status']}")
        if len(review_rows) > 50:
            print(f"Further review items: {len(review_rows) - 50} (see protected CSV report)")
        print(f"Report: {output}")
        print(f"Last processed Beds24 ID in this batch: {batch_last_id or 'none'}")
        return 0 if not counts["API_ERROR"] else 2
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("beds24-status-audit.csv"))
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--max-requests", type=int, default=100)
    parser.add_argument("--start-after-id", type=str, default="", help="Resume from the next Beds24 ID after this ID")
    args = parser.parse_args()
    raise SystemExit(run(args.output, max(0.5, args.delay), max(1, args.max_requests), args.start_after_id))

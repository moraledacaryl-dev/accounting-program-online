#!/usr/bin/env python3
"""Generate a PRIVATE, operator-review worklist; never publish transactions to CI.

All database operations execute in a PostgreSQL READ ONLY transaction. The
resulting CSV is written locally to a root-only directory, never to artifacts
or GitHub Actions logs. It does not create journals or edit accounting data.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import secrets
import sys
from sqlalchemy import create_engine, text

WORKLIST_QUERY = """
SELECT t.id, t.transaction_date, t.posted_at, t.module, t.category,
       t.subcategory, t.direction, t.amount, t.payment_method,
       t.reference_no, t.external_source, t.external_id,
       t.financial_account_id, t.linked_record_type, t.linked_record_id,
       t.receivable_id, t.payable_id, t.reversed_from_id
FROM money_transactions t
WHERE t.status = 'posted' AND t.journal_entry_id IS NULL
ORDER BY t.transaction_date, t.id
"""

FIELDS = (
    "id", "transaction_date", "posted_at", "module", "category",
    "subcategory", "direction", "amount", "payment_method",
    "reference_no", "external_source", "external_id",
    "financial_account_id", "linked_record_type", "linked_record_id",
    "receivable_id", "payable_id", "reversed_from_id",
)
WORKLIST_DIR = Path("/var/lib/hiddenoasis/accounting-audit")
MAX_ROWS = 100000


def protect_cell(value):
    """Prevent spreadsheet formula execution in operator-opened CSV files."""
    if value is None:
        return ""
    text_value = str(value)
    if text_value.lstrip().startswith(("=", "+", "-", "@")) and not isinstance(value, (int, float)):
        return "'" + text_value
    return text_value


def write_worklist(rows, directory, *, timestamp=None):
    directory = Path(directory)
    if directory.is_symlink():
        raise ValueError("Refusing symlinked audit worklist directory")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    if len(rows) > MAX_ROWS:
        raise ValueError("Excessive worklist size; refusing private export")
    stamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"journal-linkage-{stamp}-{secrets.token_hex(4)}.csv"
    destination = directory / name
    temp = directory / (name + ".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({
                    key: (str(row.get(key)) if row.get(key) is not None else "")
                    if key == "amount" else protect_cell(row.get(key))
                    for key in FIELDS
                })
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, destination)
        destination.chmod(0o600)
    finally:
        temp.unlink(missing_ok=True)
    return destination


def main():
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise SystemExit("PostgreSQL DATABASE_URL required")
    if os.geteuid() != 0:
        raise SystemExit("Root privileges required to protect worklist contents")

    engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as db:
            db.exec_driver_sql("SET TRANSACTION READ ONLY")
            db.exec_driver_sql("SET LOCAL statement_timeout = '30000ms'")
            raw_rows = db.execute(text(WORKLIST_QUERY)).mappings().all()
            rows = [dict(row) for row in raw_rows]
            db.rollback()
        outfile = write_worklist(rows, WORKLIST_DIR)
        # Only filename, count, and checksum in action logs: never transaction
        # details. A reviewer needs SSH privilege to read the private file.
        digest = sha256(outfile.read_bytes()).hexdigest()
        print("PRIVATE_WORKLIST: status=CREATED")
        print(f"PRIVATE_WORKLIST: rows={len(rows)}")
        print(f"PRIVATE_WORKLIST: directory={WORKLIST_DIR}")
        print(f"PRIVATE_WORKLIST: filename={outfile.name}")
        print(f"PRIVATE_WORKLIST: sha256={digest}")
        print("PRIVATE_WORKLIST: root_only_permissions=0700_directory_0600_file")
        print("PRIVATE_WORKLIST: no_accounting_database_writes=true")
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())

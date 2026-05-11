from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _sqlite_add_column_if_missing(engine: Engine, table_name: str, column_name: str, column_ddl: str):
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return
    existing_columns = {col.get('name') for col in inspector.get_columns(table_name)}
    if column_name in existing_columns:
        return
    with engine.begin() as conn:
        conn.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_ddl}'))


def run_startup_migrations(engine: Engine):
    if engine.url.get_backend_name() != 'sqlite':
        return

    # Booking linkage upgrades + guest linkage.
    _sqlite_add_column_if_missing(engine, 'bookings', 'guest_id', 'INTEGER')
    _sqlite_add_column_if_missing(engine, 'bookings', 'room_id', 'INTEGER')
    _sqlite_add_column_if_missing(engine, 'bookings', 'room_type_id', 'INTEGER')
    _sqlite_add_column_if_missing(engine, 'bookings', 'rate_plan_id', 'INTEGER')
    _sqlite_add_column_if_missing(engine, 'bookings', 'channel_id', 'INTEGER')
    _sqlite_add_column_if_missing(engine, 'bookings', 'external_source', 'VARCHAR(40)')
    _sqlite_add_column_if_missing(engine, 'bookings', 'external_booking_id', 'VARCHAR(120)')

    # Supplier model extensions.
    _sqlite_add_column_if_missing(engine, 'suppliers', 'supplier_type', 'VARCHAR(120)')
    _sqlite_add_column_if_missing(engine, 'suppliers', 'tin', 'VARCHAR(80)')
    _sqlite_add_column_if_missing(engine, 'booking_channels', 'is_prepaid', 'BOOLEAN DEFAULT 0')

    # Cashflow lifecycle extensions.
    _sqlite_add_column_if_missing(engine, 'money_transactions', 'reversed_from_id', 'INTEGER')
    _sqlite_add_column_if_missing(engine, 'money_transactions', 'is_reversed', 'BOOLEAN DEFAULT 0')
    _sqlite_add_column_if_missing(engine, 'money_transactions', 'posted_at', 'VARCHAR(50)')

    _sqlite_add_column_if_missing(engine, 'account_transfers', 'reversed_from_id', 'INTEGER')
    _sqlite_add_column_if_missing(engine, 'account_transfers', 'is_reversed', 'BOOLEAN DEFAULT 0')
    _sqlite_add_column_if_missing(engine, 'account_transfers', 'posted_at', 'VARCHAR(50)')

    _sqlite_add_column_if_missing(engine, 'cash_reconciliations', 'posted_at', 'VARCHAR(50)')
    _sqlite_add_column_if_missing(engine, 'cash_reconciliations', 'closed_at', 'VARCHAR(50)')
    _sqlite_add_column_if_missing(engine, 'cash_reconciliations', 'locked_at', 'VARCHAR(50)')

    _sqlite_add_column_if_missing(engine, 'receivables', 'posted_at', 'VARCHAR(50)')
    _sqlite_add_column_if_missing(engine, 'receivables', 'closed_at', 'VARCHAR(50)')

    _sqlite_add_column_if_missing(engine, 'payables', 'posted_at', 'VARCHAR(50)')
    _sqlite_add_column_if_missing(engine, 'payables', 'closed_at', 'VARCHAR(50)')

    # Channel payout linkage to booking channel setup.
    _sqlite_add_column_if_missing(engine, 'channel_payouts', 'channel_id', 'INTEGER')

    # Beds24 folio line mirror metadata.
    _sqlite_add_column_if_missing(engine, 'booking_folio_lines', 'external_source', 'VARCHAR(40)')
    _sqlite_add_column_if_missing(engine, 'booking_folio_lines', 'external_line_key', 'VARCHAR(160)')

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


def _sqlite_execute(engine: Engine, statement: str):
    with engine.begin() as conn:
        conn.execute(text(statement))


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

    # Dedicated POS receiver idempotency + receiving lifecycle.
    for table_name in ('money_transactions', 'account_transfers', 'receivables', 'sale_orders'):
        _sqlite_add_column_if_missing(engine, table_name, 'external_source', 'VARCHAR(40)')
        _sqlite_add_column_if_missing(engine, table_name, 'external_id', 'VARCHAR(160)')
        _sqlite_execute(engine, f'CREATE UNIQUE INDEX IF NOT EXISTS uq_{table_name}_external_event ON {table_name} (external_source, external_id)')

    _sqlite_add_column_if_missing(engine, 'stock_movements', 'receiving_record_id', 'INTEGER')
    _sqlite_execute(engine, '''
        CREATE TABLE IF NOT EXISTS receivable_adjustments (
            id INTEGER PRIMARY KEY,
            receivable_id INTEGER NOT NULL,
            adjustment_date VARCHAR(50),
            amount FLOAT DEFAULT 0,
            source_type VARCHAR(100),
            source_id INTEGER,
            external_source VARCHAR(40),
            external_id VARCHAR(160),
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(receivable_id) REFERENCES receivables (id)
        )
    ''')
    _sqlite_execute(engine, 'CREATE UNIQUE INDEX IF NOT EXISTS uq_receivable_adjustments_external_event ON receivable_adjustments (external_source, external_id)')

    _sqlite_execute(engine, '''
        CREATE TABLE IF NOT EXISTS integration_receipts (
            id INTEGER PRIMARY KEY,
            external_source VARCHAR(80) NOT NULL,
            external_id VARCHAR(200) NOT NULL,
            event_type VARCHAR(120) NOT NULL,
            source_record_type VARCHAR(120),
            source_record_id VARCHAR(120),
            payload_json TEXT DEFAULT '{}',
            status VARCHAR(40) DEFAULT 'For Review',
            outcome TEXT,
            error_message TEXT,
            received_at VARCHAR(50),
            processed_at VARCHAR(50),
            created_review_record_type VARCHAR(120),
            created_review_record_id VARCHAR(120),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    _sqlite_execute(engine, 'CREATE UNIQUE INDEX IF NOT EXISTS uq_integration_receipt_external_event ON integration_receipts (external_source, external_id)')
    _sqlite_execute(engine, '''
        CREATE TABLE IF NOT EXISTS external_employee_references (
            id INTEGER PRIMARY KEY,
            external_source VARCHAR(80) NOT NULL,
            source_staff_id VARCHAR(120),
            employee_code VARCHAR(120) NOT NULL,
            display_name VARCHAR(255) DEFAULT '',
            department VARCHAR(120),
            position VARCHAR(120),
            role VARCHAR(120),
            active BOOLEAN DEFAULT 1,
            primary_department VARCHAR(120),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    _sqlite_execute(engine, 'CREATE UNIQUE INDEX IF NOT EXISTS uq_external_employee_reference ON external_employee_references (external_source, employee_code)')

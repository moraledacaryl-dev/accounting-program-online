"""existing schema extensions

Revision ID: 0002_existing_schema_extensions
Revises: 0001_initial_schema
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0002_existing_schema_extensions'
down_revision = '0001_initial_schema'
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column):
    inspector = inspect(op.get_bind())
    existing = {item.get('name') for item in inspector.get_columns(table_name)}
    if column.name not in existing:
        op.add_column(table_name, column)


def upgrade():
    _add_column_if_missing('bookings', sa.Column('guest_id', sa.Integer(), nullable=True))
    _add_column_if_missing('bookings', sa.Column('room_id', sa.Integer(), nullable=True))
    _add_column_if_missing('bookings', sa.Column('room_type_id', sa.Integer(), nullable=True))
    _add_column_if_missing('bookings', sa.Column('rate_plan_id', sa.Integer(), nullable=True))
    _add_column_if_missing('bookings', sa.Column('channel_id', sa.Integer(), nullable=True))
    _add_column_if_missing('bookings', sa.Column('external_source', sa.String(length=40), nullable=True))
    _add_column_if_missing('bookings', sa.Column('external_booking_id', sa.String(length=120), nullable=True))

    _add_column_if_missing('suppliers', sa.Column('supplier_type', sa.String(length=120), nullable=True))
    _add_column_if_missing('suppliers', sa.Column('tin', sa.String(length=80), nullable=True))
    _add_column_if_missing('booking_channels', sa.Column('is_prepaid', sa.Boolean(), nullable=False, server_default=sa.false()))

    _add_column_if_missing('money_transactions', sa.Column('reversed_from_id', sa.Integer(), nullable=True))
    _add_column_if_missing('money_transactions', sa.Column('is_reversed', sa.Boolean(), nullable=False, server_default=sa.false()))
    _add_column_if_missing('money_transactions', sa.Column('posted_at', sa.String(length=50), nullable=True))

    _add_column_if_missing('account_transfers', sa.Column('reversed_from_id', sa.Integer(), nullable=True))
    _add_column_if_missing('account_transfers', sa.Column('is_reversed', sa.Boolean(), nullable=False, server_default=sa.false()))
    _add_column_if_missing('account_transfers', sa.Column('posted_at', sa.String(length=50), nullable=True))

    _add_column_if_missing('cash_reconciliations', sa.Column('posted_at', sa.String(length=50), nullable=True))
    _add_column_if_missing('cash_reconciliations', sa.Column('closed_at', sa.String(length=50), nullable=True))
    _add_column_if_missing('cash_reconciliations', sa.Column('locked_at', sa.String(length=50), nullable=True))

    _add_column_if_missing('receivables', sa.Column('posted_at', sa.String(length=50), nullable=True))
    _add_column_if_missing('receivables', sa.Column('closed_at', sa.String(length=50), nullable=True))
    _add_column_if_missing('payables', sa.Column('posted_at', sa.String(length=50), nullable=True))
    _add_column_if_missing('payables', sa.Column('closed_at', sa.String(length=50), nullable=True))

    _add_column_if_missing('channel_payouts', sa.Column('channel_id', sa.Integer(), nullable=True))
    _add_column_if_missing('booking_folio_lines', sa.Column('external_source', sa.String(length=40), nullable=True))
    _add_column_if_missing('booking_folio_lines', sa.Column('external_line_key', sa.String(length=160), nullable=True))


def downgrade():
    pass

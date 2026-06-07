"""Dedicated event workflow

Revision ID: 0004_event_workflow
Revises: 0003_pos_receiving_lifecycle
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0004_event_workflow'
down_revision = '0003_pos_receiving_lifecycle'
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return table_name in inspect(op.get_bind()).get_table_names()


def _create_index_if_missing(name: str, table_name: str, columns: list[str], *, unique: bool = False):
    if not _has_table(table_name):
        return
    existing = {item.get('name') for item in inspect(op.get_bind()).get_indexes(table_name)}
    if name not in existing:
        op.create_index(name, table_name, columns, unique=unique)


def upgrade():
    if not _has_table('event_bookings'):
        op.create_table(
            'event_bookings',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('event_no', sa.String(length=120), nullable=False),
            sa.Column('event_name', sa.String(length=255), nullable=False, server_default=''),
            sa.Column('client_name', sa.String(length=255), nullable=False, server_default=''),
            sa.Column('contact_name', sa.String(length=255), nullable=True),
            sa.Column('contact_phone', sa.String(length=80), nullable=True),
            sa.Column('contact_email', sa.String(length=180), nullable=True),
            sa.Column('event_type', sa.String(length=120), nullable=True),
            sa.Column('event_date', sa.String(length=50), nullable=True),
            sa.Column('start_time', sa.String(length=20), nullable=True),
            sa.Column('end_time', sa.String(length=20), nullable=True),
            sa.Column('venue', sa.String(length=180), nullable=True),
            sa.Column('guest_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('package_name', sa.String(length=180), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='draft'),
            sa.Column('quote_sent_at', sa.String(length=50), nullable=True),
            sa.Column('confirmed_at', sa.String(length=50), nullable=True),
            sa.Column('completed_at', sa.String(length=50), nullable=True),
            sa.Column('cancelled_at', sa.String(length=50), nullable=True),
            sa.Column('deposit_required', sa.Float(), nullable=False, server_default='0'),
            sa.Column('deposit_due_date', sa.String(length=50), nullable=True),
            sa.Column('subtotal_amount', sa.Float(), nullable=False, server_default='0'),
            sa.Column('discount_amount', sa.Float(), nullable=False, server_default='0'),
            sa.Column('tax_amount', sa.Float(), nullable=False, server_default='0'),
            sa.Column('total_amount', sa.Float(), nullable=False, server_default='0'),
            sa.Column('deposit_paid', sa.Float(), nullable=False, server_default='0'),
            sa.Column('balance_due', sa.Float(), nullable=False, server_default='0'),
            sa.Column('receivable_id', sa.Integer(), sa.ForeignKey('receivables.id'), nullable=True),
            sa.Column('record_id', sa.Integer(), sa.ForeignKey('records.id'), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_by', sa.String(length=100), nullable=True),
            sa.Column('approved_by', sa.String(length=100), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not _has_table('event_booking_lines'):
        op.create_table(
            'event_booking_lines',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('event_booking_id', sa.Integer(), sa.ForeignKey('event_bookings.id'), nullable=False),
            sa.Column('line_type', sa.String(length=50), nullable=False, server_default='package'),
            sa.Column('description', sa.String(length=255), nullable=False, server_default=''),
            sa.Column('quantity', sa.Float(), nullable=False, server_default='1'),
            sa.Column('unit_price', sa.Float(), nullable=False, server_default='0'),
            sa.Column('total_amount', sa.Float(), nullable=False, server_default='0'),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        )

    if not _has_table('event_payments'):
        op.create_table(
            'event_payments',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('event_booking_id', sa.Integer(), sa.ForeignKey('event_bookings.id'), nullable=False),
            sa.Column('payment_date', sa.String(length=50), nullable=True),
            sa.Column('amount', sa.Float(), nullable=False, server_default='0'),
            sa.Column('payment_method', sa.String(length=120), nullable=True),
            sa.Column('financial_account_id', sa.Integer(), sa.ForeignKey('financial_accounts.id'), nullable=True),
            sa.Column('reference_no', sa.String(length=255), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('money_transaction_id', sa.Integer(), sa.ForeignKey('money_transactions.id'), nullable=True),
            sa.Column('created_by', sa.String(length=100), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    _create_index_if_missing('ix_event_bookings_event_no', 'event_bookings', ['event_no'], unique=True)
    for column in (
        'event_name', 'client_name', 'event_type', 'event_date', 'venue', 'status',
        'quote_sent_at', 'confirmed_at', 'completed_at', 'cancelled_at',
        'deposit_due_date', 'receivable_id', 'record_id',
    ):
        _create_index_if_missing(f'ix_event_bookings_{column}', 'event_bookings', [column])

    _create_index_if_missing('ix_event_booking_lines_event_booking_id', 'event_booking_lines', ['event_booking_id'])
    _create_index_if_missing('ix_event_booking_lines_line_type', 'event_booking_lines', ['line_type'])

    for column in ('event_booking_id', 'payment_date', 'financial_account_id', 'reference_no', 'money_transaction_id'):
        _create_index_if_missing(f'ix_event_payments_{column}', 'event_payments', [column])


def downgrade():
    pass

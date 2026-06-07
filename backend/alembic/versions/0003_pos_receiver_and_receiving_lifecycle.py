"""POS receiver idempotency and receiving lifecycle

Revision ID: 0003_pos_receiving_lifecycle
Revises: 0002_existing_schema_extensions
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0003_pos_receiving_lifecycle'
down_revision = '0002_existing_schema_extensions'
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return table_name in inspect(op.get_bind()).get_table_names()


def _add_column_if_missing(table_name: str, column: sa.Column):
    existing = {item.get('name') for item in inspect(op.get_bind()).get_columns(table_name)}
    if column.name not in existing:
        op.add_column(table_name, column)


def _create_index_if_missing(name: str, table_name: str, columns: list[str], *, unique: bool = False):
    existing = {item.get('name') for item in inspect(op.get_bind()).get_indexes(table_name)}
    if name not in existing:
        op.create_index(name, table_name, columns, unique=unique)


def upgrade():
    for table_name in ('money_transactions', 'account_transfers', 'receivables', 'sale_orders'):
        _add_column_if_missing(table_name, sa.Column('external_source', sa.String(length=40), nullable=True))
        _add_column_if_missing(table_name, sa.Column('external_id', sa.String(length=160), nullable=True))
        _create_index_if_missing(f'ix_{table_name}_external_source', table_name, ['external_source'])
        _create_index_if_missing(f'ix_{table_name}_external_id', table_name, ['external_id'])
        _create_index_if_missing(f'uq_{table_name}_external_event', table_name, ['external_source', 'external_id'], unique=True)

    _add_column_if_missing('stock_movements', sa.Column('receiving_record_id', sa.Integer(), nullable=True))
    _create_index_if_missing('ix_stock_movements_receiving_record_id', 'stock_movements', ['receiving_record_id'])

    if not _has_table('receivable_adjustments'):
        op.create_table(
            'receivable_adjustments',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('receivable_id', sa.Integer(), sa.ForeignKey('receivables.id'), nullable=False),
            sa.Column('adjustment_date', sa.String(length=50), nullable=True),
            sa.Column('amount', sa.Float(), nullable=False, server_default='0'),
            sa.Column('source_type', sa.String(length=100), nullable=True),
            sa.Column('source_id', sa.Integer(), nullable=True),
            sa.Column('external_source', sa.String(length=40), nullable=True),
            sa.Column('external_id', sa.String(length=160), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    for column in ('receivable_id', 'adjustment_date', 'source_type', 'source_id', 'external_source', 'external_id'):
        _create_index_if_missing(f'ix_receivable_adjustments_{column}', 'receivable_adjustments', [column])
    _create_index_if_missing('uq_receivable_adjustments_external_event', 'receivable_adjustments', ['external_source', 'external_id'], unique=True)


def downgrade():
    pass

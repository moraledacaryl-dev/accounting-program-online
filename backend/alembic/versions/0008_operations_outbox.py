"""Durable Operations integration outbox

Revision ID: 0008_operations_outbox
Revises: 0007_payable_idempotency
Create Date: 2026-08-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0008_operations_outbox'
down_revision = '0007_payable_idempotency'
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def _indexes(table: str) -> set[str]:
    if not _has_table(table):
        return set()
    return {item.get('name') for item in inspect(op.get_bind()).get_indexes(table)}


def _index(name: str, table: str, columns: list[str], *, unique: bool = False):
    if _has_table(table) and name not in _indexes(table):
        op.create_index(name, table, columns, unique=unique)


def upgrade():
    if not _has_table('operations_outbox_events'):
        op.create_table(
            'operations_outbox_events',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('event_id', sa.String(length=255), nullable=False),
            sa.Column('event_type', sa.String(length=120), nullable=False),
            sa.Column('envelope_json', sa.Text(), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
            sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_http_status', sa.Integer(), nullable=True),
            sa.Column('last_error', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('event_id', name='uq_operations_outbox_event_id'),
        )

    _index('ix_operations_outbox_events_event_id', 'operations_outbox_events', ['event_id'], unique=True)
    _index('ix_operations_outbox_events_event_type', 'operations_outbox_events', ['event_type'])
    _index('ix_operations_outbox_events_status', 'operations_outbox_events', ['status'])
    _index('ix_operations_outbox_events_next_attempt_at', 'operations_outbox_events', ['next_attempt_at'])
    _index('ix_operations_outbox_events_delivered_at', 'operations_outbox_events', ['delivered_at'])
    _index('ix_operations_outbox_events_created_at', 'operations_outbox_events', ['created_at'])


def downgrade():
    if _has_table('operations_outbox_events'):
        op.drop_table('operations_outbox_events')

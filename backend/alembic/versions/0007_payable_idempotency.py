"""Payable mutation idempotency

Revision ID: 0007_payable_idempotency
Revises: 0006_auth_security_state
Create Date: 2026-08-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0007_payable_idempotency'
down_revision = '0006_auth_security_state'
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
    if not _has_table('mutation_idempotency'):
        op.create_table(
            'mutation_idempotency',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('scope', sa.String(length=80), nullable=False),
            sa.Column('idempotency_key', sa.String(length=255), nullable=False),
            sa.Column('request_fingerprint', sa.String(length=64), nullable=False),
            sa.Column('resource_type', sa.String(length=80), nullable=True),
            sa.Column('resource_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                'scope',
                'idempotency_key',
                name='uq_mutation_idempotency_scope_key',
            ),
        )
    _index('ix_mutation_idempotency_scope', 'mutation_idempotency', ['scope'])
    _index('ix_mutation_idempotency_resource_id', 'mutation_idempotency', ['resource_id'])


def downgrade():
    if _has_table('mutation_idempotency'):
        op.drop_table('mutation_idempotency')

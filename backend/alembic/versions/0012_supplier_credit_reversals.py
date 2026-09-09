"""Supplier credit application reversals

Revision ID: 0012_supplier_credit_reversals
Revises: 0011_supplier_credit_apps
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0012_supplier_credit_reversals'
down_revision = '0011_supplier_credit_apps'
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def upgrade():
    if _has_table('supplier_credit_application_reversals'):
        return
    op.create_table(
        'supplier_credit_application_reversals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'application_id',
            sa.Integer(),
            sa.ForeignKey('supplier_credit_applications.id'),
            nullable=False,
        ),
        sa.Column('reversal_date', sa.String(length=50), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False, server_default='0'),
        sa.Column('idempotency_key', sa.String(length=180), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('reversed_by', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('application_id', name='uq_supplier_credit_application_reversal_application'),
        sa.UniqueConstraint('idempotency_key', name='uq_supplier_credit_application_reversal_idempotency'),
    )
    op.create_index(
        'ix_supplier_credit_application_reversals_application_id',
        'supplier_credit_application_reversals',
        ['application_id'],
    )
    op.create_index(
        'ix_supplier_credit_application_reversals_reversal_date',
        'supplier_credit_application_reversals',
        ['reversal_date'],
    )
    op.create_index(
        'ix_supplier_credit_application_reversals_idempotency_key',
        'supplier_credit_application_reversals',
        ['idempotency_key'],
    )


def downgrade():
    if _has_table('supplier_credit_application_reversals'):
        op.drop_table('supplier_credit_application_reversals')

"""Supplier credit applications

Revision ID: 0011_supplier_credit_apps
Revises: 0010_payable_adjustments
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0011_supplier_credit_apps'
down_revision = '0010_payable_adjustments'
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def upgrade():
    if _has_table('supplier_credit_applications'):
        return
    op.create_table(
        'supplier_credit_applications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('supplier_credit_id', sa.Integer(), sa.ForeignKey('supplier_credits.id'), nullable=False),
        sa.Column('payable_id', sa.Integer(), sa.ForeignKey('payables.id'), nullable=False),
        sa.Column('application_date', sa.String(length=50), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False, server_default='0'),
        sa.Column('idempotency_key', sa.String(length=180), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('idempotency_key', name='uq_supplier_credit_application_idempotency'),
    )
    op.create_index('ix_supplier_credit_applications_credit_id', 'supplier_credit_applications', ['supplier_credit_id'])
    op.create_index('ix_supplier_credit_applications_payable_id', 'supplier_credit_applications', ['payable_id'])
    op.create_index('ix_supplier_credit_applications_application_date', 'supplier_credit_applications', ['application_date'])
    op.create_index('ix_supplier_credit_applications_idempotency_key', 'supplier_credit_applications', ['idempotency_key'])


def downgrade():
    if _has_table('supplier_credit_applications'):
        op.drop_table('supplier_credit_applications')

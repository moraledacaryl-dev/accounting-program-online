"""Payable adjustments and supplier credits

Revision ID: 0010_payable_adjustments
Revises: 0009_journal_precision
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0010_payable_adjustments'
down_revision = '0009_journal_precision'
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def upgrade():
    if not _has_table('payable_adjustments'):
        op.create_table(
            'payable_adjustments',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('payable_id', sa.Integer(), sa.ForeignKey('payables.id'), nullable=False),
            sa.Column('adjustment_date', sa.String(length=50), nullable=False),
            sa.Column('amount', sa.Float(), nullable=False, server_default='0'),
            sa.Column('source_app', sa.String(length=80), nullable=False),
            sa.Column('source_event_id', sa.String(length=160), nullable=False),
            sa.Column('purchase_order_id', sa.String(length=160), nullable=False),
            sa.Column('supplier_name', sa.String(length=255), nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                'source_app',
                'source_event_id',
                'payable_id',
                name='uq_payable_adjustment_source_payable',
            ),
        )
        op.create_index('ix_payable_adjustments_payable_id', 'payable_adjustments', ['payable_id'])
        op.create_index('ix_payable_adjustments_adjustment_date', 'payable_adjustments', ['adjustment_date'])
        op.create_index('ix_payable_adjustments_source_app', 'payable_adjustments', ['source_app'])
        op.create_index('ix_payable_adjustments_source_event_id', 'payable_adjustments', ['source_event_id'])
        op.create_index('ix_payable_adjustments_purchase_order_id', 'payable_adjustments', ['purchase_order_id'])
        op.create_index('ix_payable_adjustments_supplier_name', 'payable_adjustments', ['supplier_name'])

    if not _has_table('supplier_credits'):
        op.create_table(
            'supplier_credits',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('supplier_name', sa.String(length=255), nullable=False),
            sa.Column('purchase_order_id', sa.String(length=160), nullable=False),
            sa.Column('credit_date', sa.String(length=50), nullable=False),
            sa.Column('amount', sa.Float(), nullable=False, server_default='0'),
            sa.Column('applied_amount', sa.Float(), nullable=False, server_default='0'),
            sa.Column('balance_available', sa.Float(), nullable=False, server_default='0'),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='open'),
            sa.Column('source_app', sa.String(length=80), nullable=False),
            sa.Column('source_event_id', sa.String(length=160), nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('source_app', 'source_event_id', name='uq_supplier_credit_source_event'),
        )
        op.create_index('ix_supplier_credits_supplier_name', 'supplier_credits', ['supplier_name'])
        op.create_index('ix_supplier_credits_purchase_order_id', 'supplier_credits', ['purchase_order_id'])
        op.create_index('ix_supplier_credits_credit_date', 'supplier_credits', ['credit_date'])
        op.create_index('ix_supplier_credits_status', 'supplier_credits', ['status'])
        op.create_index('ix_supplier_credits_source_app', 'supplier_credits', ['source_app'])
        op.create_index('ix_supplier_credits_source_event_id', 'supplier_credits', ['source_event_id'])


def downgrade():
    if _has_table('supplier_credits'):
        op.drop_table('supplier_credits')
    if _has_table('payable_adjustments'):
        op.drop_table('payable_adjustments')

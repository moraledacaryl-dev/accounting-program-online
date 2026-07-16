"""Accounting integrity and integration-review framework

Revision ID: 0005_accounting_integrity
Revises: 0004_event_workflow
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0005_accounting_integrity'
down_revision = '0004_event_workflow'
branch_labels = None
depends_on = None


def _inspector():
    return inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return name in _inspector().get_table_names()


def _columns(table: str) -> set[str]:
    if not _has_table(table):
        return set()
    return {item['name'] for item in _inspector().get_columns(table)}


def _indexes(table: str) -> set[str]:
    if not _has_table(table):
        return set()
    return {item.get('name') for item in _inspector().get_indexes(table)}


def _add_column(table: str, column: sa.Column):
    if _has_table(table) and column.name not in _columns(table):
        op.add_column(table, column)


def _index(name: str, table: str, columns: list[str], *, unique: bool = False):
    if _has_table(table) and name not in _indexes(table):
        op.create_index(name, table, columns, unique=unique)


def upgrade():
    if not _has_table('audit_events'):
        op.create_table(
            'audit_events',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('entity_type', sa.String(length=80), nullable=False),
            sa.Column('entity_id', sa.Integer(), nullable=False),
            sa.Column('action', sa.String(length=80), nullable=False),
            sa.Column('before_json', sa.Text(), nullable=False, server_default='{}'),
            sa.Column('after_json', sa.Text(), nullable=False, server_default='{}'),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('username', sa.String(length=100), nullable=True),
            sa.Column('source_app', sa.String(length=80), nullable=True),
            sa.Column('correlation_id', sa.String(length=120), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    for column in ('entity_type', 'entity_id', 'action', 'user_id', 'source_app', 'correlation_id'):
        _index(f'ix_audit_events_{column}', 'audit_events', [column])

    for name, column in (
        ('reconciliation_mode', sa.Column('reconciliation_mode', sa.String(length=30), nullable=False, server_default='daily')),
        ('requires_physical_count', sa.Column('requires_physical_count', sa.Boolean(), nullable=False, server_default=sa.false())),
        ('reconciliation_day_of_week', sa.Column('reconciliation_day_of_week', sa.Integer(), nullable=True)),
        ('reconciliation_day_of_month', sa.Column('reconciliation_day_of_month', sa.Integer(), nullable=True)),
        ('variance_tolerance', sa.Column('variance_tolerance', sa.Float(), nullable=False, server_default='0')),
        ('approval_required_on_variance', sa.Column('approval_required_on_variance', sa.Boolean(), nullable=False, server_default=sa.true())),
    ):
        _add_column('financial_accounts', column)
    _index('ix_financial_accounts_reconciliation_mode', 'financial_accounts', ['reconciliation_mode'])

    for table in ('journal_entries', 'bir_book_entries'):
        _add_column(table, sa.Column('reversed_from_id', sa.Integer(), nullable=True))
        _add_column(table, sa.Column('is_reversed', sa.Boolean(), nullable=False, server_default=sa.false()))
        _add_column(table, sa.Column('posted_by', sa.String(length=100), nullable=True))
        _add_column(table, sa.Column('locked_by', sa.String(length=100), nullable=True))
        _index(f'ix_{table}_reversed_from_id', table, ['reversed_from_id'])

    if not _has_table('integration_review_items'):
        op.create_table(
            'integration_review_items',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('source_app', sa.String(length=80), nullable=False),
            sa.Column('source_event_id', sa.String(length=180), nullable=False),
            sa.Column('source_entity_type', sa.String(length=100), nullable=False),
            sa.Column('source_entity_id', sa.String(length=180), nullable=True),
            sa.Column('source_revision', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('financial_effect', sa.String(length=40), nullable=False),
            sa.Column('amount', sa.Float(), nullable=False, server_default='0'),
            sa.Column('currency', sa.String(length=10), nullable=False, server_default='PHP'),
            sa.Column('proposed_account_id', sa.Integer(), sa.ForeignKey('financial_accounts.id'), nullable=True),
            sa.Column('proposed_journal_json', sa.Text(), nullable=True),
            sa.Column('proposed_links_json', sa.Text(), nullable=True),
            sa.Column('payload_json', sa.Text(), nullable=True),
            sa.Column('validation_json', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=40), nullable=False, server_default='ready_for_review'),
            sa.Column('reviewed_at', sa.String(length=50), nullable=True),
            sa.Column('reviewed_by', sa.String(length=100), nullable=True),
            sa.Column('accepted_transaction_id', sa.Integer(), sa.ForeignKey('money_transactions.id'), nullable=True),
            sa.Column('accepted_journal_entry_id', sa.Integer(), sa.ForeignKey('journal_entries.id'), nullable=True),
            sa.Column('accepted_receivable_id', sa.Integer(), sa.ForeignKey('receivables.id'), nullable=True),
            sa.Column('accepted_payable_id', sa.Integer(), sa.ForeignKey('payables.id'), nullable=True),
            sa.Column('rejection_reason', sa.Text(), nullable=True),
            sa.Column('idempotency_key', sa.String(length=255), nullable=False),
            sa.Column('correlation_id', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint('source_app', 'source_event_id', 'source_revision', name='uq_integration_review_source_revision'),
            sa.UniqueConstraint('idempotency_key', name='uq_integration_review_idempotency'),
        )
    for column in (
        'source_app', 'source_event_id', 'source_entity_type', 'source_entity_id', 'financial_effect',
        'proposed_account_id', 'status', 'reviewed_at', 'accepted_transaction_id',
        'accepted_journal_entry_id', 'accepted_receivable_id', 'accepted_payable_id', 'idempotency_key', 'correlation_id',
    ):
        _index(f'ix_integration_review_items_{column}', 'integration_review_items', [column])


def downgrade():
    # Production-safe forward migration. Destructive downgrade is intentionally omitted.
    pass

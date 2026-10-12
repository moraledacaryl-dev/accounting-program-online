"""Register authoritative money movement timestamps in the Alembic chain.

Revision ID: 0016_money_movement_timestamps
Revises: 0015_channel_stay_snapshots

The baseline schema already contains these columns because the application models
are used to build fresh databases before Alembic validation. Production schema
extension code also predates this revision. This migration therefore only adds
missing columns/indexes, keeping upgrades safe for both legacy and fresh schemas.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0016_money_movement_timestamps'
down_revision = '0015_channel_stay_snapshots'
branch_labels = None
depends_on = None

def _columns(table):
    return {row['name'] for row in inspect(op.get_bind()).get_columns(table)}

def _indexes(table):
    return {row['name'] for row in inspect(op.get_bind()).get_indexes(table)}

def upgrade():
    if 'transaction_at' not in _columns('money_transactions'):
        op.add_column('money_transactions', sa.Column('transaction_at', sa.String(length=50), nullable=True))
    if 'ix_money_transactions_transaction_at' not in _indexes('money_transactions'):
        op.create_index('ix_money_transactions_transaction_at', 'money_transactions', ['transaction_at'])

    if 'transfer_at' not in _columns('account_transfers'):
        op.add_column('account_transfers', sa.Column('transfer_at', sa.String(length=50), nullable=True))
    if 'ix_account_transfers_transfer_at' not in _indexes('account_transfers'):
        op.create_index('ix_account_transfers_transfer_at', 'account_transfers', ['transfer_at'])

def downgrade():
    if 'ix_account_transfers_transfer_at' in _indexes('account_transfers'):
        op.drop_index('ix_account_transfers_transfer_at', table_name='account_transfers')
    if 'transfer_at' in _columns('account_transfers'):
        op.drop_column('account_transfers', 'transfer_at')
    if 'ix_money_transactions_transaction_at' in _indexes('money_transactions'):
        op.drop_index('ix_money_transactions_transaction_at', table_name='money_transactions')
    if 'transaction_at' in _columns('money_transactions'):
        op.drop_column('money_transactions', 'transaction_at')

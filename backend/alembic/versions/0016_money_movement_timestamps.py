"""Add authoritative money movement timestamps.

Revision ID: 0016_money_movement_timestamps
Revises: 0015_channel_stay_snapshots
"""
from alembic import op
import sqlalchemy as sa

revision = '0016_money_movement_timestamps'
down_revision = '0015_channel_stay_snapshots'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('money_transactions', sa.Column('transaction_at', sa.String(length=50), nullable=True))
    op.create_index('ix_money_transactions_transaction_at', 'money_transactions', ['transaction_at'])
    op.add_column('account_transfers', sa.Column('transfer_at', sa.String(length=50), nullable=True))
    op.create_index('ix_account_transfers_transfer_at', 'account_transfers', ['transfer_at'])

def downgrade():
    op.drop_index('ix_account_transfers_transfer_at', table_name='account_transfers')
    op.drop_column('account_transfers', 'transfer_at')
    op.drop_index('ix_money_transactions_transaction_at', table_name='money_transactions')
    op.drop_column('money_transactions', 'transaction_at')

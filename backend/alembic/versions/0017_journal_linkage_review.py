"""Create append-only review history separate from Accounting money and journals.

Revision ID: 0017_journal_linkage_review
Revises: 0016_money_movement_timestamps
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0017_journal_linkage_review'
down_revision = '0016_money_movement_timestamps'
branch_labels = None
depends_on = None


def upgrade():
    if 'journal_linkage_reviews' not in inspect(op.get_bind()).get_table_names():
        op.create_table(
            'journal_linkage_reviews',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('money_transaction_id', sa.Integer(),
                      sa.ForeignKey('money_transactions.id'), nullable=False),
            sa.Column('decision', sa.String(length=45), nullable=False),
            sa.Column('supporting_reference', sa.String(length=255), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('suggested_journal_entry_id', sa.Integer(),
                      sa.ForeignKey('journal_entries.id'), nullable=True),
            sa.Column('reviewed_by', sa.String(length=100), nullable=False),
            sa.Column('idempotency_key', sa.String(length=128), nullable=False,
                      unique=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
        )
    indices = {i['name'] for i in inspect(op.get_bind()).get_indexes('journal_linkage_reviews')}
    if 'ix_journal_linkage_reviews_money_transaction_id' not in indices:
        op.create_index('ix_journal_linkage_reviews_money_transaction_id',
                        'journal_linkage_reviews', ['money_transaction_id'])
    if 'ix_journal_linkage_reviews_transaction_time' not in indices:
        op.create_index('ix_journal_linkage_reviews_transaction_time',
                        'journal_linkage_reviews', ['money_transaction_id','id'])


def downgrade():
    if 'journal_linkage_reviews' in inspect(op.get_bind()).get_table_names():
        op.drop_table('journal_linkage_reviews')

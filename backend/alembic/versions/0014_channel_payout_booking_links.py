"""Link channel payouts to bookings for statement reconciliation.

Revision ID: 0014_channel_payout_booking_links
Revises: 0013_money_precision
"""
from alembic import op
import sqlalchemy as sa

revision = '0014_channel_payout_booking_links'
down_revision = '0013_money_precision'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'channel_payout_booking_links',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('payout_id', sa.Integer(), nullable=False),
        sa.Column('booking_id', sa.Integer(), nullable=False),
        sa.Column('payout_reference', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['payout_id'], ['channel_payouts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('payout_id', name='uq_channel_payout_booking_link_payout'),
        sa.UniqueConstraint('booking_id', name='uq_channel_payout_booking_link_booking'),
    )
    op.create_index('ix_channel_payout_booking_links_payout_id', 'channel_payout_booking_links', ['payout_id'])
    op.create_index('ix_channel_payout_booking_links_booking_id', 'channel_payout_booking_links', ['booking_id'])
    op.create_index('ix_channel_payout_booking_links_payout_reference', 'channel_payout_booking_links', ['payout_reference'])


def downgrade():
    op.drop_index('ix_channel_payout_booking_links_payout_reference', table_name='channel_payout_booking_links')
    op.drop_index('ix_channel_payout_booking_links_booking_id', table_name='channel_payout_booking_links')
    op.drop_index('ix_channel_payout_booking_links_payout_id', table_name='channel_payout_booking_links')
    op.drop_table('channel_payout_booking_links')

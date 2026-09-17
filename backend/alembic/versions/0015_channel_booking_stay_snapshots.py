"""Preserve first-seen OTA stay boundaries for channel payout comparisons.

Revision ID: 0015_channel_stay_snapshots
Revises: 0014_payout_booking_links
"""
from alembic import op
import sqlalchemy as sa

revision = '0015_channel_stay_snapshots'
down_revision = '0014_payout_booking_links'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'channel_booking_stay_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('booking_id', sa.Integer(), nullable=False),
        sa.Column('beds24_booking_id', sa.String(length=120), nullable=True),
        sa.Column('ota_check_in', sa.String(length=50), nullable=False),
        sa.Column('ota_check_out', sa.String(length=50), nullable=False),
        sa.Column('source', sa.String(length=40), nullable=False, server_default='beds24_first_seen'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('booking_id', name='uq_channel_booking_stay_snapshot_booking'),
        sa.UniqueConstraint('beds24_booking_id', name='uq_channel_booking_stay_snapshot_beds24'),
    )
    op.create_index('ix_channel_booking_stay_snapshots_booking_id', 'channel_booking_stay_snapshots', ['booking_id'])
    op.create_index('ix_channel_booking_stay_snapshots_beds24_booking_id', 'channel_booking_stay_snapshots', ['beds24_booking_id'])

    # Existing mappings get the best immutable baseline available at migration time.
    # New mappings are captured on first ORM insert/update and are never rewritten.
    op.execute(sa.text("""
        INSERT INTO channel_booking_stay_snapshots
            (booking_id, beds24_booking_id, ota_check_in, ota_check_out, source, created_at, updated_at)
        SELECT local_booking_id, beds24_booking_id, beds24_check_in, beds24_check_out,
               'beds24_migration_baseline', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM beds24_booking_maps
        WHERE local_booking_id IS NOT NULL
          AND beds24_check_in IS NOT NULL AND beds24_check_in <> ''
          AND beds24_check_out IS NOT NULL AND beds24_check_out <> ''
    """))


def downgrade():
    op.drop_index('ix_channel_booking_stay_snapshots_beds24_booking_id', table_name='channel_booking_stay_snapshots')
    op.drop_index('ix_channel_booking_stay_snapshots_booking_id', table_name='channel_booking_stay_snapshots')
    op.drop_table('channel_booking_stay_snapshots')

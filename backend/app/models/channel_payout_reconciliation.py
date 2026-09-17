from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, event, insert, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.entities import Beds24BookingMap, Booking, ChannelPayout, TimestampMixin


class ChannelPayoutBookingLink(Base, TimestampMixin):
    """Durable one-to-one link between a booking and its reconciled payout row."""

    __tablename__ = 'channel_payout_booking_links'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payout_id: Mapped[int] = mapped_column(ForeignKey('channel_payouts.id', ondelete='CASCADE'), nullable=False, index=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey('bookings.id', ondelete='RESTRICT'), nullable=False, index=True)
    payout_reference: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    payout: Mapped[ChannelPayout] = relationship()
    booking: Mapped[Booking] = relationship()

    __table_args__ = (
        UniqueConstraint('payout_id', name='uq_channel_payout_booking_link_payout'),
        UniqueConstraint('booking_id', name='uq_channel_payout_booking_link_booking'),
    )


class ChannelBookingStaySnapshot(Base, TimestampMixin):
    """Immutable first-seen OTA stay boundary used for channel payout comparisons."""

    __tablename__ = 'channel_booking_stay_snapshots'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey('bookings.id', ondelete='RESTRICT'), nullable=False, unique=True, index=True)
    beds24_booking_id: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True, index=True)
    ota_check_in: Mapped[str] = mapped_column(String(50), nullable=False)
    ota_check_out: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default='beds24_first_seen')

    booking: Mapped[Booking] = relationship()


def _capture_first_seen_ota_stay(mapper, connection, target: Beds24BookingMap) -> None:
    """Capture once; later Beds24 resyncs may mutate current dates but never this boundary."""
    booking_id = getattr(target, 'local_booking_id', None)
    check_in = str(getattr(target, 'beds24_check_in', '') or '').strip()
    check_out = str(getattr(target, 'beds24_check_out', '') or '').strip()
    if not booking_id or not check_in or not check_out:
        return

    table = ChannelBookingStaySnapshot.__table__
    exists = connection.execute(select(table.c.id).where(table.c.booking_id == int(booking_id)).limit(1)).first()
    if exists:
        return
    connection.execute(
        insert(table).values(
            booking_id=int(booking_id),
            beds24_booking_id=str(getattr(target, 'beds24_booking_id', '') or '').strip() or None,
            ota_check_in=check_in,
            ota_check_out=check_out,
            source='beds24_first_seen',
        )
    )


event.listen(Beds24BookingMap, 'after_insert', _capture_first_seen_ota_stay)
event.listen(Beds24BookingMap, 'after_update', _capture_first_seen_ota_stay)

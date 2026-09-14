from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.entities import Booking, ChannelPayout, TimestampMixin


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

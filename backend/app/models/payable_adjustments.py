from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base


class PayableAdjustment(Base):
    __tablename__ = 'payable_adjustments'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payable_id: Mapped[int] = mapped_column(ForeignKey('payables.id'), index=True)
    adjustment_date: Mapped[str] = mapped_column(String(50), index=True)
    amount: Mapped[float] = mapped_column(Float, default=0)
    source_app: Mapped[str] = mapped_column(String(80), index=True)
    source_event_id: Mapped[str] = mapped_column(String(160), index=True)
    purchase_order_id: Mapped[str] = mapped_column(String(160), index=True)
    supplier_name: Mapped[str] = mapped_column(String(255), index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            'source_app',
            'source_event_id',
            'payable_id',
            name='uq_payable_adjustment_source_payable',
        ),
    )


class SupplierCredit(Base):
    __tablename__ = 'supplier_credits'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_name: Mapped[str] = mapped_column(String(255), index=True)
    purchase_order_id: Mapped[str] = mapped_column(String(160), index=True)
    credit_date: Mapped[str] = mapped_column(String(50), index=True)
    amount: Mapped[float] = mapped_column(Float, default=0)
    applied_amount: Mapped[float] = mapped_column(Float, default=0)
    balance_available: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(50), default='open', index=True)
    source_app: Mapped[str] = mapped_column(String(80), index=True)
    source_event_id: Mapped[str] = mapped_column(String(160), index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            'source_app',
            'source_event_id',
            name='uq_supplier_credit_source_event',
        ),
    )


class SupplierCreditApplication(Base):
    __tablename__ = 'supplier_credit_applications'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_credit_id: Mapped[int] = mapped_column(ForeignKey('supplier_credits.id'), index=True)
    payable_id: Mapped[int] = mapped_column(ForeignKey('payables.id'), index=True)
    application_date: Mapped[str] = mapped_column(String(50), index=True)
    amount: Mapped[float] = mapped_column(Float, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

from __future__ import annotations

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.database import Base


class AuthLoginFailure(Base):
    __tablename__ = 'auth_login_failures'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64), index=True)
    attempted_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)


class RevokedAccessToken(Base):
    __tablename__ = 'revoked_access_tokens'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    subject: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    expires_at = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    revoked_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

"""
Modelo relacional de usuarios.
"""
from __future__ import annotations

from sqlalchemy import Boolean, String, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(64), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)


class RefreshTokenRow(Base):
    __tablename__ = "refresh_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    issued_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

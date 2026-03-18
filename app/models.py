from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class ExternalAPI(Base):
    __tablename__ = "external_apis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(30), default="bearer", nullable=False)
    auth_token: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    readonly_mode: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    permissions: Mapped[list[ApiPermission]] = relationship(
        back_populates="api", cascade="all,delete-orphan"
    )


class ApiPermission(Base):
    __tablename__ = "api_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    api_id: Mapped[int] = mapped_column(ForeignKey("external_apis.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path_pattern: Mapped[str] = mapped_column(String(255), nullable=False)
    risk: Mapped[str] = mapped_column(String(20), default="low", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    api: Mapped[ExternalAPI] = relationship(back_populates="permissions")
    grants: Mapped[list[ClientPermission]] = relationship(
        back_populates="permission", cascade="all,delete-orphan"
    )


class InternalClient(Base):
    __tablename__ = "internal_clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    permissions: Mapped[list[ClientPermission]] = relationship(
        back_populates="client", cascade="all,delete-orphan"
    )


class ClientPermission(Base):
    __tablename__ = "client_permissions"
    __table_args__ = (UniqueConstraint("client_id", "permission_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("internal_clients.id"), nullable=False)
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("api_permissions.id"), nullable=False
    )
    allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    client: Mapped[InternalClient] = relationship(back_populates="permissions")
    permission: Mapped[ApiPermission] = relationship(back_populates="grants")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    client_name: Mapped[str] = mapped_column(String(120), nullable=False)
    api_name: Mapped[str] = mapped_column(String(80), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    upstream_status: Mapped[str] = mapped_column(String(20), default="n/a", nullable=False)

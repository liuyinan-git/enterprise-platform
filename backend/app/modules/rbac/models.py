"""RBAC 数据模型：角色 / 权限 / 角色-权限关联。"""

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class RbacRole(Base):
    __tablename__ = "rbac_role"
    __table_args__ = (
        UniqueConstraint("role_code", name="uk_rbac_role_code"),
        UniqueConstraint("external_role_id", name="uk_rbac_external_role_id"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    role_code: Mapped[str] = mapped_column(String(64), nullable=False)
    role_name: Mapped[str] = mapped_column(String(100), nullable=False)
    external_role_id: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(String(500))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"))


class RbacPermission(Base):
    __tablename__ = "rbac_permission"
    __table_args__ = (
        UniqueConstraint("permission_code", name="uk_rbac_permission_code"),
        Index("idx_rbac_permission_module", "module"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    permission_code: Mapped[str] = mapped_column(String(64), nullable=False)
    permission_name: Mapped[str] = mapped_column(String(100), nullable=False)
    module: Mapped[str] = mapped_column(String(32), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class RbacRolePermission(Base):
    __tablename__ = "rbac_role_permission"
    __table_args__ = (
        Index("idx_rbac_role_perm_role", "role_id"),
        {"mysql_engine": "InnoDB"},
    )
    role_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("rbac_role.id"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("rbac_permission.id"), primary_key=True)

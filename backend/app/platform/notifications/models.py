from datetime import datetime

from sqlalchemy import Boolean, String, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class WecomConfig(Base):
    """企业微信自建应用配置（单行 id=1，供通知发送与消息管理页读写）。"""
    __tablename__ = "wecom_config"
    __table_args__ = ({"mysql_engine": "InnoDB"},)
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    corpid: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")
    corpsecret: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")
    agentid: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default="0")
    touser: Mapped[str] = mapped_column(String(500), nullable=False, server_default="")
    notify_min_severity: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"))

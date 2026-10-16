from datetime import datetime

from sqlalchemy import Index, String, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Attachment(Base):
    """附件（文档/表格/图片/视频），存磁盘 + 库内记录文件地址。"""
    __tablename__ = "attachment"
    __table_args__ = (
        Index("idx_attachment_category", "category"),
        Index("idx_attachment_created", "created_at"),
        {"mysql_engine": "InnoDB"},
    )
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    uploader: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(30), nullable=False, server_default="other")
    content_type: Mapped[str] = mapped_column(String(120), nullable=False, server_default="application/octet-stream")
    size: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"))

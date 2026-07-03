"""
SQLAlchemy ORM 模型 —— 单表 diagnoses，存储所有诊断记录和时间线。
使用 PostgreSQL UUID 原生类型和 server_default。
"""

import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Diagnosis(Base):
    """诊断记录表 —— 每条记录对应一次用户提交的 AI 诊断。"""

    __tablename__ = "diagnoses"

    # ---------- 主键 ----------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="诊断记录唯一 ID",
    )

    # ---------- 用户输入 ----------
    user_input: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="用户提交的业务流程描述原文",
    )

    # ---------- AI 原始回复 ----------
    raw_reply: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="DeepSeek API 返回的原始完整文本",
    )

    # ---------- 解析后的三段结果 ----------
    bottleneck: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="低效节点（JSON 字段 node）",
    )
    solution: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="AI 解决方案（JSON 字段 solution）",
    )
    saving: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="预计节省人力（JSON 字段 savings）",
    )

    # ---------- 状态跟踪 ----------
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        comment="任务状态: pending→processing→completed/failed",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="任务失败时的错误详情",
    )

    # ---------- 时间戳 ----------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="记录创建时间",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="任务完成时间",
    )

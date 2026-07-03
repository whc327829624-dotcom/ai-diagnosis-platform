"""
Pydantic 模型 —— 定义 API 请求和响应的数据结构。
FastAPI 自动根据这些模型生成 OpenAPI 文档和参数校验。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================
# 请求体
# ============================================================

class DiagnosisRequest(BaseModel):
    """POST /api/diagnosis 请求体 —— 用户提交的诊断内容。"""

    user_input: str = Field(
        ...,
        min_length=10,
        max_length=10000,
        description="用户提交的业务流程描述，10-10000 字符",
    )


# ============================================================
# 响应体
# ============================================================

class DiagnosisSubmitResponse(BaseModel):
    """POST /api/diagnosis 返回 —— 提交成功，返回任务 ID 供轮询。"""

    task_id: UUID
    status: str = "pending"


class DiagnosisStatusResponse(BaseModel):
    """GET /api/diagnosis/{task_id} 返回 —— 任务状态和结果（完成时附带三段结果）。"""

    task_id: UUID
    status: str
    user_input: str
    bottleneck: str | None = None
    solution: str | None = None
    saving: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


class DiagnosisHistoryItem(BaseModel):
    """历史列表中每条记录的摘要信息。"""

    id: UUID
    user_input_preview: str           # 用户输入的前 80 个字符（截断显示）
    status: str
    bottleneck: str | None = None     # 完成时有值
    created_at: datetime | None = None


class DiagnosisHistoryResponse(BaseModel):
    """GET /api/diagnosis/history 返回 —— 分页历史列表。"""

    items: list[DiagnosisHistoryItem]
    total: int
    page: int
    page_size: int


class ErrorResponse(BaseModel):
    """通用错误响应体。"""

    detail: str

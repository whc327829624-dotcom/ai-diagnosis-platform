"""
测试配置 —— 提供 FastAPI TestClient、Mock 数据库会话、Mock Celery 任务。
所有测试用例共享这些 fixtures。
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.database import get_db
from backend.models import Diagnosis


# ============================================================
# Mock 数据库会话
# ============================================================

@pytest.fixture
def mock_db_session():
    """
    返回一个 AsyncMock 模拟 SQLAlchemy AsyncSession。
    各测试用例在此基础上自定义 execute / commit 的返回值。
    """
    session = AsyncMock()
    # refresh 方法：给对象设置 mock 属性
    async def mock_refresh(obj):
        pass

    session.refresh = mock_refresh
    return session


# ============================================================
# Mock Celery 任务
# ============================================================

@pytest.fixture(autouse=True)
def mock_celery():
    """
    全局 Mock Celery 的 run_diagnosis.delay()，
    避免测试时真的发送 Celery 任务到 Redis。
    """
    with patch("backend.main.run_diagnosis.delay", MagicMock()) as mock_delay:
        yield mock_delay


# ============================================================
# FastAPI Async Test Client
# ============================================================

@pytest.fixture
async def client(mock_db_session):
    """
    创建支持 async 的 FastAPI 测试客户端。
    通过 FastAPI 依赖覆盖机制，将真实数据库替换为 Mock。
    """
    app.dependency_overrides[get_db] = lambda: mock_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ============================================================
# 工具函数：快速创建一个 Mock Diagnosis 对象
# ============================================================

def make_mock_diagnosis(
    diagnosis_id: uuid.UUID | None = None,
    user_input: str = "测试业务流程描述，客服每天处理50+重复咨询...",
    status: str = "pending",
    bottleneck: str | None = None,
    solution: str | None = None,
    saving: str | None = None,
) -> Diagnosis:
    """创建一个 Diagnosis ORM 对象（未绑定到真实数据库），用于 Mock 返回值。"""
    return Diagnosis(
        id=diagnosis_id or uuid.uuid4(),
        user_input=user_input,
        status=status,
        bottleneck=bottleneck,
        solution=solution,
        saving=saving,
        error_message=None,
        created_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc) if status == "completed" else None,
    )

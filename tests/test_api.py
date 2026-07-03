"""
FastAPI 接口测试
===============
测试覆盖：提交诊断、查询状态、完整流程、历史列表、输入校验。
运行: pytest tests/ -v
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.models import Diagnosis
from tests.conftest import make_mock_diagnosis


# ============================================================
# 1. POST /api/diagnosis —— 成功提交诊断
# ============================================================

@pytest.mark.asyncio
async def test_create_diagnosis(client, mock_db_session):
    """验证: 提交合法输入 → 返回 201 + 含 task_id 和 status='pending'"""

    # Arrange: 模拟数据库写入成功
    mock_db_session.commit = AsyncMock()
    mock_db_session.refresh = AsyncMock()

    payload = {
        "user_input": "我们公司每天有50+客户咨询订单状态，客服手动登录ERP逐一查询，每人每天花费3-4小时..."
    }

    # Act
    response = await client.post("/api/diagnosis", json=payload)

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "pending"
    # 验证 task_id 是合法 UUID 格式
    uuid.UUID(data["task_id"])


# ============================================================
# 2. GET /api/diagnosis/{task_id} —— 查询任务状态
# ============================================================

@pytest.mark.asyncio
async def test_get_diagnosis_status_pending(client, mock_db_session):
    """验证: 查询 pending 状态的任务 → 返回 status='pending'"""

    # Arrange: 模拟 DB 查询返回一个 pending 状态的诊断记录
    diagnosis = make_mock_diagnosis(status="pending")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = diagnosis
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Act
    response = await client.get(f"/api/diagnosis/{diagnosis.id}")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == str(diagnosis.id)
    assert data["status"] == "pending"
    assert data["user_input"] == diagnosis.user_input


@pytest.mark.asyncio
async def test_get_diagnosis_status_completed(client, mock_db_session):
    """验证: 查询 completed 状态的任务 → 返回三段结果"""

    # Arrange: 模拟一个已完成的诊断
    diagnosis = make_mock_diagnosis(
        status="completed",
        bottleneck="客服手动查询ERP是核心低效节点，AI可自动完成90%的查询工作",
        solution="接入RAG知识库+AI客服机器人，自动回答订单状态查询",
        saving="预计节省60-75%人力时间",
    )
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = diagnosis
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Act
    response = await client.get(f"/api/diagnosis/{diagnosis.id}")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["bottleneck"] == diagnosis.bottleneck
    assert data["solution"] == diagnosis.solution
    assert data["saving"] == diagnosis.saving


@pytest.mark.asyncio
async def test_get_diagnosis_not_found(client, mock_db_session):
    """验证: 查询不存在的 task_id → 返回 404"""

    # Arrange: DB 查询返回 None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute = AsyncMock(return_value=mock_result)

    # Act
    response = await client.get(f"/api/diagnosis/{uuid.uuid4()}")

    # Assert
    assert response.status_code == 404
    assert "不存在" in response.json()["detail"]


# ============================================================
# 3. GET /api/diagnosis/history —— 历史列表分页
# ============================================================

@pytest.mark.asyncio
async def test_get_history_empty(client, mock_db_session):
    """验证: 无记录时 → 返回空列表，total=0"""

    # Arrange: count 查询返回 0，列表查询返回空
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 0
    mock_list_result = MagicMock()
    mock_list_result.scalars.return_value.all.return_value = []

    # execute 第一次返回 count，第二次返回列表
    mock_db_session.execute = AsyncMock(
        side_effect=[mock_count_result, mock_list_result]
    )

    # Act
    response = await client.get("/api/diagnosis/history")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_get_history_with_data(client, mock_db_session):
    """验证: 有记录时 → 返回分页列表，包含摘要信息"""

    # Arrange: 创建 3 条 mock 记录
    diagnoses = [
        make_mock_diagnosis(
            user_input="问题A: ERP查询慢" + "x" * 80,  # 超 80 字符，触发截断
            status="completed",
            bottleneck="节点A",
        ),
        make_mock_diagnosis(
            user_input="问题B: 合同审批慢",
            status="pending",
        ),
        make_mock_diagnosis(
            user_input="问题C: 数据录入重复",
            status="failed",
        ),
    ]

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = len(diagnoses)
    mock_list_result = MagicMock()
    mock_list_result.scalars.return_value.all.return_value = diagnoses
    mock_db_session.execute = AsyncMock(
        side_effect=[mock_count_result, mock_list_result]
    )

    # Act
    response = await client.get("/api/diagnosis/history?page=1&page_size=10")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3

    # 第一条的 user_input 应被截断（超过 80 字符）
    assert data["items"][0]["user_input_preview"].endswith("...")
    assert data["items"][0]["status"] == "completed"
    # 第二条没有截断
    assert data["items"][1]["user_input_preview"] == "问题B: 合同审批慢"


# ============================================================
# 4. 输入校验
# ============================================================

@pytest.mark.asyncio
async def test_create_diagnosis_too_short(client, mock_db_session):
    """验证: user_input 少于 10 字符 → 返回 422 校验错误"""

    payload = {"user_input": "太短"}

    response = await client.post("/api/diagnosis", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_diagnosis_empty(client, mock_db_session):
    """验证: 空请求体 → 返回 422"""

    response = await client.post("/api/diagnosis", json={})

    assert response.status_code == 422


# ============================================================
# 5. 健康检查
# ============================================================

@pytest.mark.asyncio
async def test_health_check(client):
    """验证: 健康检查接口 → 返回 {'status': 'ok'}"""

    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

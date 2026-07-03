"""
FastAPI 后端主应用 —— 提供 AI 诊断的 RESTful API。
启动: uvicorn backend.main:app --host 0.0.0.0 --port 8000
"""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db, engine, Base
from backend.models import Diagnosis
from backend.schemas import (
    DiagnosisRequest,
    DiagnosisSubmitResponse,
    DiagnosisStatusResponse,
    DiagnosisHistoryItem,
    DiagnosisHistoryResponse,
    ErrorResponse,
)
from backend.tasks import run_diagnosis

# ============================================================
# 应用 lifespan —— 启动时自动创建数据库表
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时创建表，关闭时释放引擎。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


# ============================================================
# FastAPI 应用实例
# ============================================================
app = FastAPI(
    title="AI 企业业务流程诊断工作台",
    description="异步 AI 诊断服务 —— 提交业务流程描述，获取 AI 转型建议",
    version="1.0.0",
    lifespan=lifespan,
)

# ============================================================
# CORS 中间件 —— 允许 Streamlit 前端跨域访问
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],                # 开发环境允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# POST /api/diagnosis —— 提交诊断请求
# ============================================================
@app.post(
    "/api/diagnosis",
    response_model=DiagnosisSubmitResponse,
    status_code=201,
    summary="提交 AI 诊断",
    description="将用户提交的业务流程描述存入数据库，发送 Celery 异步任务，立即返回 task_id。",
)
async def create_diagnosis(
    req: DiagnosisRequest,
    db: AsyncSession = Depends(get_db),
):
    """接收用户输入 → 插入数据库 → 投递 Celery 任务 → 立即返回 task_id"""

    # 1. 插入诊断记录（status = 'pending'）
    diagnosis = Diagnosis(
        id=uuid.uuid4(),
        user_input=req.user_input,
        status="pending",
    )
    db.add(diagnosis)
    await db.commit()
    await db.refresh(diagnosis)

    # 2. 投递 Celery 异步任务（不阻塞响应）
    run_diagnosis.delay(str(diagnosis.id), req.user_input)

    # 3. 立即返回 task_id
    return DiagnosisSubmitResponse(
        task_id=diagnosis.id,
        status="pending",
    )


# ============================================================
# GET /api/diagnosis/history —— 历史诊断列表
# ============================================================
@app.get(
    "/api/diagnosis/history",
    response_model=DiagnosisHistoryResponse,
    summary="获取诊断历史",
    description="分页返回历史诊断记录摘要，按创建时间倒序排列。",
)
async def get_diagnosis_history(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(10, ge=1, le=50, description="每页条数，最大 50"),
    db: AsyncSession = Depends(get_db),
):
    """历史列表 —— 返回每条的 id、输入摘要、状态、创建时间。"""

    # 总数
    total_result = await db.execute(
        select(func.count(Diagnosis.id))
    )
    total = total_result.scalar()

    # 分页查询（按创建时间倒序）
    offset = (page - 1) * page_size
    rows = await db.execute(
        select(Diagnosis)
        .order_by(desc(Diagnosis.created_at))
        .offset(offset)
        .limit(page_size)
    )
    diagnoses = rows.scalars().all()

    # 构造返回
    items = [
        DiagnosisHistoryItem(
            id=d.id,
            user_input_preview=(
                d.user_input[:80] + "..." if len(d.user_input) > 80 else d.user_input
            ),
            status=d.status,
            bottleneck=d.bottleneck[:80] + "..." if d.bottleneck and len(d.bottleneck) > 80 else d.bottleneck,
            created_at=d.created_at,
        )
        for d in diagnoses
    ]

    return DiagnosisHistoryResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# ============================================================
# GET /api/diagnosis/detail/{diagnosis_id} —— 单条详情
# ============================================================
@app.get(
    "/api/diagnosis/detail/{diagnosis_id}",
    response_model=DiagnosisStatusResponse,
    summary="获取诊断详情",
    description="按 ID 获取某条诊断记录的完整信息。",
)
async def get_diagnosis_detail(
    diagnosis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取历史记录详情 —— 返回完整的三段结果。"""

    result = await db.execute(
        select(Diagnosis).where(Diagnosis.id == diagnosis_id)
    )
    diagnosis = result.scalar_one_or_none()

    if not diagnosis:
        raise HTTPException(status_code=404, detail="诊断记录不存在")

    return DiagnosisStatusResponse(
        task_id=diagnosis.id,
        status=diagnosis.status,
        user_input=diagnosis.user_input,
        bottleneck=diagnosis.bottleneck,
        solution=diagnosis.solution,
        saving=diagnosis.saving,
        error_message=diagnosis.error_message,
        created_at=diagnosis.created_at,
        completed_at=diagnosis.completed_at,
    )


# ============================================================
# GET /api/diagnosis/{task_id} —— 查询任务状态
# (注意: 必须放在 /history 和 /detail 之后，否则 "history" 会被当成 UUID)
# ============================================================
@app.get(
    "/api/diagnosis/{task_id}",
    response_model=DiagnosisStatusResponse,
    summary="查询诊断状态",
    description="根据 task_id 查询诊断任务的当前状态。status=completed 时附带三段分析结果。",
)
async def get_diagnosis_status(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """轮询接口 —— 前端每 2 秒调用一次，直到 status 变为 completed 或 failed。"""

    result = await db.execute(
        select(Diagnosis).where(Diagnosis.id == task_id)
    )
    diagnosis = result.scalar_one_or_none()

    if not diagnosis:
        raise HTTPException(status_code=404, detail="诊断记录不存在，请检查 task_id")

    return DiagnosisStatusResponse(
        task_id=diagnosis.id,
        status=diagnosis.status,
        user_input=diagnosis.user_input,
        bottleneck=diagnosis.bottleneck,
        solution=diagnosis.solution,
        saving=diagnosis.saving,
        error_message=diagnosis.error_message,
        created_at=diagnosis.created_at,
        completed_at=diagnosis.completed_at,
    )


# ============================================================
# 健康检查
# ============================================================
@app.get("/api/health", summary="健康检查")
async def health_check():
    """Docker Compose 用此接口判断后端是否就绪。"""
    return {"status": "ok"}

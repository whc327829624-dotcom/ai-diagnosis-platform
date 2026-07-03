"""
Celery 应用实例配置。
Celery Worker 消费 Redis 中的任务队列，异步执行 AI 诊断。
"""

from celery import Celery

from backend.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

# 创建 Celery 实例
celery_app = Celery(
    "ai_diagnosis",
    broker=CELERY_BROKER_URL,          # Redis 作为消息队列
    backend=CELERY_RESULT_BACKEND,     # Redis 作为结果存储（备用）
)

# Celery 配置
celery_app.conf.update(
    # 任务序列化格式
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # 时区
    timezone="Asia/Shanghai",
    enable_utc=True,
    # 任务超时（5 分钟，足够 DeepSeek API 响应）
    task_soft_time_limit=300,
    task_time_limit=360,
    # 结果过期时间（24 小时）
    result_expires=86400,
    # 任务追踪
    task_track_started=True,
    # 自动发现任务模块
    imports=["backend.tasks"],
)

"""
异步数据库连接管理 —— 使用 SQLAlchemy 2.0 async 引擎 + asyncpg 驱动。
FastAPI 路由通过依赖注入获取数据库会话。
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from backend.config import DATABASE_URL

# 异步引擎
engine = create_async_engine(DATABASE_URL, echo=False, pool_size=10, max_overflow=5)

# 异步会话工厂 —— expire_on_commit=False 避免访问已提交对象的属性时报错
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ORM 基类 —— 所有模型继承自 Base
class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入：每次请求创建一个数据库会话，请求结束时自动关闭。"""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()

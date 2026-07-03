"""
应用配置 —— 所有配置通过环境变量注入，Docker Compose 中设置默认值。
"""

import os


# ============================================================
# DeepSeek API 配置
# ============================================================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = os.getenv(
    "DEEPSEEK_API_URL",
    "https://api.deepseek.com/v1/chat/completions",
)
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# ============================================================
# 数据库配置 (PostgreSQL)
# ============================================================
POSTGRES_USER = os.getenv("POSTGRES_USER", "diagnosis")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "diagnosis123")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "diagnosis_db")

# 异步连接串（FastAPI 使用 asyncpg 驱动）
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
)

# 同步连接串（Celery Worker 使用 psycopg2 驱动）
DATABASE_URL_SYNC = os.getenv(
    "DATABASE_URL_SYNC",
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
)

# ============================================================
# Celery / Redis 配置
# ============================================================
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL",
    f"redis://{REDIS_HOST}:{REDIS_PORT}/0",
)
CELERY_RESULT_BACKEND = os.getenv(
    "CELERY_RESULT_BACKEND",
    f"redis://{REDIS_HOST}:{REDIS_PORT}/1",
)

# ============================================================
# AI 系统提示词（强制 JSON 输出）
# ============================================================
SYSTEM_PROMPT = """你是一个资深的企业 AI 转型顾问。请仔细分析用户提交的业务流程。

你必须严格按以下 JSON 格式返回分析结果，不要输出任何其他内容（不要加 markdown 代码块标记，只输出纯 JSON）：

{
  "node": "一句话提炼该流程中最耗时、最容易被AI替代的低效节点",
  "solution": "针对该低效节点的具体AI落地解决方案（例如：接入AI客服、搭建RAG知识库、自动化工作流等）",
  "savings": "采用该方案后预计能为企业节省的百分比人力时间，如'60%-75%'"
}

要求：
- node 字段：必须一针见血，不超过50个字
- solution 字段：必须具体可执行，说明用什么技术、解决什么问题
- savings 字段：必须是一个百分比范围，如 "40%-60%"
- 只输出上述 JSON，禁止输出任何解释性文字或 markdown 格式"""

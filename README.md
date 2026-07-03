```
 █████╗ ██╗    ██████╗ ██╗ █████╗  ██████╗ ███╗   ██╗ ██████╗ ███████╗██╗███████╗
██╔══██╗██║    ██╔══██╗██║██╔══██╗██╔════╝ ████╗  ██║██╔═══██╗██╔════╝██║██╔════╝
███████║██║    ██║  ██║██║███████║██║  ███╗██╔██╗ ██║██║   ██║███████╗██║███████╗
██╔══██║██║    ██║  ██║██║██╔══██║██║   ██║██║╚██╗██║██║   ██║╚════██║██║╚════██║
██║  ██║██║    ██████╔╝██║██║  ██║╚██████╔╝██║ ╚████║╚██████╔╝███████║██║███████║
╚═╝  ╚═╝╚═╝    ╚═════╝ ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝ ╚══════╝╚═╝╚══════╝
                         AI 企业业务流程诊断工作台
```

# 🏭 AI 企业业务流程诊断工作台

基于 **DeepSeek 大模型** 的企业 AI 转型诊断工具，帮助企业识别业务流程中的低效节点，并提供可落地的 AI 解决方案。

## 🎯 核心功能

- 🤖 **AI 诊断**: 输入业务流程痛点，DeepSeek 自动分析并输出结构化 JSON 报告
- 📊 **低效节点识别**: 一句话提炼最耗时、最易被 AI 替代的环节
- 🚀 **落地方案推荐**: RAG 知识库、AI 客服、自动化工作流等具体方案
- 📈 **提效评估**: 预估节省的人力时间百分比
- 📋 **历史记录**: 分页查看所有历史诊断报告

## 🧱 技术架构

```
┌─────────────┐      HTTP       ┌──────────────┐      Redis       ┌─────────────────┐
│  Streamlit   │ ─────────────→ │   FastAPI     │ ───────────────→ │  Celery Worker   │
│  (前端:8501) │ ←───────────── │  (后端:8000)  │                  │  (异步AI调用)     │
└─────────────┘                └──────┬───────┘                  └────────┬────────┘
                                      │                                   │
                                      │ asyncpg                            │ psycopg2
                                      ▼                                   ▼
                               ┌──────────────────────────────────────────────┐
                               │              PostgreSQL 15                    │
                               │           (诊断记录持久化)                      │
                               └──────────────────────────────────────────────┘
```

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **前端** | Streamlit 1.28+ | Python 原生 UI 框架，左右分栏布局 |
| **后端** | FastAPI 0.109+ | RESTful API 设计，async/await 异步 |
| **异步任务** | Celery 5.3 + Redis 7 | 诊断请求异步化，避免请求阻塞 |
| **数据库** | PostgreSQL 15 | 诊断记录持久化，支持分页查询 |
| **ORM** | SQLAlchemy 2.0 (async) | 异步驱动 asyncpg + 同步驱动 psycopg2 |
| **AI 模型** | DeepSeek Chat API | 强制 JSON 输出，结构化解析 |
| **容器化** | Docker + Docker Compose | 5 个服务一键编排 |
| **测试** | pytest + httpx | 9 个测试用例，覆盖全部 API 接口 |

## 📂 项目结构

```
ai_diagnosis_platform/
├── backend/                   # FastAPI 后端
│   ├── main.py                # API 路由（4 个接口 + 健康检查）
│   ├── config.py              # 环境变量配置
│   ├── models.py              # SQLAlchemy ORM 模型
│   ├── schemas.py             # Pydantic 请求/响应模型
│   ├── database.py            # 异步数据库会话管理
│   ├── celery_app.py          # Celery 实例配置
│   └── tasks.py               # 异步 AI 诊断任务（JSON 解析）
├── frontend/                  # Streamlit 前端
│   └── app.py                 # UI 交互 + 卡片展示 + 历史记录
├── tests/                     # 自动化测试
│   ├── conftest.py            # Mock Fixtures
│   └── test_api.py            # 9 个 API 测试用例
├── docker-compose.yml         # 5 服务编排配置
├── Dockerfile.backend         # 后端镜像
├── Dockerfile.frontend        # 前端镜像
├── deploy.py                  # 一键部署脚本（阿里云）
├── requirements.backend.txt   # 后端 Python 依赖
├── requirements.frontend.txt  # 前端 Python 依赖
└── .env.example               # 环境变量模板
```

## 🚀 快速开始

### 本地运行（Docker）

```bash
# 1. 克隆项目
git clone <your-repo-url>
cd ai_diagnosis_platform

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 DeepSeek API Key

# 3. 一键启动
docker compose up -d

# 4. 访问
# 前端: http://localhost:8501
# API 文档: http://localhost:8000/docs
```

### 一键部署到阿里云

```bash
# 前提：拥有一台阿里云 ECS（CentOS/Ubuntu），安全组开放 8501 和 8000 端口
pip install paramiko
python deploy.py
# 输入 root 密码，自动完成：上传 → 装 Docker → 启动服务
```

### API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/diagnosis` | 提交诊断请求，返回 `task_id` |
| `GET` | `/api/diagnosis/{task_id}` | 轮询任务状态和结果 |
| `GET` | `/api/diagnosis/history` | 分页历史记录 |
| `GET` | `/api/diagnosis/detail/{id}` | 单条诊断详情 |
| `GET` | `/api/health` | 健康检查 |

## 🧪 运行测试

```bash
pip install pytest pytest-asyncio httpx
pytest tests/ -v
```

结果：
```
tests/test_api.py::test_create_diagnosis PASSED
tests/test_api.py::test_get_diagnosis_status_pending PASSED
tests/test_api.py::test_get_diagnosis_status_completed PASSED
tests/test_api.py::test_get_diagnosis_not_found PASSED
tests/test_api.py::test_get_history_empty PASSED
tests/test_api.py::test_get_history_with_data PASSED
tests/test_api.py::test_create_diagnosis_too_short PASSED
tests/test_api.py::test_create_diagnosis_empty PASSED
tests/test_api.py::test_health_check PASSED
========================= 9 passed =========================
```

## 📝 License

MIT

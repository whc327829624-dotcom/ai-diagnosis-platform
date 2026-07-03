"""
Celery 异步任务 —— 独立于 FastAPI 请求/响应周期，在 Worker 进程中执行。
包含调用 DeepSeek API 和 JSON 解析的全部逻辑。
"""

import json
from datetime import datetime, timezone

import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from backend.celery_app import celery_app
from backend.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_API_URL,
    DEEPSEEK_MODEL,
    SYSTEM_PROMPT,
    DATABASE_URL_SYNC,
)

# ============================================================
# 同步数据库引擎（Celery Worker 为同步模型，不能使用 async）
# ============================================================
sync_engine = create_engine(DATABASE_URL_SYNC, echo=False, pool_size=5, max_overflow=5)
SyncSession = sessionmaker(bind=sync_engine, class_=Session)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)
def run_diagnosis(self, task_id: str, user_input: str):
    """
    执行 AI 诊断的核心异步任务。

    步骤:
      1. 更新 status → 'processing'
      2. 调用 DeepSeek API 获取 JSON 结果
      3. 用 json.loads 解析三段结构化输出
      4. 更新 status → 'completed'，写入结果
      5. 任何异常 → status → 'failed'，记录错误
    """

    session = SyncSession()

    try:
        # ---- 第 1 步: 标记为处理中 ----
        session.execute(
            text(
                "UPDATE diagnoses SET status = 'processing' "
                "WHERE id = :tid AND status = 'pending'"
            ),
            {"tid": task_id},
        )
        session.commit()

        # ---- 第 2 步: 调用 DeepSeek API ----
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        }
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ],
            "temperature": 0.7,
            "max_tokens": 2048,
            "stream": False,
        }

        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        api_result = response.json()
        ai_reply = api_result["choices"][0]["message"]["content"]

        # ---- 第 3 步: JSON 解析 AI 回复 ----
        # 清洗回复文本：去掉可能的 markdown 代码块标记
        cleaned = ai_reply.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned
            cleaned = cleaned.rsplit("```", 1)[0] if cleaned.endswith("```") else cleaned

        parsed = json.loads(cleaned.strip())

        # 提取三个字段，缺失字段用默认值
        node = parsed.get("node", "未能识别")
        solution = parsed.get("solution", "未能生成方案")
        savings = parsed.get("savings", "暂无法评估")

        # ---- 第 4 步: 写入诊断结果 ----
        session.execute(
            text(
                "UPDATE diagnoses SET "
                "status = 'completed', "
                "raw_reply = :raw, "
                "bottleneck = :bn, "
                "solution = :sol, "
                "saving = :sav, "
                "completed_at = :now "
                "WHERE id = :tid"
            ),
            {
                "raw": ai_reply,
                "bn": node,
                "sol": solution,
                "sav": savings,
                "now": datetime.now(timezone.utc),
                "tid": task_id,
            },
        )
        session.commit()

        return {"task_id": task_id, "status": "completed"}

    except requests.exceptions.Timeout:
        _fail_task(session, task_id, "DeepSeek API 请求超时（60s），请重试")
    except requests.exceptions.HTTPError as e:
        detail = e.response.text[:300] if e.response else str(e)
        code = e.response.status_code if e.response else "?"
        _fail_task(session, task_id, f"API 请求失败 (HTTP {code}): {detail}")
    except json.JSONDecodeError as e:
        _fail_task(session, task_id, f"AI 返回格式解析失败（非合法 JSON）: {str(e)[:200]}")
    except self.MaxRetriesExceededError:
        _fail_task(session, task_id, "任务重试次数已达上限")
    except Exception as e:
        _fail_task(session, task_id, f"未知错误: {str(e)}")
    finally:
        session.close()


def _fail_task(session: Session, task_id: str, error_msg: str):
    """将任务标记为失败并记录错误信息。"""
    session.execute(
        text(
            "UPDATE diagnoses SET "
            "status = 'failed', "
            "error_message = :err, "
            "completed_at = :now "
            "WHERE id = :tid"
        ),
        {
            "err": error_msg,
            "now": datetime.now(timezone.utc),
            "tid": task_id,
        },
    )
    session.commit()

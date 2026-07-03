"""
AI 企业业务流程诊断工作台 —— Streamlit 前端
==============================================
通过 HTTP 调用后端 FastAPI 服务，展示 AI 诊断结果和历史记录。
启动: streamlit run frontend/app.py --server.port 8501
"""

import os
import time

import requests
import streamlit as st

# ============================================================
# 后端 API 地址（Docker Compose 中服务名为 backend）
# ============================================================
BACKEND_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")

# ============================================================
# 页面基础配置
# ============================================================
st.set_page_config(
    page_title="AI 企业业务流程诊断工作台",
    page_icon="🏭",
    layout="wide",
)

# ============================================================
# 自定义 CSS —— 按钮和列表样式（卡片改用原生 Streamlit 组件）
# ============================================================
st.markdown("""
<style>
    .stButton > button {
        background: #4A90D9 !important;
        color: white !important;
        font-weight: 700 !important;
        font-size: 16px !important;
        padding: 10px 32px !important;
        border-radius: 10px !important;
        border: none !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover {
        background: #357ABD !important;
        box-shadow: 0 4px 12px rgba(74, 144, 217, 0.4) !important;
    }
    .history-item {
        padding: 12px 16px;
        border: 1px solid #e0e4e8;
        border-radius: 10px;
        margin-bottom: 8px;
        cursor: pointer;
        transition: background 0.15s;
    }
    .history-item:hover {
        background: #f0f4f8;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 页面标题
# ============================================================
st.title("🏭 AI 企业业务流程诊断工作台")
st.caption("借助 DeepSeek 大模型，快速定位业务瓶颈，获取可落地的 AI 转型方案。")
st.divider()

# ============================================================
# 会话状态初始化
# ============================================================
if "current_task_id" not in st.session_state:
    st.session_state.current_task_id = None       # 当前正在轮询的 task_id
if "polling_status" not in st.session_state:
    st.session_state.polling_status = None        # 轮询得到的最新状态
if "polling_result" not in st.session_state:
    st.session_state.polling_result = None        # 轮询完成的完整结果
if "viewing_history_id" not in st.session_state:
    st.session_state.viewing_history_id = None    # 正在查看的历史记录 ID

# ============================================================
# 双栏布局
# ============================================================
col_left, col_right = st.columns([1, 1], gap="large")

# ==================== 左侧：输入区 ====================
with col_left:
    st.subheader("📝 流程描述")

    user_input = st.text_area(
        label="请描述您的业务流程或痛点",
        placeholder=(
            "请粘贴您目前业务中的一个低效工作流程或痛点\n\n"
            "例如：\n"
            "我们公司每天有50+客户咨询订单状态，客服团队需要手动登录ERP系统逐一查询，"
            "每人每天花费3-4小时重复回答相似问题..."
        ),
        height=300,
        label_visibility="collapsed",
    )

    col_btn1, col_btn2 = st.columns([2, 1])
    with col_btn1:
        start_btn = st.button(
            "🚀 开始 AI 诊断",
            use_container_width=True,
            disabled=(len(user_input.strip()) < 10),
        )
    with col_btn2:
        if st.button("🔄 清除", use_container_width=True):
            st.session_state.current_task_id = None
            st.session_state.polling_status = None
            st.session_state.polling_result = None
            st.session_state.viewing_history_id = None
            st.rerun()

    st.caption(f"已输入 {len(user_input)} 个字符 | 最少 10 字符，建议 30 字以上")

    # ---------- 提交诊断 ----------
    if start_btn:
        try:
            resp = requests.post(
                f"{BACKEND_URL}/api/diagnosis",
                json={"user_input": user_input},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            st.session_state.current_task_id = data["task_id"]
            st.session_state.polling_status = "pending"
            st.session_state.polling_result = None
            st.session_state.viewing_history_id = None
            st.rerun()
        except requests.exceptions.ConnectionError:
            st.error(f"❌ 无法连接后端服务 ({BACKEND_URL})，请确认服务是否已启动。")
        except Exception as e:
            st.error(f"❌ 提交失败: {str(e)}")

    # ---------- 轮询逻辑 ----------
    if st.session_state.current_task_id and st.session_state.polling_status in ("pending", "processing", None):
        task_id = st.session_state.current_task_id

        # 显示等待状态
        status_text = "⏳ 正在排队等待 AI 分析..." if st.session_state.polling_status == "pending" else "🤖 AI 正在分析中..."
        with st.status(status_text, expanded=True) as status_box:
            st.write(f"任务 ID: `{task_id}`")
            st.write("处理完成后将自动展示结果，请勿刷新页面。")

        # 轮询后端
        try:
            resp = requests.get(
                f"{BACKEND_URL}/api/diagnosis/{task_id}",
                timeout=5,
            )
            resp.raise_for_status()
            poll = resp.json()
            st.session_state.polling_status = poll["status"]

            if poll["status"] == "completed":
                st.session_state.polling_result = poll
                st.rerun()
            elif poll["status"] == "failed":
                st.session_state.polling_result = poll
                st.rerun()
            else:
                # 仍在处理中，等待 2 秒后自动刷新
                time.sleep(2)
                st.rerun()
        except requests.exceptions.ConnectionError:
            st.error(f"❌ 轮询后端失败 ({BACKEND_URL})")
            time.sleep(2)

# ==================== 右侧：结果展示区 ====================
with col_right:
    st.subheader("📊 AI 诊断结果")

    # 优先显示轮询结果，其次显示历史详情
    result = st.session_state.polling_result

    # 如果正在查看历史记录且没有当前轮询结果，加载历史详情
    if not result and st.session_state.viewing_history_id:
        try:
            resp = requests.get(
                f"{BACKEND_URL}/api/diagnosis/detail/{st.session_state.viewing_history_id}",
                timeout=5,
            )
            if resp.ok:
                result = resp.json()
        except Exception:
            pass

    if result and result.get("status") == "completed":
        # ---- 三张结果卡片（使用原生 Streamlit 组件） ----
        st.markdown("### 📊 诊断报告")

        # 卡片 1: 低效节点 — st.info 蓝色信息卡
        st.info(
            f"**📉 诊断出的低效节点**\n\n"
            f"{result.get('bottleneck', '未能识别')}",
            icon="📉",
        )

        # 卡片 2: 落地方案 — st.success 绿色成功卡
        st.success(
            f"**🚀 推荐的 AI 落地方案**\n\n"
            f"{result.get('solution', '未能生成方案')}",
            icon="🚀",
        )

        # 卡片 3: 提效数据 — 自定义容器 + st.metric
        with st.container(border=True):
            col_icon, col_data = st.columns([1, 5])
            with col_icon:
                st.markdown("### 📊")
            with col_data:
                saving_value = result.get("saving", "暂无法评估")
                st.markdown("**📊 预估提效数据**")
                st.markdown(
                    f"<span style='font-size: 28px; font-weight: 700; color: #27AE60;'>{saving_value}</span>",
                    unsafe_allow_html=True,
                )
                st.caption("预计可节省的人力时间百分比")

        # 原始回复折叠
        with st.expander("🔍 查看 AI 原始 JSON 回复"):
            st.code(result.get("bottleneck", "") + "\n---\n" +
                    result.get("solution", "") + "\n---\n" +
                    result.get("saving", ""))

    elif result and result.get("status") == "failed":
        # ---- 诊断失败（含 JSON 解析错误等） ----
        err_msg = result.get("error_message", "未知错误")
        st.error(f"❌ 诊断失败")
        st.warning(f"**错误详情：** {err_msg}")
        if st.button("🔄 重新诊断"):
            st.session_state.current_task_id = None
            st.session_state.polling_status = None
            st.session_state.polling_result = None
            st.rerun()

    elif not st.session_state.current_task_id and not st.session_state.viewing_history_id:
        # ---- 初始空白状态 ----
        st.markdown("""
        <div style="text-align: center; padding: 60px 20px; color: #a0aab4;">
            <div style="font-size: 64px; margin-bottom: 16px;">🤖</div>
            <div style="font-size: 16px; font-weight: 500;">
                请在左侧输入业务流程描述，<br>然后点击「开始 AI 诊断」按钮获取分析结果
            </div>
        </div>
        """, unsafe_allow_html=True)

# ============================================================
# 底部：历史诊断记录
# ============================================================
st.divider()
st.subheader("📋 历史诊断记录")

try:
    resp = requests.get(
        f"{BACKEND_URL}/api/diagnosis/history",
        params={"page": 1, "page_size": 20},
        timeout=5,
    )
    if resp.ok:
        history = resp.json()
        items = history.get("items", [])

        if not items:
            st.info("暂无历史诊断记录，提交一次诊断后会自动出现在这里。")
        else:
            # 用列展示历史卡片
            for item in items:
                status_emoji = {
                    "completed": "✅",
                    "failed": "❌",
                    "processing": "⏳",
                    "pending": "🕐",
                }.get(item["status"], "❓")

                with st.container():
                    col_h, col_s = st.columns([5, 1])
                    with col_h:
                        st.markdown(
                            f"**{status_emoji} {item['user_input_preview']}**"
                            f"<br><small>{item.get('created_at', '')[:19] if item.get('created_at') else ''}</small>",
                            unsafe_allow_html=True,
                        )
                    with col_s:
                        if item["status"] == "completed":
                            if st.button("📖 查看", key=f"view_{item['id']}", use_container_width=True):
                                st.session_state.viewing_history_id = item["id"]
                                st.session_state.current_task_id = None
                                st.session_state.polling_result = None
                                st.rerun()
                    st.markdown("---")
    else:
        st.warning("⚠️ 无法连接后端获取历史记录。")
except requests.exceptions.ConnectionError:
    st.warning(f"⚠️ 后端服务 ({BACKEND_URL}) 未连接，历史记录不可用。")

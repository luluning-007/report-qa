"""
app.py —— 年报问答台（网页界面）

本地运行：
    streamlit run app.py

云端部署（Streamlit Community Cloud）：
    API Key 从 Secrets 读取，在网页后台配置
"""

import os

import streamlit as st

# ============================================================
# 【重要】密钥读取 —— 必须在导入 answer 之前执行
#
# 原因：answer.py 在被 import 的那一刻就会执行
#           API_KEY = os.environ.get("DEEPSEEK_API_KEY")
#       如果这时环境变量还没设好，API_KEY 就会是 None。
#
#   本地开发：用环境变量（$env:DEEPSEEK_API_KEY）
#   云端部署：用 Streamlit Secrets（网页后台配置）
# ============================================================
try:
    if "DEEPSEEK_API_KEY" in st.secrets:
        os.environ["DEEPSEEK_API_KEY"] = st.secrets["DEEPSEEK_API_KEY"]
except Exception:
    # 本地没有 secrets.toml 时会抛异常，忽略即可
    pass

# 密钥就位后，再导入业务模块
from answer import answer_question
from retrieve import build_index, load_chunks

# ============================================================
# 页面基础设置（必须是第一个 st 命令）
# ============================================================
st.set_page_config(
    page_title="年报问答台",
    page_icon="📊",
    layout="wide",
)

st.title("📊 年报问答台")
st.caption("从上市公司年报里找答案 —— 每条结论都能追溯到原文页码")

# ============================================================
# 成本防护：限制单次会话的提问次数
#
# 为什么需要：部署后是公开链接，任何人都能用，
#            会消耗你自己的 API 余额。这是一个基本的用量闸门。
# ============================================================
MAX_QUERIES_PER_SESSION = 20

if "query_count" not in st.session_state:
    st.session_state.query_count = 0


# ============================================================
# ⭐ 缓存：索引只加载一次，不要每次交互都重算
# ============================================================
@st.cache_resource
def get_data():
    """加载所有块 + 建立检索索引（只执行一次，结果会被缓存）"""
    chunks = load_chunks()
    bm25 = build_index(chunks)
    return chunks, bm25


chunks, bm25 = get_data()


# ============================================================
# 左侧边栏：显示资料库
# ============================================================
with st.sidebar:
    st.header("📚 资料库")

    # 统计每个文件有多少块
    file_counts = {}
    for c in chunks:
        file_counts[c["file"]] = file_counts.get(c["file"], 0) + 1

    for name, n in file_counts.items():
        st.markdown(f"**📄 {name}**")
        st.caption(f"　共 {n} 个文本块")

    st.divider()
    st.caption(f"索引总量：{len(chunks)} 个块")

    st.divider()
    st.markdown("### 💡 可以这样问")
    st.markdown("""
- 2025年营业收入是多少？
- 毛利率是多少？
- 公司的主要风险有哪些？
- 研发投入占营业收入的比例？
    """)
    st.caption("❌ 不支持：预测未来、投资建议、年报以外的信息")

    st.divider()
    st.caption("⚠️ 当前仅支持文字版 PDF，扫描件需 OCR")

    st.divider()
    remaining = MAX_QUERIES_PER_SESSION - st.session_state.query_count
    st.caption(f"💬 本次会话剩余提问：**{remaining}** 次")
    st.caption("本服务为个人学习项目，请勿滥用")


# ============================================================
# 主区域：提问
# ============================================================
question = st.text_input(
    "输入你的问题",
    placeholder="例如：2025年营业收入是多少？",
)

col1, _ = st.columns([1, 4])
with col1:
    ask = st.button("提问", type="primary", use_container_width=True)

# 示例问题（点一下自动填入）
st.caption("或者试试这些：")
examples = [
    "2025年营业收入是多少？",
    "公司的主要风险因素有哪些？",
    "研发投入占营业收入的比例是多少？",
]
ex_cols = st.columns(len(examples))
for i, ex in enumerate(examples):
    if ex_cols[i].button(ex, key=f"ex_{i}", use_container_width=True):
        question = ex
        ask = True


# ============================================================
# 回答区
# ============================================================
if ask and question:
    # ---------- 成本防护：检查本次会话的提问次数 ----------
    if st.session_state.query_count >= MAX_QUERIES_PER_SESSION:
        st.error(
            f"⚠️ 本次会话提问已达上限（{MAX_QUERIES_PER_SESSION} 次）。\n\n"
            "这是个人学习项目，为避免 API 余额被滥用，设置了会话上限。刷新页面可重置。"
        )
        st.stop()

    st.session_state.query_count += 1

    with st.spinner("正在检索资料并询问 AI..."):
        result = answer_question(question, chunks, bm25, top_k=5)

    st.divider()

    # ---------- 情况 1：资料里没有 ----------
    if result.get("can_answer") is False:
        st.warning("⚠️ 资料中没有找到相关内容")
        st.caption("系统不会编造答案。请换个问法，或确认该信息是否在年报中披露。")

    # ---------- 情况 2：有答案 ----------
    else:
        st.subheader("结论")
        st.write(result.get("answer", "（无）"))

        # 置信度（用颜色区分）
        conf = result.get("confidence", "未提供")
        icon = {"高": "🟢", "中": "🟡", "低": "🔴"}.get(conf, "⚪")
        st.markdown(f"**置信度：** {icon} {conf}")

        # 支撑因素（每条可展开看原文）
        supporting = result.get("supporting", [])
        if supporting:
            st.subheader("支撑因素")
            for s in supporting:
                st.markdown(f"**· {s.get('point')}**")
                title = f"📄 {s.get('file')}　第 {s.get('page')} 页"
                with st.expander(title):
                    matched = [
                        ch["text"]
                        for ch in chunks
                        if ch["file"] == s.get("file") and ch["page"] == s.get("page")
                    ]
                    if matched:
                        st.text(matched[0][:800])
                    else:
                        st.caption("（未找到对应原文）")

        # 待核实 / 风险
        risks = result.get("risks", [])
        if risks:
            st.subheader("待核实 / 风险")
            for r in risks:
                st.warning(r)

    # ---------- 底部：成本信息 ----------
    tokens = result.get("_tokens", {})
    if tokens:
        st.caption(
            f"本次消耗 token：输入 {tokens.get('输入')} / 输出 {tokens.get('输出')}"
        )

elif ask and not question:
    st.info("请先输入一个问题")

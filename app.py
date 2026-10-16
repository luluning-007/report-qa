"""
app.py —— 年报问答台（网页界面）

运行方式：
    streamlit run app.py

浏览器会自动打开，一般是 http://localhost:8501
"""

import streamlit as st

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
    with st.spinner("正在检索资料并询问 AI..."):
        result = answer_question(question, chunks, bm25, top_k=5)

    st.divider()

    # ---------- 情况 1：资料里没有 ----------
    if result.get("can_answer") is False:
        st.warning("⚠️ 资料中没有找到相关内容")
        st.caption("系统不会编造答案。请换个问法，或确认该信息是否在年报中披露。")

    # ---------- 情况 2：有答案 ----------
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

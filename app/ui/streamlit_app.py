import hmac
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# 输入边界：文件最大 5MB，简历正文最多分析前 15000 字
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_CHARS = 15000

# 云端部署时，Streamlit Secrets 不会自动变成环境变量，这里手动搬运一次
# （只做搬运，绝不打印或展示 Key 的内容）
try:
    _secrets = dict(st.secrets)
except Exception:
    _secrets = {}

for _secret_key in ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL", "ACCESS_CODE"):
    if _secret_key in _secrets:
        os.environ[_secret_key] = str(_secrets[_secret_key])

from app import config
from app.core.exporter import build_docx, build_pdf
from app.core.job_profile import load_profiles, match_direction, search_url
from app.core.llm import analyze_resume
from app.core.parser import parse_resume

st.set_page_config(page_title="简历助手 jl", layout="wide")
st.title("简历助手 jl")
st.caption("上传简历 → AI 给出针对性修改意见 → 导出 Word / PDF")

# 访问口令：只有设置了 ACCESS_CODE 才生效，本地不设则完全跳过
_access_code = os.getenv("ACCESS_CODE", "").strip()
if _access_code and not st.session_state.get("_authed"):
    _input_code = st.text_input("访问口令", type="password")
    if not _input_code:
        # 没输入口令时停在当前页，不渲染后面的上传界面
        st.stop()
    if hmac.compare_digest(_input_code.encode("utf-8"), _access_code.encode("utf-8")):
        st.session_state["_authed"] = True
        st.rerun()
    else:
        st.error("访问口令不正确")
        st.stop()

# 方向标准加载失败时直接报错，不静默跳过
try:
    profiles = load_profiles()
except Exception as exc:
    st.error(f"方向配置加载失败：{exc}")
    st.stop()

LEVEL_LABELS = {
    "have": "✅ 已具备",
    "partial": "⚠️ 部分具备",
    "missing": "❌ 缺失",
    "unknown": "❓ 未体现",
}


def render_analysis(analysis):
    score = analysis.get("score")
    if score is not None:
        st.metric("综合评分", f"{score} / 100")
    match_score = analysis.get("match_score")
    if match_score is not None:
        st.metric("JD 匹配度", f"{match_score} / 100")
    if analysis.get("overall"):
        st.subheader("总体评价")
        st.write(analysis["overall"])

    jd_hits = analysis.get("jd_hits") or []
    jd_gaps = analysis.get("jd_gaps") or []
    if jd_hits or jd_gaps:
        hit_col, gap_col = st.columns(2)
        with hit_col:
            st.subheader("已命中要求")
            for item in jd_hits:
                st.markdown(f"- {item}")
        with gap_col:
            st.subheader("缺失要求")
            for item in jd_gaps:
                st.markdown(f"- {item}")

    suggestions = analysis.get("suggestions") or []
    if suggestions:
        st.subheader("逐条修改意见")
        for i, item in enumerate(suggestions, 1):
            with st.expander(f"{i}. {item.get('section', '')}", expanded=(i == 1)):
                if item.get("problem"):
                    st.markdown(f"**问题：** {item['problem']}")
                if item.get("evidence"):
                    st.caption(f"原文依据：{item['evidence']}")
                if item.get("advice"):
                    st.markdown(f"**建议：** {item['advice']}")
                if item.get("rewrite"):
                    st.success(f"改写示例：{item['rewrite']}")
    if analysis.get("keywords_missing"):
        st.subheader("缺失关键词")
        st.write("、".join(str(k) for k in analysis["keywords_missing"]))
    if analysis.get("next_steps"):
        st.subheader("下一步优先做")
        for step in analysis["next_steps"]:
            st.markdown(f"- {step}")


def render_direction(result, profile):
    st.subheader(f"方向诊断：{profile.get('name', '')}")
    if result.get("summary"):
        st.write(result["summary"])

    rows = []
    for row in result.get("table", []):
        rows.append(
            {
                "要求": row.get("item", ""),
                "状态": LEVEL_LABELS.get(row.get("level"), LEVEL_LABELS["unknown"]),
                "依据": row.get("evidence", ""),
                "说明": row.get("note", ""),
            }
        )
    st.table(rows)
    st.caption("以上为行业通用要求，具体岗位以 JD 为准")

    missing_rows = [
        row for row in result.get("table", []) if "模型未返回" in row.get("note", "")
    ]
    if missing_rows:
        with st.expander("为什么有些是未体现？"):
            debug = result.get("_debug") or {}
            st.write("模型返回的原始 JSON（截断 800 字）：")
            st.text(debug.get("raw", ""))
            st.write(f"命中的序号：{debug.get('matched_indexes', [])}")

    priorities = result.get("priorities") or []
    if priorities:
        st.subheader("优先补什么")
        for entry in priorities:
            st.markdown(f"**{entry.get('item', '')}**")
            st.markdown(f"- 为什么：{entry.get('reason', '')}")
            st.markdown(f"- 怎么补：{entry.get('how', '')}")

    keywords = profile.get("search_keywords") or []
    if keywords:
        st.link_button("去 BOSS 看这类岗位", search_url(keywords[0]))


with st.sidebar:
    st.header("当前配置")
    st.write(f"模型：`{config.MODEL}`")
    st.write(f"接口地址：`{config.BASE_URL}`")
    if not config.API_KEY:
        st.warning("未检测到 API Key，请在 .env 或平台 Secrets 里填写 DEEPSEEK_API_KEY")

uploaded = st.file_uploader("上传简历（.docx 或 .pdf）", type=["docx", "pdf"])

if not uploaded:
    st.info("先上传一份简历开始。")
    st.stop()

# 先卡文件大小，避免超大文件把解析撑爆
if uploaded.size > MAX_UPLOAD_BYTES:
    st.error("文件超过 5MB，请压缩后重试")
    st.stop()

# 上传文件放进临时目录，解析完就自动删除，云端不留下任何简历文件
try:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / Path(uploaded.name).name
        tmp_path.write_bytes(uploaded.getbuffer())
        parsed = parse_resume(tmp_path)
except Exception as exc:
    st.error(f"解析失败：{exc}")
    st.stop()

for warning in parsed.get("warnings", []):
    st.warning(warning)

# 文本太短直接中止：拿空文本让模型分析，只会得到凭空编造的建议
if len(parsed["raw_text"].strip()) < config.MIN_TEXT_CHARS:
    page_count = parsed.get("page_count")
    st.error("没能从这份文件里提取到可用文字，已停止分析，避免模型凭空编造。")
    st.markdown(
        f"""
**诊断信息**

- 页数：{page_count if page_count is not None else "未知（.docx 没有页数概念）"}
- 提取字符数：{parsed['char_count']}
- 检测到图片：{parsed.get('image_count', 0)} 张

**可能原因**

1. 扫描件（图片型 PDF）
2. 文字转曲（设计软件导出，文字被转成矢量轮廓）
3. 加密或权限限制

**建议**：用 Word 打开后另存为 PDF 再上传，或直接上传 .docx。
"""
    )
    st.stop()

left, right = st.columns([1, 1])
with left:
    st.subheader("解析结果")
    st.caption(f"文件：{parsed['filename']}　字符数：{parsed['char_count']}")
    st.text_area("简历原文", parsed["raw_text"], height=420, disabled=True)
with right:
    st.subheader("补充信息")

    direction_keys = list(profiles.keys())
    direction_names = [profiles[key]["name"] for key in direction_keys]
    selected_name = st.selectbox("想去的方向", ["不选方向"] + direction_names)
    selected_direction = None
    if selected_name in direction_names:
        selected_direction = direction_keys[direction_names.index(selected_name)]

    target_job = st.text_input("目标岗位", placeholder="例如：通信算法工程师 / 后端开发 / 产品经理")
    jd_input = st.text_area(
        "岗位 JD（可选，粘贴招聘信息全文）",
        placeholder="把招聘信息里的岗位职责、任职要求整段粘贴进来",
        height=220,
    )
    background = st.text_area(
        "你的背景 / 想做什么职业",
        placeholder="例如：通信工程大三，做过单片机项目，在中国移动实习，想进入通信行业做研发",
        height=200,
    )

    tab_direction, tab_jd = st.tabs(["方向诊断", "JD 精筛"])

    with tab_direction:
        if st.button("诊断这个方向", type="primary", disabled=(not selected_direction)):
            if not selected_direction:
                st.warning("先在上方选择一个方向")
            elif not config.API_KEY:
                st.error("缺少 API Key，无法调用模型。请在 .env 或 Secrets 中填写后重启。")
            else:
                direction_text = parsed["raw_text"]
                if len(direction_text) > MAX_CHARS:
                    direction_text = direction_text[:MAX_CHARS]
                    st.warning("简历较长，仅分析前 15000 字")
                with st.spinner("AI 正在诊断方向..."):
                    st.session_state["direction_result"] = match_direction(
                        direction_text,
                        selected_direction,
                        profiles[selected_direction],
                        background,
                    )
                    st.session_state["direction_key"] = selected_direction
                    # 两块结果互斥：只显示最近一次操作的那一块
                    st.session_state["active_view"] = "direction"

    with tab_jd:
        if st.button("生成修改意见", type="primary"):
            if not config.API_KEY:
                st.error("缺少 API Key，无法调用模型。请在 .env 或 Secrets 中填写后重启。")
            else:
                # 简历太长时只分析前 15000 字，控制 token 消耗
                raw_text = parsed["raw_text"]
                if len(raw_text) > MAX_CHARS:
                    raw_text = raw_text[:MAX_CHARS]
                    st.warning("简历较长，仅分析前 15000 字")
                # JD 超过上限时截断，避免 prompt 过长
                jd_text, jd_truncated = config.prepare_jd(jd_input)
                if jd_truncated:
                    st.warning("JD 较长，仅比对前 3000 字")
                with st.spinner("AI 正在分析简历..."):
                    st.session_state["analysis"] = analyze_resume(
                        raw_text, target_job, background, jd_text
                    )
                    st.session_state["source_name"] = parsed["filename"]
                    st.session_state["jd_used"] = bool(jd_text)
                    # 两块结果互斥：只显示最近一次操作的那一块
                    st.session_state["active_view"] = "jd"

active_view = st.session_state.get("active_view")

direction_result = st.session_state.get("direction_result")
if active_view == "direction" and direction_result:
    st.divider()
    if "error" in direction_result:
        # 模型出错和简历没写要彻底分开：这里只报错，绝不渲染“未体现”表格
        st.error(direction_result["error"])
        error_debug = direction_result.get("debug") or {}
        if error_debug:
            with st.expander("查看模型原始返回（调试）"):
                st.write(f"问题：{error_debug.get('problems', [])}")
                st.text(error_debug.get("raw", ""))
    else:
        direction_profile = profiles.get(st.session_state.get("direction_key", ""))
        if direction_profile:
            render_direction(direction_result, direction_profile)

analysis = st.session_state.get("analysis")
if active_view == "jd" and analysis:
    st.divider()
    if st.session_state.get("jd_used"):
        st.caption("本次分析基于岗位 JD")
    if "error" in analysis:
        # 模型或解析出错时只展示错误，不渲染残缺结果
        st.error(analysis["error"])
    else:
        render_analysis(analysis)

        st.divider()
        st.subheader("导出")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 直接生成字节流，不写入 data/outputs，适配云端临时文件系统
        docx_bytes = build_docx(analysis, st.session_state.get("source_name", ""))
        pdf_bytes = build_pdf(analysis, st.session_state.get("source_name", ""))

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "下载 Word",
                data=docx_bytes,
                file_name=f"简历修改建议_{stamp}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        with col2:
            st.download_button(
                "下载 PDF",
                data=pdf_bytes,
                file_name=f"简历修改建议_{stamp}.pdf",
                mime="application/pdf",
            )
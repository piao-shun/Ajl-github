import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# 云端部署时，Streamlit Secrets 不会自动变成环境变量，这里手动搬运一次
# （只做搬运，绝不打印或展示 Key 的内容）
try:
    _secrets = dict(st.secrets)
except Exception:
    _secrets = {}

for _secret_key in ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL"):
    if _secret_key in _secrets:
        os.environ[_secret_key] = str(_secrets[_secret_key])

from app import config
from app.core.exporter import build_docx, build_pdf
from app.core.llm import analyze_resume
from app.core.parser import parse_resume

st.set_page_config(page_title="简历助手 jl", layout="wide")
st.title("简历助手 jl")
st.caption("上传简历 → AI 给出针对性修改意见 → 导出 Word / PDF")


def render_analysis(analysis):
    score = analysis.get("score")
    if score is not None:
        st.metric("综合评分", f"{score} / 100")
    if analysis.get("overall"):
        st.subheader("总体评价")
        st.write(analysis["overall"])
    suggestions = analysis.get("suggestions") or []
    if suggestions:
        st.subheader("逐条修改意见")
        for i, item in enumerate(suggestions, 1):
            with st.expander(f"{i}. {item.get('section', '')}", expanded=(i == 1)):
                if item.get("problem"):
                    st.markdown(f"**问题：** {item['problem']}")
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

left, right = st.columns([1, 1])
with left:
    st.subheader("解析结果")
    st.caption(f"文件：{parsed['filename']}　字符数：{parsed['char_count']}")
    st.text_area("简历原文", parsed["raw_text"], height=420, disabled=True)
with right:
    st.subheader("补充信息")
    target_job = st.text_input("目标岗位", placeholder="例如：通信算法工程师 / 后端开发 / 产品经理")
    background = st.text_area(
        "你的背景 / 想做什么职业",
        placeholder="例如：通信工程大三，做过单片机项目，在中国移动实习，想进入通信行业做研发",
        height=200,
    )
    if st.button("生成修改意见", type="primary"):
        if not config.API_KEY:
            st.error("缺少 API Key，无法调用模型。请在 .env 或 Secrets 中填写后重启。")
        else:
            with st.spinner("AI 正在分析简历..."):
                st.session_state["analysis"] = analyze_resume(
                    parsed["raw_text"], target_job, background
                )
                st.session_state["source_name"] = parsed["filename"]

analysis = st.session_state.get("analysis")
if analysis:
    st.divider()
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
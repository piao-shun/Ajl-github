from io import BytesIO
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

FONT_CN = "微软雅黑"


def _style_run(run, size=11, bold=False, color=None):
    # 设置中文字体，eastAsia 决定 Word 里中文字符用哪个字体
    run.font.name = FONT_CN
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), FONT_CN)


def _add_para(doc, text, size=11, bold=False, color=None, space_after=4):
    p = doc.add_paragraph()
    run = p.add_run(text)
    _style_run(run, size=size, bold=bold, color=color)
    p.paragraph_format.space_after = Pt(space_after)
    return p


def build_docx(analysis, source_name=""):
    # 在内存里生成 Word，返回字节，不写磁盘
    doc = Document()
    _add_para(doc, "简历修改建议", size=18, bold=True, space_after=8)
    if source_name:
        _add_para(doc, f"来源文件：{source_name}", size=9, color=(120, 120, 120))

    score = analysis.get("score")
    if score is not None:
        _add_para(doc, f"综合评分：{score}", size=13, bold=True, color=(192, 80, 77))

    if analysis.get("overall"):
        _add_para(doc, "总体评价", size=13, bold=True)
        _add_para(doc, analysis["overall"])

    suggestions = analysis.get("suggestions") or []
    if suggestions:
        _add_para(doc, "逐条修改意见", size=13, bold=True)
        for i, item in enumerate(suggestions, 1):
            _add_para(doc, f"{i}. {item.get('section', '')}", size=11, bold=True)
            if item.get("problem"):
                _add_para(doc, f"问题：{item['problem']}")
            if item.get("advice"):
                _add_para(doc, f"建议：{item['advice']}")
            if item.get("rewrite"):
                _add_para(doc, f"改写示例：{item['rewrite']}", color=(60, 110, 60))

    keywords = analysis.get("keywords_missing") or []
    if keywords:
        _add_para(doc, "缺失关键词", size=13, bold=True)
        _add_para(doc, "、".join(str(k) for k in keywords))

    steps = analysis.get("next_steps") or []
    if steps:
        _add_para(doc, "下一步优先做", size=13, bold=True)
        for step in steps:
            _add_para(doc, f"- {step}")

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def _esc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_pdf(analysis, source_name=""):
    # 在内存里生成 PDF，返回字节，不写磁盘
    styles = {
        "title": ParagraphStyle("title", fontName="STSong-Light", fontSize=18, leading=24, spaceAfter=8),
        "h": ParagraphStyle("h", fontName="STSong-Light", fontSize=13, leading=20, spaceBefore=10, spaceAfter=4),
        "body": ParagraphStyle("body", fontName="STSong-Light", fontSize=10.5, leading=16, spaceAfter=3),
        "small": ParagraphStyle("small", fontName="STSong-Light", fontSize=9, textColor="#777777", spaceAfter=4),
    }
    story = [Paragraph("简历修改建议", styles["title"])]
    if source_name:
        story.append(Paragraph(f"来源文件：{_esc(source_name)}", styles["small"]))
    score = analysis.get("score")
    if score is not None:
        story.append(Paragraph(f"综合评分：{score}", styles["h"]))
    if analysis.get("overall"):
        story.append(Paragraph("总体评价", styles["h"]))
        story.append(Paragraph(_esc(analysis["overall"]), styles["body"]))
    for i, item in enumerate(analysis.get("suggestions") or [], 1):
        story.append(Paragraph(f"{i}. {_esc(item.get('section', ''))}", styles["h"]))
        if item.get("problem"):
            story.append(Paragraph(f"问题：{_esc(item['problem'])}", styles["body"]))
        if item.get("advice"):
            story.append(Paragraph(f"建议：{_esc(item['advice'])}", styles["body"]))
        if item.get("rewrite"):
            story.append(Paragraph(f"改写示例：{_esc(item['rewrite'])}", styles["body"]))
    if analysis.get("keywords_missing"):
        story.append(Paragraph("缺失关键词", styles["h"]))
        story.append(Paragraph(_esc("、".join(str(k) for k in analysis["keywords_missing"])), styles["body"]))
    if analysis.get("next_steps"):
        story.append(Paragraph("下一步优先做", styles["h"]))
        for step in analysis["next_steps"]:
            story.append(Paragraph(f"- {_esc(step)}", styles["body"]))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    doc.build(story)
    return buffer.getvalue()


def export_docx(analysis, out_path, source_name=""):
    # 保留写文件版本，供本地脚本或 FastAPI 调用
    out_path = Path(out_path)
    out_path.write_bytes(build_docx(analysis, source_name))
    return out_path


def export_pdf(analysis, out_path, source_name=""):
    out_path = Path(out_path)
    out_path.write_bytes(build_pdf(analysis, source_name))
    return out_path
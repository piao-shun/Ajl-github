import tempfile
from pathlib import Path

from docx import Document
from reportlab.pdfgen import canvas

from app.core.exporter import build_docx, build_pdf
from app.core.parser import parse_resume

SAMPLE_ANALYSIS = {
    "score": 72,
    "overall": "整体结构清晰，但缺少量化成果。",
    "suggestions": [
        {
            "section": "实习经历",
            "problem": "描述太笼统",
            "advice": "补充数据和结果",
            "rewrite": "覆盖 30 个基站，掉话率下降 15%。",
        }
    ],
    "keywords_missing": ["5G", "LTE"],
    "next_steps": ["补充量化", "突出技能", "按岗位定制"],
}


def make_docx(path):
    doc = Document()
    doc.add_paragraph("张三")
    doc.add_paragraph("教育背景")
    doc.add_paragraph("某大学 通信工程 本科")
    doc.save(str(path))


def make_pdf(path):
    pdf = canvas.Canvas(str(path))
    pdf.drawString(72, 720, "Zhang San")
    pdf.drawString(72, 700, "Education: Some University")
    pdf.save()


with tempfile.TemporaryDirectory() as tmp:
    docx_path = Path(tmp) / "sample.docx"
    make_docx(docx_path)
    parsed = parse_resume(docx_path)
    assert parsed["kind"] == "docx"
    assert parsed["char_count"] > 0
    assert "张三" in parsed["raw_text"]
    print("PASS docx_parse", parsed["char_count"])

    pdf_path = Path(tmp) / "sample.pdf"
    make_pdf(pdf_path)
    parsed = parse_resume(pdf_path)
    assert parsed["kind"] == "pdf"
    assert parsed["char_count"] > 0
    assert "Zhang" in parsed["raw_text"]
    print("PASS pdf_parse", parsed["char_count"])

docx_bytes = build_docx(SAMPLE_ANALYSIS, "sample.docx")
assert len(docx_bytes) > 1000
assert docx_bytes[:2] == b"PK"
print("PASS docx_export", len(docx_bytes))

pdf_bytes = build_pdf(SAMPLE_ANALYSIS, "sample.docx")
assert len(pdf_bytes) > 1000
assert pdf_bytes[:5] == b"%PDF-"
print("PASS pdf_export", len(pdf_bytes))

print("ALL_TESTS_PASS")
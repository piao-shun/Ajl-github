import tempfile
from pathlib import Path

from docx import Document
from reportlab.pdfgen import canvas

from app.core.parser import parse_resume


def _make_docx(path):
    doc = Document()
    doc.add_paragraph("张三")
    doc.add_paragraph("教育背景")
    doc.add_paragraph("某大学 通信工程 本科")
    doc.save(str(path))


def _make_pdf(path):
    pdf = canvas.Canvas(str(path))
    pdf.drawString(72, 720, "Zhang San")
    pdf.drawString(72, 700, "Education: Some University")
    pdf.save()


def test_parse_docx_returns_text():
    with tempfile.TemporaryDirectory() as tmp:
        file_path = Path(tmp) / "sample.docx"
        _make_docx(file_path)
        result = parse_resume(file_path)

    assert result["kind"] == "docx"
    assert result["char_count"] > 0
    assert "张三" in result["raw_text"]
    assert result["page_count"] is None
    assert result["image_count"] == 0


def test_parse_pdf_returns_text():
    with tempfile.TemporaryDirectory() as tmp:
        file_path = Path(tmp) / "sample.pdf"
        _make_pdf(file_path)
        result = parse_resume(file_path)

    assert result["kind"] == "pdf"
    assert result["char_count"] > 0
    assert "Zhang" in result["raw_text"]
    assert result["page_count"] == 1
    assert result["image_count"] == 0
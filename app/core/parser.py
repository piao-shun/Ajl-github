from pathlib import Path

import pdfplumber
from docx import Document

SECTION_HINTS = (
    "教育", "学历", "实习", "工作", "项目", "科研", "技能", "荣誉", "获奖",
    "证书", "自我评价", "个人", "校园", "实践", "经历", "培训",
)


def _is_heading(line: str) -> bool:
    text = line.strip()
    if not text or len(text) > 24:
        return False
    if text[-1] in "。.;；,，:：":
        return False
    return any(hint in text for hint in SECTION_HINTS)


def _split_sections(lines):
    sections = []
    current_title = "基本信息"
    current = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if _is_heading(line):
            if current:
                sections.append({"title": current_title, "content": "\n".join(current)})
            current_title = line
            current = []
        else:
            current.append(line)
    if current:
        sections.append({"title": current_title, "content": "\n".join(current)})
    return sections


def _read_docx(path: Path):
    doc = Document(str(path))
    lines = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                lines.append(" | ".join(cells))
    return lines


def _read_pdf(path: Path):
    lines = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines.extend(text.splitlines())
    return lines


def parse_resume(path):
    path = Path(path)
    suffix = path.suffix.lower()
    warnings = []

    if suffix == ".docx":
        lines = _read_docx(path)
    elif suffix == ".pdf":
        lines = _read_pdf(path)
    elif suffix == ".doc":
        raise ValueError("旧版 .doc 暂不支持，请用 Word 另存为 .docx 后再上传")
    else:
        raise ValueError(f"不支持的文件类型：{suffix}")

    raw_text = "\n".join(line for line in (l.strip() for l in lines) if line)
    if not raw_text.strip():
        warnings.append("没有解析到文字，可能是扫描版 PDF（图片），需要 OCR 才能读取")

    return {
        "filename": path.name,
        "kind": suffix.lstrip("."),
        "raw_text": raw_text,
        "sections": _split_sections(lines),
        "char_count": len(raw_text),
        "warnings": warnings,
    }
from app.core.exporter import build_docx, build_pdf

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


def test_build_docx_returns_valid_file():
    data = build_docx(SAMPLE_ANALYSIS, "sample.docx")

    assert len(data) > 1000
    # docx 本质是 zip 包，文件头一定是 PK
    assert data[:2] == b"PK"


def test_build_pdf_returns_valid_file():
    data = build_pdf(SAMPLE_ANALYSIS, "sample.docx")

    assert len(data) > 1000
    assert data[:5] == b"%PDF-"
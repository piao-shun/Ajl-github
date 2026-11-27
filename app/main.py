from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import config
from app.core.exporter import export_docx, export_pdf
from app.core.llm import analyze_resume
from app.core.parser import parse_resume

app = FastAPI(title="简历助手 jl")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeIn(BaseModel):
    raw_text: str
    target_job: str = ""
    background: str = ""


class ExportIn(BaseModel):
    analysis: dict
    source_name: str = ""
    fmt: str = "docx"


@app.get("/api/health")
def health():
    return {"status": "ok", "model": config.MODEL, "has_key": bool(config.API_KEY)}


@app.post("/api/parse")
async def api_parse(file: UploadFile = File(...)):
    filename = Path(file.filename).name
    dest = config.UPLOAD_DIR / filename
    dest.write_bytes(await file.read())
    return parse_resume(dest)


@app.post("/api/analyze")
def api_analyze(payload: AnalyzeIn):
    return analyze_resume(payload.raw_text, payload.target_job, payload.background)


@app.post("/api/export")
def api_export(payload: ExportIn):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fmt = "pdf" if payload.fmt.lower() == "pdf" else "docx"
    out_path = config.OUTPUT_DIR / f"简历修改建议_{stamp}.{fmt}"
    if fmt == "pdf":
        export_pdf(payload.analysis, out_path, payload.source_name)
    else:
        export_docx(payload.analysis, out_path, payload.source_name)
    return {"path": str(out_path)}
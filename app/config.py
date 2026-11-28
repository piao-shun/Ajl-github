import hashlib
import os
from pathlib import Path

from dotenv import load_dotenv

# 项目根目录：以本文件位置为准往上推，不依赖"当前工作目录"
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"

for _dir in (UPLOAD_DIR, OUTPUT_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# 本地开发时从 .env 读；云端由平台把 Secrets 注入成环境变量
load_dotenv(BASE_DIR / ".env")

# 优先读 DEEPSEEK_ 前缀的变量（部署用），同时兼容本地旧的 API_KEY 写法
API_KEY = (os.getenv("DEEPSEEK_API_KEY") or os.getenv("API_KEY") or "").strip()
BASE_URL = (
    os.getenv("DEEPSEEK_BASE_URL")
    or os.getenv("BASE_URL")
    or "https://api.deepseek.com/v1"
).strip()
MODEL = (os.getenv("DEEPSEEK_MODEL") or os.getenv("MODEL") or "deepseek-chat").strip()
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))

# 文本少于这个字符数就认定没有有效内容，直接中止，不调用模型
MIN_TEXT_CHARS = 50

# 岗位 JD 最多比对前 3000 字
JD_MAX_CHARS = 3000

# 方向诊断时，用户背景最多传 200 字
DIRECTION_BG_MAX_CHARS = 200

# 换文件时需要清空的结果缓存 key；清空必须发生在渲染结果之前
RESULT_STATE_KEYS = (
    "analysis",
    "direction_result",
    "active_view",
    "jd_used",
    "jd_fingerprint",
    "source_name",
    "direction_key",
)


def prepare_jd(jd_text, max_chars=JD_MAX_CHARS):
    # 去掉首尾空白；超长则截断，并告诉调用方是否发生过截断
    text = (jd_text or "").strip()
    if len(text) > max_chars:
        return text[:max_chars], True
    return text, False


def should_reset_session(previous_file_id, new_file_id):
    # 首次上传（还没有旧 file_id）不算“换文件”，不清空
    if previous_file_id is None:
        return False
    return previous_file_id != new_file_id


def clear_result_state(state):
    # 只清结果缓存，其它 key（如访问口令态）不动
    for key in RESULT_STATE_KEYS:
        state.pop(key, None)


def jd_fingerprint(text):
    # 用内容指纹（md5 前 8 位）代替布尔值，才能发现“JD 改了但没重新分析”
    text = (text or "").strip()
    if not text:
        return ""
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:8]


def jd_changed(stored_fingerprint, current_text):
    # 没存过指纹（还没用 JD 分析过）不算“已修改”
    stored = (stored_fingerprint or "").strip()
    if not stored:
        return False
    return stored != jd_fingerprint(current_text)
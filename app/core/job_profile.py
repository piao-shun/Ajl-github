import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote

from app import config
from app.core.llm import _safe_json, chat
from app.core.prompts import DIRECTION_SYSTEM_PROMPT, build_direction_prompt

PROFILES_PATH = config.DATA_DIR / "job_profiles.json"

REQUIRED_FIELDS = ("name", "aliases", "core", "bonus", "search_keywords")
VALID_LEVELS = ("have", "partial", "missing", "unknown")
ITEM_KEYS = ("item", "要求", "name")


def _normalize_text(text):
    # 全角转半角、去掉空白和标点、统一小写，用于模糊对齐
    # 只保留字母数字和 + #：C++、C# 与 C 是不同条目，不能把 + 和 # 抹掉
    text = unicodedata.normalize("NFKC", str(text or ""))
    text = re.sub(r"[^\w+#]+", "", text)
    return text.lower()


def _row_item(row):
    # 模型可能用 item / 要求 / name 三种 key，依次取第一个非空值
    for key in ITEM_KEYS:
        if row.get(key):
            return str(row[key])
    return ""


def load_profiles(path=None):
    path = Path(path) if path else PROFILES_PATH
    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict) or not data:
        raise ValueError("job_profiles.json 必须是非空对象")

    normalized = {}
    for direction, profile in data.items():
        if not isinstance(profile, dict):
            raise ValueError(f"{direction} 配置必须是对象")
        for field in REQUIRED_FIELDS:
            if field not in profile:
                raise ValueError(f"{direction} 缺少字段：{field}")
        core = profile["core"]
        if not isinstance(core, list) or not core:
            raise ValueError(f"{direction}.core 必须是非空数组")
        for index, entry in enumerate(core):
            if not isinstance(entry, dict) or "item" not in entry:
                raise ValueError(f"{direction}.core[{index}] 缺少 item 字段")
        if not isinstance(profile["search_keywords"], list) or not profile["search_keywords"]:
            raise ValueError(f"{direction}.search_keywords 必须是非空数组")

        # 把方向的 key 注入 profile，下游 prompt 和页面都能直接用
        item = dict(profile)
        item["direction"] = direction
        normalized[direction] = item
    return normalized


def normalize_direction_result(data, direction, profile):
    rows = [row for row in (data.get("table") or []) if isinstance(row, dict)]

    # 对齐方式一：按模型返回的 index 对齐，最稳
    by_index = {}
    for row in rows:
        try:
            index = int(row.get("index"))
        except (TypeError, ValueError):
            continue
        # 重复 index 时保留第一次出现的行，避免后面的覆盖前面
        by_index.setdefault(index, row)

    # 对齐方式二：按归一化后的 item 文本对齐，兼容 key 别名和空格差异
    by_text = {}
    for row in rows:
        key = _normalize_text(_row_item(row))
        if key:
            by_text[key] = row

    table = []
    matched_indexes = []
    for position, core_entry in enumerate(profile.get("core", []), 1):
        name = core_entry.get("item", "")
        row = by_index.get(position)
        if row is None:
            row = by_text.get(_normalize_text(name))

        if row is None:
            # index 和归一化文本都对不上，才判定模型未返回
            table.append(
                {
                    "item": name,
                    "level": "unknown",
                    "evidence": "",
                    "note": "（模型未返回此项，结果可能不完整）",
                }
            )
            continue

        matched_indexes.append(position)
        level = row.get("level")
        if level not in VALID_LEVELS:
            level = "unknown"
        table.append(
            {
                # 展示一律用 profile 自己的文字，不用模型可能写歪的 item
                "item": name,
                "level": level,
                "evidence": row.get("evidence", "") or "",
                "note": row.get("note", "") or "",
            }
        )

    # priorities 用归一化匹配回表格里的标准条目，避免 key 或空格差异导致丢失
    table_by_text = {_normalize_text(row["item"]): row["item"] for row in table}
    priorities = []
    for entry in data.get("priorities") or []:
        if not isinstance(entry, dict):
            continue
        canonical = table_by_text.get(_normalize_text(_row_item(entry)))
        if canonical:
            priorities.append(
                {
                    "item": canonical,
                    "reason": entry.get("reason", "") or "",
                    "how": entry.get("how", "") or "",
                }
            )

    # 调试信息：页面在出现“未返回”时会展开显示这些内容
    debug = {
        "raw_table": json.dumps(rows, ensure_ascii=False)[:800],
        "matched_indexes": matched_indexes,
    }

    return {
        "direction": direction,
        "summary": (data.get("summary") or "")[:200],
        "table": table,
        "priorities": priorities,
        "_debug": debug,
    }


def match_direction(resume_text, direction, profile, background=""):
    # 背景只截断不报错；空背景交给 prompt 层决定是否出现
    bg_text = (background or "").strip()
    if len(bg_text) > config.DIRECTION_BG_MAX_CHARS:
        bg_text = bg_text[: config.DIRECTION_BG_MAX_CHARS]

    messages = [
        {"role": "system", "content": DIRECTION_SYSTEM_PROMPT},
        {"role": "user", "content": build_direction_prompt(resume_text, profile, bg_text)},
    ]
    try:
        content = chat(messages, json_mode=True)
    except Exception as exc:
        return {"error": f"调用模型失败：{exc}"}

    data = _safe_json(content)
    if not isinstance(data, dict):
        return {"error": "模型返回的内容不是有效 JSON，请重试一次。"}
    return normalize_direction_result(data, direction, profile)


def search_url(keyword):
    # 关键词做 URL 编码，中文不会让链接失效
    # 故意不加城市参数：定位交给 BOSS 平台按用户当前城市自动决定
    return f"https://www.zhipin.com/web/geek/job?query={quote(keyword)}"
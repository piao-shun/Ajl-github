import json
from pathlib import Path
from urllib.parse import quote

from app import config
from app.core.llm import _safe_json, chat
from app.core.prompts import DIRECTION_SYSTEM_PROMPT, build_direction_prompt

PROFILES_PATH = config.DATA_DIR / "job_profiles.json"

REQUIRED_FIELDS = ("name", "aliases", "core", "bonus", "search_keywords")
VALID_LEVELS = ("have", "partial", "missing", "unknown")


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
    # 按 profile.core 重建表格，保证顺序一致且一条不漏
    model_rows = {}
    for row in data.get("table") or []:
        if isinstance(row, dict) and row.get("item"):
            model_rows[row["item"]] = row

    table = []
    for core_entry in profile.get("core", []):
        name = core_entry.get("item", "")
        row = model_rows.get(name, {})
        level = row.get("level")
        if level not in VALID_LEVELS:
            level = "unknown"
        table.append(
            {
                "item": name,
                "level": level,
                "evidence": row.get("evidence", "") or "",
                "note": row.get("note", "") or "",
            }
        )

    # priorities 只保留能在表格里找到同名条目的项
    table_items = {row["item"] for row in table}
    priorities = []
    for entry in data.get("priorities") or []:
        if isinstance(entry, dict) and entry.get("item") in table_items:
            priorities.append(
                {
                    "item": entry["item"],
                    "reason": entry.get("reason", "") or "",
                    "how": entry.get("how", "") or "",
                }
            )

    return {
        "direction": direction,
        "summary": (data.get("summary") or "")[:200],
        "table": table,
        "priorities": priorities,
    }


def match_direction(resume_text, direction, profile):
    messages = [
        {"role": "system", "content": DIRECTION_SYSTEM_PROMPT},
        {"role": "user", "content": build_direction_prompt(resume_text, profile)},
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
    return f"https://www.zhipin.com/web/geek/job?query={quote(keyword)}"
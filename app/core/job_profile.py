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


def _validate_direction_data(data, total=None):
    # 返回问题列表；空列表表示结构合格
    problems = []

    table = data.get("table")
    if not isinstance(table, list):
        problems.append("table 字段缺失或不是数组（期望与行业标准条目数一致的数组）")
        return problems
    if len(table) == 0:
        problems.append("table 字段为空（期望与行业标准条目数一致的数组）")
        return problems

    dict_rows = [row for row in table if isinstance(row, dict)]
    if len(dict_rows) != len(table):
        problems.append(f"table 里有 {len(table) - len(dict_rows)} 行不是对象")

    if not dict_rows:
        problems.append("table 里没有任何有效行")
        return problems

    identifiable_count = _count_identifiable(data)
    if identifiable_count == 0:
        problems.append("table 里没有任何一行带 index 或 item/要求/name，无法识别条目")
    elif total is not None and identifiable_count < total:
        # 唯一项数不足也交给重试逻辑处理（重复 index 只算一项）
        problems.append(f"只返回了 {identifiable_count} 项，期望 {total} 项")

    return problems


def _row_key(row):
    # 每行只取一个标识：优先 index，没有 index 再用归一化文本
    index = row.get("index")
    if index is not None:
        try:
            return ("index", int(index))
        except (TypeError, ValueError):
            pass
    text = _normalize_text(_row_item(row))
    if text:
        return ("text", text)
    return None


def _count_identifiable(data):
    if not isinstance(data, dict):
        return 0
    rows = [row for row in (data.get("table") or []) if isinstance(row, dict)]
    # 用集合去重：5 行但只有 3 个唯一 index，只算 3 项
    keys = {_row_key(row) for row in rows}
    keys.discard(None)
    return len(keys)


def normalize_direction_result(
    data, direction, profile, missing_note="（模型未返回此项，结果可能不完整）"
):
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
                    "note": missing_note,
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

    # 调试信息：匹配命中的序号；原始返回由 match_direction 补两次内容
    debug = {"matched_indexes": matched_indexes}

    return {
        "direction": direction,
        "summary": (data.get("summary") or "")[:200],
        "table": table,
        "priorities": priorities,
        "_debug": debug,
    }


def _with_debug(result, first_content, second_content):
    # 两次原始返回都留，排查“第一次为什么错、第二次为什么还错”才有依据
    debug = result.get("_debug") or {}
    debug["raw_first"] = (first_content or "")[:800]
    debug["raw_second"] = (second_content or "")[:800]
    result["_debug"] = debug
    return result


def match_direction(resume_text, direction, profile, background=""):
    # 背景只截断不报错；空背景交给 prompt 层决定是否出现
    bg_text = (background or "").strip()
    if len(bg_text) > config.DIRECTION_BG_MAX_CHARS:
        bg_text = bg_text[: config.DIRECTION_BG_MAX_CHARS]

    total = len(profile.get("core", []))
    messages = [
        {"role": "system", "content": DIRECTION_SYSTEM_PROMPT},
        {"role": "user", "content": build_direction_prompt(resume_text, profile, bg_text)},
    ]

    first_content = ""
    second_content = ""

    try:
        first_content = chat(messages, json_mode=True)
    except Exception as exc:
        return {"error": f"调用模型失败：{exc}"}

    data = _safe_json(first_content)
    if not isinstance(data, dict):
        problems = ["模型返回的不是 JSON 对象"]
    else:
        problems = _validate_direction_data(data, total)

    if problems:
        # 第 2 次调用：把具体问题和 schema 一起告诉模型
        retry_messages = messages + [
            {
                "role": "user",
                "content": (
                    f"你上一次的返回不合格：{'；'.join(problems)}。"
                    "请严格按 JSON schema 重新输出。"
                    f"table 必须是长度为 {total} 的数组，每行必须含 index（1..{total}）、"
                    "item、level、evidence、note。"
                    "只输出 JSON，不要任何解释。"
                ),
            }
        ]
        try:
            second_content = chat(retry_messages, json_mode=True)
        except Exception as exc:
            return {"error": f"调用模型失败：{exc}"}

        data = _safe_json(second_content)
        if not isinstance(data, dict):
            problems = ["模型第二次返回的不是 JSON 对象"]
        else:
            problems = _validate_direction_data(data, total)

        if problems:
            identifiable = _count_identifiable(data)
            if identifiable > 0:
                # 部分成功：表格非空但不完整，返回 partial 让页面照常渲染并提示
                result = normalize_direction_result(
                    data, direction, profile, missing_note="（本次未返回）"
                )
                result["partial"] = True
                result["returned"] = identifiable
                result["missing"] = [
                    row["item"]
                    for row in result["table"]
                    if row["note"] == "（本次未返回）"
                ]
                return _with_debug(result, first_content, second_content)

            # 完全失败：只回 error，绝不带 table
            return {
                "error": "模型返回格式异常（缺少能力表格），请再点一次重试",
                "debug": {
                    "raw_first": (first_content or "")[:800],
                    "raw_second": (second_content or "")[:800],
                    "problems": problems,
                },
            }

    result = normalize_direction_result(data, direction, profile)
    return _with_debug(result, first_content, second_content)


def search_url(keyword):
    # 关键词做 URL 编码，中文不会让链接失效
    # 故意不加城市参数：定位交给 BOSS 平台按用户当前城市自动决定
    return f"https://www.zhipin.com/web/geek/job?query={quote(keyword)}"
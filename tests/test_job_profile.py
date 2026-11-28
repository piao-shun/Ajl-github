import json

import pytest

from app.core import job_profile, prompts
from app.core.job_profile import (
    _normalize_text,
    load_profiles,
    match_direction,
    normalize_direction_result,
    search_url,
)


def test_all_profiles_pass_validation():
    profiles = load_profiles()

    assert len(profiles) == 5
    for direction, profile in profiles.items():
        assert profile["direction"] == direction
        assert profile["name"]
        assert profile["core"]
        assert profile["search_keywords"]


def test_missing_field_raises(tmp_path):
    bad = {"backend": {"name": "缺字段示例", "aliases": [], "core": [{"item": "A"}]}}
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError):
        load_profiles(path)


def test_core_has_at_least_three_items():
    profiles = load_profiles()

    for direction, profile in profiles.items():
        assert len(profile["core"]) >= 3, direction


def test_invalid_level_is_normalized_to_unknown():
    profile = {"core": [{"item": "A"}, {"item": "B"}]}
    data = {
        "summary": "测试",
        "table": [
            {"item": "A", "level": "totally_made_up", "evidence": "原文", "note": "说明"},
        ],
        "priorities": [],
    }

    result = normalize_direction_result(data, "backend", profile)

    assert result["table"][0]["level"] == "unknown"
    assert result["table"][1]["level"] == "unknown"
    assert [row["item"] for row in result["table"]] == ["A", "B"]


def test_priorities_outside_table_are_dropped():
    profile = {"core": [{"item": "A"}, {"item": "B"}]}
    data = {
        "summary": "测试",
        "table": [{"item": "A", "level": "have"}],
        "priorities": [
            {"item": "A", "reason": "r", "how": "h"},
            {"item": "表外项", "reason": "r", "how": "h"},
        ],
    }

    result = normalize_direction_result(data, "backend", profile)

    table_items = {row["item"] for row in result["table"]}
    assert all(entry["item"] in table_items for entry in result["priorities"])
    assert [entry["item"] for entry in result["priorities"]] == ["A"]


def test_direction_prompt_does_not_regress_jd_prompt():
    resume = "张三 通信工程 某大学 中国移动实习 " * 20

    base = prompts.build_analysis_prompt(resume)
    with_jd = prompts.build_analysis_prompt(resume, jd="岗位要求")

    assert "level" not in base
    assert "table" not in base
    assert "match_score" in with_jd

    profile = {
        "direction": "backend",
        "name": "后端开发工程师",
        "core": [{"item": "数据库与 SQL", "expect": "能写查询"}],
    }
    direction_prompt = prompts.build_direction_prompt(resume, profile)
    assert "direction" in direction_prompt
    assert "数据库与 SQL" in direction_prompt


def test_search_url_encodes_chinese():
    url = search_url("后端开发 实习")

    assert url.startswith("https://www.zhipin.com/web/geek/job?query=")
    assert "%" in url
    assert " " not in url

def test_missing_table_rows_are_labeled_as_model_omission():
    profile = {"core": [{"item": name} for name in ["A", "B", "C", "D", "E"]]}
    data = {
        "summary": "测试",
        "table": [
            {"item": "A", "level": "have", "evidence": "a", "note": "n"},
            {"item": "B", "level": "partial", "evidence": "b", "note": "n"},
            {"item": "C", "level": "missing", "evidence": "", "note": "n"},
        ],
        "priorities": [],
    }

    result = normalize_direction_result(data, "backend", profile)

    assert len(result["table"]) == 5
    missing_rows = result["table"][3:]
    assert [row["item"] for row in missing_rows] == ["D", "E"]
    for row in missing_rows:
        assert row["level"] == "unknown"
        assert row["evidence"] == ""
        assert "模型未返回" in row["note"]

def test_item_with_space_difference_still_matches():
    profile = {"core": [{"item": "HTTP 与 REST 接口"}, {"item": "数据库与 SQL"}]}
    data = {
        "summary": "测试",
        "table": [
            {"index": 1, "item": "HTTP与REST接口", "level": "have", "evidence": "e", "note": "n"},
        ],
        "priorities": [],
    }

    result = normalize_direction_result(data, "backend", profile)

    assert result["table"][0]["item"] == "HTTP 与 REST 接口"
    assert result["table"][0]["level"] == "have"
    assert "模型未返回" not in result["table"][0]["note"]


def test_alternate_requirement_key_still_matches():
    profile = {"core": [{"item": "数据库与 SQL"}]}
    data = {
        "summary": "测试",
        "table": [
            {"index": 1, "要求": "数据库与SQL", "level": "partial", "evidence": "e", "note": "n"}
        ],
        "priorities": [],
    }

    result = normalize_direction_result(data, "backend", profile)

    assert result["table"][0]["level"] == "partial"
    assert "模型未返回" not in result["table"][0]["note"]


def test_index_alignment_wins_even_if_text_differs():
    profile = {"core": [{"item": "A"}, {"item": "B"}, {"item": "C"}]}
    data = {
        "summary": "测试",
        "table": [
            {"index": 1, "item": "完全不同的描述", "level": "missing", "evidence": "", "note": "n"},
            {"index": 3, "item": "写歪的第三项", "level": "have", "evidence": "e", "note": "n"},
        ],
        "priorities": [],
    }

    result = normalize_direction_result(data, "backend", profile)

    assert result["table"][0]["level"] == "missing"
    assert result["table"][1]["level"] == "unknown"
    assert "模型未返回" in result["table"][1]["note"]
    assert result["table"][2]["level"] == "have"

def test_normalization_keeps_plus_and_hash():
    assert _normalize_text("C++") != _normalize_text("C")
    assert _normalize_text("C#") != _normalize_text("C")

PROFILE = {
    "direction": "backend",
    "name": "后端开发工程师",
    "core": [
        {"item": "A"},
        {"item": "B"},
        {"item": "C"},
        {"item": "D"},
        {"item": "E"},
    ],
}


def _full_table():
    return {
        "summary": "正常",
        "table": [
            {"index": i, "item": name, "level": "have", "evidence": "e", "note": "n"}
            for i, name in enumerate(["A", "B", "C", "D", "E"], 1)
        ],
        "priorities": [],
    }


def test_retry_once_then_success(monkeypatch):
    responses = [
        json.dumps({"summary": "缺表格"}, ensure_ascii=False),
        json.dumps(_full_table(), ensure_ascii=False),
    ]
    calls = []

    def fake_chat(messages, **kwargs):
        calls.append(messages)
        return responses[len(calls) - 1]

    monkeypatch.setattr(job_profile, "chat", fake_chat)

    result = match_direction("简历" * 20, "backend", PROFILE)

    assert len(calls) == 2
    assert "error" not in result
    assert len(result["table"]) == 5


def test_retry_twice_invalid_returns_error_without_table(monkeypatch):
    def fake_chat(messages, **kwargs):
        return json.dumps({"summary": "一直缺表格"}, ensure_ascii=False)

    monkeypatch.setattr(job_profile, "chat", fake_chat)

    result = match_direction("简历" * 20, "backend", PROFILE)

    assert "error" in result
    assert "table" not in result
    assert result["debug"]["problems"]


def test_valid_first_time_no_retry(monkeypatch):
    calls = []

    def fake_chat(messages, **kwargs):
        calls.append(messages)
        return json.dumps(_full_table(), ensure_ascii=False)

    monkeypatch.setattr(job_profile, "chat", fake_chat)

    result = match_direction("简历" * 20, "backend", PROFILE)

    assert len(calls) == 1
    assert len(result["table"]) == 5

def _table_with_rows(count):
    names = ["A", "B", "C", "D", "E"][:count]
    return {
        "summary": "部分",
        "table": [
            {"index": i, "item": name, "level": "have", "evidence": "e", "note": "n"}
            for i, name in enumerate(names, 1)
        ],
        "priorities": [],
    }


def test_retry_fills_missing_rows(monkeypatch):
    responses = [
        json.dumps(_table_with_rows(3), ensure_ascii=False),
        json.dumps(_table_with_rows(5), ensure_ascii=False),
    ]
    calls = []

    def fake_chat(messages, **kwargs):
        calls.append(messages)
        return responses[len(calls) - 1]

    monkeypatch.setattr(job_profile, "chat", fake_chat)

    result = match_direction("简历" * 20, "backend", PROFILE)

    assert len(calls) == 2
    assert "error" not in result
    assert result.get("partial") is not True
    assert len(result["table"]) == 5


def test_partial_when_both_attempts_incomplete(monkeypatch):
    def fake_chat(messages, **kwargs):
        return json.dumps(_table_with_rows(3), ensure_ascii=False)

    monkeypatch.setattr(job_profile, "chat", fake_chat)

    result = match_direction("简历" * 20, "backend", PROFILE)

    assert "error" not in result
    assert result["partial"] is True
    assert len(result["missing"]) == 2
    assert len(result["table"]) == 5

def test_duplicate_index_does_not_count_as_complete(monkeypatch):
    duplicated = {
        "summary": "重复 index",
        "table": [
            {"index": 1, "item": "A", "level": "have", "evidence": "e", "note": "n"},
            {"index": 1, "item": "A", "level": "have", "evidence": "e", "note": "n"},
            {"index": 2, "item": "B", "level": "have", "evidence": "e", "note": "n"},
            {"index": 2, "item": "B", "level": "have", "evidence": "e", "note": "n"},
            {"index": 3, "item": "C", "level": "have", "evidence": "e", "note": "n"},
        ],
        "priorities": [],
    }
    responses = [
        json.dumps(duplicated, ensure_ascii=False),
        json.dumps(_table_with_rows(5), ensure_ascii=False),
    ]
    calls = []

    def fake_chat(messages, **kwargs):
        calls.append(messages)
        return responses[len(calls) - 1]

    monkeypatch.setattr(job_profile, "chat", fake_chat)

    result = match_direction("简历" * 20, "backend", PROFILE)

    assert len(calls) == 2
    assert "error" not in result
    assert result.get("partial") is not True
    assert len(result["table"]) == 5
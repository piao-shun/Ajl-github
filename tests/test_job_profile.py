import json

import pytest

from app.core import prompts
from app.core.job_profile import load_profiles, normalize_direction_result, search_url


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
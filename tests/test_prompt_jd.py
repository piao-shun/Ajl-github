from app import config
from app.core import prompts

RESUME = "张三 通信工程 某大学 中国移动 网络优化实习 " * 30
JD = "岗位职责：负责 5G 网络优化，要求熟悉 Python，有通信行业实习经验。"


def test_without_jd_prompt_has_no_jd_section():
    prompt = prompts.build_analysis_prompt(RESUME)

    assert "岗位 JD" not in prompt
    assert "match_score" not in prompt
    assert "jd_hits" not in prompt
    assert "jd_gaps" not in prompt
    assert "keywords_missing" in prompt


def test_with_jd_prompt_contains_jd_and_new_fields():
    prompt = prompts.build_analysis_prompt(RESUME, jd=JD)

    assert "岗位 JD" in prompt
    assert JD in prompt
    assert "match_score" in prompt
    assert "jd_hits" in prompt
    assert "jd_gaps" in prompt


def test_blank_jd_is_treated_as_empty():
    blank = prompts.build_analysis_prompt(RESUME, jd="   \n\t ")
    empty = prompts.build_analysis_prompt(RESUME, jd="")

    assert blank == empty
    assert "match_score" not in blank


def test_long_jd_is_truncated():
    long_jd = "x" * (config.JD_MAX_CHARS + 500)

    text, truncated = config.prepare_jd(long_jd)

    assert truncated is True
    assert len(text) == config.JD_MAX_CHARS


def test_short_jd_is_not_truncated():
    text, truncated = config.prepare_jd("短 JD")

    assert truncated is False
    assert text == "短 JD"
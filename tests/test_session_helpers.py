from app.config import (
    clear_result_state,
    jd_changed,
    jd_fingerprint,
    should_reset_session,
)


def test_file_change_clears_result_state():
    state = {
        "analysis": {"score": 70},
        "direction_result": {"table": []},
        "active_view": "jd",
        "jd_used": True,
        "jd_fingerprint": "abc12345",
        "source_name": "old.pdf",
        "direction_key": "backend",
        "uploaded_file_id": "old-id",
        "unrelated": "keep me",
    }

    assert should_reset_session("old-id", "new-id") is True
    clear_result_state(state)

    for key in (
        "analysis",
        "direction_result",
        "active_view",
        "jd_used",
        "jd_fingerprint",
        "source_name",
        "direction_key",
    ):
        assert key not in state
    # 清空只动结果缓存，别的 key 必须保留
    assert state["unrelated"] == "keep me"


def test_same_file_keeps_result_state():
    state = {"analysis": {"score": 70}, "uploaded_file_id": "same-id"}

    assert should_reset_session("same-id", "same-id") is False
    assert should_reset_session(None, "first-id") is False

    # 同一份文件不应触发清空
    assert state["analysis"] == {"score": 70}


def test_jd_fingerprint_change_is_detected():
    original = jd_fingerprint("原来的 JD")

    assert jd_changed(original, "原来的 JD") is False
    assert jd_changed(original, "改过的 JD") is True
    # 空 JD 没有指纹，也不该报“已修改”
    assert jd_fingerprint("") == ""
    assert jd_changed("", "改过的 JD") is False


def test_jd_fingerprint_is_stable_and_short():
    fingerprint = jd_fingerprint("同样的文本")

    assert fingerprint == jd_fingerprint("同样的文本")
    assert len(fingerprint) == 8
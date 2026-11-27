from app.core import llm

LONG_TEXT = "这是一份足够长的简历文本，用来确认正常流程。" * 20


def test_short_text_never_calls_model(monkeypatch):
    calls = []

    def fake_chat(*args, **kwargs):
        calls.append(kwargs)
        return "{}"

    monkeypatch.setattr(llm, "chat", fake_chat)

    result = llm.analyze_resume("太短")

    assert "error" in result
    assert calls == []


def test_normal_text_calls_model_once(monkeypatch):
    calls = []

    def fake_chat(*args, **kwargs):
        calls.append(kwargs)
        return '{"score": 80}'

    monkeypatch.setattr(llm, "chat", fake_chat)

    result = llm.analyze_resume(LONG_TEXT)

    assert len(calls) == 1
    assert result["score"] == 80
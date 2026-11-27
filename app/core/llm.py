import json

from openai import OpenAI

from app import config
from app.core.prompts import SYSTEM_PROMPT, build_analysis_prompt

_client = None


def get_client():
    global _client
    if _client is None:
        if not config.API_KEY:
            raise RuntimeError(
                "未配置 API Key，请在 .env 或平台 Secrets 中填写 DEEPSEEK_API_KEY"
            )
        # timeout=60：单次请求最多等 60 秒；max_retries=1：失败后自动重试一次
        _client = OpenAI(
            api_key=config.API_KEY,
            base_url=config.BASE_URL,
            timeout=60,
            max_retries=1,
        )
    return _client


def chat(messages, temperature=0.3, json_mode=False):
    kwargs = {
        "model": config.MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": config.MAX_TOKENS,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = get_client().chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def _safe_json(text):
    # 模型有时会把 JSON 包在 ```json ... ``` 里，先剥掉再解析
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("`").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 再试一次：截取第一个 { 到最后一个 } 之间的内容
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
    return None


def analyze_resume(raw_text, target_job="", background="", jd=""):
    if len((raw_text or "").strip()) < config.MIN_TEXT_CHARS:
        # 文本过短时直接返回错误，不调用模型，避免凭空编造
        return {
            "error": "简历文本过短（少于 50 个字符），未调用模型。请上传可复制文字的 PDF 或 .docx。"
        }
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_analysis_prompt(raw_text, target_job, background, jd)},
    ]
    try:
        content = chat(messages, json_mode=True)
    except Exception as exc:
        # 网络超时、Key 无效、模型服务报错都在这里兜住，返回可展示的错误，不让页面崩
        return {"error": f"调用模型失败：{exc}"}

    data = _safe_json(content)
    if data is None:
        return {"error": "模型返回的内容不是有效 JSON，请重试一次。"}
    if not isinstance(data, dict):
        return {"error": "模型返回的 JSON 结构不符合预期，请重试一次。"}
    return data
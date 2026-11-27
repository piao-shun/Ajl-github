SYSTEM_PROMPT = (
    "你是一名有 10 年经验的资深招聘官和简历顾问，熟悉互联网、通信、硬件、国企等行业的招聘标准。"
    "你的任务是审阅候选人简历，给出具体、可执行的修改意见。"
    "要求：只讲能落地的改法，不说空话；指出问题时要给出改写示例；所有内容用简体中文。只输出 JSON。"
)


def build_analysis_prompt(raw_text, target_job="", background=""):
    job = target_job.strip() or "未指定（按通用优质简历标准）"
    bg = background.strip() or "未提供"
    return f"""请审阅下面的简历，输出一个 JSON 对象，字段如下：
{{
  "score": 0 到 100 的整数,
  "overall": "150 字以内的总体评价",
  "suggestions": [
    {{"section": "涉及章节", "problem": "具体问题", "advice": "可直接执行的改法", "rewrite": "改写示例，没有则填空字符串"}}
  ],
  "keywords_missing": ["岗位需要但简历里缺失的关键词"],
  "next_steps": ["接下来优先做的 3 件事"]
}}

目标岗位：{job}
候选人背景：{bg}

简历原文：
\"\"\"
{raw_text}
\"\"\"
"""
from datetime import date

SYSTEM_PROMPT = (
    f"今天是 {date.today().isoformat()}。只有日期晚于今天的经历，才可以被称为'未来时间'。"
    "你是一名有 10 年经验的资深招聘官和简历顾问，熟悉互联网、通信、硬件、国企等行业的招聘标准。"
    "你的任务是审阅候选人简历，给出具体、可执行的修改意见。"
    "硬约束：只能使用简历原文中出现过的事实（公司名、数字、技术栈、日期、指标），不得新增原文没有的技术名词或经历。"
    "每条建议必须给出 evidence 字段，内容是简历原文里逐字复制的片段；找不到原文依据，就不要提这条建议。"
    "如果改写示例包含原文没有的内容，必须用【需你补充】标出，并在 next_steps 说明怎么补。"
    "只讲能落地的改法，不说空话；所有内容用简体中文。只输出 JSON。"
    "改写示例是目标状态，不是现状。用户可能直接复制粘贴，所以必须明确区分。"
)


def build_analysis_prompt(raw_text, target_job="", background="", jd=""):
    job = target_job.strip() or "未指定（按通用优质简历标准）"
    bg = background.strip() or "未提供"
    jd_text = (jd or "").strip()

    # JD 为空时这两段都是空字符串，保证 jd 空场景下 prompt 与旧版逐字一致
    extra_fields = ""
    jd_section = ""
    if jd_text:
        extra_fields = (
            ',\n'
            '  "match_score": 0 到 100 的整数（简历与岗位 JD 的匹配度）,\n'
            '  "jd_hits": ["简历已满足的 JD 要求"],\n'
            '  "jd_gaps": ["简历缺失的 JD 要求"]'
        )
        jd_section = (
            "\n岗位 JD：\n"
            '"""\n'
            f"{jd_text}\n"
            '"""\n'
            "\n请逐条判断简历是否命中 JD 要求，命中的写进 jd_hits，缺失的写进 jd_gaps。\n"
        )

    return f"""请审阅下面的简历，输出一个 JSON 对象，字段如下：
{{
  "score": 0 到 100 的整数,
  "overall": "150 字以内的总体评价",
  "suggestions": [
    {{
      "section": "涉及章节",
      "problem": "具体问题",
      "advice": "可直接执行的改法",
      "evidence": "从简历原文里逐字复制的片段，必须能在原文中找到；找不到就不要提这条建议",
      "rewrite": "改写示例，没有则填空字符串；包含原文没有的内容时用【需你补充】标出"
    }}
  ],
  "keywords_missing": ["岗位需要但简历里缺失的关键词"],
  "next_steps": ["接下来优先做的 3 件事，包括如何补上【需你补充】的内容"]{extra_fields}
}}

目标岗位：{job}
候选人背景：{bg}
{jd_section}
简历原文：
\"\"\"
{raw_text}
\"\"\"
"""
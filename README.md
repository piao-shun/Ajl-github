# 简历助手（jl）

上传 Word / PDF 简历 → AI 给出针对性修改意见 → 导出 Word / PDF。

## 环境要求

- Python 3.10 及以上（推荐 3.12）

## 🔗 在线体验

https://jl-resume.streamlit.app/

> 免费层无流量时会休眠，首次打开约需 30 秒冷启动，属正常现象。

## 已知问题

| 问题 | 说明 | 处理方式 |
|---|---|---|
| 首次访问慢 | Streamlit 免费层休眠，唤醒约 30 秒 | 属正常，等待或刷新 |
| 扫描件 / 转曲 PDF 读不出 | 图片型 PDF、设计软件导出的"文字转曲"PDF 提取不到文字 | 用 Word 另存为 PDF，或直接上传 .docx |
| 单文件上限 5MB | 传输层限制（server.maxUploadSize） | 压缩或拆分文件 |
| 分析文字上限 15000 字 | 超出部分不参与分析，界面会提示 | 精简到核心内容 |
| 需要访问口令 | 公开链接防止被滥用 | 口令由维护者私下提供 |

## 本地运行

```bash
git clone https://github.com/piao-shun/Ajl-github.git
cd Ajl-github

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

复制 `.env.example` 为 `.env`，填写其中的变量（具体变量名以 `.env.example` 为准，通常包括模型 Key、Base URL、模型名与访问口令）。

```bash
streamlit run app/ui/streamlit_app.py
```

浏览器打开 http://localhost:8501

## 环境变量（只写变量名）

| 变量名 | 必填 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 是 | DeepSeek 的 API Key |
| `DEEPSEEK_BASE_URL` | 否 | 默认 `https://api.deepseek.com/v1` |
| `DEEPSEEK_MODEL` | 否 | 默认 `deepseek-chat` |

本地放在 `.env` 文件；云端放在 Streamlit 后台的 Secrets 里。

## 项目结构

```
app/
  config.py            读环境变量，统一配置
  core/parser.py       解析 Word / PDF 简历
  core/llm.py          调大模型（超时 + 重试 + JSON 容错）
  core/prompts.py      简历修改提示词
  core/exporter.py     生成 Word / PDF（内存字节流）
  ui/streamlit_app.py  主界面
  main.py              FastAPI 接口（预留）
tests/
  test_parser.py       解析测试
  test_exporter.py     导出测试
data/
  samples/             假简历示例（张三，仅供测试）
```

## 测试

```bash
python -m pytest -q
```

测试不调用模型，只验证解析和导出。

## 知识路线（边做边学）

| 你将学到 | 在 jl 里对应哪部分 |
|---|---|
| 什么是 AI / LLM / token / prompt | `core/llm.py` `core/prompts.py` |
| 什么是 Agent（会自己调工具的 AI） | 后续「解析→分析→改写→导出」串联成工作流 |
| 什么是 RAG（先查资料再回答） | 后续把优秀简历模板 / 岗位 JD 放进向量库 |
| 什么是 Skill（可复用的能力包） | 把「按岗位定制」「量化改写」抽成独立模块 |

## 后续计划

- P1：支持岗位 JD 粘贴，意见按 JD 关键词打分
- P2：一键改写正文并回填到 Word 原格式
- P3：简历模板库 + RAG 检索

- 🔗 在线体验：https://jl-resume.streamlit.app/

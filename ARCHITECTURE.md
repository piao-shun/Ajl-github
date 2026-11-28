# 架构说明

## 文件清单

| 文件 | 职责 | 谁调用它 |
|---|---|---|
| `app/ui/streamlit_app.py` | 页面入口，接收上传、展示结果、提供下载 | 用户 / Streamlit |
| `app/config.py` | 读取环境变量，给出目录和模型配置 | 所有模块 |
| `app/core/parser.py` | 把 Word / PDF 解析成文字和章节 | `streamlit_app.py`、测试 |
| `app/core/llm.py` | 调 DeepSeek，带超时、重试、JSON 容错 | `streamlit_app.py` |
| `app/core/prompts.py` | 存放提示词模板 | `llm.py` |
| `app/core/exporter.py` | 把分析结果生成 Word / PDF 字节流 | `streamlit_app.py`、`main.py` |
| `app/main.py` | FastAPI 接口（预留，未部署） | 暂无调用方 |
| `tests/test_parser.py` | 验证 Word / PDF 解析非空 | pytest |
| `tests/test_exporter.py` | 验证 Word / PDF 导出成功 | pytest |
| `data/samples/` | 假简历示例（张三） | 人工测试 |

## 数据流

用户上传简历并填写岗位 → `streamlit_app.py` 把文件写进临时目录 → `parser.py` 解析出文字 → `llm.py` 拼好提示词调用 DeepSeek → 模型返回 JSON 存进 `session_state` → 页面渲染评分和建议 → `exporter.py` 在内存生成 Word / PDF 字节 → 浏览器直接下载。

## 五句话说明

1. 这是一个把简历和岗位做匹配分析的网页工具。
2. 用户上传 Word 或 PDF 简历，并填写目标岗位。
3. 后端解析出简历文字，交给 DeepSeek 生成评分、缺失点和改写建议。
4. 结果在页面上展示，并可直接下载为 Word 或 PDF。
5. 模型 Key 只存在服务端环境变量里，云端不保存任何上传文件。

## 已知耦合

- 方向诊断的 `missing` 列表是通过 `row["note"] == "（本次未返回）"` 从表格里反查出来的。以后改这句文案时，`job_profile.py` 的 partial 分支与这里必须同步，否则 `missing` 会变空。

## 故障排查

### 页面空白

- 检查终端是否还在运行 `streamlit run app/ui/streamlit_app.py`，有没有 ImportError。
- 刷新一次页面，再看浏览器控制台有没有红色报错。

### 请求返回 500

- 看终端输出的最后几行报错原文。
- 多数是依赖没装全，重新执行 `pip install -r requirements.txt`。

### Key 报错

- 报 `AuthenticationError`：Key 填错或已过期，重新复制一次。
- 报「未配置 API Key」：本地查 `.env` 里的 `DEEPSEEK_API_KEY`，云端查 Secrets 是否已保存。
- 报余额不足：去 DeepSeek 控制台充值。
# 部署到 Streamlit Community Cloud

## 前置条件

- 代码已推到一个**公开**的 GitHub 仓库
- 有一个 DeepSeek API Key

## 步骤（按顺序做）

1. 把代码推到公开 GitHub 仓库：

   ```bash
   git add -A
   git commit -m "P0: 完成解析-分析-导出主链路，补测试与安全配置"
   git push origin main
   ```

2. 打开 https://share.streamlit.io ，用 GitHub 账号登录。

3. 点「New app」。

4. 选择你的仓库，Branch 选 `main`。

5. 入口文件（Main file path）填：

   ```
   app/ui/streamlit_app.py
   ```

6. 点「Advanced settings」，在 Secrets 框里填：

   ```toml
   DEEPSEEK_API_KEY = "你的 DeepSeek Key"
   ACCESS_CODE = "自己定一个口令"
   ```

   可选再加：

   ```toml
   DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
   DEEPSEEK_MODEL = "deepseek-chat"
   ```

   `ACCESS_CODE` 是访问口令：不设则跳过校验，仅建议本地使用；建议用字母数字，不要用中文。

7. 点「Deploy」，等待构建完成（首次约几分钟）。

8. 部署完成后，应用地址形如 `https://xxx.streamlit.app`。

## 注意事项

- 闲置一段时间会休眠，首次打开约 30 秒，属正常现象。
- 云端不保存任何上传文件，每次都要重新上传。
- 上传大小在传输层就被限制为 5MB（见 `.streamlit/config.toml`）。
- Key 只填在 Secrets，绝不写进代码、绝不提交到 git。
# PPT Agent Studio

一个本地运行的模板驱动 PPT 生成工作台。它的目标不是从零画一套幻灯片，而是先理解用户上传的 PowerPoint 模板，再根据主题、大纲和模板合同，把内容填进合适的封面、目录、过渡页、正文页和结束页。

## 主要能力

- 上传 PPT 模板并生成标准化模板合同，记录页面类型、文本框用途、字号、字体和版式线索。
- 使用 OpenAI 兼容接口生成完整 PPT 大纲，并在真正渲染前让用户确认。
- 按目录分章节生成过渡页，为每一部分选择合适的正文页模板。
- 在生成过程中展示阶段进度，让用户知道 AI 正在做什么。
- 支持 AI 连接测试；未配置或连接失败时可以使用本地兜底规划逻辑。
- 生成后可下载 PPTX，并运行基础质量检查，减少空白页、文本过少、标题过长和内容溢出等问题。

## 快速开始

建议使用 Python 3.11 或更新版本。

```powershell
cd C:\Users\ymzwh\ppt-agent-mvp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.main
```

打开浏览器访问：

```text
http://127.0.0.1:8787
```

也可以在 Windows 上直接运行：

```powershell
.\run-8788.cmd
```

此脚本会使用 `8788` 端口和项目内的 `data` 目录。

## AI 配置

应用支持 OpenAI 兼容的 `chat/completions` 接口。可以在网页的“AI 配置”页填写，也可以通过环境变量设置：

```powershell
$env:OPENAI_API_KEY="你的 API Key"
$env:OPENAI_BASE_URL="https://api.openai.com/v1"
$env:OPENAI_MODEL="gpt-4.1-mini"
python -m app.main
```

可用环境变量：

- `PPT_AGENT_DATA_DIR`：运行数据目录，默认是 `./data`
- `PPT_AGENT_HOST`：监听地址，默认是 `127.0.0.1`
- `PPT_AGENT_PORT`：监听端口，默认是 `8787`
- `OPENAI_API_KEY`：AI 接口密钥
- `OPENAI_BASE_URL`：OpenAI 兼容接口地址，默认是 `https://api.openai.com/v1`
- `OPENAI_MODEL`：模型名称，默认是 `gpt-4.1-mini`

## 工作流

1. 在“模板库”上传 PPT 模板，并生成标准化模板。
2. 在“工作台”填写主题、页数、受众和语气。
3. 点击生成大纲，确认 AI 返回的完整 PPT 大纲。
4. 确认后生成 PPT，等待进度完成。
5. 下载生成的 `.pptx` 文件并检查效果。

## 本地数据

`data/` 目录会保存运行时配置、上传模板和生成结果，其中可能包含 API Key、用户模板和生成的 PPT 文件。这个目录已被 `.gitignore` 排除，不应提交到公开仓库。

## 测试

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
node --check app\static\app.js
```

## 许可

当前暂未指定开源许可证。公开使用或二次分发前，请先补充合适的许可证文件。

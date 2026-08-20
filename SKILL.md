---
name: obsidian-idea-crawler
description: "把小红书图文 / 抖音 / B站 视频链接一键转成 Obsidian(EdenVault) 10-AI 结构化笔记 + 点子落地分析。当用户发来 xiaohongshu.com / xhslink.com / douyin.com / v.douyin.com / bilibili.com / b23.tv 链接，希望'让 AI 替我看、榨成可复用点子存进知识库'时触发。覆盖：小红书图文抓取、视频下载→转写、以及爬完自动填四段落地分析。"
version: 1.0.0
agent_created: true
---

# obsidian-idea-crawler —— 小红书 / 抖音 / B站 → Obsidian 笔记 + 落地分析

把社交平台优质内容（图文 / 视频）一键转成 EdenVault `10-AI/` 里的结构化知识笔记，
并自动补一段「点子落地分析」（能变成什么 / 往哪融 / 技术栈 / 成效 / 思路方向），
供 WorkBuddy 在对话里回给用户决策：**融进已有项目 / 新开项目 / 先攒着**。

> 本 skill 是 `xhs-to-obsidian-idea` + `video-to-obsidian-idea` 的合并可移植版。
> 全部路径相对 skill 目录或走环境变量，**复制整个文件夹到任意设备即可迁移**。
> ⚠️ **前置条件**：需安装 **WorkBuddy 客户端**（Mac / Windows 版，从 workbuddy.cn 下载）才能"在对话里发链接给我跑"。本 skill **不是浏览器插件**，Chrome 等浏览器无法直接运行；若只想纯命令行手动跑脚本也可，但需本机 Python 3.10+。

## 触发条件
- 用户发来以下任一类链接：
  - 小红书：`https://www.xiaohongshu.com/discovery/item/...` 或 `https://xhslink.com/...`
  - 抖音：`https://www.douyin.com/...` / `https://v.douyin.com/...`
  - B站：`https://www.bilibili.com/...` / `https://b23.tv/...`
- 用户希望自动抓取内容、提取图文 / 转写语音，并整理成可复用点子。

## 环境前提（首次安装跑 `setup` 即可，详见本 skill 目录 README.md）
- **小红书**：只需 cookie（Netscape 格式，Cookie-Editor 从 xiaohongshu.com 导出）→ `<skill>/cookies/xiaohongshu.txt`；curl 内置。
- **抖音**：需 cookie → `<skill>/cookies/douyin.txt` + SiliconFlow Key（写进 `<skill>/.venv/.env` 的 `SILICONFLOW_API_KEY=...`）。
- **B站**：无需 cookie，公开下载。
- 依赖（自动装）：`<skill>/.venv` 里装 `yt-dlp httpx requests`；ffmpeg 由 setup 下载到 `<skill>/bin/`。
- 输出仓库：`<EDEN_VAULT>/10-AI/`，默认 `~/Obsidian/EdenVault/10-AI`（用 `EDEN_VAULT` 环境变量覆盖）。

## 运行步骤

### 第 1 步：判别平台，跑对应脚本
所有脚本在 `<skill>/scripts/` 下。建议从目标 `10-AI` 目录运行，使图片相对路径在 Obsidian 正确解析。

**小红书图文（自动抓文字+下载全部图片到本地）**
```bash
cd "<EDEN_VAULT>/10-AI"
python3 "<skill>/scripts/xhs_pipe.py" "<小红书链接>" --tmp xhs_tmp_<短标识>   # Windows 若只有 python 则改用 python
```
生成 `xhs-<标题>.md` 骨架 + `xhs_tmp_<短标识>/images/*.jpg|png` + `page.html`。

**抖音 / B站 视频（下载→抽音频→SiliconFlow 转写→写笔记→清临时）**
```bash
# 先用 venv python（httpx/yt-dlp 在那）
# Windows：
"<skill>\.venv\Scripts\python.exe" "<skill>\scripts\vidpipe.py" "<视频链接>"
# macOS / Linux：
"<skill>/.venv/bin/python" "<skill>/scripts/vidpipe.py" "<视频链接>"
# 只想验证链路（零花费）加 --dry-run 即可
```
脚本自动识别平台；抖音带 cookie、B站公开下。打印 `NOTE_SAVED:<路径>` 与 `TRANSCRIPT_LEN:<字数>`。
> 注意：抖音纯口播无字视频也能转（走语音）；B站更稳无需登录。

### 第 2 步：读原文 + 图片 OCR（Agent 必做）
- 小红书：用 Read 打开生成的 `xhs-*.md` + `xhs_tmp_*/images/img_*.jpg` 做多模态 OCR，补全正文（图文笔记细节常在图里）。
- 视频：笔记已含完整转写文本；抖音视频抽帧（若有画面）存 `<skill>/../eden-frames/` 或临时，可 Read OCR 画面。

### 第 3 步：填四段分析（Agent 必做，脚本只出骨架）
把以下四段补进笔记对应位置（骨架已留空占位），并在对话里回给用户：
1. **核心观点（1 句话）** —— 这内容最值得记住的一个判断
2. **关键要点** —— 3–5 条可执行要点 / 表格 / 对比
3. **💡 可落地想法（Prompt 种子）** —— 以后做项目时把这段丢给 AI 说"照这个做"
4. **🚀 点子落地分析** —— 能变成什么 / 怎么用·往哪融（融已有项目 or 新开 or 先攒）/ 技术栈 / 成效 / 3 个思路方向 / 待用户决策

### 第 4 步：清理（可选）
小红书临时 `xhs_tmp_*/` 与 `page.html` 可保留作备份，或清掉只留 md + images。视频临时 mp4/wav 脚本已自动删，**保留 cookie**。

## 文件约定（全部相对 skill 目录，可移植）
- cookie：`cookies/xiaohongshu.txt`、`cookies/douyin.txt`（用户自导出，不进版本库）
- 输出：`<EDEN_VAULT>/10-AI/<平台>-<标题>.md`
- 视频转写 Key：`.venv/.env` 的 `SILICONFLOW_API_KEY=...`（或环境变量）
- 依赖 venv：`.venv/`（或 `IDEA_VENV` 环境变量指定）
- ffmpeg：`.venv` 外的 `bin/ffmpeg[.exe]`（setup 自动放）

## 故障处理
- **小红书抓不到正文 / 图裂**：cookie 过期 → 重导 `cookies/xiaohongshu.txt`；或让用户直接发截图，走「用户截图发我」兜底。
- **抖音 "Sign in to confirm"**：cookie 过期或抖音改版 → 重导 `cookies/douyin.txt`。
- **ffmpeg / yt-dlp 未找到**：重跑 `setup`；或确认 `bin/`、` .venv/Scripts` 在。
- **转写接口报错**：确认 `SILICONFLOW_API_KEY` 有效、音频是 16k 单声道 wav（脚本已处理）。
- **B站下载失败**：`.venv` 里 `pip install -U yt-dlp` 后重试。

## 注意
- **隐私红线**：cookie / API Key 是登录凭证，等同账号密码——只存隔离的 skill 目录，**绝不写进任何共享记忆 / 不复述 / 不上传**。
- 小红书反爬策略可能变化，遇异常先切「用户截图发我」兜底。
- 用户是纯文科大二升大三学生，讲解避免黑话，多用比喻。
- 本机原有 `xhs-to-obsidian-idea` / `video-to-obsidian-idea` 两个旧 skill 仍可用；本 skill 为统一可移植版，跨设备以本 skill 为准。

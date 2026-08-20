# obsidian-idea-crawler 安装与使用

> ⚠️ **前置条件**：这是一个 **WorkBuddy 本地 Skill**，**不是浏览器插件**。使用前需先安装 **WorkBuddy 客户端（Mac / Windows 版，从 workbuddy.cn 下载）**，再把本文件夹放到 WorkBuddy 的 skills 目录。只装浏览器（哪怕 Chrome）无法运行。若你只想纯命令行手动跑脚本，也可，但需本机自备 Python 3.10+。

把**小红书图文 / 抖音 / B站视频**一键转成 Obsidian(EdenVault) `10-AI/` 结构化笔记 + 点子落地分析。
本 skill 为**可移植打包版**：复制整个文件夹到任意设备即可迁移，所有路径相对 skill 目录或走环境变量。

---

## 一、跨设备安装（3 步）

### 步骤 1：复制 skill 文件夹
把整个 `obsidian-idea-crawler/` 文件夹放到目标设备的 WorkBuddy skills 目录：
- Windows：`%USERPROFILE%\.workbuddy\skills\obsidian-idea-crawler\`
- macOS / Linux：`~/.workbuddy/skills/obsidian-idea-crawler/`

（若是从 Git 仓库克隆，直接 clone 即可。）

### 步骤 2：运行 setup（建 venv + 装依赖 + 下 ffmpeg）
- **Windows**（PowerShell / Git Bash）：
  ```bat
  cd %USERPROFILE%\.workbuddy\skills\obsidian-idea-crawler
  setup.bat
  ```
- **macOS / Linux**：
  ```bash
  cd ~/.workbuddy/skills/obsidian-idea-crawler
  bash setup.sh
  ```
setup 会自动：
1. 用系统 / 托管 Python 建 `.venv`
2. `pip install yt-dlp httpx requests`（视频转写依赖）
3. 下载 ffmpeg 到 `bin/`（Windows 走 gyan.dev；mac/linux 走静态构建或包管理器）
4. 创建 `cookies/` 目录（放你的 cookie）

### 步骤 3：放入你的凭证（不打包、不外传）
- **小红书 cookie**：用浏览器插件 Cookie-Editor 从 `xiaohongshu.com` 导出 Netscape 格式 → 存为 `cookies/xiaohongshu.txt`
- **抖音 cookie**：同理从 `douyin.com` 网页版导出 → 存为 `cookies/douyin.txt`（B站无需 cookie）
- **SiliconFlow Key**（仅视频转写需要）：新建 `.venv/.env`，写入
  ```
  SILICONFLOW_API_KEY=sk-你的key
  ```
  （Key 只存隔离的 `.venv/.env`，**不要**提交到 Git / 发给任何人）

> 凭证过期后重导即可。Obsidian 仓库路径用环境变量 `EDEN_VAULT` 覆盖（默认 `~/Obsidian/EdenVault`）。

---

## 二、日常使用（在 WorkBuddy 对话里）

直接把链接发给我（在 WorkBuddy 对话里），我会按 skill 流程跑：

- **小红书**：`python3 scripts/xhs_pipe.py "<链接>" --tmp xhs_tmp_xxx`（从 `10-AI` 目录运行；Mac/Linux 用 python3，Windows 用 python）
- **抖音 / B站**：
  - Windows：`.venv\Scripts\python.exe scripts\vidpipe.py "<链接>"`
  - macOS / Linux：`.venv/bin/python scripts/vidpipe.py "<链接>"`
  - 想先验证链路：加 `--dry-run`（零花费）

爬完我（Agent）会自动读图 / 转写并补四段落地分析。

---

## 三、环境变量速查（均可选，不改也行）

| 变量 | 作用 | 默认 |
|---|---|---|
| `EDEN_VAULT` | 笔记输出根目录 | `~/Obsidian/EdenVault` |
| `IDEA_VENV` | 指定已装好依赖的 venv | `<skill>/.venv` |
| `XHS_COOKIE` | 覆盖小红书 cookie 路径 | `<skill>/cookies/xiaohongshu.txt` |
| `VIDKNOT_DOUYIN_COOKIE_FILE` | 覆盖抖音 cookie 路径 | `<skill>/cookies/douyin.txt` |
| `SILICONFLOW_API_KEY` | 转写 Key（也可写进 `.venv/.env`） | 从 `.venv/.env` 读 |

---

## 四、目录结构

```
obsidian-idea-crawler/
├── SKILL.md              # WorkBuddy 技能说明（触发/流程/排错）
├── README.md             # 本文件
├── setup.sh / setup.bat  # 一键安装依赖 + ffmpeg
├── scripts/
│   ├── xhs_pipe.py       # 小红书图文抓取
│   ├── vidpipe.py        # 抖音/B站 视频→转写
│   └── frame_extract.py  # 视频抽帧（画面 OCR 增强）
├── cookies/              # 放你的 xiaohongshu.txt / douyin.txt（不打包）
│   └── README.md
├── .venv/                # 依赖 venv（setup 生成，不打包）
└── bin/                  # ffmpeg（setup 下载，不打包）
```

> `cookies/`、`.venv/`、`.env`、`bin/` 含你的私人凭证与二进制，**请勿提交到公开仓库**。

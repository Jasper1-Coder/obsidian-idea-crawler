#!/usr/bin/env bash
# ============================================================
#  setup.sh —— obsidian-idea-crawler 一键安装（macOS / Linux）
#  建 .venv + 装依赖 + 下载 ffmpeg 到 bin/
# ============================================================
set -e
SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SKILL_DIR"

echo "============================================================"
echo " 注意：本 skill 需要 WorkBuddy 客户端（Mac / Win 版）才能"
echo " '在对话里发链接给我跑'。它不是浏览器插件，Chrome 无法运行。"
echo " 若只想纯命令行手动跑脚本也可，但需本机 Python 3.10+。"
echo "============================================================"

echo "[1/4] 检测 Python ..."
PYTHON="$(command -v python3 || command -v python)"
if [ -z "$PYTHON" ]; then echo "未找到 python3/python，请先安装 Python 3.10+"; exit 1; fi
echo "      使用: $PYTHON"

echo "[2/4] 建 venv ..."
if [ ! -d ".venv" ]; then
  "$PYTHON" -m venv .venv || { echo "创建 venv 失败"; exit 1; }
fi
. .venv/bin/activate
python -m pip install -U pip >/dev/null 2>&1

echo "[3/4] 装依赖 yt-dlp / httpx / requests ..."
pip install -U yt-dlp httpx requests || { echo "依赖安装失败（检查网络）"; exit 1; }

echo "[4/4] 准备 ffmpeg ..."
mkdir -p bin
if [ -x "bin/ffmpeg" ]; then
  echo "      ffmpeg 已存在，跳过"
else
  if command -v brew >/dev/null 2>&1; then
    echo "      通过 brew 安装 ffmpeg ..."
    brew install ffmpeg >/dev/null 2>&1 && cp "$(command -v ffmpeg)" bin/ffmpeg 2>/dev/null || true
  elif command -v apt-get >/dev/null 2>&1; then
    echo "      尝试 apt 安装 ffmpeg（可能需要 sudo）..."
    sudo apt-get install -y ffmpeg >/dev/null 2>&1 && cp "$(command -v ffmpeg)" bin/ffmpeg 2>/dev/null || true
  fi
  if [ ! -x "bin/ffmpeg" ]; then
    echo "      包管理器不可用，尝试下载静态构建 ..."
    OS="$(uname -s)"
    ARCH="$(uname -m)"
    if [ "$OS" = "Darwin" ]; then
      # 按芯片架构选 BtbN 静态构建（Apple Silicon / Intel）；evermeet.cx 已停服
      if [ "$ARCH" = "arm64" ]; then
        FURL="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-macos-arm64-gpl.zip"
      else
        FURL="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-macos64-gpl.zip"
      fi
    else
      FURL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
    fi
    curl -L -s -o bin/ffmpeg.zip "$FURL" 2>/dev/null || true
    if [ -f bin/ffmpeg.zip ]; then
      ( cd bin && tar -xf ffmpeg.zip >/dev/null 2>&1; find . -name ffmpeg -type f -exec cp {} ffmpeg \; 2>/dev/null )
      rm -f bin/ffmpeg.zip
      chmod +x bin/ffmpeg 2>/dev/null || true
    fi
  fi
  if [ -x "bin/ffmpeg" ]; then echo "      ffmpeg 已就位: bin/ffmpeg"; else echo "      自动下载失败，请手动安装 ffmpeg 并放到 bin/ 目录"; fi
fi

mkdir -p cookies
echo
echo "============ 安装完成 ============"
echo "下一步：把 cookie 放进 cookies/ 目录"
echo "  - cookies/xiaohongshu.txt  (小红书图文抓取必需)"
echo "  - cookies/douyin.txt       (抖音视频转写必需，B站不需要)"
echo "再新建 .venv/.env 写入：SILICONFLOW_API_KEY=sk-你的key   （仅视频转写需要）"
echo "然后直接在 WorkBuddy 里把链接发给我即可。"

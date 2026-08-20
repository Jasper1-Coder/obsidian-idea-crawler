#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
vidpipe.py —— 视频 → Obsidian 笔记 一键流水线
==============================================
把抖音 / B站 视频链接转成结构化知识笔记，存进 Obsidian 的 10-AI/ 目录。

流程：平台识别 → yt-dlp 下载 → ffmpeg 抽 16k 单声道 wav
      → SiliconFlow SenseVoice 转写 → 写 Markdown 笔记 → 清理临时文件

设计要点（来自实战踩坑）：
- 抖音必须带登录 Cookie（<skill>/cookies/douyin.txt），否则被登录墙挡住。
- 绝对不能把 .mp4 直接丢给转写接口（SiliconFlow 只收音频），必须先抽 wav。
- 转写 Key 从环境变量 SILICONFLOW_API_KEY 或 <venv>/.env 读，不写死在脚本里。
- 跑完删除临时 mp4/wav，只留笔记 + Cookie。

用法：
  python vidpipe.py "<视频链接>" [--title "标题"] [--dry-run]
  --dry-run  只验证 平台识别 / 可执行文件 / Cookie 有效性 / 标题抓取，不下载不转写（零花费）

依赖（用 skill 自带 .venv 的 python 跑，httpx / yt-dlp 都在那）：
  venv 默认 <skill>/.venv，可用环境变量 IDEA_VENV 覆盖。
"""

import os
import re
import sys
import json
import argparse
import tempfile
import subprocess
from datetime import datetime
from shutil import which

# ---------- 配置（路径默认相对 skill 目录，跨设备复制即用）----------
# 脚本位于 <skill>/scripts/vidpipe.py，skill 根目录 = 上两级
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# venv 默认建在 skill 自带的 .venv 里（随 skill 文件夹一起复制即迁移）；
# 也可用环境变量 IDEA_VENV 指向任意已装好依赖的 venv
VENV = os.environ.get("IDEA_VENV") or os.path.join(SKILL_DIR, ".venv")
ENV_FILE = os.path.join(VENV, ".env")
DEFAULT_VAULT = os.environ.get("EDEN_VAULT") or os.path.expanduser("~/Obsidian/EdenVault")
# 抖音 Cookie 默认放在 skill 自带的 cookies/douyin.txt（跨设备复制即用）；
# 也可用环境变量 VIDKNOT_DOUYIN_COOKIE_FILE 或 .env 同名字段覆盖
DEFAULT_COOKIE = os.environ.get("VIDKNOT_DOUYIN_COOKIE_FILE") or os.path.join(SKILL_DIR, "cookies", "douyin.txt")
TRANSCRIBE_URL = "https://api.siliconflow.cn/v1/audio/transcriptions"
MODEL = "FunAudioLLM/SenseVoiceSmall"

# 这些位置都试一遍，提升鲁棒性
FFMPEG_CANDIDATES = [
    os.path.join(SKILL_DIR, "bin", "ffmpeg.exe"),
    os.path.join(SKILL_DIR, "bin", "ffmpeg"),
    os.path.expanduser("~/AppData/Local/Microsoft/WinGet/Links/ffmpeg.EXE"),
    os.path.expanduser("~/.workbuddy/binaries/ffmpeg/bin/ffmpeg.exe"),
]
YTDLP_CANDIDATES = [
    os.path.join(VENV, "Scripts", "yt-dlp.exe"),
    os.path.join(VENV, "bin", "yt-dlp"),
    os.path.join(SKILL_DIR, "bin", "yt-dlp.exe"),
    os.path.join(SKILL_DIR, "bin", "yt-dlp"),
]

# “音频+画面”双通道增强：抽帧存这里（在 vault 外，Agent 之后 Read OCR）
FRAME_DIR = os.environ.get("EDEN_FRAME_DIR") or os.path.expanduser("~/.workbuddy/eden-frames")
FRAME_INTERVAL = 8      # 每 8 秒抽一帧
FRAME_MAX = 20          # 最多保留 20 帧（均匀采样，防爆 context）
# 只有这些扩展名才含画面，B站只下音频(m4a)不抽帧
VIDEO_EXTS = ("mp4", "webm", "mkv", "mov", "flv", "avi", "m4v")


# ---------- 工具函数 ----------
def load_env_file(path):
    """读 vidknot 的 .env，拿 Key / Vault / Cookie 路径（不含密钥落到日志）"""
    env = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env


def resolve_config():
    """优先级：进程环境变量 > skill .venv/.env > 默认值"""
    fe = load_env_file(ENV_FILE)
    api_key = os.environ.get("SILICONFLOW_API_KEY") or fe.get("SILICONFLOW_API_KEY", "")
    vault = (os.environ.get("EDEN_VAULT") or os.environ.get("OBSIDIAN_VAULT_PATH")
             or fe.get("OBSIDIAN_VAULT_PATH") or DEFAULT_VAULT)
    cookie = (os.environ.get("VIDKNOT_DOUYIN_COOKIE_FILE")
              or fe.get("VIDKNOT_DOUYIN_COOKIE_FILE") or DEFAULT_COOKIE)
    return api_key, vault, cookie


def find_exe(name, candidates=None):
    p = which(name)
    if p:
        return p
    for c in (candidates or []):
        if os.path.exists(c):
            return c
    return None


def detect_platform(url):
    u = url.lower()
    if "douyin.com" in u or "v.douyin" in u or "iesdouyin" in u:
        return "douyin"
    if "bilibili.com" in u or "b23.tv" in u:
        return "bilibili"
    return "unknown"


def safe_filename(s, maxlen=40):
    # Windows 会自动剥离路径末尾的空格/点，但 listdir 不会反向兼容，
    # 导致 makedirs 建了无空格目录、listdir 带空格查找而崩溃。
    # 这里显式 rstrip，并且截断后再 strip 一次，防止 maxlen 正好切在空格上。
    s = re.sub(r'[\\/:*?"<>|]', "_", s or "").strip().rstrip(". ")
    s = s[:maxlen].strip().rstrip(". ")
    return s or "video"


# ---------- 核心步骤 ----------
def download(url, platform, workdir, cookie):
    # 用 %(ext)s 模板，让 yt-dlp 按实际格式落正确的扩展名
    out_tmpl = os.path.join(workdir, "vid.%(ext)s")
    if platform == "bilibili":
        # B站是 DASH 分离流（视频/音频分开），没有合并 mp4。
        # 转写只需音频 → 只下最佳音频流，省带宽、避开格式匹配失败。
        cmd = [YTDLP, "-f", "ba[ext=m4a]/bestaudio", "--write-info-json", "-o", out_tmpl]
    else:
        cmd = [YTDLP, "-f", "best[ext=mp4]/best", "--write-info-json", "-o", out_tmpl]
    if platform == "douyin":
        if not os.path.exists(cookie):
            print(f"ERROR: 抖音 Cookie 不存在：{cookie}\n请让用户在抖音网页版用 Cookie-Editor 重导。", file=sys.stderr)
            sys.exit(2)
        cmd += ["--cookies", cookie]
    cmd += [url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("DOWNLOAD_FAIL:\n" + r.stderr, file=sys.stderr)
        sys.exit(3)
    # 找到下载下来的文件（覆盖视频与音频常见扩展名）
    candidates = (".mp4", ".webm", ".mkv", ".mov", ".m4a", ".aac", ".ogg", ".mka")
    mp4 = None
    for f in os.listdir(workdir):
        if f.startswith("vid") and f.endswith(candidates):
            mp4 = os.path.join(workdir, f)
            break
    if not mp4:
        print("DOWNLOAD_FAIL: 未找到下载文件", file=sys.stderr)
        sys.exit(3)
    return mp4


def extract_audio(mp4, workdir):
    wav = os.path.join(workdir, "vid.wav")
    cmd = [FFMPEG, "-y", "-i", mp4, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", wav]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(wav):
        print("AUDIO_FAIL:\n" + r.stderr, file=sys.stderr)
        sys.exit(4)
    return wav


def transcribe(wav, api_key):
    if not api_key:
        print("ERROR: 缺少 SILICONFLOW_API_KEY（环境变量或 vidknot .env）", file=sys.stderr)
        sys.exit(5)
    import httpx
    with open(wav, "rb") as f:
        files = {"file": ("audio.wav", f, "audio/wav")}
        data = {"model": MODEL, "language": "auto"}
        headers = {"Authorization": f"Bearer {api_key}"}
        r = httpx.post(TRANSCRIBE_URL, headers=headers, data=data, files=files, timeout=180)
    if r.status_code != 200:
        print(f"TRANSCRIBE_FAIL: {r.status_code}\n{r.text}", file=sys.stderr)
        sys.exit(6)
    return r.json().get("text", "")


def read_meta(workdir):
    """从 yt-dlp 写的 info.json 拿标题/时长"""
    title, duration = None, None
    for f in os.listdir(workdir):
        if f.endswith(".info.json"):
            try:
                with open(os.path.join(workdir, f), encoding="utf-8") as jf:
                    m = json.load(jf)
                title = m.get("title")
                duration = m.get("duration")
            except Exception:
                pass
            break
    return title, duration


def save_note(platform, url, title, duration, transcript, vault, frames=None):
    ai_dir = os.path.join(vault, "10-AI")
    os.makedirs(ai_dir, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    title = title or "untitled"
    base = f"{platform}-{safe_filename(title)}"
    path = os.path.join(ai_dir, base + ".md")
    # 防覆盖
    if os.path.exists(path):
        path = os.path.join(ai_dir, base + "-" + datetime.now().strftime("%H%M%S") + ".md")

    dur_str = f"{int(duration)}秒" if isinstance(duration, (int, float)) else "未知"
    frame_lines = "\n".join([f"- {p}" for p in (frames or [])]) or "_（本视频无画面 / 仅音频，未抽帧）_"
    content = f"""---
title: "{title}"
source: "{url}"
platform: {platform}
date_processed: {date}
duration: {dur_str}
tags: [AI工具, 视频笔记, 点子种子]
---

# {title}

## 核心观点（1 句话）
> _（待补充：用一句话概括这视频最值得记住的一个判断）_

## 关键要点
- _（待补充：3-5 条可执行的要点）_

## 💡 可落地想法（Prompt 种子）
> 以后想做项目时，把这段丢给任意 AI 说"照这个做"：
> **做 ___**：功能1 / 功能2 / 功能3 + 技术参考

## 原文转写（完整）
{transcript}

## 画面关键帧（已自动抽帧，待 WorkBuddy OCR 补画面内容）
{frame_lines}

---
## 🚀 点子落地分析（WorkBuddy 生成，勿删此段）
### 这个点子能变成什么
### 怎么用 / 往哪融（融入已有项目 / 新开项目）
### 需要调用的技术栈
### 能做出什么成效（对用户）
### 给你 3 个思路方向
### 待用户决策（融已有？新开？先攒？）
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def cleanup(workdir):
    for f in os.listdir(workdir):
        try:
            os.remove(os.path.join(workdir, f))
        except Exception:
            pass
    try:
        os.rmdir(workdir)
    except Exception:
        pass


# ---------- 入口 ----------
def main():
    global FFMPEG, YTDLP
    ap = argparse.ArgumentParser(description="视频 → Obsidian 笔记 一键流水线")
    ap.add_argument("url", help="抖音 / B站 视频链接")
    ap.add_argument("--title", default=None, help="视频标题（可选，用于命名；默认从视频元数据取）")
    ap.add_argument("--dry-run", action="store_true", help="只验证环境+链接，不下载不转写（零花费）")
    args = ap.parse_args()

    api_key, vault, cookie = resolve_config()
    FFMPEG = find_exe("ffmpeg", FFMPEG_CANDIDATES)
    YTDLP = find_exe("yt-dlp", YTDLP_CANDIDATES)

    platform = detect_platform(args.url)
    print(f"[平台] {platform}")
    print(f"[ffmpeg] {FFMPEG or '未找到!'}")
    print(f"[yt-dlp] {YTDLP or '未找到!'}")
    print(f"[vault]  {vault}")
    if platform == "douyin":
        print(f"[cookie] {cookie}  -> {'存在' if os.path.exists(cookie) else '缺失! 需重导'}")
    print(f"[apikey] {'已配置' if api_key else '缺失!'}")

    if platform == "unknown":
        print("ERROR: 不支持的平台（仅抖音/B站）", file=sys.stderr)
        sys.exit(1)
    if not FFMPEG or not YTDLP:
        print("ERROR: ffmpeg 或 yt-dlp 未找到", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        # 验证链接可达 + 标题可抓（不下载整视频、不转写）
        probe = [YTDLP, "--simulate", "--print", "%(title)s"]
        if platform == "douyin":
            if not os.path.exists(cookie):
                print("DRYRUN: Cookie 缺失，无法验证抖音链接"); sys.exit(2)
            probe += ["--cookies", cookie]
        probe += [args.url]
        r = subprocess.run(probe, capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            print(f"[dry-run] 链接有效，标题预览：{r.stdout.strip()[:60]}")
        else:
            print(f"[dry-run] 链接验证失败：\n{r.stderr[:500]}")
        print("DRYRUN_DONE（未下载/未转写，零花费）")
        return

    workdir = tempfile.mkdtemp(prefix="vidpipe_")
    try:
        mp4 = download(args.url, platform, workdir, cookie)
        wav = extract_audio(mp4, workdir)
        transcript = transcribe(wav, api_key)
        meta_title, duration = read_meta(workdir)
        title = args.title or meta_title
        base = f"{platform}-{safe_filename(title)}"
        # “音频+画面”双通道：仅对含画面的视频抽帧（B站只下音频跳过）
        frames = []
        vext = mp4.rsplit(".", 1)[-1].lower()
        if vext in VIDEO_EXTS:
            _here = os.path.dirname(os.path.abspath(__file__))
            sys.path.insert(0, _here)
            sys.path.insert(0, os.path.join(_here, "scripts"))
            import frame_extract
            frames = frame_extract.extract_frames(
                mp4, os.path.join(FRAME_DIR, base),
                interval=FRAME_INTERVAL, max_frames=FRAME_MAX,
            )
            print(f"FRAMES_EXTRACTED:{len(frames)} -> {os.path.join(FRAME_DIR, base)}")
        path = save_note(platform, args.url, title, duration, transcript, vault, frames=frames)
        print("NOTE_SAVED:" + path)
        print("TRANSCRIPT_LEN:" + str(len(transcript)))
    finally:
        cleanup(workdir)


if __name__ == "__main__":
    main()

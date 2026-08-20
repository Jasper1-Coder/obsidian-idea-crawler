#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xhs_pipe.py - 小红书图文笔记 → Obsidian 10-AI 骨架生成器

用法：
    python xhs_pipe.py "<小红书链接>" [--tmp xhs_tmp_xxx]

环境要求：
    - cookie 文件：默认 <skill>/cookies/xiaohongshu.txt（可用环境变量 XHS_COOKIE 覆盖）
    - curl 可用（Git Bash / WSL / Windows curl）
    - 输出目录：默认 $EDEN_VAULT/10-AI（可用环境变量 EDEN_VAULT 覆盖）

注意：从 10-AI 目录运行（或传 --tmp 绝对路径到 10-AI 下），图片相对路径才能在 Obsidian 里正确解析。
"""

import argparse
import html
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from urllib.parse import urlparse

# 脚本位于 <skill>/scripts/xhs_pipe.py，skill 根目录 = 上两级
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# cookie 默认放在 skill 自带 cookies/ 里，跨设备复制即用；也可被环境变量 XHS_COOKIE 覆盖
DEFAULT_COOKIE = os.environ.get("XHS_COOKIE") or os.path.join(
    SKILL_DIR, "cookies", "xiaohongshu.txt"
)
DEFAULT_OUTPUT = os.path.join(
    os.environ.get("EDEN_VAULT") or os.path.expanduser("~/Obsidian/EdenVault"),
    "10-AI",
)
DEFAULT_TMP = "xhs_tmp"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def fetch_html(url: str, cookie_path: str, tmp_dir: str) -> str:
    out = os.path.join(tmp_dir, "page.html")
    cmd = ["curl", "-s", "-b", cookie_path, "-A", UA, url, "-o", out]
    subprocess.run(cmd, check=False)
    return out


def extract_title(page_html: str) -> str:
    m = re.search(
        r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']',
        page_html,
    )
    if m:
        return html.unescape(m.group(1).strip())
    m = re.search(r"<title>([^<]+)</title>", page_html)
    if m:
        return html.unescape(m.group(1).strip())
    return "未命名小红书笔记"


def extract_desc(page_html: str) -> str:
    for key in ("description", "og:description"):
        m = re.search(
            rf'<meta[^>]*(?:name|property)=["\']{key}["\'][^>]*content=["\']([^"\']+)["\']',
            page_html,
        )
        if m:
            t = m.group(1).strip()
            # 小红书通用标语不是正文，过滤掉
            if "生活经验" not in t:
                return html.unescape(t)
    return ""


def extract_note_text(page_html: str) -> str:
    """从 window.__INITIAL_STATE__ 里提取小红书笔记正文。

    小红书 meta description 常被平台通用标语占据（'3 亿人的生活经验...'），
    真实正文在 __INITIAL_STATE__ JSON 的 'desc' 字段里。
    """
    idx = page_html.find("window.__INITIAL_STATE__=")
    if idx < 0:
        return ""
    start = page_html.find("{", idx)
    end = page_html.find("</script>", start)
    if start < 0 or end < 0:
        return ""
    raw = page_html[start:end].strip()
    if raw.endswith(";"):
        raw = raw[:-1]
    candidates = []
    for m in re.finditer(r'"desc":"([^"]{40,8000})"', raw):
        t = m.group(1).replace("\\n", "\n").replace("\\u002F", "/").replace("\\/", "/")
        t = html.unescape(t)
        if "生活经验" in t or "3 亿人" in t:
            continue
        candidates.append(t)
    if candidates:
        return max(candidates, key=len)
    return ""


def _extract_json_array(page_html: str, key: str) -> list:
    """用括号计数提取 key 后面的 JSON 数组，避免嵌套 [] 被正则截断。"""
    idx = page_html.find(f'"{key}":')
    if idx < 0:
        return []
    start = page_html.find("[", idx)
    if start < 0:
        return []
    depth = 0
    for i in range(start, len(page_html)):
        c = page_html[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                raw = page_html[start : i + 1]
                raw = raw.replace("\\u002F", "/").replace("\\/", "/").replace('\\"', '"')
                try:
                    return json.loads(raw)
                except Exception:
                    return []
    return []


def extract_image_urls(page_html: str) -> list:
    urls = []
    seen = set()

    # og:image
    for m in re.finditer(
        r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']//?([^"\']+)["\']',
        page_html,
    ):
        u = m.group(1)
        if u.startswith("//"):
            u = "http:" + u
        elif not u.startswith("http"):
            u = "http://" + u
        if u not in seen:
            seen.add(u)
            urls.append(u)

    # 小红书图文笔记的真实图片在 imageList JSON 数组里（支持多图轮播）
    for item in _extract_json_array(page_html, "imageList"):
        chosen = ""
        for info in item.get("infoList", []):
            scene = info.get("imageScene", "")
            if scene in ("ORIGIN", "CRD_WM_JPG", "WB_LSD", "WB_PRV", "WB_DFT"):
                chosen = info.get("url", "")
                if scene == "ORIGIN":
                    break
        if not chosen:
            chosen = item.get("url", "")
        if chosen:
            chosen = chosen.replace("\\u002F", "/").replace("\\/", "/")
            if chosen.startswith("//"):
                chosen = "http:" + chosen
            elif not chosen.startswith("http"):
                chosen = "http://" + chosen
            if chosen not in seen:
                seen.add(chosen)
                urls.append(chosen)

    # 兜底：JSON 里的 urlDefault / urlPre 等字段
    for m in re.finditer(
        r'"url(?:Default|Pre|Pre12w|PreOrigin)?":"(https?:\\?/\\?/[^"\\]+?)"',
        page_html,
    ):
        u = m.group(1).replace("\\/", "/")
        if any(e in u for e in [".jpg", ".png", ".webp", ".jpeg"]) and u not in seen:
            seen.add(u)
            urls.append(u)

    # 兜底：直接 CDN
    for m in re.finditer(
        r'(https?:\\?/\\?/(?:picasso-static|xhs|sns-webpic)[^"\\]+?\.(?:jpg|jpeg|png|webp))',
        page_html,
    ):
        u = m.group(1).replace("\\/", "/")
        if u not in seen:
            seen.add(u)
            urls.append(u)

    return urls


def download_images(urls: list, img_dir: str, cookie_path: str = "") -> list:
    os.makedirs(img_dir, exist_ok=True)
    paths = []
    for i, u in enumerate(urls):
        ext = u.split("?")[0].split(".")[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"
        out = os.path.join(img_dir, f"img_{i:02d}.{ext}")
        # 小红书图片 CDN 有防盗链：必须带 Referer + Cookie 才能取到真实图，否则返回 logo 占位图
        cmd = ["curl", "-s", "-A", UA, "-H", "Referer: https://www.xiaohongshu.com", "-o", out, u]
        if cookie_path and os.path.exists(cookie_path):
            cmd += ["-b", cookie_path]
        subprocess.run(cmd, check=False)
        if os.path.exists(out) and os.path.getsize(out) > 1024:
            paths.append(out)
    return paths


def sanitize_filename(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]', "_", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:80]


def detect_video(page_html: str) -> bool:
    """小红书笔记也可能是视频（封面图 + 视频流），通过 html 里的 \"video\": 字段判断。"""
    return '"video":' in page_html and '"streamTypes"' in page_html


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--cookie", default=DEFAULT_COOKIE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--tmp", default=DEFAULT_TMP)
    args = parser.parse_args()

    if not os.path.exists(args.cookie):
        print(f"Cookie file not found: {args.cookie}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.tmp, exist_ok=True)
    html_path = fetch_html(args.url, args.cookie, args.tmp)
    if not os.path.exists(html_path) or os.path.getsize(html_path) < 1024:
        print("Failed to fetch HTML", file=sys.stderr)
        sys.exit(1)

    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    title = extract_title(html)
    desc = extract_desc(html)
    note_text = extract_note_text(html)
    if note_text:
        desc = note_text
    is_video = detect_video(html)

    imgs = extract_image_urls(html)
    img_dir = os.path.join(args.tmp, "images")
    img_paths = download_images(imgs, img_dir, args.cookie)

    safe_title = sanitize_filename(title)
    md_path = os.path.join(args.output, f"xhs-{safe_title}.md")
    os.makedirs(args.output, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    img_lines = "\n".join([f"- {p}" for p in img_paths]) or "_无图片_"

    if is_video:
        note_type = "视频笔记（图文封面 + 视频主讲）"
        fetch_method = "curl+cookie 抓 HTML 取封面；视频正文由 Agent 走 yt-dlp+cookie 下载 → ffmpeg 抽 16k wav → SenseVoice 转写 → frame_extract 抽关键帧（每8秒1帧，最多20帧）→ Read OCR 画面"
        video_note = "\n> ⚠️ 检测到该小红书笔记为**视频笔记**。xhs_pipe 已自动取封面；视频正文 Agent 会走\"下载→音频转写→抽帧→OCR 画面\"双通道处理，无需额外操作。"
    else:
        note_type = "图文笔记（文字+图片）"
        fetch_method = "curl+cookie 抓 HTML，提取图片并本地 OCR"
        video_note = ""

    content = f"""---
title: "{title}"
source: "{args.url}"
platform: xiaohongshu
date_processed: {date_str}
note_type: {note_type}
fetch_method: {fetch_method}
tags: [小红书, 内容搬运, 待分类]
---

# {title}
{video_note}

> 来源：小红书 ｜ 分类：待 Agent 判定

## 核心观点（1 句话）
> _（待补充）_

## 关键要点
- _（待补充：结合 HTML 原文与图片 OCR）_

## 💡 可落地想法（Prompt 种子）
> _（待补充）_

## 原文转写（从 HTML / 图片 OCR 整理）
{desc}

*图片列表（已下载到本地）：*
{img_lines}

*原始 HTML 文件：* `{html_path}`

---
## 🚀 点子落地分析（WorkBuddy 生成，勿删此段）
### 这个点子能变成什么
### 怎么用 / 往哪融（融入已有项目 / 新开项目）
### 需要调用的技术栈
### 能做出什么成效（对用户）
### 给你 3 个思路方向
### 待用户决策（融已有？新开？先攒？）
"""
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"SAVED {md_path}")
    print(f"HTML {html_path}")
    print(f"IMAGES {img_dir}")
    print(f"IMAGE_COUNT {len(img_paths)}")


if __name__ == "__main__":
    main()

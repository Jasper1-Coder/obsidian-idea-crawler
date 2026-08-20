#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""frame_extract.py —— 视频均匀抽关键帧（"音频+画面"双通道增强）

把视频按固定时间间隔抽成一帧帧 jpg，供 WorkBuddy 用 Read 多模态 OCR 画面文字。
不依赖任何第三方库，只调系统 ffmpeg。

用法（两个 skill 共用，绝对路径调用即可）：
  python frame_extract.py <video_path> <out_dir> [--interval 8] [--max 20]
返回：stdout 输出 JSON 数组（抽到的帧绝对路径），便于调用方写进笔记。

设计要点：
- fps=1/interval：每 interval 秒抽一帧，避免帧过多爆 context。
- 超过 max_frames 则均匀保留，重点时段不丢。
- 只认 >2KB 的 jpg，过滤 ffmpeg 生成的空占位。
"""
import os
import sys
import json
import subprocess
import argparse

# 脚本位于 <skill>/scripts/frame_extract.py，skill 根目录 = 上两级
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FFMPEG_CANDIDATES = [
    os.path.join(SKILL_DIR, "bin", "ffmpeg.exe"),
    os.path.join(SKILL_DIR, "bin", "ffmpeg"),
    os.path.expanduser("~/AppData/Local/Microsoft/WinGet/Links/ffmpeg.EXE"),
    os.path.expanduser("~/.workbuddy/binaries/ffmpeg/bin/ffmpeg.exe"),
]


def find_ffmpeg():
    for c in FFMPEG_CANDIDATES:
        if os.path.exists(c):
            return c
    return "ffmpeg"


def _valid_frames(out_dir):
    """列出目录里大于 2KB 的有效 jpg 帧，按文件名排序。"""
    return sorted(
        os.path.join(out_dir, f)
        for f in os.listdir(out_dir)
        if f.endswith(".jpg") and os.path.getsize(os.path.join(out_dir, f)) > 2000
    )


def extract_frames(video_path, out_dir, interval=8, max_frames=20):
    # Windows 会自动剥离路径末尾空格/点，listdir 却按原串查找会崩溃，
    # 这里先规范化，保证 makedirs 与 listdir 用同一个一致路径。
    out_dir = out_dir.rstrip(" .")
    os.makedirs(out_dir, exist_ok=True)

    # 快路径：目录里已有足够有效帧，直接复用，不再调用 ffmpeg
    existing = _valid_frames(out_dir)
    if len(existing) >= max_frames:
        return existing[:max_frames]

    ffmpeg = find_ffmpeg()
    pat = os.path.join(out_dir, "frame_%03d.jpg")
    subprocess.run(
        [ffmpeg, "-y", "-i", video_path, "-vf", f"fps=1/{interval}", pat],
        capture_output=True,
        text=True,
    )
    frames = _valid_frames(out_dir)

    # 超过上限则均匀保留子集返回，**不删除**多余帧——
    # WorkBuddy 沙箱会拦截批量 os.remove，触发 SAFE_DELETE_BULK_CONFIRM_REQUIRED。
    # 多余帧留在目录里 harmless，下次调用快路径直接复用。
    if len(frames) > max_frames:
        keep_idx = set(
            int(round(i * (len(frames) - 1) / (max_frames - 1)))
            for i in range(max_frames)
        )
        frames = sorted([frames[i] for i in keep_idx])
    return frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out_dir")
    ap.add_argument("--interval", type=int, default=8)
    ap.add_argument("--max", type=int, default=20)
    args = ap.parse_args()
    frames = extract_frames(args.video, args.out_dir, args.interval, args.max)
    print(json.dumps(frames, ensure_ascii=False))


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""三个 GIF 交替播放，每个 GIF 展示 0.5 秒后切换到下一个，无限循环"""
from PIL import Image

SRCS = ["glitched_yishuhua-1.gif", "glitched_yishuhua-2.gif", "glitched_yishuhua-3.gif"]
OUT = "glitched_yishuhua_alternating.gif"
SEGMENT_MS = 500  # 每个 GIF 停留的时长（毫秒）


def load_frames(path):
    """读取每个 GIF 的全部 RGB 帧和原始帧时长"""
    frames, durations = [], []
    with Image.open(path) as im:
        for i in range(getattr(im, "n_frames", 1)):
            im.seek(i)
            frames.append(im.convert("RGB"))
            durations.append(int(im.info.get("duration") or 100))
    return frames, durations


def rescale(durations):
    """把帧时长按比例压缩，使整个 GIF 段落总时长等于 SEGMENT_MS"""
    total = sum(durations)
    n = len(durations)
    ms = [max(20, round(d * SEGMENT_MS / total)) for d in durations]
    # 修正四舍五入带来的误差，保证段落总时长为 SEGMENT_MS
    diff = SEGMENT_MS - sum(ms)
    if diff != 0 and n > 0:
        ms[-1] = max(20, ms[-1] + diff)
    return ms


def main():
    all_frames, all_durations = [], []
    for path in SRCS:
        frames, durations = load_frames(path)
        print(f"{path}: {len(frames)} frames, 原始 {sum(durations) / 1000:.2f}s -> 压缩为 {SEGMENT_MS / 1000:.2f}s")
        ms = rescale(durations)
        all_frames.extend(frames)
        all_durations.extend(ms)

    all_frames[0].save(
        OUT,
        save_all=True,
        append_images=all_frames[1:],
        duration=all_durations,
        loop=0,
        optimize=False,
    )
    print("saved:", OUT, f"({len(all_frames)} frames, 一轮循环 {sum(all_durations) / 1000:.2f}s)")


if __name__ == "__main__":
    main()

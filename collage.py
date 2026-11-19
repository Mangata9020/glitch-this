# -*- coding: utf-8 -*-
"""把三张图片拼贴成一张不规则形状的拼贴画"""
import math
import random
from PIL import Image, ImageDraw, ImageFilter

random.seed(42)

CANVAS_W, CANVAS_H = 1600, 1200
BG_COLOR = (238, 234, 228)  # 米白纸底

SRC = ["yishuhua-1.jpg", "yishuhua-2.jpg", "yishuhua-3.jpg"]
OUT = "yishuhua_collage.png"

# 每张图的位置/缩放/旋转（从后往前叠放）
LAYOUT = [
    dict(center=(560, 480),  target_h=900, rot=-7),
    dict(center=(1050, 430), target_h=850, rot=6),
    dict(center=(830, 760),  target_h=880, rot=-3),
]

JAG = 18      # 边缘锯齿幅度
STEPS = 26    # 每条边的扰动采样数
BORDER = 26   # 白边宽度


def irregular_polygon(w, h):
    """生成一个不规则四边形（角点和边线都带随机扰动）"""
    pts = []
    corners = [(0, 0), (w, 0), (w, h), (0, h)]
    for i, (cx, cy) in enumerate(corners):
        pts.append((cx + random.uniform(-JAG * 2, JAG * 2),
                    cy + random.uniform(-JAG * 2, JAG * 2)))
    # 在每条边上插入扰动点，形成手撕/剪裁效果
    poly = []
    for i in range(4):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % 4]
        for t in [k / STEPS for k in range(STEPS)]:
            x = x1 + (x2 - x1) * t + random.uniform(-JAG, JAG)
            y = y1 + (y2 - y1) * t + random.uniform(-JAG, JAG)
            poly.append((x, y))
    return poly


def expand_polygon(poly, d):
    """把多边形沿质心方向外扩 d 像素（用于白边）"""
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    out = []
    for x, y in poly:
        dx, dy = x - cx, y - cy
        r = math.hypot(dx, dy) or 1.0
        out.append((x + dx / r * d, y + dy / r * d))
    return out


def make_piece(img, target_h):
    """缩放图片，裁成不规则多边形，带白边，返回带透明通道的碎片"""
    scale = target_h / img.height
    w, h = int(img.width * scale), int(img.height * scale)
    img = img.resize((w, h), Image.LANCZOS).convert("RGB")

    poly = irregular_polygon(w, h)
    pad = BORDER + JAG * 3
    piece = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    poly_pad = [(x + pad, y + pad) for x, y in poly]

    # 白边（外扩多边形）
    border_mask = Image.new("L", piece.size, 0)
    ImageDraw.Draw(border_mask).polygon(expand_polygon(poly_pad, BORDER), fill=255)
    white = Image.new("RGBA", piece.size, (250, 248, 244, 255))
    piece.paste(white, (0, 0), border_mask)

    # 图片内容
    mask = Image.new("L", piece.size, 0)
    ImageDraw.Draw(mask).polygon(poly_pad, fill=255)
    piece.paste(img, (pad, pad), mask)
    return piece, poly_pad


def make_shadow(piece, blur=14, alpha=110):
    """根据碎片 alpha 通道生成投影"""
    sh = Image.new("RGBA", piece.size, (0, 0, 0, 0))
    a = piece.split()[3].point(lambda v: min(v, alpha))
    sh.paste((30, 25, 20, alpha), (0, 0), a)
    # 只保留 alpha 通道做模糊
    alpha_blur = a.filter(ImageFilter.GaussianBlur(blur))
    shadow = Image.new("RGBA", piece.size, (0, 0, 0, 0))
    shadow.putalpha(alpha_blur)
    return shadow


def main():
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), BG_COLOR)
    # 纸底加一点噪点纹理
    noise = Image.effect_noise((CANVAS_W, CANVAS_H), 12).convert("L")
    canvas = Image.composite(
        Image.new("RGB", canvas.size, (228, 223, 214)), canvas, noise.point(lambda v: 40 if v > 200 else 0)
    ).convert("RGBA")

    for path, cfg in zip(SRC, LAYOUT):
        img = Image.open(path)
        piece, _ = make_piece(img, cfg["target_h"])
        piece = piece.rotate(cfg["rot"], expand=True, resample=Image.BICUBIC)

        shadow = make_shadow(piece)
        px = int(cfg["center"][0] - piece.width / 2)
        py = int(cfg["center"][1] - piece.height / 2)

        canvas.alpha_composite(shadow, (px + 10, py + 14))
        canvas.alpha_composite(piece, (px, py))

    canvas.convert("RGB").save(OUT, quality=95)
    print("saved:", OUT)


if __name__ == "__main__":
    main()

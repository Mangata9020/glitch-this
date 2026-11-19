# -*- coding: utf-8 -*-
"""三个 glitched GIF 不规则拼贴（透明背景版）：
- 去掉白色背景板，输出为透明图层
- 每张图应用不同方向的故障效果（水平错位 / 垂直错位 / 对角剪切）
- 每张图单独输出为独立图层 PNG，另合并输出透明 PNG 与动画 APNG
"""
import random
from PIL import Image, ImageSequence, ImageFilter, ImageDraw, ImageChops

paths = [rf"D:\DigitalMediaArt\glitch-this\glitched_yishuhua-{i}.gif" for i in (1, 2, 3)]

# 不规则布局：缩放、旋转角度、故障方向、位置
layout = [
    {"scale": 1.00, "angle": -12, "glitch": "h",   "pos": (60, 40)},    # 左上，水平错位
    {"scale": 0.80, "angle": 8,   "glitch": "v",   "pos": (1150, 420)}, # 中部，垂直错位
    {"scale": 0.85, "angle": -5,  "glitch": "diag", "pos": (2180, 80)},  # 右侧，对角剪切
]

# ---------- 故障效果 ----------
def glitch_h(im, seed):
    """水平方向：随机条带左右错位"""
    im = im.copy()
    rnd = random.Random(seed)
    w, h = im.size
    for _ in range(rnd.randint(6, 10)):
        y = rnd.randint(0, max(1, h - 12))
        bh = rnd.randint(4, max(6, h // 12))
        sh = rnd.randint(-w // 18, w // 18)
        band = im.crop((0, y, w, min(h, y + bh)))
        im.paste(band, (sh, y), band)
    return im

def glitch_v(im, seed):
    """垂直方向：随机条带上下错位"""
    im = im.copy()
    rnd = random.Random(seed)
    w, h = im.size
    for _ in range(rnd.randint(6, 10)):
        x = rnd.randint(0, max(1, w - 12))
        bw = rnd.randint(4, max(6, w // 14))
        sh = rnd.randint(-h // 14, h // 14)
        band = im.crop((x, 0, min(w, x + bw), h))
        im.paste(band, (x, sh), band)
    return im

def glitch_diag(im, seed):
    """对角方向：整体剪切 + 随机条带沿对角错位"""
    rnd = random.Random(seed)
    w, h = im.size
    shear = rnd.choice([-1, 1]) * (0.08 + rnd.random() * 0.06)
    im = im.transform((w, h), Image.AFFINE, (1, shear, -shear * h / 2, 0, 1, 0), resample=Image.BICUBIC)
    for _ in range(rnd.randint(4, 7)):
        y = rnd.randint(0, max(1, h - 12))
        bh = rnd.randint(4, max(6, h // 14))
        sh = int((y / h - 0.5) * w * 0.25) + rnd.randint(-20, 20)
        band = im.crop((0, y, w, min(h, y + bh)))
        im.paste(band, (sh, y), band)
    return im

GLITCH_FN = {"h": glitch_h, "v": glitch_v, "diag": glitch_diag}

POSITIONS = [cfg["pos"] for cfg in layout]  # 3 个可选位置
SWAP_FRAMES = 5                              # 每 5 帧（200ms×5=1 秒）互换一次位置

def pos_of(layer_idx, offset):
    """第 layer_idx 张图在轮换 offset 下的位置（三张图循环轮换）"""
    return POSITIONS[(layer_idx + offset) % len(POSITIONS)]

# ---------- 预处理 ----------
imgs = [Image.open(p) for p in paths]
base_h = max(im.height for im in imgs)

def torn_mask(size, seed):
    """生成撕纸毛边遮罩：白芯 + 随机抖动的粗糙边缘"""
    w, h = size
    rnd = random.Random(seed)
    m = max(8, min(w, h) // 30)     # 边缘内缩距离
    amp = max(3, min(w, h) // 45)   # 撕边抖动幅度
    step = max(5, min(w, h) // 45)  # 采样步长
    def j(v):
        return v + rnd.randint(-amp, amp)
    pts = []
    x = 0
    while x < w:                       # 上边
        pts.append((x, j(m))); x += step
    pts.append((w - m, m))
    y = 0
    while y < h:                       # 右边
        pts.append((w - j(m), y)); y += step
    pts.append((w - m, h - m))
    x = w
    while x > 0:                       # 下边
        pts.append((x, h - j(m))); x -= step
    pts.append((m, h - m))
    y = h
    while y > 0:                       # 左边
        pts.append((j(m), y)); y -= step
    pts.append((m, m))
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(1.2))

def prepare_layer(im, cfg, seed, mask):
    """单张图：缩放 → 故障 → 撕边 → 旋转 → 带投影"""
    h = round(base_h * cfg["scale"])
    f = im.convert("RGBA").resize((round(im.width * h / im.height), h), Image.LANCZOS)
    f = GLITCH_FN[cfg["glitch"]](f, seed)
    f.putalpha(ImageChops.multiply(f.split()[3], mask))
    f = f.rotate(cfg["angle"], expand=True, resample=Image.BICUBIC)
    # 投影
    alpha = f.split()[3]
    shadow = Image.new("RGBA", f.size, (20, 20, 20, 255))
    shadow.putalpha(alpha.point(lambda a: int(a * 0.55)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    return f, shadow

def make_canvas():
    return Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

TRANSITION_FRAMES = 3  # 每段 5 帧中前 3 帧（600ms）做幻灯片式滑动过渡，后 2 帧停住

def ease(t):
    """平滑缓动（smoothstep），滑动起步和停止更自然"""
    return t * t * (3 - 2 * t)

def lerp_pos(p0, p1, k):
    return (round(p0[0] + (p1[0] - p0[0]) * k), round(p0[1] + (p1[1] - p0[1]) * k))

def current_pos(li, frame_idx):
    """第 li 张图在第 frame_idx 帧的位置：每段开头平滑滑到新位置，之后停住"""
    seg = frame_idx // SWAP_FRAMES
    offset = seg % len(POSITIONS)
    t = frame_idx % SWAP_FRAMES
    if t >= TRANSITION_FRAMES:
        return pos_of(li, offset)
    prev_offset = (seg - 1) % len(POSITIONS)  # 循环点上从上一段滑入，衔接无缝
    k = ease(t / TRANSITION_FRAMES)
    return lerp_pos(pos_of(li, prev_offset), pos_of(li, offset), k)

def combine(frame_idx):
    """把某一帧的所有图层按布局合成到透明画布（滑动换位 + 故障动画）"""
    canvas = make_canvas()
    for li, cfg in enumerate(layout):
        f, shadow = layers[li][frame_idx % len(layers[li])]
        x, y = current_pos(li, frame_idx)
        canvas.alpha_composite(shadow, (x + 18, y + 22))
        canvas.alpha_composite(f, (x, y))
    return canvas

def combine_static():
    """静态排布：三张图各就位（偏移 0），不做过渡"""
    canvas = make_canvas()
    for li, cfg in enumerate(layout):
        f, shadow = layers[li][0]
        x, y = pos_of(li, 0)
        canvas.alpha_composite(shadow, (x + 18, y + 22))
        canvas.alpha_composite(f, (x, y))
    return canvas

# 计算画布尺寸（覆盖所有轮换组合，保证互换时不出界）
imgs_h = []
for im, cfg in zip(imgs, layout):
    h = round(base_h * cfg["scale"])
    imgs_h.append(im.convert("RGBA").resize((round(im.width * h / im.height), h), Image.LANCZOS)
                  .rotate(cfg["angle"], expand=True, resample=Image.BICUBIC))
max_w = max(pos_of(li, off)[0] + f.width
            for off in range(len(POSITIONS))
            for li, f in [(li, imgs_h[li]) for li in range(len(imgs_h))])
max_h = max(pos_of(li, off)[1] + f.height
            for off in range(len(POSITIONS))
            for li, f in [(li, imgs_h[li]) for li in range(len(imgs_h))])
margin = 50
canvas_w, canvas_h = max_w + margin, max_h + margin

# 每个 GIF 的全部帧都应用各自的故障效果（seed 随帧变化，动画时故障会跳动）
# 撕边遮罩每层固定一个，边缘不会逐帧闪烁
layers = []
for li, (im, cfg) in enumerate(zip(imgs, layout)):
    h = round(base_h * cfg["scale"])
    first = im.convert("RGBA").resize((round(im.width * h / im.height), h), Image.LANCZOS)
    mask = torn_mask(first.size, seed=li * 77 + 13)
    frames = [prepare_layer(f, cfg, seed=li * 1000 + fi, mask=mask) for fi, f in enumerate(ImageSequence.Iterator(im))]
    layers.append(frames)

n_frames = max(len(fr) for fr in layers)
out_dir = r"D:\DigitalMediaArt\glitch-this"

# 1) 独立图层 PNG（透明背景，各占一层，互不合并）
for li, cfg in enumerate(layout):
    f, shadow = layers[li][0]
    layer_img = make_canvas()
    x, y = pos_of(li, 0)
    layer_img.alpha_composite(shadow, (x + 18, y + 22))
    layer_img.alpha_composite(f, (x, y))
    layer_img.save(rf"{out_dir}\collage_layer_{li + 1}.png")
print(f"已保存 3 个独立透明图层: collage_layer_1~3.png  (画布 {canvas_w}x{canvas_h})")

# 2) 合成的透明静态图
static = combine_static()
static.save(rf"{out_dir}\collage_yishuhua_irregular.png")
print("透明背景静态拼贴图已保存: collage_yishuhua_irregular.png")

# 3) 3D 环绕动画：三张图绕中心球沿椭圆轨道匀速旋转（近大远小、前后遮挡、深度透明度）
import math

ORBIT_MS = 16                       # 每帧 16ms（60fps，运动平滑无跳变）
DEPTH_SCALE = 0.20                  # 深度引起的缩放幅度（前面放大、后面缩小）
DEPTH_ALPHA = 0.25                  # 深度引起的透明度幅度

imgs_h_max_w = max(f.width for f in imgs_h)
imgs_h_max_h = max(f.height for f in imgs_h)
SCENE = 0.42                        # 场景整体缩放，控制动画尺寸与体积
IMG_SCALE = 1.50                    # 图片相对轨道的放大系数（表现力）
Rx0 = imgs_h_max_w * 1.45           # 轨道横向半径（原始单位）
Ry0 = imgs_h_max_h * 1.30           # 轨道纵向半径（上下绕的摆幅）
# 三种绕法轮换：上下绕一圈 → 斜着绕一圈 → 左右旋转一圈，循环往复
FRAMES_PER_LOOP = 180    # 每个绕法一圈的帧数（16ms×180 ≈ 3 秒/圈）
TRANSITION_FRAMES = 16   # 相邻绕法之间的平滑过渡帧数（约 0.26 秒）
OUT_SCALE = 0.5          # 输出缩放：降低单帧像素量，播放器解码更跟手、不卡顿
N_PHASES = 3

def _norm(vec):
    l = math.sqrt(sum(c * c for c in vec))
    return tuple(c / l for c in vec)

# 每种绕法由轨道平面基向量 u(cosθ 方向)、v(sinθ 方向) 定义，分量为 屏幕x / 屏幕y / 深度z
ORBITS = [
    _norm((0.55, 0.00, 0.84)), _norm((0.10, 0.99, 0.00)),    # 0 上下绕：竖直大摆动 + 前后纵深
    _norm((0.72, 0.45, 0.25)), _norm((-0.28, 0.62, 0.75)),   # 1 斜着绕：对角平面盘旋
    _norm((1.00, 0.00, 0.00)), _norm((0.00, 0.30, 0.95)),    # 2 左右旋转：水平转盘
]

def plane_basis(frame_idx):
    """当前帧的轨道平面基向量；每圈开头从上一绕法平滑旋转过渡"""
    seg = frame_idx // FRAMES_PER_LOOP
    t = frame_idx % FRAMES_PER_LOOP
    ci = 2 * (seg % N_PHASES)
    cur_u, cur_v = ORBITS[ci], ORBITS[ci + 1]
    if t >= TRANSITION_FRAMES:
        return cur_u, cur_v
    pi = 2 * ((seg - 1) % N_PHASES)
    prev_u, prev_v = ORBITS[pi], ORBITS[pi + 1]
    k = ease(t / TRANSITION_FRAMES)
    u = _norm(tuple(prev_u[i] + (cur_u[i] - prev_u[i]) * k for i in range(3)))
    v = _norm(tuple(prev_v[i] + (cur_v[i] - prev_v[i]) * k for i in range(3)))
    return u, v

def orbit_state(frame_idx, li):
    """第 li 张图在第 frame_idx 帧的：屏幕偏移 x/y、尺寸缩放 s、深度 dn(-1~1)"""
    # 规律旋转：三张纸均分 120°，绕球匀速转动
    theta = 2 * math.pi * frame_idx / FRAMES_PER_LOOP + li * (2 * math.pi / len(layout))
    u, v = plane_basis(frame_idx)
    ux, uy, uz = u
    vx, vy, vz = v
    ct, st = math.cos(theta), math.sin(theta)
    return (Rx * (ux * ct + vx * st), Ry * (uy * ct + vy * st),
            1 + DEPTH_SCALE * (uz * ct + vz * st), uz * ct + vz * st)

# 数值采样全部帧，计算画布外接范围
Rx, Ry = Rx0 * SCENE, Ry0 * SCENE
half_w = half_h = 0.0
for i in range(FRAMES_PER_LOOP * N_PHASES):
    for li in range(len(imgs_h)):
        off_x, off_y, s, _ = orbit_state(i, li)
        f0 = imgs_h[li]
        half_w = max(half_w, abs(off_x) + f0.width * s * SCENE * IMG_SCALE * 0.65)
        half_h = max(half_h, abs(off_y) + f0.height * s * SCENE * IMG_SCALE * 0.65)
orbit_cw = 2 * round(half_w) + 40
orbit_ch = 2 * round(half_h) + 40
cx, cy = orbit_cw // 2, orbit_ch // 2
ball_r = round(0.46 * Ry)          # 球体按轨道半径取值，图片放大时球保持原大小

def make_ball(radius):
    """中心透明玻璃球：淡色透体 + 菲涅尔边缘 + 折射暗环 + 双高光 + 底部焦散光"""
    size = radius * 2
    grad = Image.radial_gradient("L").resize((size, size), Image.BILINEAR)  # 中心 0 → 边缘 255
    # 圆形遮罩（4 倍超采样抗锯齿）
    big = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(big).ellipse([0, 0, size * 4 - 1, size * 4 - 1], fill=255)
    circle = big.resize((size, size), Image.LANCZOS)

    # 1) 玻璃透体：更清澈透明，中心几乎全透、仅边缘略密（菲涅尔效应）
    ball = Image.new("RGBA", grad.size, (198, 218, 242, 255))
    tint_a = grad.point(lambda v: int(9 + 82 * (v / 255) ** 2.6))
    ball.putalpha(ImageChops.multiply(tint_a, circle))

    def layer(color, alpha_img):
        """按 alpha 遮罩叠加一层颜色（限制在球体圆内）"""
        img = Image.new("RGBA", grad.size, color + (255,))
        img.putalpha(ImageChops.multiply(alpha_img, circle))
        return img

    # 2) 外缘白色亮环（玻璃表面反光）
    ring = grad.point(lambda v: 255 if v >= 212 else 0).filter(ImageFilter.GaussianBlur(radius * 0.025))
    ring = ring.point(lambda v: int(v * 0.70))
    ball.alpha_composite(layer((246, 250, 255), ring))

    # 2b) 最外沿细亮线（勾勒球体轮廓，透明背景下也能看清形状）
    outline = grad.point(lambda v: 255 if v >= 247 else 0).filter(ImageFilter.GaussianBlur(radius * 0.008))
    ball.alpha_composite(layer((255, 255, 255), outline))

    # 2c) 外沿极细暗边（白底图片上也能分辨球的边界）
    darkline = grad.point(lambda v: 255 if 238 <= v < 247 else 0).filter(ImageFilter.GaussianBlur(radius * 0.006))
    darkline = darkline.point(lambda v: int(v * 0.30))
    ball.alpha_composite(layer((24, 34, 56), darkline))

    # 3) 内侧暗环（玻璃厚度的折射边）
    ring2 = grad.point(lambda v: 255 if 180 <= v < 212 else 0).filter(ImageFilter.GaussianBlur(radius * 0.02))
    ring2 = ring2.point(lambda v: int(v * 0.22))
    ball.alpha_composite(layer((30, 42, 70), ring2))

    # 3a) 球心白色发光小球：亮核 + 柔和光晕
    core = Image.new("L", grad.size, 0)
    ImageDraw.Draw(core).ellipse([size * 0.43, size * 0.43, size * 0.57, size * 0.57], fill=255)
    core = core.filter(ImageFilter.GaussianBlur(radius * 0.035))
    ball.alpha_composite(layer((255, 255, 255), core))
    halo = Image.new("L", grad.size, 0)
    ImageDraw.Draw(halo).ellipse([size * 0.33, size * 0.33, size * 0.67, size * 0.67], fill=40)
    halo = halo.filter(ImageFilter.GaussianBlur(radius * 0.14))
    ball.alpha_composite(layer((242, 247, 255), halo))

    # 3b) 左上大面积弧形反光（玻璃曲面上的环境反射，减淡以免发白）
    sheen = Image.new("L", grad.size, 0)
    ImageDraw.Draw(sheen).ellipse(
        [size * 0.10, size * 0.06, size * 0.90, size * 0.72], fill=22)
    sheen = sheen.filter(ImageFilter.GaussianBlur(radius * 0.18))
    ball.alpha_composite(layer((235, 244, 255), sheen))

    # 4) 左上主高光 + 右下反射光点
    spec = Image.new("L", grad.size, 0)
    ImageDraw.Draw(spec).ellipse([size * 0.22, size * 0.14, size * 0.48, size * 0.34], fill=210)
    spec = spec.filter(ImageFilter.GaussianBlur(radius * 0.09))
    ball.alpha_composite(layer((255, 255, 255), spec))
    spec2 = Image.new("L", grad.size, 0)
    ImageDraw.Draw(spec2).ellipse([size * 0.60, size * 0.66, size * 0.72, size * 0.74], fill=150)
    spec2 = spec2.filter(ImageFilter.GaussianBlur(radius * 0.06))
    ball.alpha_composite(layer((255, 255, 255), spec2))

    # 5) 底部焦散光（光透过玻璃球聚焦的亮斑）
    caustic = Image.new("L", grad.size, 0)
    ImageDraw.Draw(caustic).ellipse([size * 0.30, size * 0.62, size * 0.70, size * 0.86], fill=48)
    caustic = caustic.filter(ImageFilter.GaussianBlur(radius * 0.14))
    ball.alpha_composite(layer((210, 228, 252), caustic))
    return ball

ball = make_ball(ball_r)

def warp_around_ball(f, bx, by, bend, grid=14):
    """纸张绕球曲折：靠近球的区域沿径向向外弯出弧度（网格变形）"""
    if bend <= 0.03:
        return f
    w, h = f.size

    def src(px, py):
        dx, dy = px - bx, py - by
        dist = math.hypot(dx, dy)
        if dist < 1e-3:
            return (px, py)
        rr = dist / ball_r
        if rr >= 1.5:
            return (px, py)
        amp = min(ball_r * 1.15 * bend * (1 - rr / 1.5) ** 2, dist * 0.5)
        return (px + dx / dist * amp, py + dy / dist * amp)

    xs = [w * i / grid for i in range(grid + 1)]
    ys = [h * j / grid for j in range(grid + 1)]
    mesh = []
    for j in range(grid):
        for i2 in range(grid):
            x0, x1, y0, y1 = xs[i2], xs[i2 + 1], ys[j], ys[j + 1]
            # MESH 每项 = (bbox 4 元组, quad 8 元组)；quad 顶点顺序：左上→左下→右下→右上
            bbox = (round(x0), round(y0), round(x1), round(y1))
            s0, s1 = src(x0, y0), src(x0, y1)
            s2, s3 = src(x1, y1), src(x1, y0)
            srcq = (*s0, *s1, *s2, *s3)
            # 用与 PIL 相同的行列式判断退化，避免除零
            det = ((s0[0] - s1[0]) * (s3[1] - s2[1]) - (s3[0] - s2[0]) * (s0[1] - s1[1]))
            if abs(det) < 1e-6:
                srcq = (x0, y0, x0, y1, x1, y1, x1, y0)
            mesh.append((bbox, srcq))
    return f.transform(f.size, Image.MESH, mesh, resample=Image.BILINEAR)

n_total = FRAMES_PER_LOOP * N_PHASES
orbit_frames = []
for i in range(n_total):
    canvas = Image.new("RGBA", (orbit_cw, orbit_ch), (0, 0, 0, 0))
    items = []
    for li in range(len(layout)):
        off_x, off_y, s, dn = orbit_state(i, li)
        f, shadow = layers[li][i % len(layers[li])]
        w2, h2 = round(f.width * s * SCENE * IMG_SCALE), round(f.height * s * SCENE * IMG_SCALE)
        fr = f.resize((w2, h2), Image.BILINEAR)
        sh = shadow.resize((w2, h2), Image.BILINEAR)
        a = 1 - DEPTH_ALPHA * (1 - (dn + 1) / 2)                    # 越远越透明
        fr.putalpha(fr.split()[3].point(lambda v, aa=a: int(v * aa)))
        x = int(cx + off_x - w2 / 2)
        y = int(cy + off_y - h2 / 2)
        # 纸张绕球曲折：屏幕上离球越近、深度越接近球面，弯曲越明显
        dist_c = math.hypot(cx - (x + w2 / 2), cy - (y + h2 / 2))
        near = max(0.0, 1 - dist_c / (ball_r + max(w2, h2) * 0.65))
        bend = min(1.0, near * 1.6) * max(0.0, 1 - abs(dn) / 1.2)
        if bend > 0.03:
            bx, by = cx - x, cy - y                                  # 球心在图内的坐标
            fr = warp_around_ball(fr, bx, by, bend)
            sh = warp_around_ball(sh, bx, by, bend)
        items.append((dn, fr, sh, x, y))
    items.sort(key=lambda it: it[0])                                 # 远的先画，近的后画
    for d, fr, sh, x, y in items:
        canvas.alpha_composite(sh, (x + 12, y + 16))
        if d < 0:
            canvas.alpha_composite(fr, (x, y))
    canvas.alpha_composite(ball, (cx - ball_r, cy - ball_r))         # 中心玻璃球在 z=0 层
    for d, fr, sh, x, y in items:
        if d >= 0:
            canvas.alpha_composite(fr, (x, y))
    orbit_frames.append(canvas)

if OUT_SCALE < 1.0:
    orbit_frames = [fr.resize((round(fr.width * OUT_SCALE), round(fr.height * OUT_SCALE)),
                              Image.LANCZOS) for fr in orbit_frames]
first, rest = orbit_frames[0], orbit_frames[1:]
first.save(rf"{out_dir}\collage_yishuhua_orbit.webp",
           save_all=True, append_images=rest, duration=ORBIT_MS, loop=0,
           quality=70, method=4, lossless=False)
print(f"3D 环绕动画已保存: collage_yishuhua_orbit.webp  画布 {orbit_cw}x{orbit_ch}，"
      f"共 {n_total} 帧（三种绕法各 {FRAMES_PER_LOOP * ORBIT_MS / 1000:.1f} 秒，循环往复）")

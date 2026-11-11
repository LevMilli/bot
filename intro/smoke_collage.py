"""Stadium smoke over an original football collage.

The dashboard already opens with a canvas smoke intro. This module is a
separate, editable preview: original night-stadium artwork (no league
photos, marks, or player likenesses) with layered smoke on top.

Change the look through IntroConfig, or with the preview flags:

    smoke_density   0 clears the smoke, 1 is a thick plume
    drift_speed     how far each layer travels during one loop
    tiles           which collage scenes are painted, back to front

Run a preview with ``python -m intro --help``.
"""

from __future__ import annotations

import math
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

TILE_IDS: tuple[str, ...] = (
    "night-stadium",
    "snow-game",
    "crowd-light",
    "end-zone",
    "goal-posts",
    "football",
    "turf",
)

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/macos/Inter-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)

# Smoke shape. Density and drift are the public knobs; these tune the plume.
_WARP_PIXELS = (30.0, 54.0, 18.0)
_LAYER_BLUR = (5.0, 2.2, 0.6)
_ALPHA_CAP = 0.68


@dataclass(frozen=True)
class IntroConfig:
    """Knobs for the intro still and the looping clip."""

    width: int = 1280
    height: int = 720
    smoke_density: float = 0.62
    drift_speed: float = 1.0
    tiles: tuple[str, ...] = TILE_IDS
    seed: int = 11
    fps: int = 12
    seconds: float = 2.5
    still_time: float = 0.85
    title: str = "PICKS"

    def checked(self) -> IntroConfig:
        unknown = [name for name in self.tiles if name not in TILE_IDS]
        if unknown:
            known = ", ".join(TILE_IDS)
            raise ValueError(f"unknown collage tile(s): {', '.join(unknown)}. Choose from: {known}")
        if not self.tiles:
            raise ValueError("pick at least one collage tile")
        if self.width < 64 or self.height < 64:
            raise ValueError("frame must be at least 64x64")
        if self.fps < 1 or self.seconds <= 0:
            raise ValueError("fps and seconds must be positive")
        return self


@dataclass
class _SmokeFields:
    base: np.ndarray
    mid: np.ndarray
    high: np.ndarray
    warp_x: np.ndarray
    warp_y: np.ndarray
    curl_x: np.ndarray
    curl_y: np.ndarray
    light: np.ndarray


def _font(size: int) -> ImageFont.ImageFont:
    size = max(8, int(size))
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _rng(seed: int, salt: str) -> np.random.Generator:
    mix = seed * 10007 + (int.from_bytes(salt.encode(), "little") % 1_000_003)
    return np.random.default_rng(mix)


def _gradient(h: int, w: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> np.ndarray:
    fade = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None, None]
    c0 = np.array(top, dtype=np.float32)
    c1 = np.array(bottom, dtype=np.float32)
    sheet = np.zeros((h, w, 1), dtype=np.float32)
    return c0 * (1.0 - fade) + c1 * fade + sheet


def _to_image(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def _glow(img: np.ndarray, cx: float, cy: float, radius: float, color: tuple[int, int, int], strength: float) -> None:
    h, w = img.shape[:2]
    yy, xx = np.ogrid[0:h, 0:w]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    falloff = np.clip(1.0 - dist / max(radius, 1.0), 0.0, 1.0) ** 2
    img += falloff[..., None] * np.array(color, dtype=np.float32) * strength


def _blur_unit(arr: np.ndarray, radius: float) -> np.ndarray:
    if radius <= 0.2:
        return arr
    image = Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), "L")
    image = image.filter(ImageFilter.GaussianBlur(radius))
    return np.asarray(image, dtype=np.float32) / 255.0


def _smoothstep(edge0: float, edge1: float, value: np.ndarray) -> np.ndarray:
    span = max(edge1 - edge0, 1e-4)
    t = np.clip((value - edge0) / span, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _periodic_noise(h: int, w: int, cells_y: int, cells_x: int, rng: np.random.Generator) -> np.ndarray:
    grid = rng.random((max(2, cells_y), max(2, cells_x))).astype(np.float32)
    gh, gw = grid.shape
    ys = np.linspace(0.0, gh, h, endpoint=False, dtype=np.float32)
    xs = np.linspace(0.0, gw, w, endpoint=False, dtype=np.float32)
    y0 = np.floor(ys).astype(np.int32)
    x0 = np.floor(xs).astype(np.int32)
    yf = ys - y0
    xf = xs - x0
    yf = yf * yf * (3.0 - 2.0 * yf)
    xf = xf * xf * (3.0 - 2.0 * xf)
    y1 = (y0 + 1) % gh
    x1 = (x0 + 1) % gw
    g00 = grid[y0][:, x0]
    g10 = grid[y0][:, x1]
    g01 = grid[y1][:, x0]
    g11 = grid[y1][:, x1]
    yf = yf[:, None]
    xf = xf[None, :]
    return g00 * (1 - xf) * (1 - yf) + g10 * xf * (1 - yf) + g01 * (1 - xf) * yf + g11 * xf * yf


def _fbm(h: int, w: int, rng: np.random.Generator, octaves: tuple[tuple[int, int], ...]) -> np.ndarray:
    total = np.zeros((h, w), dtype=np.float32)
    weight = 0.0
    amp = 1.0
    for cells_y, cells_x in octaves:
        total += amp * _periodic_noise(h, w, cells_y, cells_x, rng)
        weight += amp
        amp *= 0.5
    return total / weight


def _bilinear(img: np.ndarray, y: np.ndarray, x: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    y = np.mod(np.asarray(y, dtype=np.float32), h)
    x = np.mod(np.asarray(x, dtype=np.float32), w)
    # float modulo can land exactly on h/w and then floor out of range
    y = np.where(y >= h, np.float32(0), y)
    x = np.where(x >= w, np.float32(0), x)
    y0 = np.floor(y).astype(np.int32) % h
    x0 = np.floor(x).astype(np.int32) % w
    yf = y - y0
    xf = x - x0
    if img.ndim == 3:
        yf = yf[..., None]
        xf = xf[..., None]
    y1 = (y0 + 1) % h
    x1 = (x0 + 1) % w
    a = img[y0, x0]
    b = img[y0, x1]
    c = img[y1, x0]
    d = img[y1, x1]
    return a * (1 - xf) * (1 - yf) + b * xf * (1 - yf) + c * (1 - xf) * yf + d * xf * yf


def _shift(img: np.ndarray, ox: float, oy: float) -> np.ndarray:
    h, w = img.shape[:2]
    ys = (np.arange(h, dtype=np.float32) - oy)[:, None]
    xs = (np.arange(w, dtype=np.float32) - ox)[None, :]
    return _bilinear(img, np.broadcast_to(ys, (h, w)), np.broadcast_to(xs, (h, w)))


def _warp(img: np.ndarray, dx: np.ndarray, dy: np.ndarray, amount: float) -> np.ndarray:
    h, w = img.shape[:2]
    yy = np.arange(h, dtype=np.float32)[:, None]
    xx = np.arange(w, dtype=np.float32)[None, :]
    y = np.broadcast_to(yy, (h, w)) + dy * amount
    x = np.broadcast_to(xx, (h, w)) + dx * amount
    return _bilinear(img, y, x)


def paint_night_stadium(w: int, h: int, rng: np.random.Generator) -> Image.Image:
    img = _gradient(h, w, (5, 8, 20), (16, 28, 58))
    star_n = max(16, (w * h) // 2200)
    ys = rng.integers(0, max(2, int(h * 0.42)), star_n)
    xs = rng.integers(0, w, star_n)
    pick = rng.random(star_n)
    bright = np.array((210, 220, 245), dtype=np.float32)
    dim = np.array((120, 130, 160), dtype=np.float32)
    img[ys, xs] = np.where(pick[:, None] > 0.75, bright, dim)

    far_y = h * 0.40
    near_y = h - 1.0
    far_l, far_r = w * 0.20, w * 0.80
    near_l, near_r = w * 0.03, w * 0.97
    yy, xx = np.mgrid[0:h, 0:w]
    nx = (xx / max(w - 1, 1) - 0.5) * 2.0
    stand_top = h * (0.08 + 0.08 * nx * nx)
    stand = (yy > stand_top) & (yy < far_y + 2)
    img[stand] = img[stand] * 0.28 + np.array((10, 12, 22), dtype=np.float32)

    seat_n = max(300, w * h // 70)
    sx = rng.random(seat_n)
    sy = rng.random(seat_n) ** 0.65
    px = np.clip((sx * (w - 1)).astype(np.int32), 0, w - 1)
    curve = (sx - 0.5) * 2.0
    top = h * (0.08 + 0.08 * curve * curve)
    bot = far_y
    py = np.clip((top + (bot - top) * sy).astype(np.int32), 0, h - 1)
    warm = rng.random(seat_n) > 0.62
    lamp = np.where(warm[:, None], (255, 196, 120), (170, 198, 255))
    lamp = lamp * (0.25 + 0.85 * rng.random((seat_n, 1)))
    img[py, px] = np.clip(lamp, 0, 255)

    def depth_point(frac: float, across: float) -> tuple[float, float]:
        persp = frac ** 1.32
        y = far_y + (near_y - far_y) * persp
        left = far_l + (near_l - far_l) * persp
        right = far_r + (near_r - far_r) * persp
        return left + (right - left) * across, y

    field = np.zeros(yy.shape, dtype=bool)
    for row in range(int(far_y), h):
        frac_screen = max(0.0, (row - far_y) / max(near_y - far_y, 1.0))
        persp = frac_screen ** 0.76
        left = int(far_l + (near_l - far_l) * persp)
        right = int(far_r + (near_r - far_r) * persp)
        field[row, max(0, left) : min(w, right + 1)] = True
    span = np.clip((yy - far_y) / max(near_y - far_y, 1.0), 0.0, 1.0)
    grass_far = np.array((7, 62, 36), dtype=np.float32)
    grass_near = np.array((18, 122, 62), dtype=np.float32)
    grass = grass_far * (1 - span[..., None]) + grass_near * span[..., None]
    stripes = np.sin(span * 26.0) > 0
    grass = np.where(stripes[..., None], grass * 1.07, grass * 0.9)
    img = np.where(field[..., None], grass, img)

    for cx, cy, radius, strength in (
        (w * 0.08, h * 0.1, w * 0.2, 0.85),
        (w * 0.92, h * 0.1, w * 0.2, 0.85),
        (w * 0.18, h * 0.16, w * 0.1, 0.45),
        (w * 0.82, h * 0.16, w * 0.1, 0.45),
    ):
        _glow(img, cx, cy, radius, (255, 236, 196), strength)

    out = _to_image(img)
    draw = ImageDraw.Draw(out, "RGBA")
    line_w = max(1, w // 420)
    for step in range(11):
        frac = step / 10
        left_pt = depth_point(frac, 0.0)
        right_pt = depth_point(frac, 1.0)
        color = (236, 244, 236, 210 if step % 5 == 0 else 160)
        draw.line([left_pt, right_pt], fill=color, width=line_w + (1 if step % 5 == 0 else 0))
        for across in (0.35, 0.65):
            a = depth_point(frac, across - 0.025)
            b = depth_point(frac, across + 0.025)
            draw.line([a, b], fill=(236, 244, 236, 150), width=line_w)
    draw.line([depth_point(0, 0), depth_point(1, 0)], fill=(244, 248, 244, 220), width=line_w + 1)
    draw.line([depth_point(0, 1), depth_point(1, 1)], fill=(244, 248, 244, 220), width=line_w + 1)
    number_font = _font(max(10, int(h * 0.055)))
    for frac, label in ((0.18, "10"), (0.36, "20"), (0.54, "30"), (0.72, "40")):
        x, y = depth_point(frac, 0.2)
        draw.text((x, y - h * 0.03), label, font=number_font, fill=(244, 248, 244, 170))
    # Far uprights, small and generic.
    post = (255, 214, 70, 230)
    goal_l = depth_point(0.04, 0.42)
    goal_r = depth_point(0.04, 0.58)
    cross_y = goal_l[1] - h * 0.045
    draw.line([(goal_l[0], cross_y), (goal_r[0], cross_y)], fill=post, width=max(2, line_w + 1))
    draw.line([(goal_l[0], cross_y), (goal_l[0], cross_y - h * 0.07)], fill=post, width=max(2, line_w))
    draw.line([(goal_r[0], cross_y), (goal_r[0], cross_y - h * 0.07)], fill=post, width=max(2, line_w))
    draw.line([((goal_l[0] + goal_r[0]) / 2, cross_y), ((goal_l[0] + goal_r[0]) / 2, far_y + 2)], fill=post, width=max(2, line_w))

    beams = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    beam_draw = ImageDraw.Draw(beams)
    for lx in (w * 0.08, w * 0.92):
        toward = 1.0 if lx < w / 2 else -1.0
        for step in range(3):
            dest = lx + toward * w * (0.1 + step * 0.07)
            spread = w * (0.045 + step * 0.02)
            beam_draw.polygon(
                [(lx - 2, h * 0.1), (lx + 2, h * 0.1), (dest + toward * spread, h * 0.97), (dest - toward * spread * 0.15, h * 0.97)],
                fill=(255, 242, 214, 16),
            )
    beams = beams.filter(ImageFilter.GaussianBlur(max(2, w // 70)))
    out = out.convert("RGBA")
    out.alpha_composite(beams)
    return _frame(out.convert("RGB"))


def paint_snow_game(w: int, h: int, rng: np.random.Generator) -> Image.Image:
    img = _gradient(h, w, (168, 180, 194), (92, 108, 124))
    yy = np.mgrid[0:h, 0:w][0]
    horizon = h * 0.46
    sky = yy < horizon
    img[sky] = img[sky] * 0.92 + np.array((20, 24, 32), dtype=np.float32) * 0.08
    stand = (yy > h * 0.28) & (yy < horizon)
    img[stand] = np.array((28, 34, 44), dtype=np.float32)
    field = yy >= horizon
    depth = np.clip((yy - horizon) / max(h - horizon, 1.0), 0.0, 1.0)
    snow = np.array((236, 240, 244), dtype=np.float32) * (1.0 - 0.12 * depth[..., None])
    snow = snow + np.array((8, 16, 22), dtype=np.float32) * depth[..., None]
    blotch = _fbm(h, w, rng, ((5, 6), (9, 11), (14, 18)))
    detail = _fbm(h, w, rng, ((12, 16), (20, 26)))
    worn = _smoothstep(0.70, 0.9, blotch) * _smoothstep(0.42, 0.75, detail)
    grass = np.array((74, 104, 70), dtype=np.float32)
    img[field] = snow[field] * (1.0 - worn[field, None]) + grass * worn[field, None]
    _glow(img, w * 0.2, h * 0.3, w * 0.22, (255, 214, 150), 0.35)
    _glow(img, w * 0.78, h * 0.28, w * 0.18, (255, 220, 170), 0.28)

    out = _to_image(img)
    draw = ImageDraw.Draw(out, "RGBA")
    line = (255, 255, 255, 150)
    for i in range(6):
        y = horizon + (h - horizon) * ((i / 5) ** 1.25)
        inset = w * 0.12 * (1 - i / 5)
        draw.line([(inset, y), (w - inset, y)], fill=line, width=max(1, h // 180))
    draw.line([(w * 0.38, horizon + 4), (w * 0.38, horizon - h * 0.16)], fill=(255, 206, 70, 220), width=max(2, w // 140))
    draw.line([(w * 0.62, horizon + 4), (w * 0.62, horizon - h * 0.16)], fill=(255, 206, 70, 220), width=max(2, w // 140))
    draw.line([(w * 0.38, horizon - h * 0.1), (w * 0.62, horizon - h * 0.1)], fill=(255, 206, 70, 220), width=max(2, w // 140))

    flakes = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for count, blur, alpha in ((max(80, w * h // 900), 0.4, 210), (max(40, w * h // 2200), 1.6, 180), (max(16, w * h // 6000), 3.2, 150)):
        layer = np.zeros((h, w), dtype=np.float32)
        fx = rng.integers(0, w, count)
        fy = rng.integers(0, h, count)
        layer[fy, fx] = rng.uniform(0.45, 1.0, count)
        soft = _blur_unit(layer, blur)
        tone = Image.fromarray(np.clip(soft * alpha, 0, 255).astype(np.uint8), "L")
        sheet = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        sheet.putalpha(tone)
        flakes.alpha_composite(sheet)
    out = out.convert("RGBA")
    out.alpha_composite(flakes)
    return _frame(out.convert("RGB"))


def paint_crowd_light(w: int, h: int, rng: np.random.Generator) -> Image.Image:
    img = _gradient(h, w, (8, 6, 16), (18, 10, 28))
    out = _to_image(img).convert("RGBA")
    orbs = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(orbs)
    palette = (
        (255, 214, 130),
        (255, 248, 236),
        (130, 176, 255),
        (255, 150, 170),
        (255, 186, 90),
    )
    count = max(18, (w * h) // 9000)
    for _ in range(count):
        radius = int(rng.uniform(w * 0.02, w * 0.16))
        cx = int(rng.integers(0, w))
        cy = int(rng.integers(0, h))
        color = palette[int(rng.integers(0, len(palette)))]
        alpha = int(rng.uniform(50, 120))
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=(*color, alpha))
    orbs = orbs.filter(ImageFilter.GaussianBlur(max(1.2, w / 90)))
    out.alpha_composite(orbs)

    specks = np.zeros((h, w), dtype=np.float32)
    n = max(200, w * h // 40)
    specks[rng.integers(0, h, n), rng.integers(0, w, n)] = rng.uniform(0.3, 1.0, n)
    # Crowd reads as bands of light, not faces.
    band = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    specks *= 0.35 + 0.65 * (np.sin(band * 40) > 0)
    tone = Image.fromarray(np.clip(_blur_unit(specks, 0.6) * 255, 0, 255).astype(np.uint8), "L")
    sheet = Image.new("RGBA", (w, h), (255, 228, 190, 0))
    sheet.putalpha(tone)
    out.alpha_composite(sheet)
    streak = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(streak).rectangle([0, int(h * 0.42), w, int(h * 0.48)], fill=(255, 236, 200, 50))
    streak = streak.filter(ImageFilter.GaussianBlur(max(2, h // 18)))
    out.alpha_composite(streak)
    return _frame(out.convert("RGB"))


def paint_end_zone(w: int, h: int, rng: np.random.Generator) -> Image.Image:
    img = _gradient(h, w, (12, 110, 58), (22, 150, 74))
    noise = rng.random((h, w, 1)).astype(np.float32)
    img = img * (0.92 + 0.1 * noise)
    out = _to_image(img)
    draw = ImageDraw.Draw(out, "RGBA")
    margin = int(min(w, h) * 0.08)
    draw.rectangle([margin, margin, w - margin, h - margin], outline=(244, 248, 244, 230), width=max(2, min(w, h) // 40))
    font = _font(int(min(w, h) * 0.42))
    text = "10"
    box = font.getbbox(text)
    tw, th = box[2] - box[0], box[3] - box[1]
    draw.text(((w - tw) / 2, (h - th) / 2 - box[1] * 0.2), text, font=font, fill=(248, 252, 248, 230))
    pylon = (255, 106, 26, 255)
    pw, ph = max(6, w // 18), max(10, h // 5)
    for x, y in ((margin, h - margin - ph), (w - margin - pw, h - margin - ph)):
        draw.rectangle([x, y, x + pw, y + ph], fill=pylon)
        draw.rectangle([x, y, x + pw, y + max(3, ph // 5)], fill=(255, 170, 90, 255))
    return _frame(out.convert("RGB"))


def _post(draw: ImageDraw.ImageDraw, start: tuple[float, float], end: tuple[float, float], width: int) -> None:
    x0, y0 = start
    x1, y1 = end
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy) or 1.0
    px, py = -dy / length, dx / length
    half = max(2.0, width / 2)
    body = (255, 206, 64, 255)
    shade = (176, 120, 20, 255)
    draw.polygon(
        [
            (x0 + px * half, y0 + py * half),
            (x0 - px * half * 0.85, y0 - py * half * 0.85),
            (x1 - px * half * 0.85, y1 - py * half * 0.85),
            (x1 + px * half, y1 + py * half),
        ],
        fill=body,
    )
    draw.line([(x0 - px * half * 0.55, y0 - py * half * 0.55), (x1 - px * half * 0.55, y1 - py * half * 0.55)], fill=shade, width=max(1, width // 4))
    draw.line([(x0 + px * half * 0.62, y0 + py * half * 0.62), (x1 + px * half * 0.62, y1 + py * half * 0.62)], fill=(255, 246, 210, 230), width=max(1, width // 5))


def paint_goal_posts(w: int, h: int, rng: np.random.Generator) -> Image.Image:
    del rng
    img = _gradient(h, w, (6, 10, 24), (20, 36, 72))
    _glow(img, w * 0.5, h * 0.42, w * 0.45, (255, 228, 180), 0.45)
    _glow(img, w * 0.82, h * 0.16, w * 0.16, (255, 244, 220), 0.7)
    out = _to_image(img).convert("RGBA")
    draw = ImageDraw.Draw(out, "RGBA")
    thickness = max(4, w // 28)
    cx = w * 0.5
    cross_y = h * 0.58
    spread_c = w * 0.2
    spread_t = w * 0.36
    _post(draw, (cx, h * 0.96), (cx, cross_y), thickness)
    _post(draw, (cx - spread_c, cross_y), (cx + spread_c, cross_y), thickness)
    _post(draw, (cx - spread_c, cross_y), (cx - spread_t, h * 0.04), thickness)
    _post(draw, (cx + spread_c, cross_y), (cx + spread_t, h * 0.04), thickness)
    # Ball in flight: leather oval and short laces, no mark.
    ball = (cx * 0.62, h * 0.3)
    rw, rh = w * 0.04, h * 0.028
    draw.ellipse([ball[0] - rw, ball[1] - rh, ball[0] + rw, ball[1] + rh], fill=(122, 68, 36, 255))
    for step in range(-2, 3):
        y = ball[1] + step * rh * 0.38
        draw.line([(ball[0] - rw * 0.28, y), (ball[0] + rw * 0.28, y)], fill=(244, 236, 220, 255), width=max(1, w // 240))
    return _frame(out.convert("RGB"))


def paint_football(w: int, h: int, rng: np.random.Generator) -> Image.Image:
    img = _gradient(h, w, (18, 12, 10), (8, 6, 6))
    pebble = _fbm(h, w, rng, ((6, 8), (12, 16), (22, 28)))
    img *= 0.85 + 0.2 * pebble[..., None]
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = w * 0.5, h * 0.52
    ang = math.radians(-16)
    xr = (xx - cx) * math.cos(ang) + (yy - cy) * math.sin(ang)
    yr = -(xx - cx) * math.sin(ang) + (yy - cy) * math.cos(ang)
    rx, ry = max(w * 0.34, 1), max(h * 0.3, 1)
    ell = (xr / rx) ** 2 + (yr / ry) ** 2
    shade = np.clip(0.22 + 0.95 * np.power(np.clip(1 - ell, 0, 1), 0.55), 0, 1.25)
    spec = np.exp(-((xr / rx + 0.32) ** 2) / 0.05 - ((yr / ry + 0.38) ** 2) / 0.09)
    leather = np.array((118, 64, 34), dtype=np.float32) * (0.75 + 0.35 * pebble[..., None])
    leather = leather * shade[..., None] + spec[..., None] * np.array((90, 70, 50), dtype=np.float32)
    shadow = np.exp(-((xx - cx) / (rx * 1.05)) ** 2 - ((yy - (cy + ry * 0.85)) / (ry * 0.28)) ** 2)
    img *= 1 - 0.45 * shadow[..., None]
    mask = ell <= 1.0
    img = np.where(mask[..., None], leather, img)
    edge = (ell > 0.86) & mask
    img[edge] *= 0.72
    stripe = (np.abs(np.abs(xr) - rx * 0.62) < rx * 0.04) & mask
    img[stripe] = np.array((236, 232, 220), dtype=np.float32)
    bars = (np.abs(np.mod(yr / ry + 1.0, 0.18) - 0.09) < 0.028) & (np.abs(xr) < rx * 0.12) & (np.abs(yr) < ry * 0.5) & mask
    lace = (np.abs(xr) < rx * 0.015) & (np.abs(yr) < ry * 0.52) & mask
    img[bars | lace] = np.array((246, 242, 234), dtype=np.float32)
    return _frame(_to_image(img))


def paint_turf(w: int, h: int, rng: np.random.Generator) -> Image.Image:
    stripe_h = max(3, h // 6)
    yy = np.arange(h, dtype=np.int32)[:, None, None]
    stripe = ((yy // stripe_h) % 2).astype(np.float32)
    dark = np.array((14, 86, 42), dtype=np.float32)
    lite = np.array((24, 124, 58), dtype=np.float32)
    img = np.broadcast_to(dark * (1 - stripe) + lite * stripe, (h, w, 3)).astype(np.float32).copy()
    grain = rng.random((h, w, 1)).astype(np.float32)
    img *= 0.9 + 0.16 * grain
    scuff_n = max(6, w // 40)
    for _ in range(scuff_n):
        sx = int(rng.integers(0, w))
        sy = int(rng.integers(0, h))
        rad = int(rng.integers(max(2, w // 80), max(4, w // 28)))
        _glow(img, sx, sy, rad, (40, 70, 30), 0.25)
    out = _to_image(img)
    draw = ImageDraw.Draw(out, "RGBA")
    y = int(h * 0.58)
    draw.line([(int(w * 0.04), y), (int(w * 0.96), y)], fill=(244, 248, 244, 230), width=max(2, h // 16))
    tick = max(2, h // 10)
    for x_frac in (0.2, 0.4, 0.6, 0.8):
        x = int(w * x_frac)
        draw.line([(x, y - tick), (x, y + tick)], fill=(244, 248, 244, 180), width=max(1, w // 180))
    return _frame(out.convert("RGB"))


PAINTERS = {
    "night-stadium": paint_night_stadium,
    "snow-game": paint_snow_game,
    "crowd-light": paint_crowd_light,
    "end-zone": paint_end_zone,
    "goal-posts": paint_goal_posts,
    "football": paint_football,
    "turf": paint_turf,
}


def _frame(image: Image.Image) -> Image.Image:
    out = image.convert("RGBA")
    draw = ImageDraw.Draw(out)
    w, h = out.size
    draw.rectangle([0, 0, w - 1, h - 1], outline=(12, 10, 14, 255), width=max(3, min(w, h) // 48))
    inset = max(3, min(w, h) // 48)
    draw.rectangle([inset, inset, w - 1 - inset, h - 1 - inset], outline=(232, 220, 196, 180), width=1)
    return out


_LAYOUTS: dict[int, tuple[tuple[float, float, float, float], ...]] = {
    1: ((0.0, 0.0, 1.0, 1.0),),
    2: ((0.0, 0.0, 0.60, 1.0), (0.58, 0.0, 0.42, 1.0)),
    3: ((0.0, 0.0, 0.66, 0.64), (0.64, 0.0, 0.36, 0.64), (0.0, 0.62, 1.0, 0.38)),
    4: ((0.0, 0.0, 0.60, 0.62), (0.58, 0.0, 0.42, 0.62), (0.0, 0.60, 0.50, 0.40), (0.48, 0.60, 0.52, 0.40)),
    5: (
        (0.0, 0.0, 0.60, 0.58),
        (0.58, 0.0, 0.42, 0.36),
        (0.58, 0.34, 0.42, 0.28),
        (0.0, 0.56, 0.50, 0.44),
        (0.48, 0.56, 0.52, 0.44),
    ),
    6: (
        (0.0, 0.0, 0.60, 0.62),
        (0.58, 0.0, 0.42, 0.40),
        (0.58, 0.38, 0.42, 0.26),
        (0.0, 0.60, 0.34, 0.40),
        (0.32, 0.60, 0.30, 0.40),
        (0.60, 0.62, 0.40, 0.38),
    ),
    7: (
        (0.0, 0.0, 0.615, 0.635),
        (0.595, 0.0, 0.405, 0.40),
        (0.595, 0.385, 0.405, 0.255),
        (0.0, 0.615, 0.345, 0.385),
        (0.325, 0.615, 0.285, 0.385),
        (0.595, 0.615, 0.215, 0.385),
        (0.795, 0.615, 0.205, 0.385),
    ),
}


def _boxes(count: int, width: int, height: int) -> list[tuple[int, int, int, int]]:
    fracs = _LAYOUTS[count]
    boxes = []
    for x, y, bw, bh in fracs:
        left = int(round(x * width))
        top = int(round(y * height))
        right = int(round((x + bw) * width))
        bottom = int(round((y + bh) * height))
        left = max(0, min(width - 2, left))
        top = max(0, min(height - 2, top))
        right = max(left + 2, min(width, right))
        bottom = max(top + 2, min(height, bottom))
        boxes.append((left, top, right - left, bottom - top))
    return boxes


def render_collage(config: IntroConfig) -> Image.Image:
    config.checked()
    canvas = Image.new("RGBA", (config.width, config.height), (5, 6, 10, 255))
    boxes = _boxes(len(config.tiles), config.width, config.height)
    for name, (x, y, bw, bh) in zip(config.tiles, boxes):
        tile = PAINTERS[name](bw, bh, _rng(config.seed, name)).convert("RGBA")
        shadow = Image.new("RGBA", (bw + 36, bh + 36), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rectangle([14, 16, 14 + bw, 16 + bh], fill=(0, 0, 0, 120))
        shadow = shadow.filter(ImageFilter.GaussianBlur(8))
        canvas.alpha_composite(shadow, (max(0, x - 14), min(config.height - shadow.size[1], y - 6)))
        canvas.alpha_composite(tile, (x, y))
    return canvas.convert("RGB")


def _smoke_size(config: IntroConfig) -> tuple[int, int]:
    sw = max(160, config.width // 2)
    sh = max(90, config.height // 2)
    return sw - sw % 2, sh - sh % 2


def prepare_smoke(config: IntroConfig, collage: Image.Image) -> _SmokeFields:
    sw, sh = _smoke_size(config)
    rng = _rng(config.seed, "smoke")
    base = _fbm(sh, sw, rng, ((4, 5), (8, 10), (14, 18)))
    mid = _fbm(sh, sw, rng, ((7, 9), (14, 18), (26, 32)))
    high = _fbm(sh, sw, rng, ((16, 20), (28, 36), (48, 60)))
    warp_x = _fbm(sh, sw, rng, ((4, 5), (8, 11)))
    warp_y = _fbm(sh, sw, rng, ((4, 6), (9, 12)))
    curl_x = _fbm(sh, sw, rng, ((6, 8), (12, 15)))
    curl_y = _fbm(sh, sw, rng, ((5, 7), (11, 14)))
    small = collage.resize((sw, sh), Image.Resampling.BILINEAR)
    rgb = np.asarray(small, dtype=np.float32)
    lum = (0.22 * rgb[..., 0] + 0.68 * rgb[..., 1] + 0.10 * rgb[..., 2]) / 255.0
    light = _blur_unit(lum, 16)
    light = light / (float(light.max()) + 1e-6)
    return _SmokeFields(base, mid, high, warp_x, warp_y, curl_x, curl_y, light)


def _drift(img: np.ndarray, angle: float, ax: float, ay: float, phase: float, speed: float) -> np.ndarray:
    ox = ax * math.cos(angle + phase) * speed
    oy = ay * math.sin(angle + phase) * speed
    return _shift(img, ox, oy)


def render_smoke(config: IntroConfig, fields: _SmokeFields, t: float) -> tuple[np.ndarray, np.ndarray]:
    """Return RGB smoke and alpha, both at the smoke working resolution."""
    cycle = (t % config.seconds) / config.seconds
    angle = 2.0 * math.pi * cycle
    speed = config.drift_speed
    warp_x = _drift(fields.warp_x, angle, 28, 16, 0.4, speed)
    warp_y = _drift(fields.warp_y, angle, 18, 26, 1.2, speed)
    dx = warp_x * 2.0 - 1.0
    dy = warp_y * 2.0 - 1.0

    def curled(img: np.ndarray, ax: float, ay: float, phase: float, amount: float) -> np.ndarray:
        moved = _drift(img, angle, ax, ay, phase, speed)
        return _warp(moved, dx, dy, amount * max(speed, 0.15))

    base = curled(fields.base, 42, 14, 0.0, _WARP_PIXELS[0])
    mid = curled(fields.mid, -22, 36, 2.1, _WARP_PIXELS[1])
    curl_x = _drift(fields.curl_x, angle, 14, 18, 0.6, speed)
    curl_y = _drift(fields.curl_y, angle, 16, 12, 2.2, speed)
    mid = _warp(mid, curl_x * 2.0 - 1.0, curl_y * 2.0 - 1.0, 20.0 * max(speed, 0.15))
    high = curled(fields.high, 64, -28, 4.0, _WARP_PIXELS[2])

    shift = (config.smoke_density - 0.62) * 0.2
    veil = _blur_unit(_smoothstep(0.56 - shift, 0.82 - shift, base), _LAYER_BLUR[0])
    billow = _blur_unit(_smoothstep(0.60 - shift, 0.88 - shift, mid), _LAYER_BLUR[1])
    ridges = 1.0 - np.abs(high * 2.0 - 1.0)
    wisps = _blur_unit(_smoothstep(0.68 - shift * 0.3, 0.92, ridges), _LAYER_BLUR[2])

    # Billows carry the plume. The veil only softens around them, and the
    # wisps stay thin, so the frame keeps real gaps instead of a flat sheet.
    cover = np.clip(billow * 1.05 + veil * 0.22 + wisps * 0.28, 0.0, 1.0)
    cover = _smoothstep(0.16, 0.62, cover)
    alpha = np.clip(cover * config.smoke_density * 1.35, 0.0, _ALPHA_CAP)
    sh, sw = alpha.shape
    yy = np.linspace(-1.0, 1.0, sh, dtype=np.float32)[:, None]
    xx = np.linspace(-1.0, 1.0, sw, dtype=np.float32)[None, :]
    rim = _smoothstep(0.0, 0.1, 1.0 - np.maximum(np.abs(xx), np.abs(yy)))
    alpha *= 0.4 + 0.6 * rim

    gy, gx = np.gradient(_blur_unit(mid, 1.2))
    shade = np.clip(0.9 + gy * 1.6 - gx * 0.2, 0.74, 1.16)
    core = np.clip(billow, 0.0, 1.0)[..., None]
    gray = np.array((198, 202, 208), dtype=np.float32) * (1 - core) + np.array((250, 250, 252), dtype=np.float32) * core
    gray = gray * shade[..., None]
    light = fields.light[..., None]
    gray = np.clip(gray * (0.86 + 0.28 * light) + light * np.array((22.0, 14.0, 4.0), dtype=np.float32), 0, 255)
    return gray, alpha


def _draw_title(image: Image.Image, title: str) -> None:
    if not title.strip():
        return
    draw = ImageDraw.Draw(image, "RGBA")
    w, h = image.size
    font = _font(max(18, int(w * 0.072)))
    letters = list(title.strip().upper())
    tracking = int(w * 0.012)
    boxes = [font.getbbox(ch) for ch in letters]
    widths = [box[2] - box[0] for box in boxes]
    total = sum(widths) + tracking * (len(letters) - 1)
    x = (w - total) / 2
    y = h * 0.42
    for ch, cw, box in zip(letters, widths, boxes):
        draw.text((x + 2, y + 3), ch, font=font, fill=(0, 0, 0, 110))
        draw.text((x, y), ch, font=font, fill=(255, 255, 255, 230))
        x += cw + tracking
    rule_y = y + max(box[3] for box in boxes) + h * 0.012
    draw.line([(w * 0.38, rule_y), (w * 0.62, rule_y)], fill=(232, 208, 140, 200), width=max(1, w // 640))


def render_frame(config: IntroConfig, collage: Image.Image, fields: _SmokeFields, t: float) -> Image.Image:
    gray, alpha = render_smoke(config, fields, t)
    color = Image.fromarray(np.clip(gray, 0, 255).astype(np.uint8), "RGB").resize(
        (config.width, config.height), Image.Resampling.BICUBIC
    )
    mask = Image.fromarray(np.clip(alpha * 255.0, 0, 255).astype(np.uint8), "L").resize(
        (config.width, config.height), Image.Resampling.BICUBIC
    )
    rgb = np.asarray(color, dtype=np.float32)
    a = np.asarray(mask, dtype=np.float32)[..., None] / 255.0
    base = np.asarray(collage, dtype=np.float32)
    out = base * (1.0 - a) + rgb * a
    yy, xx = np.mgrid[0 : config.height, 0 : config.width]
    nx = (xx / max(config.width - 1, 1) - 0.5) * 1.2
    ny = (yy / max(config.height - 1, 1) - 0.5) * 1.2
    vignette = np.clip(1.0 - (nx * nx + ny * ny), 0.0, 1.0) ** 0.65
    out *= (0.86 + 0.14 * vignette)[..., None]
    frame = _to_image(out)
    _draw_title(frame, config.title)
    return frame


def render_still(config: IntroConfig, collage: Image.Image | None = None, fields: _SmokeFields | None = None) -> Image.Image:
    config = config.checked()
    collage = collage if collage is not None else render_collage(config)
    fields = fields if fields is not None else prepare_smoke(config, collage)
    return render_frame(config, collage, fields, config.still_time)


def render_frames(config: IntroConfig) -> list[Image.Image]:
    config = config.checked()
    collage = render_collage(config)
    fields = prepare_smoke(config, collage)
    count = max(2, int(round(config.seconds * config.fps)))
    frames = []
    for index in range(count):
        t = config.seconds * index / count
        frames.append(render_frame(config, collage, fields, t))
    return frames


def write_still(config: IntroConfig, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    render_still(config).save(path, "PNG")
    return path


def write_clip(config: IntroConfig, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = render_frames(config)
    suffix = path.suffix.lower()
    if suffix == ".gif":
        delay = max(20, int(round(1000 / config.fps)))
        first, *rest = frames
        first.save(path, save_all=True, append_images=rest, duration=delay, loop=0, disposal=2)
        return path
    if suffix != ".mp4":
        raise ValueError("clip must be a .mp4 or .gif")
    with tempfile.TemporaryDirectory(prefix="smoke-intro-") as tmp:
        folder = Path(tmp)
        for index, frame in enumerate(frames):
            frame.save(folder / f"f{index:04d}.png")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-framerate",
                str(config.fps),
                "-i",
                str(folder / "f%04d.png"),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-crf",
                "17",
                "-movflags",
                "+faststart",
                str(path),
            ],
            check=True,
            capture_output=True,
        )
    return path

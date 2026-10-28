#!/usr/bin/env python
"""Build every raster asset for the dreamcore Tangled page.

    python tools/build_assets.py            # all steps
    python tools/build_assets.py static     # one step

Steps that need a source image exist in tools/build_user_assets.py (tv, bg).
"""
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "site", "img")
SRC = os.path.join(IMG, "src")
FONTS = os.path.join(ROOT, "site", "fonts")
PROXY = "http://127.0.0.1:7890"
os.makedirs(IMG, exist_ok=True)
os.makedirs(FONTS, exist_ok=True)
os.makedirs(SRC, exist_ok=True)

FONT_URLS = {
    "VT323.woff2":
        "https://fonts.gstatic.com/s/vt323/v18/pxiKyp0ihIEF2isfFJU.woff2",
    "IMFellEnglish-Italic.woff2":
        "https://fonts.gstatic.com/s/imfellenglish/v14/Ktk3ALSLW8zDe0rthJysWrnLsAzHFZOafYs.woff2",
}


def fetch(url):
    return subprocess.run(
        ["curl", "-sS", "-x", PROXY, "--max-time", "60", url],
        capture_output=True).stdout


def fonts():
    for name, url in FONT_URLS.items():
        out = os.path.join(FONTS, name)
        if os.path.exists(out) and os.path.getsize(out) > 4000:
            print("font kept", name)
            continue
        data = fetch(url)
        if len(data) < 4000:
            print("FONT FAIL", name, len(data))
            continue
        open(out, "wb").write(data)
        print("font", name, len(data))


def static_gif():
    w, h = 200, 150
    rng = np.random.default_rng(3)
    frames = []
    for i in range(12):
        n = rng.random((h, w)).astype(np.float32)
        n = 0.72 * n + 0.28 * np.asarray(
            Image.fromarray((n * 255).astype(np.uint8)).filter(
                ImageFilter.GaussianBlur(0.8))).astype(np.float32) / 255.0
        band = 0.5 + 0.5 * np.sin((np.arange(h) / h * 2.2 + i * 0.11) * np.pi)
        n = n * 0.72 + band[:, None] * 0.28
        n[::4, :] *= 0.52
        n[1::4, :] *= 0.78
        n[2::4, :] *= 0.92
        n = np.clip((n - 0.18) * 1.55 + 0.22, 0, 1)
        rgb = np.stack([n, n * 0.90, n * 0.94], axis=2)
        frames.append(Image.fromarray((rgb * 255).astype(np.uint8), "RGB"))
    frames[0].save(os.path.join(IMG, "static.gif"), save_all=True,
                   append_images=frames[1:], duration=190, loop=0, optimize=True)
    print("static.gif", os.path.getsize(os.path.join(IMG, "static.gif")))


def glass_overlay():
    w, h, r = 640, 480, 26
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for i in range(w):
        t = max(0.0, 1.0 - i / (w * 0.62))
        a = int(26 * t ** 2)
        if a:
            d.line([(i, 0), (i, h)], fill=(255, 240, 246, a))
    lay = lay.filter(ImageFilter.GaussianBlur(18))
    edge = Image.new("L", (w, h), 0)
    ImageDraw.Draw(edge).rounded_rectangle([0, 0, w - 1, h - 1], radius=r,
                                           outline=255, width=90)
    edge = edge.filter(ImageFilter.GaussianBlur(30))
    dark = Image.new("RGBA", (w, h), (10, 4, 12, 0))
    dark.putalpha(edge.point(lambda v: int(v * 0.30)))
    lay = Image.alpha_composite(lay, dark)
    lay.putalpha(Image.composite(lay.getchannel("A"), Image.new("L", (w, h), 0), mask))
    lay.save(os.path.join(IMG, "glass.png"))
    print("glass.png", os.path.getsize(os.path.join(IMG, "glass.png")))


def grain():
    n = 256
    rng = np.random.default_rng(9)
    v = rng.normal(128, 26, (n, n)).clip(0, 255).astype(np.uint8)
    Image.merge("RGBA", (Image.fromarray(v), Image.fromarray(v), Image.fromarray(v),
                         Image.fromarray(np.full((n, n), 26, dtype=np.uint8)))
                ).save(os.path.join(IMG, "grain.png"))
    print("grain.png", os.path.getsize(os.path.join(IMG, "grain.png")))


# ---------------------------------------------------------------- line art
def stencil(src_path, out_path, colour=(255, 245, 250), gain=1.0, blur=0.7):
    """Black ink on white -> transparent PNG whose alpha is the ink."""
    im = Image.open(src_path).convert("RGB")
    a = np.asarray(im).astype(np.float32) / 255.0
    lum = a @ np.array([0.299, 0.587, 0.587 - 0.587 + 0.114], dtype=np.float32)
    alpha = np.clip((1.0 - lum) * gain, 0, 1)
    h, w = alpha.shape
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[..., 0], out[..., 1], out[..., 2] = colour
    out[..., 3] = (alpha * 255).astype(np.uint8)
    img = Image.fromarray(out, "RGBA").filter(ImageFilter.GaussianBlur(blur))
    bbox = img.getchannel("A").point(lambda v: 255 if v > 12 else 0).getbbox()
    if bbox:
        img = img.crop(bbox)
    img.save(out_path)
    print("stencil", os.path.basename(out_path), img.size,
          os.path.getsize(out_path))


def key_chroma(src_path, out_path, chroma=(255, 0, 255), lo=60, hi=120):
    """Flat magenta ground -> transparent PNG, alpha feathered."""
    im = Image.open(src_path).convert("RGB")
    a = np.asarray(im).astype(np.float32)
    d = np.sqrt(((a - np.array(chroma, dtype=np.float32)) ** 2).sum(axis=2))
    alpha = np.clip((d - lo) / (hi - lo), 0, 1)
    h, w = alpha.shape
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[..., :3] = np.asarray(im)
    out[..., 3] = (alpha * 255).astype(np.uint8)
    img = Image.fromarray(out, "RGBA").filter(ImageFilter.GaussianBlur(0.7))
    bbox = img.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
    if bbox:
        img = img.crop(bbox)
    img.save(out_path)
    print("key", os.path.basename(out_path), img.size)
    return img


def sprites():
    for cand in ("floating-sheet3.png", "floating-sheet2.png", "floating-sheet.png"):
        if os.path.exists(os.path.join(SRC, cand)):
            sheet = os.path.join(SRC, cand)
            print("slicing", cand)
            break
    else:
        sheet = ""
    if not os.path.exists(sheet):
        print("no floating-sheet.png yet")
        return
    im = Image.open(sheet).convert("RGB")
    w, h = im.size
    cw, ch = w // 3, h // 3
    for r in range(3):
        for c in range(3):
            # inset each cell so a neighbour's overflow (or a spec) never rides
            # along with the object
            ix, iy = int(cw * 0.035), int(ch * 0.035)
            cell = im.crop((c * cw + ix, r * ch + iy,
                            (c + 1) * cw - ix, (r + 1) * ch - iy))
            tmp = os.path.join(SRC, "_cell.png")
            cell.save(tmp)
            keyed = key_chroma(tmp, os.path.join(SRC, "_cell_keyed.png"),
                               lo=45, hi=110)
            white_ink(keyed, os.path.join(IMG, "s%d.png" % (r * 3 + c + 1)),
                      gain=1.95, grid=12)
    if os.path.exists(os.path.join(SRC, "_cell.png")):
        os.remove(os.path.join(SRC, "_cell.png"))


def white_ink(keyed, out_path, tint=(255, 240, 247), gain=1.06, grid=24):
    """RGBA ink on chroma keyed out -> same silhouette, ink recoloured light."""
    a = np.asarray(keyed.convert("RGB")).astype(np.float32) / 255.0
    alpha = np.asarray(keyed.getchannel("A")).astype(np.float32) / 255.0
    lum = a @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    ink = np.clip((1.0 - lum) * gain, 0, 1) * alpha
    h, w = ink.shape
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[..., 0], out[..., 1], out[..., 2] = tint
    out[..., 3] = (ink * 255).astype(np.uint8)
    img = Image.fromarray(out, "RGBA").filter(ImageFilter.GaussianBlur(0.3))
    img = drop_specks(img, grid=grid)
    bbox = img.getchannel("A").point(lambda v: 255 if v > 10 else 0).getbbox()
    if bbox:
        img = img.crop(bbox)
    img.save(out_path)
    return img


def drop_specks(img, grid=72):
    """Keep only the biggest blob of ink: kills keying debris in the corners."""
    a = np.asarray(img.getchannel("A")).astype(np.float32) / 255.0
    h, w = a.shape
    gh, gw = grid, grid
    cells = np.zeros((gh, gw), dtype=bool)
    for y in range(gh):
        for x in range(gw):
            block = a[y * h // gh:(y + 1) * h // gh, x * w // gw:(x + 1) * w // gw]
            cells[y, x] = block.mean() > 0.02
    seen = np.zeros_like(cells)
    best = []
    for sy in range(gh):
        for sx in range(gw):
            if not cells[sy, sx] or seen[sy, sx]:
                continue
            stack, blob = [(sy, sx)], []
            seen[sy, sx] = True
            while stack:
                cy, cx = stack.pop()
                blob.append((cy, cx))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < gh and 0 <= nx < gw and cells[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            if len(blob) > len(best):
                best = blob
    keep = np.zeros((gh, gw), dtype=bool)
    for cy, cx in best:
        keep[cy, cx] = True
    # grow the kept region by one cell so nothing clips
    grown = keep.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            grown |= np.roll(np.roll(keep, dy, axis=0), dx, axis=1)
    mask = np.kron(grown, np.ones((h // gh + 1, w // gw + 1)))[:h, :w]
    out = np.asarray(img).copy()
    out[..., 3] = (np.asarray(img.getchannel("A")) * mask).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def hero():
    src = os.path.join(SRC, "rabbit-courier.png")
    if not os.path.exists(src):
        print("no rabbit-courier.png yet")
        return
    # the sheet is black ink on a magenta ground: key first, then invert to ink
    keyed = os.path.join(SRC, "_rabbit_keyed.png")
    img = key_chroma(src, keyed, lo=55, hi=115)
    white_ink(img, os.path.join(IMG, "rabbit.png"), gain=1.06)
    return
    # ink = darkness inside the kept silhouette
    a = np.asarray(img.convert("RGB")).astype(np.float32) / 255.0
    alpha = np.asarray(img.getchannel("A")).astype(np.float32) / 255.0
    lum = a @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    ink = np.clip((1.0 - lum) * 1.06, 0, 1) * alpha
    h, w = ink.shape
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[..., 0], out[..., 1], out[..., 2] = 255, 240, 247
    out[..., 3] = (ink * 255).astype(np.uint8)
    final = Image.fromarray(out, "RGBA").filter(ImageFilter.GaussianBlur(0.3))
    final = drop_specks(final)
    bbox = final.getchannel("A").point(lambda v: 255 if v > 10 else 0).getbbox()
    if bbox:
        final = final.crop(bbox)
    final.save(os.path.join(IMG, "rabbit.png"))
    print("hero rabbit.png", final.size)


STEPS = {"fonts": fonts, "static": static_gif, "glass": glass_overlay,
         "grain": grain, "sprites": sprites, "hero": hero}

if __name__ == "__main__":
    for name in (sys.argv[1:] or list(STEPS)):
        STEPS[name]()

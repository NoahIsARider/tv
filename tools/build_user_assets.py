#!/usr/bin/env python
"""Build the site's raster assets from the owner's own renders.

    python tools/build_user_assets.py

Outputs
    site/img/tv.png          keyed television, trimmed
    site/img/tv-mask.png     alpha mask of the glass, same box as tv.png
    site/img/tv-geo.css      --gl-* variables for the glass box
    site/img/bg.jpg          graded full-bleed background
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "site", "img")
USER = os.path.join(ROOT, "src", "user")   # owner's originals, not deployed
SITE = os.path.join(ROOT, "site")


def build_tv():
    src = Image.open(os.path.join(USER, "tv-silver.png")).convert("RGBA")
    a = np.asarray(src)
    alpha = a[..., 3]
    ys, xs = np.where(alpha > 8)
    pad = 3
    box = (max(int(xs.min()) - pad, 0), max(int(ys.min()) - pad, 0),
           min(int(xs.max()) + pad, src.width), min(int(ys.max()) + pad, src.height))
    tv = src.crop(box)
    w, h = tv.size
    tv.save(os.path.join(IMG, "tv.png"))

    # flood fill the glass on a WHITE-flattened copy, or the transparent border
    # (black RGB, alpha 0) merges with the black screen and swallows the frame
    flat = Image.new("RGB", tv.size, (255, 255, 255))
    flat.paste(tv, (0, 0), tv)
    # the screen is essentially black (0-1) while the shadow band under the top
    # bezel sits around 45-80, so a hard threshold separates them and the band
    # keeps its shadow instead of being punched out with the glass
    Lf = np.asarray(flat.convert("L"))
    binim = Image.fromarray(((Lf < 35) * 255).astype(np.uint8))
    work = binim.convert("RGB")
    ImageDraw.floodfill(work, (int(w * 0.5), int(h * 0.5)), (255, 0, 255), thresh=0)
    arr = np.asarray(work)
    glass = (arr[..., 0] == 255) & (arr[..., 1] == 0) & (arr[..., 2] == 255)
    ys2, xs2 = np.where(glass)
    x0, x1, y0, y1 = int(xs2.min()), int(xs2.max()), int(ys2.min()), int(ys2.max())

    m = Image.fromarray((glass * 255).astype(np.uint8))
    # grow the aperture a little: the glass has a lighter bevel inside it, and
    # leaving any of it shows up as a dark rim around the static
    m = m.filter(ImageFilter.MaxFilter(9))
    m = m.filter(ImageFilter.GaussianBlur(1.2))
    # the box everything else is measured from is the DILATED aperture, not the
    # raw flood fill, or the hole ends up wider than the element that fills it
    ma = np.asarray(m)
    ys3, xs3 = np.where(ma > 24)
    dx0, dx1, dy0, dy1 = int(xs3.min()), int(xs3.max()), int(ys3.min()), int(ys3.max())
    padm = 2
    cx0, cy0 = max(dx0 - padm, 0), max(dy0 - padm, 0)
    cx1, cy1 = min(dx1 + padm, w), min(dy1 + padm, h)
    m = m.crop((cx0, cy0, cx1, cy1))
    # save as RGBA with the shape in ALPHA: a greyscale PNG is an ambiguous
    # mask source and Chrome can end up hiding everything
    rgba = Image.new("RGBA", m.size, (255, 255, 255, 0))
    rgba.putalpha(m)
    rgba.save(os.path.join(IMG, "tv-mask.png"))

    # a copy of the chassis with the glass punched out: the page puts the screen
    # content BEHIND it, so the bezel's own curve does the clipping and no CSS
    # mask is involved
    hole = Image.new("L", tv.size, 0)
    hole.paste(m, (cx0, cy0))
    hole = hole.filter(ImageFilter.GaussianBlur(1.0))
    tv_arr = np.asarray(tv).copy()
    tv_arr[..., 3] = (tv_arr[..., 3].astype(np.float32) * (1.0 - np.asarray(hole).astype(np.float32) / 255.0)).astype(np.uint8)
    Image.fromarray(tv_arr, "RGBA").save(os.path.join(IMG, "tv-window.png"))
    print("tv-window.png written")
    print("tv-mask.png", m.size)

    gx0, gy0, gx1, gy1 = cx0, cy0, cx1, cy1
    css = """:root{{
  /* glass box inside img/tv.png, written by tools/build_user_assets.py.
     Grown 6px past the measured edge so the screen content runs under the
     bezel instead of leaving a dark rim. */
  --gl-left:{l:.3f}%;
  --gl-top:{t:.3f}%;
  --gl-w:{w:.3f}%;
  --gl-h:{h:.3f}%;
}}
""".format(l=gx0 / w * 100, t=gy0 / h * 100,
           w=(gx1 - gx0) / w * 100, h=(gy1 - gy0) / h * 100)
    open(os.path.join(SITE, "tv-geo.css"), "w", encoding="utf-8").write(css)
    print("tv.png", tv.size, "glass px", (x0, y0, x1, y1),
          "pct", round(x0 / w * 100, 1), round(y0 / h * 100, 1),
          round((x1 - x0) / w * 100, 1), round((y1 - y0) / h * 100, 1))


def build_bg():
    im = Image.open(os.path.join(USER, "beach-night.png")).convert("RGB")
    w, h = im.size
    # trim the black window frame at the far left, keep the city glow
    left = int(w * 0.045)
    im = im.crop((left, 0, w, h))
    w, h = im.size
    target = 16 / 9
    if w / h > target:                       # too wide, keep the left (city) side
        nw = int(h * target)
        im = im.crop((int((w - nw) * 0.18), 0, int((w - nw) * 0.18) + nw, h))
    im = im.resize((1760, round(1760 * im.height / im.width)), Image.LANCZOS)

    a = np.asarray(im).astype(np.float32) / 255.0
    lum = a @ np.array([0.299, 0.587, 0.114], dtype=np.float32)

    # a little more rose in the highs, a little more violet in the shadows
    a = a + ((lum ** 2.2)[..., None] * np.array([0.10, 0.0, 0.05], dtype=np.float32))
    a = a + (((1 - lum) ** 2.4)[..., None] * np.array([0.05, 0.0, 0.09], dtype=np.float32))
    a = np.clip(a, 0, 1)

    base = Image.fromarray((a * 255).astype(np.uint8))
    bloom = base.filter(ImageFilter.GaussianBlur(18))
    b = np.asarray(bloom).astype(np.float32) / 255.0
    a = 1.0 - (1.0 - a) * (1.0 - b * 0.30)

    hh, ww = a.shape[:2]
    yy, xx = np.mgrid[0:hh, 0:ww]
    r = np.sqrt(((xx - ww / 2) / (ww / 2)) ** 2 + ((yy - hh / 2) / (hh / 2)) ** 2) / 1.414
    a *= (1.0 - 0.34 * r ** 2.0)[..., None]

    rng = np.random.default_rng(5)
    a = np.clip(a + rng.normal(0, 0.013, (hh, ww, 1)), 0, 1)

    out = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.4))
    out.save(os.path.join(IMG, "bg.jpg"), quality=88, optimize=True, progressive=True)
    print("bg.jpg", out.size, os.path.getsize(os.path.join(IMG, "bg.jpg")))


if __name__ == "__main__":
    build_tv()
    build_bg()

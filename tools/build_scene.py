#!/usr/bin/env python
"""Cut the owner's scene art into the pieces the page places.

    python tools/build_scene.py

Inputs   src/user/rabbit-rider.png, objects.png, spread.png, rabbit-dog.png
Outputs  site/img/rabbit.png, rabbit-dog.png, obj-*.png, spread.png

Every source is white ink on black, so nothing is keyed: the page blends each
piece with mix-blend-mode:screen and black simply disappears.
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src", "user")
IMG = os.path.join(ROOT, "site", "img")


def trim_black(im, thresh=24, pad=6):
    a = np.asarray(im.convert("L")).astype(np.float32)
    ys, xs = np.where(a > thresh)
    if not len(ys):
        return im
    box = (max(int(xs.min()) - pad, 0), max(int(ys.min()) - pad, 0),
           min(int(xs.max()) + pad, im.width), min(int(ys.max()) + pad, im.height))
    return im.crop(box)


def blobs(im, grid=96, floor=0.004):
    """Coarse connected components of bright pixels -> bboxes, reading order."""
    a = np.asarray(im.convert("L")).astype(np.float32) / 255.0
    h, w = a.shape
    gh = grid * h // w
    cells = np.zeros((gh, grid), dtype=bool)
    for y in range(gh):
        for x in range(grid):
            cells[y, x] = a[y * h // gh:(y + 1) * h // gh,
                            x * w // grid:(x + 1) * w // grid].mean() > 0.03
    seen = np.zeros_like(cells)
    out = []
    for sy in range(gh):
        for sx in range(grid):
            if not cells[sy, sx] or seen[sy, sx]:
                continue
            stack, comp = [(sy, sx)], []
            seen[sy, sx] = True
            while stack:
                cy, cx = stack.pop()
                comp.append((cy, cx))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < gh and 0 <= nx < grid and cells[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
            if len(comp) / (gh * grid) < floor:
                continue
            ys = [c[0] for c in comp]
            xs = [c[1] for c in comp]
            x0, x1 = min(xs) * w // grid, (max(xs) + 1) * w // grid
            y0, y1 = min(ys) * h // gh, (max(ys) + 1) * h // gh
            out.append((y0, x0, x1, y1, len(comp)))
    out.sort(key=lambda t: (0 if t[0] < h * 0.5 else 1, t[1]))
    return out


def book_mask(L, grid=260):
    """1 inside the book, 0 for the surround, by flooding the coarse border in."""
    h, w = L.shape
    gh = max(int(grid * h / w), 8)
    cells = np.zeros((gh, grid), dtype=bool)
    for y in range(gh):
        for x in range(grid):
            cells[y, x] = L[y * h // gh:(y + 1) * h // gh,
                            x * w // grid:(x + 1) * w // grid].mean() > 25
    outside = np.zeros_like(cells)
    stack = []
    for y in range(gh):
        for x in (0, grid - 1):
            if not cells[y, x] and not outside[y, x]:
                outside[y, x] = True
                stack.append((y, x))
    for x in range(grid):
        for y in (0, gh - 1):
            if not cells[y, x] and not outside[y, x]:
                outside[y, x] = True
                stack.append((y, x))
    while stack:
        cy, cx = stack.pop()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < gh and 0 <= nx < grid and not cells[ny, nx] and not outside[ny, nx]:
                outside[ny, nx] = True
                stack.append((ny, nx))
    full = np.kron(~outside, np.ones((h // gh + 1, w // grid + 1), dtype=bool))[:h, :w]
    return full.astype(np.float32)


def to_alpha(im, tint=(255, 242, 248), gain=1.0, gamma=1.0, pad=0):
    """White ink on black -> a real cut-out: alpha is the ink, colour is flat."""
    a = np.asarray(im.convert("L")).astype(np.float32) / 255.0
    alpha = np.clip((a ** gamma) * gain, 0, 1)
    h, w = alpha.shape
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[..., 0], out[..., 1], out[..., 2] = tint
    out[..., 3] = (alpha * 255).astype(np.uint8)
    img = Image.fromarray(out, "RGBA")
    bbox = img.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if bbox:
        img = img.crop((max(bbox[0] - pad, 0), max(bbox[1] - pad, 0),
                        min(bbox[2] + pad, w), min(bbox[3] + pad, h)))
    return img


def main():
    # ---- the two characters -------------------------------------------
    for src, dst in (("rabbit-rider.png", "rabbit.png"),
                     ("rabbit-dog.png", "rabbit-dog.png")):
        im = Image.open(os.path.join(SRC, src)).convert("RGB")
        im = trim_black(im, thresh=18, pad=4)
        to_alpha(im, gain=1.04, pad=3).save(os.path.join(IMG, dst))
        print(dst, Image.open(os.path.join(IMG, dst)).size)

    # ---- the six objects, cut one by one ------------------------------
    objs = Image.open(os.path.join(SRC, "objects.png")).convert("RGB")
    boxes = blobs(objs)
    names = ["obj-book", "obj-backpack", "obj-walkman",
             "obj-cassettes", "obj-laptop", "obj-map"]
    print("found", len(boxes), "blobs")
    if len(boxes) != 6:
        for b in boxes:
            print("  blob", b)
    for name, (y0, x0, x1, y1, _) in zip(names, boxes):
        pad = 10
        piece = objs.crop((max(x0 - pad, 0), max(y0 - pad, 0),
                           min(x1 + pad, objs.width), min(y1 + pad, objs.height)))
        piece = trim_black(piece, thresh=18, pad=4)
        to_alpha(piece, gain=1.05, pad=3).save(os.path.join(IMG, name + ".png"))
        print(name, Image.open(os.path.join(IMG, name + ".png")).size)

    # ---- the notebook spread --------------------------------------------
    # spread2.png is already light ink on a black ground, so it only needs the
    # alpha cut; the page stretches it to the screen with object-fit:fill
    sp = Image.open(os.path.join(SRC, "spread2.png")).convert("RGB")
    sp = trim_black(sp, thresh=16, pad=2)
    to_alpha(sp, gain=1.05, pad=2).save(os.path.join(IMG, "spread.png"))
    print("spread.png", Image.open(os.path.join(IMG, "spread.png")).size)


def favicon():
    """The map file icon, on a dark round tile, for the browser tab."""
    src = Image.open(os.path.join(IMG, "obj-map.png")).convert("RGBA")
    size = 256
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=58,
                        fill=(13, 8, 16, 255))
    inner = src.copy()
    inner.thumbnail((int(size * 0.80), int(size * 0.80)), Image.LANCZOS)
    tile.alpha_composite(inner, ((size - inner.width) // 2,
                                 (size - inner.height) // 2))
    tile.save(os.path.join(IMG, "favicon.png"))
    tile.resize((32, 32), Image.LANCZOS).save(
        os.path.join(IMG, "favicon-32.png"))
    print("favicon.png", os.path.getsize(os.path.join(IMG, "favicon.png")))


if __name__ == "__main__":
    main()
    favicon()

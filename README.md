# tangled-home

The page served at `noahisarider.tngl.io`, published from this repository by
Tangled Sites.

## What it is

A silver CRT television floating over a night beach. The screen is running
static until you click it; then the set grows to fill the window and the
screen shows a rabbit courier on a motorbike with nine engraved objects
floating around it, plus a single link out to Tangled.

Everything is a raster asset. Nothing is drawn in CSS or SVG, no canvas, no
runtime graphics library.

## Layout

```
site/                 the deploy directory (Tangled Sites -> deploy dir "site")
  index.html          the whole page: markup, styles, 40 lines of JS
  tv-geo.css          the glass rectangle inside img/tv.png, generated
  img/
    bg.jpg            graded night beach background
    tv.png            the keyed television
    tv-window.png     the same set with the glass punched out
    tv-mask.png       the glass shape (alpha), used to build tv-window.png
    static.gif        12 frames of CRT static
    glass.png         sheen and edge vignette drawn over the screen
    grain.png         tiling film grain for the page
    rabbit.png        the character, converted to white ink on transparency
    s1..s9.png        the nine floating objects, same conversion
  fonts/              Permanent Marker, Special Elite, Rock Salt (all OFL)
tools/
  build_user_assets.py   owner's renders -> tv.png, tv-window.png, tv-geo.css, bg.jpg
  build_assets.py        fonts, static, glass, grain, sprite slicing, ink conversion
  gen.py                 FLUX space generator (fallback)
  gen_codex.py           queue runner for codex image_gen
prompts/                 the prompts used for each generated asset
```

## Why the screen sits behind the chassis

`#glass` is positioned inside `#tvwrap` at the rectangle stored in
`tv-geo.css`, and `img/tv-window.png` is drawn on top of it with the glass area
made transparent. The bezel's own inner curve does the clipping, so the static
and the artwork follow the real CRT shape. A CSS mask was tried first and
rendered the screen blank in headless Chrome, so it was dropped.

## Rebuilding

```
python tools/build_user_assets.py     # after replacing a file in site/img/user/
python tools/build_assets.py fonts static glass grain sprites hero
```

`site/img/user/` holds the owner's original renders and is not deployed.

## Deploying

Repository Settings -> Sites: branch `main`, deploy directory `site`, site type
`Index site`. Pushing to `main` redeploys.

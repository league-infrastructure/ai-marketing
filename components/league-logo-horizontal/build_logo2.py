"""Builds logo-arced-2.svg end to end -- checkpoint 2, a variant of checkpoint 1
(build_logo.py / logo-arced-1.svg) with a dramatically different AMAZING curve and a
different PROGRAMMERS placement. Differences from checkpoint 1, all per direct design
feedback:

  - AMAZING's curve is column-only (Pillow MESH, top/bottom stretch per column) with
    NO horizontal flare -- an earlier attempt added a row-based horizontal flare to
    splay the sides outward, which was explicitly rejected ("I don't want it angled").
  - The curve direction is CONVEX the opposite way from a first (also rejected)
    attempt: A and G droop DOWN, the compressed center (Z/I/N) bows UP, not a pointed
    V dipping down at the center. bot_off is POSITIVE (droop) at the word's edges and
    strongly NEGATIVE (pulled up) at the center -- see bot_shape() below.
  - The curve is exaggerated far past a "natural" look: G's rendered height is
    exactly 3.25x Z's rendered height (was 2.0x in the prior round; Eric asked for
    "more curve" after seeing 2.0x).
  - The drop shadow is composited AFTER warping (uniform pixel offset on the warped
    result), not baked into the flat pre-warp render. Baking it in pre-warp was the
    actual root cause of an earlier "twisted/sheared" look Eric rejected -- the
    shadow's constant offset got stretched unevenly across the dramatic curve and
    created visual noise that read as broken letterforms. Warping a shadow-free
    render and adding a clean constant-offset shadow afterward fixed it.
  - The flat render is done at device_scale_factor=4 (not 3) and the warp uses
    segments=400 (not ~80-100), specifically to eliminate visible column-boundary
    "staircase" jaggies that showed up once the curve got this steep.
  - PROGRAMMERS is NOT stretched to AMAZING's width. It sits at font-size 90, natural
    width, centered, and is pulled UP to nest in the curve's central valley -- the
    empty space under the compressed center letters, well short of where A/G's
    drooping tips reach. Its position is derived from measuring how deep the ink
    actually goes within PROGRAMMERS' own horizontal span (not overall AMAZING ink
    depth, which is dominated by the far-out A/G tips at the edges).

Run with:
    uv run --with playwright --with pillow --with numpy python3 build_logo2.py
"""
import base64
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent.parent
FONT_PATH = REPO_ROOT / "projects/_fonts/TradeGothicLTPro-Bold.ttf"
FLAT_HTML = HERE / "flat-amazing-2.html"
OUT_SVG = HERE / "logo-arced-2.svg"

sys.path.insert(0, str(HERE))
from column_warp import column_warp  # noqa: E402

GAP = 16
ROW_GAP = 24
TARGET_W = 960
TLO_FS = 70
PROG_FS = 90
EDGE_DROOP = 0.30    # bot_off at f=0 and f=1 (A, G): +30% of word height, hangs DOWN
CENTER_LIFT = -0.60  # bot_off at f=0.5 (Z/I/N): -60% of word height, pulled UP
# ratio of rendered heights = (1+EDGE_DROOP) / (1+CENTER_LIFT) = 1.30/0.40 = 3.25x
SEGMENTS = 400
DSF = 4  # device_scale_factor for the flat render
SHADOW_OFFSET = 13

BOLT_PATH_D = """M3849 5311 c-30 -32 -299 -317 -599 -633 -481 -506 -1414 -1495
      -1757 -1863 -67 -71 -119 -133 -115 -136 4 -4 214 -82 467 -174 253 -92 461
      -168 463 -170 4 -3 -106 -310 -487 -1358 -188 -515 -341 -940 -341 -942 0 -7
      138 136 721 750 266 281 781 822 1144 1204 363 381 666 701 673 711 11 16 -1
      22 -135 70 -454 161 -803 295 -803 307 0 2 187 517 415 1145 229 627 414 1142
      412 1145 -3 2 -29 -23 -58 -56z"""
BOLT_G = f'''    <g id="boltpath" transform="translate(-137.787849,536.678602) scale(0.1,-0.1)">
      <path d="{BOLT_PATH_D}"/>
    </g>'''


def render_flat_amazing():
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1300, "height": 340}, device_scale_factor=DSF)
        page.goto(f"file://{FLAT_HTML}")
        page.wait_for_timeout(300)
        page.screenshot(path=str(HERE / "_flat_tmp.png"), omit_background=True)
        b.close()
    img = Image.open(HERE / "_flat_tmp.png")
    bbox = img.getbbox()
    img = img.crop(bbox)
    (HERE / "_flat_tmp.png").unlink()
    return img


def bot_shape(f):
    return EDGE_DROOP - (EDGE_DROOP - CENTER_LIFT) * (1 - (2 * f - 1) ** 2)


def warp_and_shadow(flat_img):
    fs = [0, 0.25, 0.5, 0.75, 1]
    top_coef = np.polyfit(fs, [0, 0, 0, 0, 0], 2)
    bot_coef = np.polyfit(fs, [bot_shape(f) for f in fs], 2)

    warped = column_warp(flat_img, word_h=flat_img.size[1], segments=SEGMENTS,
                          top_coef=top_coef, bot_coef=bot_coef)
    bbox = warped.getbbox()
    main = warped.crop(bbox)

    w, h = main.size
    pad = 24
    canvas = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    arr = np.array(main)
    alpha = arr[..., 3]
    shadow_arr = np.zeros_like(arr)
    shadow_arr[..., 0] = 0x10
    shadow_arr[..., 1] = 0x10
    shadow_arr[..., 2] = 0x10
    shadow_arr[..., 3] = alpha
    shadow_img = Image.fromarray(shadow_arr, "RGBA")
    canvas.paste(shadow_img, (pad + SHADOW_OFFSET, pad + SHADOW_OFFSET), shadow_img)
    canvas.paste(main, (pad, pad), main)
    bbox = canvas.getbbox()
    return canvas.crop(bbox)


def measure_ink():
    measure_html = HERE / "_measure_tmp.html"
    measure_html.write_text(f'''<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
 @font-face {{ font-family:'TradeGothicBold';
   src:url('file://{FONT_PATH}') format('truetype'); }}
 body{{margin:0;background:#fff;}}
 .row-text{{font-family:'TradeGothicBold',sans-serif;fill:#101010;stroke:#101010;
   stroke-width:2px;stroke-linejoin:miter;paint-order:stroke fill;}}
</style></head><body>
<svg width="2000" height="1800" xmlns="http://www.w3.org/2000/svg">
  <defs>{BOLT_G}</defs>
  <use id="bolt" href="#boltpath" fill="#101010" transform="translate(50,50)"/>
  <text id="tlo" x="50" y="900" class="row-text" font-size="{TLO_FS}">THE LEAGUE OF</text>
</svg></body></html>''')
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 2000, "height": 1800}, device_scale_factor=1)
        page.goto(f"file://{measure_html}")
        page.wait_for_timeout(300)
        page.screenshot(path=str(HERE / "_measure_tmp.png"))
        b.close()
    measure_html.unlink()

    arr = np.array(Image.open(HERE / "_measure_tmp.png").convert("L"))
    (HERE / "_measure_tmp.png").unlink()

    def ink_bounds(region, y_off=0):
        dark = region < 128
        rows = np.where(dark.any(axis=1))[0]
        cols = np.where(dark.any(axis=0))[0]
        return dict(top=int(rows.min()) + y_off, bottom=int(rows.max()) + y_off,
                    left=int(cols.min()), right=int(cols.max()))

    bolt = ink_bounds(arr[0:600, 0:600])
    tlo = ink_bounds(arr[600:1000, 0:600], y_off=600)
    return bolt, tlo


def measure_amazing_center_ink_bottom(amazing_img):
    """How deep the ink goes within the middle 60% of AMAZING's width (where
    PROGRAMMERS will sit) -- NOT the overall bottom, which is dominated by A/G's
    drooping tips far out at the edges and would make PROGRAMMERS sit way too low."""
    arr = np.array(amazing_img.convert("RGBA"))
    alpha = arr[..., 3]
    h, w = alpha.shape
    lo, hi = int(w * 0.20), int(w * 0.80)
    bottoms = []
    for x in range(lo, hi, 10):
        col = alpha[:, x]
        opaque = np.where(col > 100)[0]
        if len(opaque):
            bottoms.append(opaque.max())
    return max(bottoms) / h  # fraction of image height


def build_svg(amazing_img, bolt, tlo, center_ink_frac):
    bolt_h, bolt_w = bolt["bottom"] - bolt["top"], bolt["right"] - bolt["left"]
    tlo_h, tlo_w = tlo["bottom"] - tlo["top"], tlo["right"] - tlo["left"]
    bolt_scale = tlo_h / bolt_h
    bolt_w_scaled = bolt_w * bolt_scale
    row1_w = bolt_w_scaled + GAP + tlo_w + GAP + bolt_w_scaled
    row1_h = tlo_h
    scale_x1 = TARGET_W / row1_w
    left_bolt_tx = bolt_w_scaled
    text_x = bolt_w_scaled + GAP
    text_y = row1_h
    right_bolt_tx = bolt_w_scaled + GAP + tlo_w + GAP

    box_x, box_y, box_w, box_h = 288, 220, 960, 280
    aw, ah = amazing_img.size
    rendered_h = box_w / (aw / ah)
    pad = (box_h - rendered_h) / 2
    amz_ink_top = box_y + pad

    row1_top = amz_ink_top - ROW_GAP - row1_h

    # PROGRAMMERS: measure its own natural size via a throwaway render, then tuck it
    # up so its top sits just below the center ink, not the far-out A/G tips.
    prog_html = HERE / "_prog_tmp.html"
    prog_html.write_text(f'''<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
 @font-face {{ font-family:'TradeGothicBold';
   src:url('file://{FONT_PATH}') format('truetype'); }}
 body{{margin:0;background:#fff;}}
 .row-text{{font-family:'TradeGothicBold',sans-serif;fill:#101010;stroke:#101010;
   stroke-width:2px;stroke-linejoin:miter;paint-order:stroke fill;}}
</style></head><body>
<svg width="1200" height="300" xmlns="http://www.w3.org/2000/svg">
  <text id="prog" x="50" y="200" class="row-text" font-size="{PROG_FS}">PROGRAMMERS</text>
</svg></body></html>''')
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1200, "height": 300}, device_scale_factor=1)
        page.goto(f"file://{prog_html}")
        page.wait_for_timeout(200)
        page.screenshot(path=str(HERE / "_prog_tmp.png"))
        b.close()
    prog_html.unlink()
    parr = np.array(Image.open(HERE / "_prog_tmp.png").convert("L"))
    (HERE / "_prog_tmp.png").unlink()
    dark = parr < 128
    rows = np.where(dark.any(axis=1))[0]
    prog_h = int(rows.max() - rows.min())
    prog_baseline_from_top = 200 - int(rows.min())

    center_ink_y = box_y + pad + center_ink_frac * rendered_h
    row2_top = center_ink_y + 15  # small buffer clear of the center letters' ink
    row2_baseline = row2_top + prog_baseline_from_top

    ribbon_ink_top_wanted = row2_top + prog_h + ROW_GAP
    # +20 (rect top offset) +4 (stroke bleed) +20 (extra clearance -- A/G's drooping
    # tips reach almost to the ribbon at this curve depth; confirmed by rendering and
    # measuring the gap, not assumed)
    ribbon_translate_y = ribbon_ink_top_wanted + 20 + 4 + 20

    font_b64 = base64.b64encode(FONT_PATH.read_bytes()).decode()
    buf = HERE / "_amz_tmp.png"
    amazing_img.save(buf)
    img_b64 = base64.b64encode(buf.read_bytes()).decode()
    buf.unlink()

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="1536" height="1024" viewBox="0 0 1536 1024" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
<title>The League of Amazing Programmers — horizontal arced wordmark (checkpoint 2)</title>
<desc>Self-contained vector wordmark, variant 2: Trade Gothic Pro Bold (embedded), a
dramatically deeper convex bow on "AMAZING" (A/G drooping to roughly 3.25x the
rendered height of the compressed center letters Z/I/N -- flat top, no side flare,
verticals stay vertical), and "PROGRAMMERS" pulled up to nest in the curve's central
valley.</desc>
<defs>
  <style>
   @font-face {{
     font-family: 'TradeGothicBold';
     src: url('data:font/ttf;base64,{font_b64}') format('truetype');
     font-weight: 700;
   }}
   .row-text{{font-family:'TradeGothicBold',sans-serif;fill:#101010;stroke:#101010;stroke-width:2px;stroke-linejoin:miter;paint-order:stroke fill;}}
   .ribbon-text{{font-family:'TradeGothicBold',sans-serif;font-size:34px;letter-spacing:2px;fill:#101010;}}
  </style>
{BOLT_G}
</defs>

<g transform="translate(288,{row1_top:.4f}) scale({scale_x1:.6f},1)">
  <use href="#boltpath" fill="#101010" transform="translate({left_bolt_tx:.4f},0) scale({-bolt_scale:.6f},{bolt_scale:.6f})"/>
  <text x="{text_x:.4f}" y="{text_y:.4f}" class="row-text" font-size="{TLO_FS}">THE LEAGUE OF</text>
  <use href="#boltpath" fill="#101010" transform="translate({right_bolt_tx:.4f},0) scale({bolt_scale:.6f},{bolt_scale:.6f})"/>
</g>

<image href="data:image/png;base64,{img_b64}"
       x="{box_x}" y="{box_y}" width="{box_w}" height="{box_h}" preserveAspectRatio="xMidYMid meet"/>

<text x="768" y="{row2_baseline:.4f}" text-anchor="middle" class="row-text" font-size="{PROG_FS}">PROGRAMMERS</text>

<g transform="translate(768,{ribbon_translate_y:.4f})">
  <polygon points="-420,-20 -560,-20 -495,17.5 -560,55 -420,55"
           fill="#fff" stroke="#101010" stroke-width="8" stroke-linejoin="round"/>
  <polygon points="420,-20 560,-20 495,17.5 560,55 420,55"
           fill="#fff" stroke="#101010" stroke-width="8" stroke-linejoin="round"/>
  <rect x="-420" y="-20" width="840" height="75" fill="#fff" stroke="#101010" stroke-width="8"/>
  <text x="0" y="35" text-anchor="middle" class="ribbon-text">SMART MINDS &#183; BOLD IDEAS &#183; BRIGHT FUTURES</text>
</g>
</svg>
'''


if __name__ == "__main__":
    flat = render_flat_amazing()
    amazing_img = warp_and_shadow(flat)
    amazing_img.save(HERE / "amazing-warped-2.png")
    bolt, tlo = measure_ink()
    center_ink_frac = measure_amazing_center_ink_bottom(amazing_img)
    print("bolt/tlo ink:", json.dumps(dict(bolt=bolt, tlo=tlo)))
    print("center ink fraction:", center_ink_frac)
    svg = build_svg(amazing_img, bolt, tlo, center_ink_frac)
    OUT_SVG.write_text(svg)
    print("wrote", OUT_SVG, OUT_SVG.stat().st_size, "bytes")

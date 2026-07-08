"""Builds logo-arced-1.svg end to end: measures the REAL rendered ink of the bolt and
of "THE LEAGUE OF" / "PROGRAMMERS" (not SVG getBBox(), which over-reports text bbox
height by ~35-40% due to stroke-miter/font-metric padding -- confirmed by direct pixel
comparison), then lays out four rows (bolt+THE LEAGUE OF+bolt, AMAZING, PROGRAMMERS,
ribbon) with equal 24px gaps between each one's ink, and writes a self-contained SVG
(font + AMAZING raster embedded as base64 data URIs, no external file dependencies).

Run with:
    uv run --with playwright --with pillow --with numpy python3 build_logo.py

Prerequisites (already run once, see logo-arced.md "Regenerating AMAZING" section):
  1. flat-amazing.html rendered via Playwright at device_scale_factor=3, trimmed
  2. column_warp.py applied to the trimmed flat render, output trimmed again
     -> amazing-warped.png (checked into this directory)
This script does NOT redo that warp step -- it only lays out the four rows around
the already-warped AMAZING raster and re-measures the bolt/text ink each run, so it
stays correct if the font or bolt path ever changes.
"""
import base64
import json
from pathlib import Path

from playwright.sync_api import sync_playwright
from PIL import Image
import numpy as np

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent.parent
FONT_PATH = REPO_ROOT / "projects/_fonts/TradeGothicLTPro-Bold.ttf"
AMAZING_RASTER = HERE / "amazing-warped.png"
OUT_SVG = HERE / "logo-arced-1.svg"

GAP = 16          # natural-space gap (px, pre-stretch) between bolt and "THE LEAGUE OF"
ROW_GAP = 24       # rendered gap (SVG units) between every row's ink: row1/AMAZING/row2/ribbon
TARGET_W = 960     # width every row is stretched to match (== AMAZING's width)
TLO_FS = 70        # "THE LEAGUE OF" font-size
PROG_FS = 140      # "PROGRAMMERS" font-size -- double TLO_FS, keeps its natural width
                   # close to TARGET_W so the horizontal stretch barely distorts it

BOLT_PATH_D = """M3849 5311 c-30 -32 -299 -317 -599 -633 -481 -506 -1414 -1495
      -1757 -1863 -67 -71 -119 -133 -115 -136 4 -4 214 -82 467 -174 253 -92 461
      -168 463 -170 4 -3 -106 -310 -487 -1358 -188 -515 -341 -940 -341 -942 0 -7
      138 136 721 750 266 281 781 822 1144 1204 363 381 666 701 673 711 11 16 -1
      22 -135 70 -454 161 -803 295 -803 307 0 2 187 517 415 1145 229 627 414 1142
      412 1145 -3 2 -29 -23 -58 -56z"""
BOLT_G = f'''    <g id="boltpath" transform="translate(-137.787849,536.678602) scale(0.1,-0.1)">
      <path d="{BOLT_PATH_D}"/>
    </g>'''


def ink_bounds(gray_arr, thresh=128):
    dark = gray_arr < thresh
    rows = np.where(dark.any(axis=1))[0]
    cols = np.where(dark.any(axis=0))[0]
    return dict(top=int(rows.min()), bottom=int(rows.max()),
                left=int(cols.min()), right=int(cols.max()))


def measure_ink():
    """Render bolt / THE LEAGUE OF / PROGRAMMERS in isolated, non-overlapping regions
    of one throwaway SVG and read back their true ink pixel bounds -- this is the
    step that replaces (and corrects) SVG getBBox()."""
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
  <text id="prog" x="50" y="1700" class="row-text" font-size="{PROG_FS}">PROGRAMMERS</text>
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
    bolt = ink_bounds(arr[0:600, 0:600])
    tlo = ink_bounds(arr[600:1000, 0:600]);  tlo = {k: v + 600 if k in ("top", "bottom") else v for k, v in tlo.items()}
    prog = ink_bounds(arr[1000:1800, 0:1000]); prog = {k: v + 1000 if k in ("top", "bottom") else v for k, v in prog.items()}
    (HERE / "_measure_tmp.png").unlink()
    return bolt, tlo, prog


def compute_layout(bolt, tlo, prog):
    bolt_h, bolt_w = bolt["bottom"] - bolt["top"], bolt["right"] - bolt["left"]
    tlo_h, tlo_w = tlo["bottom"] - tlo["top"], tlo["right"] - tlo["left"]
    prog_h, prog_w = prog["bottom"] - prog["top"], prog["right"] - prog["left"]

    bolt_scale = tlo_h / bolt_h          # bolt ink height == "THE LEAGUE OF" ink height
    bolt_w_scaled = bolt_w * bolt_scale

    row1_w = bolt_w_scaled + GAP + tlo_w + GAP + bolt_w_scaled
    row1_h = tlo_h
    scale_x1 = TARGET_W / row1_w
    scale_x2 = TARGET_W / prog_w

    # AMAZING's real ink sits inside its 960x280 box with vertical letterboxing
    # (preserveAspectRatio="xMidYMid meet"): compute the true ink top/bottom so the
    # 24px gaps are measured against ink, not the box's nominal edges.
    amz = Image.open(AMAZING_RASTER)
    amz_w, amz_h = amz.size
    box_w, box_h, box_x, box_y = 960, 280, 288, 220
    rendered_h = box_w * amz_h / amz_w   # width-constrained (raster is much wider than tall)
    pad = (box_h - rendered_h) / 2
    amz_ink_top = box_y + pad
    amz_ink_bottom = box_y + box_h - pad

    row1_top = amz_ink_top - ROW_GAP - row1_h
    row2_top = amz_ink_bottom + ROW_GAP
    row2_h = prog_h
    ribbon_ink_top_wanted = row2_top + row2_h + ROW_GAP
    # ribbon rect top = translate_y - 20, and its 8px stroke bleeds the visible ink up
    # by ~4px (half the stroke width) -- confirmed by measuring the rendered banner,
    # so nudge the nominal translate down by that amount to make the ink gap true.
    ribbon_translate_y = ribbon_ink_top_wanted + 20 + 4

    left_bolt_tx = bolt_w_scaled
    text_x = bolt_w_scaled + GAP
    text_y = row1_h
    right_bolt_tx = bolt_w_scaled + GAP + tlo_w + GAP

    return dict(
        bolt_scale=bolt_scale, bolt_w_scaled=bolt_w_scaled,
        row1_w=row1_w, row1_h=row1_h, scale_x1=scale_x1, scale_x2=scale_x2,
        left_bolt_tx=left_bolt_tx, text_x=text_x, text_y=text_y, right_bolt_tx=right_bolt_tx,
        row1_top=row1_top, row2_top=row2_top, prog_text_y=row2_h,
        ribbon_translate_y=ribbon_translate_y,
        amz_ink_top=amz_ink_top, amz_ink_bottom=amz_ink_bottom,
    )


def build_svg(L):
    font_b64 = base64.b64encode(FONT_PATH.read_bytes()).decode()
    img_b64 = base64.b64encode(AMAZING_RASTER.read_bytes()).decode()

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="1536" height="1024" viewBox="0 0 1536 1024" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
<title>The League of Amazing Programmers — horizontal arced wordmark (checkpoint 1)</title>
<desc>Self-contained vector wordmark: Trade Gothic Pro Bold (embedded), potrace-traced
League bolt, and a column-warped "AMAZING" raster (embedded) bowed along independently
measured top/bottom curves. All row spacing is uniform at {ROW_GAP}px between THE LEAGUE OF,
AMAZING, PROGRAMMERS, and the ribbon banner.</desc>
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

<g transform="translate(288,{L['row1_top']:.4f}) scale({L['scale_x1']:.6f},1)">
  <use href="#boltpath" fill="#101010" transform="translate({L['left_bolt_tx']:.4f},0) scale({-L['bolt_scale']:.6f},{L['bolt_scale']:.6f})"/>
  <text x="{L['text_x']:.4f}" y="{L['text_y']:.4f}" class="row-text" font-size="{TLO_FS}">THE LEAGUE OF</text>
  <use href="#boltpath" fill="#101010" transform="translate({L['right_bolt_tx']:.4f},0) scale({L['bolt_scale']:.6f},{L['bolt_scale']:.6f})"/>
</g>

<image href="data:image/png;base64,{img_b64}"
       x="288" y="220" width="960" height="280" preserveAspectRatio="xMidYMid meet"/>

<g transform="translate(288,{L['row2_top']:.4f}) scale({L['scale_x2']:.6f},1)">
  <text x="0" y="{L['prog_text_y']:.4f}" class="row-text" font-size="{PROG_FS}">PROGRAMMERS</text>
</g>

<g transform="translate(768,{L['ribbon_translate_y']:.4f})">
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
    bolt, tlo, prog = measure_ink()
    print("measured ink:", json.dumps(dict(bolt=bolt, tlo=tlo, prog=prog), indent=2))
    layout = compute_layout(bolt, tlo, prog)
    print("layout:", json.dumps(layout, indent=2))
    OUT_SVG.write_text(build_svg(layout))
    print("wrote", OUT_SVG, OUT_SVG.stat().st_size, "bytes")

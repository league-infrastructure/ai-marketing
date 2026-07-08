# League Logo — Horizontal — logo-arced (construction notes)

Three checkpoints live here:

- **`logo-arced.svg`** — first checkpoint. Anton font, `textLength`/`lengthAdjust="spacing"`
  layout, uniform-scaled top row. Superseded but kept for reference.
- **`logo-arced-1.svg`** — second checkpoint. Trade Gothic Pro Bold, natural-spacing +
  horizontal-stretch layout, four rows locked to equal 24px gaps, a mild/subtle
  convex bow on AMAZING. Built by `build_logo.py`. Superseded by checkpoint 2 below
  but kept for reference (some designs may prefer the subtler curve).
- **`logo-arced-2.svg`** — current checkpoint (this doc's "Checkpoint 2" section
  describes it). Same font and bolt/THE LEAGUE OF mechanism as checkpoint 1, but a far
  more extreme AMAZING curve (A/G droop to 3.25x Z's rendered height) and PROGRAMMERS
  tucked up into the curve's central valley instead of stretched full-width below it.
  Built by `build_logo2.py`, fully reproducible from files in this directory.

Replicates draft #9 of `League-Logo-Angled` (`iter-009.png`), refined per design
feedback into a reusable component. Not AI-generated — real HTML/SVG construction,
verified at every step with Playwright screenshots.

## Files in this directory

| File | Role |
|---|---|
| `logo-arced-2.svg` | **The current deliverable** (checkpoint 2). Self-contained: font + AMAZING raster embedded as base64 data URIs, zero external file dependencies. |
| `build_logo2.py` | Regenerates `logo-arced-2.svg` end to end. Run with `uv run --with playwright --with pillow --with numpy python3 build_logo2.py` from this directory. |
| `flat-amazing-2.html` | Flat (unwarped), shadow-free "AMAZING" render source for checkpoint 2. |
| `amazing-warped-2.png` | The checkpoint-2 warped+shadowed AMAZING raster `build_logo2.py` embeds. |
| `logo-arced-1.svg` | Prior checkpoint (subtler curve). Self-contained the same way. |
| `build_logo.py` | Regenerates `logo-arced-1.svg` — measures ink, computes layout, writes the SVG. |
| `column_warp.py` | The shared AMAZING curve-warp primitive (Pillow MESH transform), used by both `build_logo.py` and `build_logo2.py`. |
| `flat-amazing.html` | Flat (unwarped) "AMAZING" render source for checkpoint 1, drop-shadow baked in (see checkpoint 2's notes on why checkpoint 2 stopped doing this). |
| `amazing-warped.png` | The checkpoint-1 warped AMAZING raster `build_logo.py` embeds. |

## Checkpoint 1 — structure: four rows, three fixed 24px ink gaps

The wordmark is four rows stacked with **exactly 24px of gap between each row's real
rendered ink** (not their nominal bounding boxes — see "Why ink, not getBBox" below):

1. Bolt + **"THE LEAGUE OF"** + bolt
2. **"AMAZING"** (arced raster)
3. **"PROGRAMMERS"**
4. Ribbon banner ("SMART MINDS · BOLD IDEAS · BRIGHT FUTURES")

### Row 1 — bolt + THE LEAGUE OF + bolt

Built at natural size, then the *whole row* is stretched horizontally (scaleX only,
scaleY=1) to span 960px — the same width as AMAZING. This means the letters and
bolts get slightly wider without getting taller; accepted deliberately (Eric: "the
letters are going to be stretched out but well").

1. Render "THE LEAGUE OF" at font-size 70, `.row-text` class (see CSS below), **no
   manual letter-spacing, no `textLength`** — just the font's own natural spacing
   ("in whatever spacing the font wants us to do it").
2. Measure its real ink height (see measurement method below) → **52px**.
3. Scale the bolt (`#boltpath`, potrace-traced from `assets/logos/bolt.png`) so its
   ink height also equals 52px → `bolt_scale = 52 / bolt_ink_height`.
4. Lay out left-to-right: `[bolt][16px gap][THE LEAGUE OF][16px gap][bolt]`, all
   ink-top-aligned (bolt ink height == text ink height, so top-aligned == bottom-aligned
   == center-aligned, no separate vertical centering math needed).
5. Wrap that whole cluster in one `<g>` and apply `scale(960 / naturalRowWidth, 1)`.

### Row 2 — PROGRAMMERS

Font-size **140** — double THE LEAGUE OF's 70 — specifically so its *natural* width
(893px ink) is already close to the 960px target, keeping the horizontal stretch factor
small (1.075x, vs row 1's 1.834x) and the letters nearly undistorted. Same `.row-text`
class, no letter-spacing override, no `textLength`. Same horizontal-only stretch
technique as row 1.

### Row 3 — AMAZING

Unchanged mechanism from the first checkpoint — see "Regenerating AMAZING" below.
Placed at a fixed box `x=288 y=220 width=960 height=280`. Because the raster is much
wider than tall, `preserveAspectRatio="xMidYMid meet"` letterboxes it vertically inside
that box — the real ink only occupies the middle ~211px of the 280px box. `build_logo.py`
computes that padding from the raster's actual aspect ratio so the 24px gaps above/below
are measured against the *real ink edge*, not the box edge.

### Row 4 — ribbon banner

Plain SVG polygons + rect, unchanged from the first checkpoint. Its 8px stroke bleeds
the visible ink ~4px above the rect's nominal top edge, so `build_logo.py` adds that
4px back onto the translate so the ink gap (not the nominal box gap) reads as 24px.

## Why ink measurement, not SVG `getBBox()`

The first attempt at this checkpoint scaled the bolt to match `getBBox()`'s reported
height of "THE LEAGUE OF" (70.24px at font-size 70). The bolt came out way too tall —
towering above and hanging below the text's actual line. Direct pixel analysis (numpy,
threshold ink pixels < 128, find min/max row) showed the *true* rendered ink height was
only **52px**, not 70.24px — `getBBox()` was over-reporting by ~35%, most likely
stroke-miter corner extension on the `paint-order:stroke fill` faux-bold technique.
Rebuilding with the pixel-measured 52px fixed it immediately — bolt tips now land on
the same cap-height/baseline as the letters. **Lesson: for this stroke+miter text
style, trust rendered pixels over `getBBox()`.**

`build_logo.py`'s `measure_ink()` renders the bolt, "THE LEAGUE OF", and "PROGRAMMERS"
each in their own non-overlapping region of a throwaway SVG (overlapping regions in an
earlier attempt corrupted the measurement — bolt ink bled into what was meant to be a
"text only" crop), screenshots it, and reads back ink bounds with:

```python
def ink_bounds(gray_arr, thresh=128):
    dark = gray_arr < thresh
    rows = np.where(dark.any(axis=1))[0]
    cols = np.where(dark.any(axis=0))[0]
    return dict(top=int(rows.min()), bottom=int(rows.max()),
                left=int(cols.min()), right=int(cols.max()))
```

## CSS (embedded in the SVG's `<style>`)

```css
@font-face {
  font-family: 'TradeGothicBold';
  src: url('data:font/ttf;base64,...') format('truetype');
  font-weight: 700;
}
.row-text{
  font-family:'TradeGothicBold',sans-serif;
  fill:#101010; stroke:#101010; stroke-width:2px;
  stroke-linejoin:miter; paint-order:stroke fill;
}
.ribbon-text{
  font-family:'TradeGothicBold',sans-serif;
  font-size:34px; letter-spacing:2px; fill:#101010;
}
```

`stroke-width:2px` is a faux-bold push on top of Trade Gothic Pro Bold's native weight
— started at 6px (too heavy/"inflated", per feedback), settled at 2px. `stroke-linejoin:
miter` keeps corners sharp/square (`round` was explicitly rejected earlier in this
project's history for a different element, same reasoning applies here).

## Exact layout numbers (current checkpoint)

Computed by `build_logo.py`; re-running it recomputes these from scratch (they will
drift by a pixel or two if the font file or bolt path changes — that's expected and
correct, not a bug):

| Quantity | Value |
|---|---|
| Bolt ink height (unscaled) | 531px |
| "THE LEAGUE OF" ink height (font-size 70) | 52px |
| "PROGRAMMERS" ink height (font-size 140) | 104px |
| `bolt_scale` | 0.097928 |
| Bolt-to-text gap (natural, pre-stretch) | 16px |
| Row 1 natural width → `scale_x1` | 523.51px → **1.833775** |
| Row 2 (PROGRAMMERS) natural width → `scale_x2` | 893px → **1.075028** |
| Row 1 top (`translate` y) | ≈178.7 |
| AMAZING box | `x=288 y=220 width=960 height=280` |
| AMAZING real ink | ≈254.7 to ≈465.3 (letterboxed inside the box) |
| Row 2 top (`translate` y) | ≈489.3 |
| Ribbon `translate` y | ≈641.3 |
| Gap between every row's ink | **24px**, uniform |

## Regenerating AMAZING

If the curve, text, or font needs to change:

1. Edit `flat-amazing.html` (currently Trade Gothic Pro Bold, `font-size:230px`, a
   drop-shadow copy (`.arc-shadow`, offset `dx=8 dy=10`) behind a white-fill/black-stroke
   main copy (`.arc-main`, `stroke-width:12px`) — the shadow is baked in *before*
   warping so it warps consistently with the letters).
2. Screenshot it with Playwright at `device_scale_factor=3` (needed — 1x produced
   visible pixelation on the curve), `omit_background=True`, then
   `magick shot.png -trim +repage flat-trimmed.png`.
3. Run `column_warp.py flat-trimmed.png warped.png` — independent quadratic top/bottom
   curve coefficients (`TOP_COEF`/`BOT_COEF`, measured from `type-sample-07.png` by
   pixel-scanning + `numpy.polyfit`) applied as a Pillow `Image.MESH` transform: each
   thin vertical column-strip is translated/scaled in Y only, **never rotated**, so
   verticals (outer edges of A and G) stay vertical — unlike SVG `textPath` (rotates
   glyphs) or ImageMagick `-distort Arc` (rotates radially, tilts verticals toward the
   arc center). `BOT_COEF` is negated from its raw measurement to make the bottom
   curve convex (domed) instead of concave (sagging), per design direction.
4. `magick warped.png -trim +repage amazing-warped.png` and drop it in this directory
   — `build_logo.py` picks it up automatically (no path change needed, same filename).

## Regenerating the whole thing

```bash
cd components/league-logo-horizontal
uv run --with playwright --with pillow --with numpy python3 build_logo.py
```

Re-measures the bolt/text ink live and rewrites `logo-arced-1.svg`. Safe to re-run any
time; it's idempotent given the same font file and `amazing-warped.png`.

## Checkpoint 2 — a far more extreme, differently-directed curve

Checkpoint 2 keeps checkpoint 1's bolt/THE LEAGUE OF mechanism (natural spacing +
horizontal-only stretch to 960px, bolt scaled to the text's real ink height) unchanged.
Everything about AMAZING and PROGRAMMERS is different, driven by several rounds of
direct correction:

### The curve: direction and amplitude

- **Direction.** An earlier attempt built a *pointed* curve — flat top, sides angled
  outward (trapezoid), a sharp V dipping DOWN at the center ("sticking out like
  Galaga"). Eric rejected this outright: he wanted the OPPOSITE — **A and G droop
  DOWN, the center (Z/I/N) bows UP** — a smooth convex curve, not a downward point,
  and explicitly no side-angling ("I don't want it angled"). This is the *same
  direction* checkpoint 1's subtle bow already used, just pushed far past subtle.
- **Amplitude, round 1: exactly 2.0x.** Eric: "I want the G to be twice the height of
  the Z. That's how extreme this curve needs to be." Solved directly: rendered column
  height = `word_h + bot_off(fx)` with a flat top, so `(1+edge_droop)/(1+center_lift)
  = 2.0` — landed on `edge_droop=+0.20`, `center_lift=-0.40` (A/G hang 20% below their
  natural baseline, Z/I/N pulled up 40%).
- **Amplitude, round 2: 3.25x.** Eric: "let's get more curve." Pushed to
  `edge_droop=+0.30`, `center_lift=-0.60` → ratio `1.30/0.40 = 3.25`. These are the
  `EDGE_DROOP`/`CENTER_LIFT` constants at the top of `build_logo2.py`.

The curve is still built with `column_warp.py` — **per-column Y stretch only, no
horizontal shear** — using `bot_shape(f) = EDGE_DROOP - (EDGE_DROOP - CENTER_LIFT) *
(1 - (2f-1)^2)`, a plain quadratic (smooth curve, not a sharp angular point — the
pointed version was the rejected one). `TOP_COEF` is flat (0 everywhere): "the top is
going to stay straight."

### The shadow bug (the actual cause of the first "this is terrible")

The pointed/angled first attempt wasn't just the wrong shape — it also looked
"twisted," with sheared, drunk-looking letters, which Eric flagged as fundamentally
broken. Two root causes, found by validating the warp on a synthetic grid image
(flat grid of horizontal/vertical lines) before trusting it on real letters:

1. The flare (horizontal shear) was implemented as a second, separate Pillow MESH pass
   applied *after* the vertical bow pass. Running two independent per-axis warps
   sequentially doesn't compose correctly — the second pass operates on rows that the
   first pass already displaced unevenly, so it shears rather than cleanly flaring.
   Fixed (for that attempt) by deriving a single closed-form simultaneous inverse
   instead of chaining passes — moot now since the flare was dropped entirely, but the
   grid-test-before-trusting-real-letters method is worth reusing for any future warp.
2. **This is the one that carried forward.** The drop shadow was baked into the flat
   text *before* warping (an offset duplicate `<text>` in the HTML). Under a mild curve
   this is invisible; under a dramatic one, the shadow's constant pixel offset gets
   stretched by wildly different amounts at different letters (since nearby columns
   can have very different local curve slopes), scattering it into visual noise that
   reads as broken letterforms. **Fix: warp a shadow-free render, then composite a
   shadow afterward as a uniform pixel offset on the already-warped result** — a clean,
   consistent shadow at any curve depth. See `warp_and_shadow()` in `build_logo2.py`.

### Resolution and jaggies

Once the curve got this steep, column-boundary "staircase" artifacts became visible —
each column in the MESH transform has a locally-constant stretch factor, and adjacent
columns with very different stretch factors show a visible kink at the boundary. Fixed
by (a) rendering the flat text at `device_scale_factor=4` instead of 3, and (b) raising
`column_warp`'s `segments` from the ~80-100 default to **400**, shrinking each column
to a few px wide so the per-column discretization stops being visible at normal zoom.

### PROGRAMMERS: tucked into the curve, not stretched below it

Checkpoint 1 stretched PROGRAMMERS to the full 960px width, matching AMAZING. Eric
first asked to shrink it, then to move it up "into the curve." Because the curve now
pulls the center letters (Z/I/N) way up while A/G stay low at the far outer edges,
there's a large empty "valley" under the center of AMAZING that the far corners don't
reach into. `measure_amazing_center_ink_bottom()` measures ink depth **only within the
middle 60% of AMAZING's width** (where PROGRAMMERS will actually sit) rather than
AMAZING's overall ink bottom (which is dominated by A/G's drooping tips and would put
PROGRAMMERS much too low) — PROGRAMMERS' top is placed 15px below that center-only
ink depth. It's rendered natural-width (font-size 90), centered, **not** stretched.

One consequence: at 3.25x curve depth, A/G's drooping tips reach close enough to the
ribbon banner that they were nearly touching it. `build_logo2.py`'s ribbon placement
includes an extra +20px clearance term (on top of the usual +20 rect-offset and +4
stroke-bleed corrections) found by rendering and directly measuring the gap — not
assumed up front.

## Standing display-mode note for future sessions

Per Eric: never open `.svg` files directly (a non-browser SVG viewer he uses renders
fonts incorrectly). All visual iteration/verification happens through an HTML page that
either inlines the SVG markup or embeds it as an `<img>`/background — opened via plain
`open` (his default browser). This file and `logo-arced-1.svg` are written/updated
programmatically and verified via Playwright screenshots read back into the session —
they are not opened for on-screen display.

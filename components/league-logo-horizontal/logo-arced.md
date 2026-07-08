# League Logo — Horizontal — logo-arced (construction notes)

Paired with `logo-arced.svg` — a self-contained vector wordmark (embedded Anton font +
embedded arced-AMAZING raster, no external file dependencies). Built from
`type-sample-07.png`'s proportions, not AI-generated — see below for how each piece
was made.

Replicates draft #9 of `League-Logo-Angled` (`iter-009.png`), refined per design
feedback into a reusable component.

## Structure

- **"THE LEAGUE OF"** and **"PROGRAMMERS"** — real SVG `<text>`, font Anton (self-hosted
  woff2, embedded as base64 in this file). Solid black fill with a matching-color stroke
  (`stroke-width:6px; stroke-linejoin:miter; paint-order:stroke fill`) to push the
  weight heavier than Anton's native weight, with sharp/square corners (miter, not
  round). Both lines use `textLength` + `lengthAdjust="spacing"` to hit an exact target
  width by spreading letter-spacing — never `spacingAndGlyphs`, which stretches the
  glyph outlines themselves and visibly distorts the letterforms.
- **"AMAZING"** — NOT SVG text. Rendered flat first (normal HTML layout so kerning is
  correct), at 3x resolution, then warped as a whole raster with a custom column-warp
  (`mcp-server` scratch tool `column_warp.py`, built on Pillow's `Image.transform(...,
  Image.MESH, ...)`): each thin vertical column is translated/scaled in Y only — never
  rotated — so verticals (the outer edges of A and G) stay vertical, unlike SVG
  `<textPath>` or ImageMagick's `-distort Arc`, both of which rotate glyphs radially and
  break spacing at any real curvature. The top edge curves gently; the bottom/baseline
  curves further, in the *same* (convex/domed) direction — both measured and matched to
  `type-sample-07.png`'s actual pixel envelope, then adjusted to convex per feedback.
  Drop shadow is baked into the flat render (offset copy behind the white-fill/
  black-stroke main copy) before warping, so it warps consistently with the letters.
- **Lightning bolts** — not hand-drawn. Traced from the real asset
  `assets/logos/bolt.png` via `potrace` (alpha-extract → threshold → invert → potrace
  `-s --tight`), giving an exact vector path of the actual League bolt. Placed inline
  with "THE LEAGUE OF" (same row), mirrored on the left side, with a gap to the text and
  the outer bolt-to-bolt span matching the width of "AMAZING".
- **Ribbon banner** — plain SVG polygons (box + two forked/notched tails), holding
  "SMART MINDS · BOLD IDEAS · BRIGHT FUTURES" in Anton.

## Regenerating the AMAZING raster

If the text, font, or curve needs to change, the flat-render → column-warp → trim
pipeline needs to be redone. `column_warp.py` (in this directory) is the warp step —
`TOP_COEF`/`BOT_COEF` are the measured curve shapes; negate `BOT_COEF` for a concave
(sagging) bottom instead of the current convex (domed) one. It takes a flat-rendered
raster in and writes a warped raster out; the flat render and the potrace bolt tracing
still need to be done separately (see chat history for those exact commands), and the
result re-embedded into `logo-arced.svg` as a base64 data URI.

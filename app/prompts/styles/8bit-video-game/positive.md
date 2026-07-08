# 8-Bit Video Game — Style

Render as authentic 8-bit video-game pixel art — the look of late-1980s NES / Famicom games.
Blocky pixel rendering with limited color palettes, crisp pixel edges, and the charm of
8-bit sprite art. The image should look like a direct screen capture from an NES.

## Rendering
- **Pixel grid:** Visible pixel grid — everything rendered at the sprite/block level, with
  individual pixels discernible as colored squares. No anti-aliasing, no sub-pixel rendering.
- **Resolution:** NES-resolution feel (256×240 equivalent), characters at 16×16 to 32×32
  sprite sizes. If scaled up, use nearest-neighbor scaling — no interpolation or blur.
- **Color palette:** Authentic NES palette limitations — roughly 4 colors per sprite
  (3 colors + transparency) drawn from the NES 54-color master palette, with the distinctive
  NES color cast. Backgrounds use a 4-color palette per 16×16 tile block.
- **Shading:** Flat pixel colors. Dithering patterns (checkerboard, stripes) may suggest
  extra colors or shading. No smooth lighting, glows, or drop shadows.
- **Outlines:** Sprites use black or dark outlines for readability — the classic NES look.

## Background & UI
- Tile-based backgrounds from repeating 16×16 tiles; simple parallax layers (distant
  mountains → mid-ground → foreground). Sky is a solid color or simple dither gradient.
- Optional HUD: score (top-left), lives/health (top-right), level indicator. Text in an
  8×8 pixel all-caps NES font. Dialog boxes: black background, white border, pixel text.

## Subject & Brand
- **Robots** become NES sprites — blocky, readable, black-outlined — but keep the
  recognizable silhouette of the real student-built educational robot (chassis, wheels,
  grabber/arm). Not a generic sci-fi mech.
- **Kids are the heroes** — expressive sprite poses, proud and determined.
- Any code or readable text appears only in a pixel dialog/HUD box or on a sprite screen,
  never as free-floating modern text. The image celebrates kids who build real robots.

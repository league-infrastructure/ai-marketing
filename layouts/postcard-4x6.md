# 4×6 Postcard Layout

## Format Description
Standard 4×6 inch postcard (aspect ratio 2:3, portrait or landscape). Designed for
print marketing mailers or handout cards. Glossy cardstock feel with room for a
hero image on the front and brief text/messaging.

## Dimensions & Ratio
- **Aspect ratio:** 2:3 (portrait) or 3:2 (landscape)
- **Orientation:** Portrait is standard for mailers; landscape for event handouts
- **Resolution target:** 1800×1200 px (landscape) or 1200×1800 px (portrait) at
  300 DPI print equivalent

## Layout Zones

### Front (Image Side)
- **Zone A — Hero Image (70-80% of area):** The primary illustration in the chosen
  art style. Fills the majority of the card. Character(s), robot(s), and action.
- **Zone B — Headline Bar (10-15%, top or bottom):** Bold text overlay or solid-color
  strip with the primary marketing message. Examples:
  - "Your Kids. Our Robots. Host a Tech Club."
  - "LEARN TO CODE. BUILD ROBOTS. CHANGE THE WORLD."
  - "THE LEAGUE OF AMAZING PROGRAMMERS"
- **Zone C — Logo / Brand Mark (small, corner):** League logo in one corner, small
  and unobtrusive.

### Back (Reserved for address/message area — not part of this image generation)

## Integration with Art Styles
- Text should feel native to the art style — not a modern graphic-design overlay
- Pop-art: Caption strip along the bottom
- Comic: Cover furniture elements (masthead, starburst)
- Manga: Integrated into the panel layout
- DBZ: Bold action-text integrated with energy effects
- Blueprint: Title block / annotation style text
- 8-bit: Pixel font HUD or dialog box

## Prompt Addition
> Format as a 4×6 inch postcard in [portrait/landscape] orientation. Hero image fills
> 75% of the card with a bold headline [text] in [style-appropriate treatment] along
> the [top/bottom]. Small League logo in [corner]. Clean composition with generous
> margins. Print-ready quality.

## Print Bleed

Every postcard needs a 1/8 inch (0.125in) cutting bleed on all four sides — the
standard commercial-print margin for small printed pieces (postcards, business cards,
flyers) that gets trimmed off, so a slightly-off cut never exposes white edge or clips
the art. (Large-format pieces — signs, posters, trade-show graphics — need 1/4in
instead; not relevant to postcard-4x6, but keep it in mind if a poster-size layout
gets added later.) Trim size stays 6×4in; the bleed-inclusive sheet is 6.25×4.25in.

Two ways to satisfy it, and the rule for choosing between them:

- **Solid border/frame designs** (masthead bands, flat color edges): the border color
  simply extends outward 1/8in. Nothing to compose around — flat color has no "content"
  to protect.
- **Edge-to-edge art** (figures, background bleeding to the frame): compose so that
  only inconsequential art — background, a figure's body — is what reaches the true
  edge and can extend past it. **Text and logos must stay fully inside the 6×4 trim,
  never in the outer 1/8in.** A person can walk out of frame; a slogan can't.

Mechanically, `generate_postcard_pdf` adds this bleed automatically: it captures a
flattened raster of each face at the trim size, then extends the outer edge by 32px
(1/8in at the 256dpi postcard-4x6 resolution) via edge-replication — a standard
print-shop technique for source art that has no built-in overscan. This is why the
composition rule above matters: the pad only repeats whatever pixel is already at the
edge, so any text or logo living too close to the edge gets smeared into the bleed
rather than protected by it.

The exported PDF is also rotated 90° per the print vendor's submission requirement —
see `generate_postcard_pdf`'s docstring in `mcp-server/server.py`.

## Safety Margin (inside the trim, separate from bleed)

Bleed protects against cutting *outside* the trim line; safety margin protects
against cutting *inside* it. They're both needed:

- **Standard safety margin — 1/8in (0.125in):** the minimum gap between any important
  content (text, a logo) and the trim line, for plain edge-to-edge art with no frame.
- **Border safety margin — 1/4in (0.25in):** when the design has a border/frame around
  the edge — which is every postcard we've made so far (masthead bands, navy border
  frames) — content needs the LARGER 1/4in margin from the trim line. A border makes
  any unevenness in the cut immediately visible (the border width appears to vary
  card-to-card), so it needs more tolerance than plain content would.

In practice: when writing a prompt for a bordered design, don't just say "keep text
inside the trim" — say "keep text at least 1/4in inside the trim, with visible border
showing on every side." Loose phrasing like "a clear margin" is not precise enough to
reliably hold a print vendor's tolerance; use the actual number.

## Crop Marks

Print vendors expect crop marks (trim-position tick marks) at all 4 corners of a
bleed-inclusive file, positioned outside the bleed box. **`generate_postcard_pdf` does
not currently draw crop marks** — it exports a plain bled/rotated page with no marks.
If a vendor's intake requires them, that's a real gap to close (drawing 8 short lines
per page, offset outside the 6.25×4.25in bleed box) — flag it before submitting a file
to a vendor that needs them, rather than assuming they're present.

## Source

Bleed, safety-margin, and crop-mark figures above come from
[Smartpress's bleed & borders guide](https://smartpress.com/support/printing-basics/bleed-borders)
(the "Key Measurements for Bleed & Crop Marks" table) — treat it as the reference if
these numbers ever need rechecking.
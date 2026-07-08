# Single-Event Facebook Image Layout (Template)

## Format Description
Promotes **one** event — a Type-A single-event piece where the date is the star. Sized for
Facebook. The **artwork is the hero**; content is a compact cluster (title + date + short
teaser) in a lower band, with the rest of the frame left for the illustration. **No QR code
or link** — on Facebook the image itself is the click target, so there's nothing to scan.
This file describes the **template** form (blank content areas for later CSS fill). Read
`template-content-areas.md` first for the square master, `#00FF00` chroma key, and JSON schema.

## Dimensions & Ratio
- **Master:** square, 1:1 — generate at 2048×2048 (min 1024×1024).
- **Outputs (composed in CSS from the square):**
  - `facebook-feed` — 1:1 (1080×1080). Uses the full square.
  - `facebook-link` — 1.91:1 (1200×630). A centered landscape crop; keep all zones inside
    the central band so this crop stays intact.
- Design to the tighter of the two: everything essential lives inside a 1.91:1 center band.

## Required Content (Type A — Single Event)
Blank content areas:

1. **Title** — the event name.
2. **Date + time** — the headline fact, wrapped in a pill/callout in CSS.
3. **Teaser** — one short line; a hook, not a description.

No QR or link (the image is the click target). Optional: small logo.

## Required Zones (role + relative size — the generator places them)
Specify *which* zones and their *relative* sizes; let the model arrange them — **or** feed it
the zone map (below) to fix the arrangement. Everything essential lives inside the central
1.91:1 band so both the feed and link crops keep it. **Keep the content compact — content
should be a small fraction of the frame; the rest is art.**

| Role | Relative size | Required | Purpose |
|---|---|---|---|
| *(hero art)* | **Most of the frame, blank of green** | Yes | The illustration; not a content area. |
| `title` | Medium | Yes | Event name. |
| `datetime` | Small | Yes | Date + time — the headline fact (CSS pill). |
| `teaser` | Small | Yes | One short hook line. |
| `logo` | Small, a corner | No | Logo lock-up. |

No QR/link zone — the Facebook image is itself the click target.

## Zone Map (concrete example layout to hand the generator)
`zone-maps/single-event-facebook.svg` shows the green content rectangles inside both the
1:1 feed frame and the 1.91:1 link crop — pass it to the model as a reference image. The
**Sidecar JSON** below is its machine-readable twin. Edit via `zone-maps/generate_zone_maps.py`.

## Style Integration
- **Comic book:** a single dramatic cover — inked frame, one bold color field; the green
  rectangles sit like blank caption boxes and a blank cover starburst (for the date).
- **Technical blueprint:** a spec sheet for one event — title block, leader lines pointing
  to blank annotation fields on blue paper.
- **8-bit:** an NES title screen — pixel border, HUD; blank green slots for the title and a
  dialog box for the teaser. (Use magenta `#FF00FF` if the pixel art is green-heavy.)

## Template Mode (what the model actually draws)
> Generate a **square** single-event promo in [STYLE]. Render only the art — frame,
> background, style furniture. Leave every content area as a **flat, solid `#00FF00`
> rectangle**, straight axis-aligned edges, uniform color, **no text and no drawn QR code**,
> no gradient/border/shadow/dots on the green. **The illustration is the hero — it should
> fill most of the frame. Cluster the small content areas in a lower band and keep the upper
> area open for art.** Include these compact content areas, all blank green, sized *relative*
> to each other; place them to suit the composition **or match the attached zone map exactly
> if one is provided**:
> — a **medium rectangle** for the title;
> — a **small rectangle** for the date/time;
> — a **small rectangle** for a one-line teaser.
> There is **no QR code and no link** on this piece. Nothing else in the art may use `#00FF00`.
> Keep all rectangles within the central horizontal band so both a 1:1 and a 1.91:1 crop
> preserve them. Square master; final Facebook sizes are cropped later in CSS.

Negative additions: no placeholder event name, no sample date, no QR code, no rounded
corners/outlines on the green fills.

## Sidecar JSON (example — mirrors `zone-maps/single-event-facebook.svg`)
```json
{
  "template": "single-event-facebook",
  "form": "template",
  "style": "8bit-video-game",
  "art": "single_event_fb_8bit_v1.png",
  "canvas": { "width": 2048, "height": 2048, "aspect": "1:1" },
  "chroma": { "hex": "#00FF00", "rgb": [0, 255, 0], "tolerance": 24 },
  "safe_region": { "x": 0.0, "y": 0.238, "w": 1.0, "h": 0.524 },
  "art_note": "No QR/link (image is the click target). Content ~13% of the link crop; rest is hero art.",
  "outputs": [
    { "name": "facebook-feed", "aspect": "1:1",    "crop": { "x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0 } },
    { "name": "facebook-link", "aspect": "1.91:1", "crop": { "x": 0.0, "y": 0.238, "w": 1.0, "h": 0.524 } }
  ],
  "zones": [
    { "id": "title", "role": "title", "required": true,
      "bbox": { "x": 0.08, "y": 0.49, "w": 0.58, "h": 0.10 },
      "text_align": "left", "vertical_align": "middle", "max_lines": 2,
      "notes": "Event name." },
    { "id": "datetime", "role": "datetime", "required": true,
      "bbox": { "x": 0.08, "y": 0.61, "w": 0.40, "h": 0.06 },
      "text_align": "left", "vertical_align": "middle", "max_lines": 1,
      "notes": "Date + time; rendered as a pill in CSS." },
    { "id": "teaser", "role": "description", "required": true,
      "bbox": { "x": 0.08, "y": 0.68, "w": 0.62, "h": 0.07 },
      "text_align": "left", "vertical_align": "top", "max_lines": 1,
      "notes": "One short hook line — not a description." }
  ]
}
```

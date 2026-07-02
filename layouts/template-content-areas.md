# Template Content Areas — Chroma-Key + JSON Spec

Shared reference for all **template** layouts (`peachjar-multi-event-flyer`,
`single-event-facebook`). Read this alongside any layout file that says "Template Mode."

## Two forms of every layout

Each layout can be generated in one of two forms:

1. **Template** *(the form we care about here)* — the model draws **only** the art:
   decorative border, background, style furniture, and iconography. Every place that will
   later hold real text or a QR code is left as a **flat, blank, solid-color rectangle** —
   a "content area." No titles, no placeholder copy, no lorem ipsum, no drawn QR code.
   The template is generated **square (1:1)**. Final print/social dimensions are produced
   afterward in HTML/CSS, which crops the square and lays real content into the blank
   rectangles.

2. **Filled** — a person (or a later automated pass) drops real headline, dates,
   description, and a real QR code onto the template. This spec does not govern the filled
   form; it exists so the filled form is trivial to produce.

**Everything below is about producing good templates.**

## Art is the hero — keep content areas small

These pieces exist to drive people to the QR code / URL, not to carry event detail. Copy is
a title plus a short teaser at most. So the content areas are **deliberately small**: hold
them to a minority of each crop (target ≲ 40%, less on social) and leave the rest — usually a
big open region up top — for the illustration. `generate_zone_maps.py` prints the content-vs-art
split for every map so you can check this.

## Why square

The generation models compose most reliably at 1:1, and a single square master can drive
every output size. The layout does not bake in 8.5×11 or 4×6 — CSS does that. The template
just has to keep all content areas inside a safe region so any reasonable crop still
contains them (see *Safe region* below).

## The chroma-key color

Every content area is filled with one precise, garish color so it can be found
programmatically and keyed out in CSS/canvas.

- **Primary chroma:** green-screen green — `#00FF00`, `rgb(0, 255, 0)`.
- **Fallback chroma (documented swap):** magenta — `#FF00FF`, `rgb(255, 0, 255)`.
  Use magenta **only** when a given piece's artwork contains strong greens (e.g. an 8-bit
  grass field) that would collide with the key. One template uses exactly one chroma color
  — never mix two keys in the same image.

Rules for the color in the prompt:
- The rectangles must be **100% flat, uniform `#00FF00`** — no gradient, no texture, no
  Ben-Day dots, no drop shadow, no border, no glow bleeding into them.
- Nothing else in the art may use this exact green. The League styles are warm
  (comic red/blue/yellow/flesh/cream), blueprint (blue paper + white line), and NES
  palette — pure `#00FF00` does not occur naturally in any of them, which is the point.
- Content areas are **axis-aligned rectangles** with hard, straight edges. No rounded
  corners in the *keyed* fill itself — rounding, pills, and borders are added later in CSS.

## The sidecar JSON

Every generated template PNG ships with a sidecar JSON of the same basename
(`peachjar_comic_v3.png` → `peachjar_comic_v3.json`). The JSON is the **source of truth**
for where content goes; the green pixels are a visual mirror of it. A build step can either
trust the JSON coordinates directly or detect the green rectangles and match them to the
nearest JSON zone by position.

### Coordinate system

All positions are **normalized floats in `[0,1]`**, measured from the **top-left of the
square master**. `x`/`y` are the top-left corner of the box; `w`/`h` its width/height.
Normalized coordinates survive any rescale, so the same JSON works whether the PNG is
1024², 2048², or 4096².

### Schema

```json
{
  "template": "peachjar-multi-event-flyer",   // layout id (matches the .md filename stem)
  "form": "template",
  "style": "comic-book",                        // comic-book | technical-blueprint | 8bit-video-game
  "art": "peachjar_comic_v3.png",               // the square master this JSON describes
  "canvas": { "width": 2048, "height": 2048, "aspect": "1:1" },
  "chroma": { "hex": "#00FF00", "rgb": [0, 255, 0], "tolerance": 24 },
  "safe_region": { "x": 0.08, "y": 0.08, "w": 0.84, "h": 0.84 },
  "outputs": [
    { "name": "peachjar", "aspect": "8.5:11", "crop": { "x": 0.10, "y": 0.02, "w": 0.80, "h": 0.96 } }
  ],
  "zones": [
    {
      "id": "event-list",
      "role": "event-list",
      "required": true,
      "bbox": { "x": 0.12, "y": 0.24, "w": 0.76, "h": 0.48 },
      "text_align": "left",
      "vertical_align": "top",
      "max_lines": 12,
      "notes": "Dominant central block. One row per event: name + date + short tag."
    }
  ]
}
```

### Field reference

| Field | Meaning |
|---|---|
| `template` | Layout id — matches the layout `.md` filename stem. |
| `form` | Always `"template"` for this pipeline. |
| `style` | Which art style was layered on this master. |
| `art` | Filename of the square PNG this JSON describes. |
| `canvas` | Pixel size + aspect of the master (always `1:1`). |
| `chroma` | The key color used in this image and a match `tolerance` (0–255 per channel) for detection. |
| `safe_region` | Normalized box that every intended output crop stays within. All zones must sit inside it. |
| `outputs` | Named target crops (e.g. `peachjar`, `facebook-feed`, `facebook-link`) with the normalized crop rect to take from the square. |
| `zones[]` | The content areas. |
| `zones[].id` | Unique within the file. |
| `zones[].role` | Semantic role (`event-list`, `qr`, `org-statement`, `nonprofit`, `title`, `datetime`, `description`, `link`, `logo`). The build step maps role → real content. |
| `zones[].required` | Whether a filled piece must populate it. |
| `zones[].bbox` | Normalized `x,y,w,h` of the green rectangle. |
| `zones[].text_align` / `vertical_align` | Hints for the CSS overlay. |
| `zones[].max_lines` | Soft cap so copy fits without reflowing outside the box. |
| `zones[].notes` | Human note about what belongs there. |

### Conventions

- **One role, one box** unless a layout explicitly needs repeats; if it does, use the same
  `role` with distinct `id`s (`event-row-1`, `event-row-2`, …).
- Zones **must not overlap** and **must sit inside `safe_region`**.
- The `qr` zone must be **square** (`w == h` in pixel terms after accounting for canvas
  aspect; since the canvas is 1:1, `w == h` in normalized units) and sized so the printed
  QR is at least ~0.9 in / ~2.5 cm on the smallest output.
- Because a single chroma color is used for all zones, **zone identity lives in the JSON**,
  not the pixels. A detector that finds green rectangles must reconcile them against
  `zones[]` by position/area; the JSON wins on any conflict.

## Zone maps (SVG) — the concrete layout you hand the generator

The layout prompts describe zones by **role and relative size** and let the model place
them. When you want a specific arrangement, give the model a **zone map**: a square SVG that
draws each content area as a flat `#00FF00` rectangle in position, with the safe region and
output crops marked. Pass it as a reference image (image-to-image / layout guide) so the
model paints the style *around* the fixed rectangles.

- Maps live in `zone-maps/` — e.g. `peachjar-multi-event-A.svg`,
  `peachjar-multi-event-B.svg`, `single-event-facebook.svg`.
  There is more than one per format on purpose, so you can compare arrangements.
- `zone-maps/generate_zone_maps.py` is the source of truth for the coordinates and
  regenerates every SVG. It **validates** that every zone fits inside every output crop and
  that QR/square zones stay square, so a map can't drift out of its crop.
- The labels in an SVG ("EVENT LIST", "QR", …) are annotations for you and the model; they
  are not meant to be rendered into the art. The green rectangles are the payload.
- Each map's coordinates match the **Sidecar JSON example** in the corresponding layout
  `.md`, so the reference image and the machine-readable zone list stay in lockstep.

## What the layout prompt must tell the model

Every template prompt should, in its own words, instruct the model to:

1. Render the full art style (border, background, furniture) but **leave the listed content
   areas as flat solid `#00FF00` rectangles**.
2. Draw **no text and no QR code** inside those rectangles — they are blank on purpose.
3. Keep rectangle edges straight and axis-aligned, colors uniform, no effects on the green.
4. Keep all content areas within the central safe region so any crop keeps them intact.
5. Match the rectangle positions/sizes described in the layout's zone table (which the
   sidecar JSON encodes precisely).

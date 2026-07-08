# Peachjar Multi-Event Flyer Layout (Template)

## Format Description
A single digital flyer that advertises **several League events at once** — the kind pushed
to families through Peachjar and posted on school channels. The **artwork is the hero**; the
content areas are compact and sit in the lower ~60% while the top is open for a big
illustration. The event list is only titles + short teasers — just enough to make a parent
scan the QR or type the URL, not a full schedule. This file describes the **template** form
(blank content areas for later CSS fill). Read `template-content-areas.md` first — it defines
the square master, the `#00FF00` chroma key, and the sidecar JSON schema referenced below.

## Dimensions & Ratio
- **Master:** square, 1:1 — generate at 2048×2048 (min 1024×1024).
- **Primary output:** Peachjar / print flyer, 8.5:11 portrait, composed in CSS by cropping
  the square (`outputs[].name = "peachjar"`). The art is designed so a centered portrait
  crop keeps every content area intact.
- Do **not** bake 8.5×11 into the generated art — the master stays square.

## Required Content (from the Flyer Content Analysis)
This flyer type must carry, as blank content areas:

1. **Event list** — the largest *content* area (though smaller than the art). A compact
   stack of events, each row just a title + a short teaser. No detail, no full schedule.
2. **QR code** — one square code, paired in CSS with a short URL fallback.
3. **Organization + location statement** — who the League is and where it is
   ("The League of Amazing Programmers — free coding & robotics for grades 3–12, San Diego").
4. **Nonprofit statement** — the 501(c)(3) / nonprofit line.

Optional (leave a zone only if the design wants it): small logo lock-up in a corner, a
single slogan strip above the list.

## Required Zones (role + relative size — the generator places them)
The prompt tells the model *which* content areas to include and *how big each should be
relative to the others*; it lets the model decide exact placement — **unless** you hand it
a zone map (below), in which case it should follow that arrangement.

Content areas are **compact — reserve most of the page for art** (aim for content ≲ 40% of
the sheet, with a big open hero region up top).

| Role | Relative size | Required | Purpose |
|---|---|---|---|
| *(hero art)* | **Biggest — the top ~⅓, left blank of green** | Yes | The illustration; not a content area. |
| `event-list` | Largest *content* area, but compact | Yes | Stack of events; each row is just a title + short teaser. |
| `title` / masthead | Small strip | No | Standing header ("League Events" / the month). |
| `org-statement` | Small | Yes | Who + where the League is (free coding/robotics, grades 3–12, San Diego). |
| `qr` | Small **square** | Yes | QR code; short URL added beneath in CSS. |
| `nonprofit` | Thin strip | Yes | 501(c)(3) / nonprofit line, small. |
| `logo` | Small, a corner | No | Logo lock-up. |

## Zone Maps (concrete example layouts to hand the generator)
Two example arrangements live beside this file and can be passed to the model as a reference
image (image-to-image / layout guide). They show the exact green content rectangles on the
square master; the generator matches them and paints the chosen style around them.

- `zone-maps/peachjar-multi-event-A.svg` — list-dominant, QR bottom-right.
- `zone-maps/peachjar-multi-event-B.svg` — QR top-right, org statement as a full-width footer.

Regenerate or edit them with `zone-maps/generate_zone_maps.py` (it validates that every zone
fits inside the 8.5×11 crop and that squares stay square). The **Sidecar JSON** below is the
machine-readable twin of arrangement A.

## Style Integration
Style-agnostic — layer any League style on top; the border/background changes, the zone
map does not.

- **Comic book:** the whole sheet reads as a Golden-Age comic **page** — a bold inked
  panel frame around the edge, cream/newsprint field behind the list, small starburst
  furniture in the corners. The blank green rectangles are the "panels" the letterer will
  fill.
- **Technical blueprint:** the sheet is a **drafting sheet** — white border frame on deep
  blue paper, a title block in the lower-right, faint drafting grid, leader-line ticks
  pointing at each content area. The green rectangles read as blank annotation fields.
- **8-bit video game:** the sheet is an **NES menu / level-select screen** — tiled pixel
  border, a HUD bar top and bottom, dithered background. The green rectangles are the blank
  menu slots. (If the pixel scene uses greens, switch the key to magenta `#FF00FF`.)

## Template Mode (what the model actually draws)
> Generate a **square** flyer in [STYLE]. Render only the decorative frame, background, and
> style furniture. Leave every content area as a **flat, solid `#00FF00` (green-screen
> green) rectangle** with straight, axis-aligned edges and perfectly uniform color — no
> text, no placeholder copy, no drawn QR code, no gradient, border, shadow, or dots inside
> them. **The artwork is the hero: keep the top third or so an open illustration and hold all
> content areas to the lower portion — content should be well under half the sheet.** Include
> these compact content areas, all blank green, sized *relative* to each other; place them to
> suit the composition **or match the attached zone-map exactly if one is provided**:
> — a **compact rectangle** (the largest of the content areas, but not dominating the page)
>   for the event list — it holds only titles + short teasers;
> — a small, shallow **masthead strip** for the header;
> — a **small rectangle** for the organization/location statement;
> — a **small square** for a QR code;
> — a **thin strip** for the nonprofit line.
> Nothing in the artwork outside these rectangles may use `#00FF00`. Keep all rectangles
> inside the central portrait region so the 8.5×11 crop preserves them. Print-ready,
> square master; final 8.5×11 crop is applied later in CSS.

Negative additions: no lorem ipsum, no sample event names, no fake dates, no rendered QR
pattern, no rounded corners or outlines on the green fills.

## Sidecar JSON (example — mirrors `zone-maps/peachjar-multi-event-A.svg`)
```json
{
  "template": "peachjar-multi-event-flyer",
  "form": "template",
  "style": "comic-book",
  "art": "peachjar_comic_v1.png",
  "canvas": { "width": 2048, "height": 2048, "aspect": "1:1" },
  "chroma": { "hex": "#00FF00", "rgb": [0, 255, 0], "tolerance": 24 },
  "safe_region": { "x": 0.121, "y": 0.01, "w": 0.757, "h": 0.98 },
  "art_note": "Top ~0.01-0.34 of the crop is reserved hero art; content is ~39% of the page.",
  "outputs": [
    { "name": "peachjar", "aspect": "8.5:11", "crop": { "x": 0.121, "y": 0.01, "w": 0.757, "h": 0.98 } }
  ],
  "zones": [
    { "id": "masthead", "role": "title", "required": false,
      "bbox": { "x": 0.17, "y": 0.35, "w": 0.66, "h": 0.06 },
      "text_align": "center", "vertical_align": "middle", "max_lines": 1,
      "notes": "Standing header + month." },
    { "id": "event-list", "role": "event-list", "required": true,
      "bbox": { "x": 0.17, "y": 0.43, "w": 0.66, "h": 0.27 },
      "text_align": "left", "vertical_align": "top", "max_lines": 6,
      "notes": "Compact list. One row per event: title + short teaser only — no detail." },
    { "id": "org-statement", "role": "org-statement", "required": true,
      "bbox": { "x": 0.17, "y": 0.74, "w": 0.45, "h": 0.075 },
      "text_align": "left", "vertical_align": "top", "max_lines": 3,
      "notes": "Who + where the League is (free coding/robotics, grades 3-12, San Diego)." },
    { "id": "qr", "role": "qr", "required": true,
      "bbox": { "x": 0.68, "y": 0.735, "w": 0.15, "h": 0.15 },
      "text_align": "center", "vertical_align": "middle",
      "notes": "Square QR area; short URL rendered beneath in CSS." },
    { "id": "nonprofit", "role": "nonprofit", "required": true,
      "bbox": { "x": 0.17, "y": 0.845, "w": 0.45, "h": 0.035 },
      "text_align": "left", "vertical_align": "middle", "max_lines": 1,
      "notes": "501(c)(3) nonprofit line, small; sits left of the QR square." }
  ]
}
```

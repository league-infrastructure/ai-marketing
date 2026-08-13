# Empower Today — 4×6 postcard, print files

Two-sided landscape postcard, built **straight from the approved artwork**.

| File | |
|---|---|
| `Empower-Today-postcard.pdf` | **Send this.** 2 pages — p1 front, p2 back |
| `Empower-Today-front.pdf` / `-back.pdf` | Single-page versions |
| `Front-print-300dpi.png` / `Back-print-300dpi.png` | The rasters inside them, 1875×1275, 300 dpi |
| `proof.html` | Proof with trim/safe guides |

Trim 6×4 in · bleed 0.125 in all round · file 6.25×4.25 in.

## The PDFs

Built by `scratchpad/make_pdf.py`.

- **MediaBox / BleedBox** `450 × 306 pt` = 6.25 × 4.25 in
- **TrimBox / ArtBox** `432 × 288 pt` = 6 × 4 in, inset 9 pt (0.125 in)
- Image `1875 × 1275` drawn to the full page = **exactly 300 dpi**
- 8-bit **DeviceRGB**, **FlateDecode** — lossless, no JPEG artifacts

The TrimBox matters: the RIP reads the cut line out of the file rather than being
told it in an email.

> **Gotcha for anyone touching `make_pdf.py`:** the `kCGPDFContext*Box` keys need a
> `CFData` holding a `CGRect` *by value*. Passing a bare `CGRect` is accepted
> silently and then ignored — the boxes never reach the file, and
> `CGPDFPageGetBoxRect` falls back to reporting MediaBox, which looks like success.
> Verify with `grep -a /TrimBox`, not with the API.

Verified: every PDF page rasterised at 300 dpi and compared against its source
raster — **0 of 265,625 sampled pixels differ, worst delta 0**.

## Why the artwork is the source, not a vector conversion

The first approach converted the PNGs to editable layers via `12ui`
(`design-convert`). The text extraction was genuinely good — live type, correct
strings, identified fonts — but the conversion lost too much else to be usable:

- The **photo plate was corrupted**. `crop-1` is marked `pixels: "cleaned"`; the
  converter inpainted the orange circuit traces off the photograph and duplicated
  the instructor's head doing it. 28.3% of pixels in the head region were wrong.
  Every later version inherited it because every later version used that plate.
- The **curved photo edge** was flattened to `<rect fill="#f8eadc">` plus a raster
  cutout carrying an inpainting blob.
- **Its own icons were substituted** — MENTOR lost a figure, the megaphone lost its
  sound lines, the gift box was simplified.
- **Type was re-set** — headline leading opened up, `AMAZING,` became `AMAZING.`
- **Seven back decorations** exported as empty outlined rects.
- **PSD exports** came back at inconsistent sizes (front 1382×940, back 1401×952).

None of that is recoverable downstream, and the artwork was already correct. The
build is now: heal the QR footprint, lift the left column for cut clearance, pad to
bleed, scale to 300 dpi. Nothing else is touched.

The conversion files (`*.layerdoc.json`, `*-final.svg`, `*-print.svg`, `front/`,
`back/`) are kept for reference but **are not the deliverable**.

## What the build does — `scratchpad/build_print.py`

**1. Heal the QR (front only).** The removed panel's footprint is filled from the
converter's cleaned plate, feathered over a 26px ramp. That plate is trusted only
*inside* the old QR rectangle — the one region where the original artwork has no
photograph, just opaque card.

**2. Lift the left column (front only).** The label row sat 1.18 mm above the cut —
it survives an accurate cut but not normal guillotine drift (±1.6 mm). Buying
clearance means growing the orange bar upward, which collides with the body copy,
which crowds the headline, which crowds the logo:

```
logo            -12px    top margin 45 -> 33px (3.5mm, still outside the cut)
headline        -30px
copy            -30px    same lift as headline, so the orange rule stays centred
bar top          878     126 -> 156px tall
footer content  -21px    less than the bar, so it re-centres inside it
```

Result: **label clearance 1.18 mm → 3.17 mm**, the standard 1/8 in safe margin.
Rule centring 33 px above / 32 px below. The rule→copy and copy→bar gaps are
unchanged.

**Two rules the edit must obey**, both learned by breaking them:

- A moved region must **clear the swooping curve**. The curve's leftmost outer edge
  is x=640; cutting the copy block at x=660 sliced it and stranded a 1.8 mm orange
  triangle in the peach field.
- A moved region must **not cut any decoration**. Cutting the logo block at x=660
  sliced `circuits-top` (x 614–999, y 0–190) and offset its left end by 12 px,
  visibly breaking the traces. The logo ends at x=568, so its cut is now x=600.

`check_no_slice()` asserts both against `DECORATIONS` before any pixel moves.

**3. Pad to bleed by continuing the edge pixel** — never mirroring. A mirrored
margin reads as a reflected duplicate whenever the cut drifts off the line.

The art is 1.471:1 and a 6×4 card is 1.5:1, so it is 30 px narrower than the trim.
The surplus is pushed **entirely to the left**, where the edge is flat peach, flat
orange, and circuit traces already meant to run off the page. The right edge — the
photograph — therefore gets exactly one bleed of margin, all of it trimmed away:
**0 extended pixels land inside the cut on the right.**

**4. Scale to 1875×1275** and stamp 300 dpi, no alpha.

## Verified

Independently inspected against the originals at each revision:

- Instructor single and intact; photograph otherwise pixel-faithful
- Swooping curve one continuous stroke — row-run analysis found exactly one orange
  run per row, top to bottom, no breaks and no duplicates
- Circuit traces continuous; all 10 top-decoration components map one-to-one to the
  original, shift dy=0 on both sides of the old cut
- No stranded fragments: a connected-component sweep of the entire peach field
  returned nothing unaccounted for
- QR heal reads as genuine workbench content; grain matches the surrounding shallow
  depth of field
- Back: all circuit traces, curved arrow, QR, six icons and three stat rows intact

## Known, and your call

- **Effective resolution is 259 ppi.** The artwork is 1521×1034, which is 259 ppi at
  6×4 in. The file is written at 300 dpi, so it is a 1.16× upsample — it satisfies a
  vendor's 300 dpi requirement but carries 259 ppi of real detail. Only a larger
  original changes that.
- **The logo now crowds the headline** — that gap went 62 px → 41 px, so the logo
  reads as part of the headline stack rather than a separate mark. Widening it means
  lifting the logo further, which eats its top margin (already 3.5 mm).
- **`AMAZING,` sits 2.4 mm from the right cut**, inside the 3.175 mm safe zone.
  Inherited from the source artwork, not introduced. Fixable by nudging the tagline
  left.
- **The front carries no URL** now that the QR panel is gone. The back still has its
  QR and `jointheleague.org/about/impact`.
- **RGB, not CMYK.** The PDFs are DeviceRGB. Most postcard printers convert for
  you, but the orange will shift unless they use a profile you approve — ask which
  they want before the run.
- **Scan the printed QR** on the back before the run.

## Rebuilding

```
build_print.py front <Front.png> <out.png> <healing-plate.png>
build_print.py back  <Back.png>  <out.png>
```

The healing plate is `Front.layerdoc.json.assets/clean-1-2038e8f0b2cb.png`, used
only inside the old QR rectangle.

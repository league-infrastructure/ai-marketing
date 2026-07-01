# League Logo — Angled — Type Sample (prompt)

Paired with `type-sample.png` (the angled black-&-white structural type sample).

## How it was made
The image model cannot reliably draw clean 45° type, so this used a **draw-straight-then-rotate**
method:

1. **Straight render** (image generator, League-Logo-Angled project): the wordmark was drawn
   perfectly horizontal from the clean `components/loap-type.png` reference, with the
   component's "diagonal banner" text **nulled** so no enclosing box/banner was drawn.
2. **Rotate**: the straight render was rotated **+45° (counter-clockwise)** with PIL
   (`expand=True`, white fill) and whitespace-trimmed.

- project: `League-Logo-Angled`
- style: `type-sample`  ·  composition: `type-sample`  ·  layout: `type-sample`
- component: *(nulled — blank — to avoid the banner/box)*
- reference image: `components/loap-type.png`
- model: `chatgpt-image-latest`  ·  post: rotate +45°, trim

---

## Full assembled prompt (straight render)

# Art Style

Render as a clean BLACK-AND-WHITE structural sample — pure line art, no color and no shading.
The purpose is to DEMONSTRATE THE STRUCTURE and LAYOUT of a single component (a logo, badge, or
masthead): where every element sits, not how it is finally colored or finished.

## Rendering
- **Black and white only.** Black linework and, where needed, solid black fills on a plain WHITE
  background. No color of any kind. No gray, no gradients, no drop shadows, no glow, no texture.
- **Line art / flat:** Every element is drawn as clean, confident black outlines, with at most
  flat solid-black fills for emphasis. Think a crisp vector wireframe or a printer's layout
  sheet — precise and diagrammatic.
- **Show the structure:** Make the placement and relative size of each element unmistakable —
  the text lines and their stacking, the lightning bolts, rules/lines, and highlight shapes.
  Highlights are indicated as clean outlined shapes, not as rendered light.
- **Type:** Render the lettering in its correct layout, weight, and proportion (in black) so the
  wordmark's structure reads clearly.

## Purpose
This is a schematic/spec sample, not finished art. It exists to lock the LAYOUT of a component
so the identical structure can later be re-skinned in any color style.

# Composition

A single component isolated and centered on a plain white field, presented as a structural
layout sample.

## Layout
- ONE component (the logo / badge / masthead) centered, filling most of the frame with generous
  white margins around it.
- Nothing else in the frame — no scene, no extra graphics, no caption, no border.
- Elements are arranged exactly per the component's structure description so their placement
  reads clearly: text stacking, lightning bolts, rules, and highlight shapes.

## Feel
Clean, precise, diagrammatic — a spec sheet that documents the component's structure.

# Component

 

# Scene

The angled (diagonal corner banner) League of Amazing Programmers wordmark, rendered as a black-and-white structural type sample per the component description.

# Layout

> Present the single component centered on a plain white background with generous margins. No
> border, no scene, no extra text beyond the component itself. Crisp, high-resolution line art
> suitable as a reusable structural reference sheet.

# Additional Direction

IMPORTANT: Render PERFECTLY HORIZONTAL and LEVEL (this straight version will be rotated later).
Reproduce ONLY the wordmark from the reference — "THE LEAGUE OF" (top), "AMAZING" (large, spelled A-M-A-Z-I-N-G, slight arch), "PROGRAMMERS" (below), and the two lightning bolts — as clean B&W line art (black outlines / solid black on white).
ADD a thin horizontal ribbon strip directly BELOW the wordmark reading "SMART MINDS · BOLD IDEAS · BRIGHT FUTURES".
ABSOLUTELY NO box, NO banner, NO frame, NO outline, NO parallelogram, NO rectangle, and NO enclosing shape of ANY kind around the wordmark. Nothing but the letters, the two lightning bolts, and the subhead ribbon — floating on plain white. No horizontal lines or rules anywhere except the subhead ribbon itself.
Level, centered, no color, no shading, no texture.

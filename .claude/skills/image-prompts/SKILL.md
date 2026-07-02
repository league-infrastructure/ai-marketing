---
name: image-prompts
description: Write a final image-generation prompt for the League marketing system — gather the style/palette/composition/layout/component pieces and rewrite them into one single-voice prompt with exact text and a strong negative. Use before every generate_project_image call.
---

# Writing Image Prompts

The house method, learned the hard way. The assembled pieces are raw material;
the deliverable is a rewritten, single-voice prompt.

## Procedure

1. **Gather.** Read the relevant files: `prompts/styles/<style>/{positive,negative}.md`,
   `prompts/palettes/<palette>.md`, `prompts/compositions/<comp>.md`,
   `layouts/<layout>.md`, and any `components/<name>/description.md` in play. You can
   call `assemble_prompt` to collect them, but NEVER ship its output raw — the sections
   repeat and contradict each other.
2. **Rewrite into one voice.** Produce a single coherent prompt with this shape:
   - **Style declaration** — one paragraph nailing the visual language.
   - **Color** — the palette, stated as a hard budget ("~7 flat ink colors, max 9",
     name the key hexes when the palette file has them).
   - **Detail budget** — say explicitly where detail is spent ("spend visual detail
     ONLY on: the child, the robot, …; simplify everything else into bold graphic
     shapes").
   - **Scene** — the story in concrete visual terms: who, where, what pose, what mood,
     what the joke/second-read is.
   - **Composition** — camera angle, staging, diagonals/triangles. If a reference
     photo is attached, state that its composition is STRICT: same camera angle,
     same figure count, same left-to-right placement, same orientation.
   - **Reference scoping** — when multiple references are attached, say which aspect
     each governs ("use the photo ONLY for the robot's physical construction — do NOT
     copy its composition").
   - **TEXT block** — every piece of lettering, spelled EXACTLY, each with placement
     and lettering style (e.g. 'TITLE across the TOP: "TAKE US TO YOUR LEADER" in huge
     bold retro pulp letters, red with heavy black outline, on a jagged burst').
     End with: *no other lettering, signs, labels, or captions anywhere*.
   - **Brand components** — logo/badge/masthead per `components/*/description.md`,
     with placement (e.g. "League wordmark bottom-right, sitting directly on the art,
     NO box behind it").
3. **Write the negative prompt.** Texture prohibitions go FIRST: grain, speckle,
   stipple, halftone, newsprint, parchment, aged/yellowed paper, print-dot texture,
   soft glows, airbrush gradients. Then: photorealism/CGI/3D render, wrong
   orientation, extra figures, invented lettering, and anything the designer has vetoed in
   this project.
4. **Send** via `generate_project_image(prompt=..., negative_prompt=..., ...)` with the
   right `size` (`1536x1024` landscape postcard, `1024x1536` portrait, `1024x1024` square).

## Style truths (do not relearn these)

- **comic-book / "pulp"** = 1940s Golden Age cover art: bold hand-inked black contours,
  large VIVID flat four-color fields, flat-black shadow shapes, rich detail on hero
  subjects, simplified-but-illustrated environment, dramatic low-heroic composition.
  "Four-color aesthetic" means the COLOR look and is wanted; only surface GRAIN is
  banned. Do not overcorrect into a flat modern vector poster.
- **graphic-novel** = the HisMastersVoice look: cinematic painted shading, dramatic
  screen-glow lighting, deep inky blacks, sharp detailed inking.
- **type-sample** = black-and-white, no shading (except the 8bit variant, which uses
  gray-tone shading to show layers): documents STRUCTURE — element placement, bolts,
  lines, text layout — not style.
- Model-side grain gotcha: gpt-image models spray faint stipple onto soft glows and
  gradients even when the prompt is clean. Prefer hard-edged flat shapes and a single
  flat background color zone over halos and sprayed beams.
- Kids are the heroes; real student robots rendered faithfully; code only on a laptop
  screen; no outside branding; no chibi/Funko/Pixar/photorealism.

## Iteration deltas

When revising, change the minimum: quote back the previous iteration's prompt from
`project.json` and edit it, rather than rewriting from scratch — that's what keeps
"draft 9's logo" recoverable. Fix systemic flaws in the shared `prompts/` files too,
so the fix outlives the project.

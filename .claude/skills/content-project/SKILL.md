---
name: content-project
description: Run a League marketing content project end to end — set up the project, open the live gallery, iterate on images from chat feedback, and harvest approved art into components. Use whenever Eric asks to create a new postcard/flyer/logo/image project or to continue iterating on one.
---

# Content Project Workflow

The full process rationale is in `docs/PROCESS.md`; this is the operating procedure.

## Starting a new project

1. **Parse the brief.** Extract: style, composition, layout, palette, theme, scene,
   the exact slogan text (check `League_Campaign_Slogans.md`), and reference images.
   A reference photo defines the COMPOSITION (camera angle, figure placement,
   orientation) unless Eric says it's only for subject detail.
2. **`create_project`** with that config, passing reference photos as `source_images`.
3. **`open_project` immediately** — before the first generation. Tell Eric the URL.
   This is mandatory: he watches the gallery, not the filesystem.
4. **Write the prompt** using the `image-prompts` skill (single voice, exact text,
   texture in the negative), then `generate_project_image(prompt=..., negative_prompt=...)`.
   Give each iteration a `label` and `notes` saying what it tried.

## Iterating

Translate each piece of chat feedback into a concrete prompt or parameter delta:

- **"Use X from draft N"** → open `project.json`, diff the prompts of iteration N vs.
  current, and carry forward the exact winning language. Never guess from memory.
- **"Make it look like <image/project>"** → attach that image as a reference AND state
  in the prompt which aspect it governs (style / lettering / build / composition).
- **Wrong aspect ratio or wasted space** → fix the `size` parameter
  (`1536x1024` landscape postcards, `1024x1536` portrait) before touching prompt text.
- **A recurring flaw traced to a shared file** (style/composition/palette) → fix the
  file in `prompts/` or `layouts/` so the whole system improves, then regenerate.
- **A change that should persist** → `update_project` so it becomes the default.
  Keep `project.json` truthful even when overriding with `prompt=`.

After EVERY generation the gallery auto-reloads; confirm the new iteration number to
Eric. If he says he can't see it, use the `show-work` skill right away.

## Cleaning up / harvesting

- "Delete everything except draft N" → prune `iterations/` and the `iterations` array
  in `project.json`, renumber as asked, bump `state.json`, `render_project_html`.
- "Record / save this one" → keep it, label it clearly.
- "Store as a type sample" → save the PNG into the matching `components/<name>/` folder
  plus a same-named `.md` containing the EXACT prompt that generated it. Backfill
  prompts from `project.json` iteration records when asked.
- Commit only when Eric says to.

## Guardrails

- Prompts are data: never hardcode prompt text in scripts; never hand-number iterations.
- Generation is OpenAI-direct (`IMAGE_MODEL` from `.env`, `quality=high`, `/images/edits`
  for references). Never Gemini for generation.
- New style names require an MCP server restart (in-memory `STYLES` list) — ask Eric to
  restart; the `.md` prompt files themselves are re-read every call.
- Real solutions over hacks unless he says "do it right now".

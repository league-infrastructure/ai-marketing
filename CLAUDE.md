# League Marketing — Agent Instructions

This repo generates marketing images for The League of Amazing Programmers through the
`league-image-generator` MCP server. Read `SKILL.md` for the tool reference and
`docs/PROCESS.md` for the full content-project process. Skills in `.claude/skills/`
cover the three core workflows: `content-project`, `image-prompts`, `show-work`.

## Non-negotiable rules

1. **SHOW EVERYTHING.** The designer must be able to SEE every image you produce, in the
   browser, without asking. Never end a turn having generated an image that isn't visible
   on their screen. For projects: `open_project` immediately after `create_project` —
   before the first generation — and re-open it whenever they say "show me" / "I can't
   see it".
   For anything outside a project (font tests, crops, one-offs): build a small HTML page
   and `open` it, or `open <file>` directly. See the `show-work` skill.

2. **Prompts are data, not code.** Reusable prompt text lives in `prompts/styles/`,
   `prompts/palettes/`, `prompts/compositions/`, `layouts/`, `components/`; per-project
   direction lives in that project's `project.json`. Never hardcode prompt text into a
   script, and never hand-number iteration files — the MCP server does that.

3. **Rewrite the assembled prompt.** Never send `assemble_prompt`'s concatenated output
   raw. Gather the pieces, then rewrite them into ONE coherent, single-voice prompt and
   pass it via `generate_project_image(prompt=..., negative_prompt=...)`. Texture
   prohibitions go at the front of the NEGATIVE prompt. See the `image-prompts` skill.

4. **A reference photo is a composition contract.** When the designer attaches a photo,
   they want that exact camera angle, figure count, left-to-right placement, and
   orientation. Do not flip landscape/portrait. Reproduce the composition precisely
   unless they say the reference is only for subject/build detail (then say so in the
   prompt).

5. **Generation goes through OpenAI directly** — model from `.env` (`IMAGE_MODEL`,
   currently `gpt-image-2`), `quality=high`, `/v1/images/edits` when reference images
   are attached. Never route generation to Gemini/OpenRouter. Postcards are landscape:
   `1536x1024`.

6. **Flat color is a war we already fought.** House comic styles use dark black ink,
   solid flat color fields (~7 colors, max 9), NO texture — no newsprint, parchment,
   grain, speckle, halftone, soft glows. But do NOT overcorrect into a generic flat
   vector poster: keep Golden-Age richness (bold inked contours, detailed hero subjects,
   dramatic composition). `graphic-novel` = the HisMastersVoice look.

7. **Exact text only.** Every slogan is spelled exactly as given, with explicit placement
   and lettering style for each piece, and the prompt ends with "no other lettering
   anywhere". Slogans live in `League_Campaign_Slogans.md`.

8. **Real solutions, not hacks.** The designer solves problems for the long term. Only
   take a shortcut when they explicitly say "do it right now" / "hack it".

## Operational gotchas

- The MCP server is long-lived. Edits to `mcp-server/server.py` or new style names
  (the in-memory `STYLES` list) require a restart — ask the designer to restart, don't
  work around it silently. Style/palette/composition `.md` files ARE re-read every call.
- The gallery (`index.html`) polls `state.json` and reloads only when `version` changes.
  Don't break that — aggressive reloading ("blinking") is a known regression.
- `project.json` must stay truthful: when you pass `prompt=` overrides, still update
  `scene_description` / `theme` / `custom_additions` (via `update_project`) so the
  config describes what the project actually is.
- When the designer says a change should stick ("keep the logo from draft 9"), lock it
  into the project defaults with `update_project`, don't just carry it in your head.
- Good iterations get harvested: save keepers as components/type samples with a
  same-named `.md` containing the exact prompt that produced them.

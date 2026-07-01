# League Marketing Image Generator

Generate marketing images for The League of Amazing Programmers in multiple art styles and layouts.
Uses OpenRouter image generation models (Gemini 3 Pro Image, GPT-5.4 Image, etc.) and evaluates
output with vision models.

## Project Structure

```
marketing/
├── prompts/           # Prompt components, joined at assembly time
│   ├── styles/        # One folder per art style: positive.md + negative.md
│   │   ├── pop-art/           # Roy Lichtenstein 1960s pop art
│   │   ├── comic-book/        # 1940s Golden-Age comics
│   │   ├── manga/             # Black-and-white manga
│   │   ├── dragon-ball-z/     # DBZ / Toriyama anime
│   │   ├── technical-blueprint/  # Blueprint/drafting style
│   │   └── 8bit-video-game/      # NES pixel art
│   └── compositions/  # One markdown file per composition (arena-action.md,
│                      #   vintage-cover.md, power-up.md, …) — shared across styles
├── layouts/           # Format/layout prompt components
│   ├── postcard-4x6.md
│   ├── business-card.md
│   ├── individual-cut-images.md
│   ├── individual-panels.md
│   └── full-page-flyer.md
├── rubrics/           # Evaluation rubrics (per style + per layout)
│   ├── README.md      # Master index and usage guide
│   ├── pop-art.md
│   ├── comic-book.md
│   ├── manga.md
│   ├── dragon-ball-z.md
│   ├── technical-blueprint.md
│   ├── 8bit-video-game.md
│   └── layouts.md
├── mcp-server/        # MCP server for OpenRouter image generation
│   ├── server.py      # Main MCP server
│   └── run.sh         # Self-locating `uv run` launcher
├── pyproject.toml     # Project metadata + dependencies (uv-managed)
├── uv.lock            # Pinned dependency lockfile
├── .mcp.json          # MCP client config (uv run, relative paths)
├── output/            # One-off generated images land here
├── projects/          # Iterative image jobs — one folder per project (config +
│                      #   sources + iterations + auto-reloading index.html gallery)
├── IDEA.md
└── SKILL.md           # This file
```

## Prerequisites

1. **OpenRouter API key** — Set `OPENROUTER_API_KEY` (read from the project `.env`)
2. **[uv](https://docs.astral.sh/uv/)** — manages the virtual environment and Python
3. Dependencies live in `pyproject.toml` (`mcp`, `httpx`, `python-dotenv`) and are pinned
   in `uv.lock`. `uv run` / `uv sync` create and populate `.venv` automatically — no manual
   venv setup or `pip install` needed.

## MCP Server Setup

The project ships a `.mcp.json` (auto-detected by Claude Code when the project is the
workspace). It launches the server with `uv run` using paths relative to the project root,
so it keeps working if the project is moved:

```json
{
  "mcpServers": {
    "league-image-generator": {
      "command": "uv",
      "args": ["run", "mcp-server/server.py"],
      "env": {}
    }
  }
}
```

For other MCP clients, point them at the self-locating launcher (absolute path to it is
fine; it `cd`s to its own project root internally):
`mcp-server/run.sh`.

Or run directly from the project root:
```bash
uv run mcp-server/server.py       # syncs .venv from uv.lock, then starts the server
```

## MCP Tools

### `assemble_prompt`
Assemble a complete prompt by concatenating the full markdown components:
`styles/<style>/positive.md` + `compositions/<composition>.md` + scene + layout + custom.
The `negative_prompt` returned is the full `styles/<style>/negative.md`. Whatever the
markdown files say is exactly what goes to the model — edit those files to change output.
- `style`: One of the 6 art styles (folder under `prompts/styles/`)
- `layout`: One of the 5 layouts (optional)
- `composition`: Composition name (a file stem under `prompts/compositions/`, e.g.
  "extreme-close-up", "vintage-cover")
- `scene_description`: What should be depicted
- `custom_additions`: Any extra prompt text

### `generate_image`
Call OpenRouter to generate an image.
- Uses `assemble_prompt` internally if no explicit prompt provided
- Saves output to `output/` directory
- Supports reference images for image-to-image generation

### `evaluate_image`
Use a vision model to evaluate a generated image against a rubric.
- Loads the appropriate style rubric automatically
- Returns structured evaluation with scores, strengths, issues, and verdict

### `list_available`
List all available styles, compositions, and layouts.

## Project Tools (iterative image jobs)

A **project** is a directory under `projects/<slug>/` that holds one marketing-image job:
its config, source images, every generated iteration, and an auto-reloading HTML gallery
the user watches in a browser while you iterate over chat.

```
projects/<slug>/
  project.json   # config (style/composition/layout/theme/scene) + iteration history
  state.json     # {"version": N} — bumped on every write; the HTML polls it to live-reload
  index.html     # gallery, regenerated on every write (newest iteration on top)
  sources/       # copied source/reference images
  iterations/    # iter-001.png, iter-002.png, …
```

### `create_project`
Create the project directory + `project.json` + gallery. Args: `name`, `style`,
`composition`, `layout`, `theme`, `scene_description`, `model`, `negative_prompt`,
`custom_additions`, `source_images` (paths — copied into `sources/`).

### `open_project`
Open the gallery in the browser. Default `serve=True` starts a small local static server
for the project so the fetch-based auto-reload works flicker-free; `serve=False` opens
`file://` (auto-reload falls back to a periodic refresh). Servers are reused per project.

### `generate_project_image`
Generate the next iteration and append it to the gallery. Assembles the prompt from the
project config; **any arg overrides the stored default for that one call** (`scene_description`,
`style`, `composition`, `layout`, `custom_additions`, `negative_prompt`, `model`). Pass an
explicit `prompt` to bypass assembly with a hand-edited prompt. Project sources are sent as
references by default (`use_sources=True`; add more with `reference_images`). `label`/`notes`
annotate the card. Saves to `iterations/iter-NNN.png`, records it, regenerates the HTML →
the open tab auto-reloads.

### `update_project`
Change any subset of config fields and/or add sources (`add_sources`). Rewrites the gallery.

### `get_project` / `list_projects` / `render_project_html`
Inspect one project's full JSON, list all projects, or force-rebuild a gallery's HTML.

## Workflow

### Quick Generate
1. Call `assemble_prompt` with style, layout, and scene description
2. Review the assembled prompt
3. Call `generate_image` with the same parameters

### Quality Pipeline
1. Call `generate_image` with style + layout + scene → get image
2. Call `evaluate_image` with the generated image path and style
3. If verdict is REVISE: adjust scene description, regenerate
4. If verdict is FAIL: check style fidelity issues, try different approach
5. If verdict is PASS: image is marketing-ready

### Batch Generation (for campaigns)
1. Define a set of (style, layout, scene) combinations
2. Generate all in parallel
3. Evaluate each
4. Pass PASS images to the marketing pipeline

### Project Iteration (the main interactive loop)
This is how you work with a user who wants to dial in one image over several rounds.
1. **Set up.** From the user's ask (e.g. "a 1940s cover of a girl building a robot, for a
   postcard"), call `create_project` with the matching `style` / `composition` / `layout` /
   `theme` / `scene_description`, and pass any photos they gave as `source_images`.
2. **Open the gallery.** Call `open_project` once — it serves the project and opens the
   browser. Leave that tab open; it auto-reloads on every new iteration.
3. **Generate.** Call `generate_project_image`. The new image and its prompt appear at the
   top of the gallery.
4. **Iterate from chat.** When the user asks for a change ("make it brighter", "girl on the
   left", "try the manga style"), translate it into an override and call
   `generate_project_image` again — adjust `scene_description` / `custom_additions` for
   tweaks, `style` / `composition` / `layout` to switch treatment, or pass a hand-edited
   `prompt` for fine control. Use `label`/`notes` to caption what each round tried. Each
   call adds a new iteration; nothing is overwritten, so the history stays comparable.
5. **Lock in defaults.** If a change should stick for all future rounds, use
   `update_project` so it becomes the project's default.

Prefer `generate_project_image` over the bare `generate_image` whenever the user is
iterating — it keeps the config, history, and live gallery in sync. Reserve `generate_image`
for one-off, throwaway generations.

## Available Models

Via OpenRouter image generation (as of June 2026):
- `google/gemini-3-pro-image` — **Default.** Best quality. Nano Banana Pro.
- `google/gemini-3.1-flash-image` — Fast, cost-effective
- `openai/gpt-5.4-image-2` — OpenAI's latest image model
- `openai/gpt-5-image` — GPT-5 with image generation
- `google/gemini-2.5-flash-image` — Budget option

Vision evaluation model (configurable):
- `google/gemini-2.5-flash` — Default. Fast, cheap, good enough for evaluation

## Art Styles Reference

| Style | Key Visual Signal | Gate Check |
|-------|-------------------|------------|
| Pop Art | Ben-Day dots everywhere | Dots visible? |
| Comic Book | Flat solid color, NO dots | No dots? |
| Manga | Black & white, screentone | No color? |
| DBZ Anime | Spiky hair, cel shading, energy auras | Toriyama face style? |
| Blueprint | White lines on blue paper | Correct color scheme? |
| 8-Bit | Visible pixel grid, NES palette | Pixels visible? |

## Shared Brand Rules (All Styles)

These rules from the pop-art-design project apply to ALL styles:
- Real student robots, rendered faithfully (Micro:bit boards, two-wheel chassis, etc.)
- Kids are the heroes — expressive, proud, focused
- Celebrate ingenuity: engineering, creativity, teamwork
- No outside branding or wall text
- No Funko Pop / chibi / oversized heads / Pixar / CGI / photorealism
- Code appears ONLY on a laptop screen facing the viewer
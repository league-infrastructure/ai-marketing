# League Marketing Image Generation System

A prompt-engineering + evaluation pipeline for generating marketing images for
The League of Amazing Programmers across multiple art styles and formats.

## Quick Start

```bash
cd /Volumes/Proj/proj/league-projects/infrastructure/marketing
source .venv/bin/activate
OPENROUTER_API_KEY=*** python mcp-server/server.py
```

## Art Styles (6)
1. **Pop Art** — Roy Lichtenstein 1960s, Ben-Day dots, primary colors
2. **Comic Book** — 1940s Golden-Age, flat solid color, newsstand covers
3. **Manga** — Black & white, screentone, angular, kinetic
4. **Dragon Ball Z** — Toriyama anime, cel-shaded, spiky hair, energy auras
5. **Technical Blueprint** — White lines on blue, drafting, wireframe
6. **8-Bit Video Game** — NES pixel art, visible pixel grid

## Layouts (5)
1. 4×6 Postcard
2. Business Card
3. Individual Cut Images (isolated assets)
4. Individual Panels (web embeds, hero images)
5. Full-Page Flyer (8.5×11)

## Architecture
- `prompts/styles/{style}/` — positive.md + negative.md per style
- `prompts/compositions/{name}.md` — one file per composition, shared across styles
- `layouts/` — Format-specific layout instructions
- `rubrics/` — Evaluation checklists (per style + per layout)
- `mcp-server/` — MCP server calling OpenRouter image models
- `output/` — Generated images

## The Pipeline
1. **Assemble** → Combine style + layout + scene → full prompt
2. **Generate** → Call OpenRouter image model → save image
3. **Evaluate** → Vision model checks image against rubric → PASS/FAIL/REVISE
4. **Iterate** → Revise prompt based on evaluation → regenerate

## Reference
- Source art examples: `../pop-art-design/images/`
- Source prompt examples: `../pop-art-design/Prompts/`
- Style documentation: `../pop-art-design/docs/`
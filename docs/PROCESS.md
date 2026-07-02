# The Content-Project Process

How a new marketing image goes from an idea in chat to a finished, on-brand asset.
This is the formalization of how the designer and the agent actually work together in this
repo, distilled from the project history. `SKILL.md` documents the MCP tools;
this document describes the *process* — who does what, in what order, and the
conventions that make the output good.

## The mental model

The designer is the **art director**. The agent is the **production artist and prompt
engineer**. The browser gallery is the **light table** — the shared surface where
every draft appears. The designer never inspects files in a file manager; if it isn't in
their browser, it doesn't exist.

The unit of work is a **project**: one marketing deliverable (a postcard, a logo,
a flyer) that gets dialed in over many iterations. Projects live in
`projects/<slug>/` and are managed entirely through the `league-image-generator`
MCP server, which keeps `project.json` (config + full iteration history),
`iterations/iter-NNN.png`, `state.json` (version counter the gallery polls), and
`index.html` (the auto-reloading gallery).

## Raw materials

| Directory | What it holds | Role in a prompt |
|---|---|---|
| `prompts/styles/<style>/` | `positive.md` + `negative.md` per art style | The visual language (comic-book, graphic-novel, 8bit, type-sample, …) |
| `prompts/palettes/` | One file per palette | Color constraints, layered on any style |
| `prompts/compositions/` | One file per composition | Camera/staging (single-moment, vintage-cover, type-sample, …) |
| `layouts/` | One file per output format | Physical format: postcard-4x6, flyer, business card |
| `components/` | `example.png` + `description.md` per brand component | Logos, badges, mastheads that must render identically everywhere |
| `assets/logos/` | Official League art from images.jointheleague.org | Reference inputs |
| `stock_images/` | Photos used as composition references | Composition contracts |
| `League_Campaign_Slogans.md` | Campaign copy | The exact text that goes on the art |

All of this is **data**. The agent never copies prompt text into scripts; it edits
these files or the project config, and generates through the server.

## The lifecycle

### 1. Brief

The designer opens with a compact brief, typically: theme/slogan (often by pointing at
`League_Campaign_Slogans.md`), style, layout, palette, and usually a reference
photo. Example, verbatim from history:

> "Let's create a new project. It will be a postcard in the technical drawing
> style with a child at a computer. Use stock_images/….jpg as an example image
> for composure. The slogan is 'A great career starts with Hello World'. Use
> drafting style callouts to indicate the child is learning problem solving
> skills (pointing to the computer) and having fun (pointing to the child's head)."

Everything in a brief is load-bearing: the reference photo defines the
composition, the slogan is exact copy, and named styles refer to the files in
`prompts/styles/`. If the brief names a style that doesn't exist yet, that may be
a request to create one (that's how `graphic-novel` was born).

### 2. Set up and open the gallery

`create_project` with the brief's style/composition/layout/palette/theme/scene and
any reference photos as `source_images`. Then **immediately** `open_project` —
before generating anything — and tell the designer the URL. The gallery tab stays open for
the whole session and auto-reloads as iterations land.

### 3. Write the prompt

This is the craft step; the full rules are in the `image-prompts` skill. In short:
gather the style/palette/composition/layout/component text, then **rewrite it into
one single-voice prompt** — not a concatenated hodgepodge — with the scene, the
exact text and its placement, and composition instructions tied to the reference
photo. Texture prohibitions and everything unwanted go in the negative prompt.
Pass both via `generate_project_image(prompt=..., negative_prompt=...)`.

### 4. Iterate

The designer reacts to each draft in chat. Their feedback is terse and precise; translate it
into prompt deltas, not vibes:

- **Named-draft references** ("use the logo from draft 9", "the map from draft 9
  was closer") — diff the two iterations' recorded prompts in `project.json` and
  carry the specific winning language forward.
- **Reference images** ("make it look like HisMastersVoice", "use Head.png for
  the lettering") — attach them as references AND describe in the prompt exactly
  which aspect each reference governs (style vs. lettering vs. robot build vs.
  composition).
- **Style corrections** ("too dingy", "too much yellow", "get rid of the
  texture") — fix the prompt AND, if the flaw came from a shared file in
  `prompts/`, fix the shared file so it never comes back.
- **Layout corrections** ("this must be 4x6", "it's landscape", "use all the
  vertical space") — check the `size` parameter first; aspect problems are
  usually parameters, not prompt wording.

Label each iteration (`label`, `notes`) with what it tried, so "draft 9" style
references stay resolvable. Nothing is overwritten; history stays comparable.

When a change should persist ("keep this logo from now on"), lock it into the
project defaults with `update_project`. Keep `project.json` truthful even when
generating with a hand-written `prompt=` override.

### 5. Harvest

When an iteration is approved:

- Save keepers explicitly — the designer says things like "record this one" or "store
  version 11 as a type sample".
- Reusable brand elements are promoted into `components/<name>/` as
  `example.png` + `description.md`, and/or a **type sample**: a black-and-white,
  structure-only rendering (`type-sample.png`) that documents element placement,
  with a same-named `type-sample.md` containing the **exact prompt** that
  produced it.
- Commit when the designer says to commit; branch names describe the work.

Components then feed future projects: attach the component's `example.png` as a
reference and fold its `description.md` into the prompt so logos and mastheads
render identically across every piece.

## Feedback decoder

Recurring designer phrasings and what they require:

| They say | It means |
|---|---|
| "Show me" / "Open it" / "I can't see it" | You failed rule #1. `open_project` or `open` the file right now. |
| "That's trash" / "boy, that's ass" | Dead end — don't tweak, change approach and ask what direction if unclear. |
| "Refer to <project/draft>" | That artifact is the ground truth; use it as a reference image and mine its prompt. |
| "Get rid of the texture" | Flat solid color fields; texture terms go in the negative; also purge the shared style files. |
| "Why did you…?" (process question) | He wants the root-cause explanation *before* any fix. Answer the question; don't touch code first. |
| "Do it right now" | Explicit permission to hack. Absent these words, build the real solution. |

## Environment facts

- Generation: OpenAI direct, `IMAGE_MODEL` from `.env` (currently `gpt-image-2`),
  `quality=high`, `/v1/images/edits` for reference-image jobs. Never Gemini for
  generation (evaluation uses Gemini Flash — that's fine).
- Sizes: `1536x1024` landscape (postcards), `1024x1536` portrait, `1024x1024`.
- The MCP server is long-lived: `server.py` edits and new `STYLES` entries need a
  restart (ask the designer); the prompt `.md` files are re-read on every call.
- The gallery reloads only when `state.json`'s version changes — never make it
  poll-refresh blindly (the "blinking" bug).

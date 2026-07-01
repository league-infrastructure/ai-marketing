# Marketing Components

Reusable brand components — logos, badges, and mastheads — that should look the SAME across
every marketing image. Each component is a folder containing:

- `example.png` — a reference image of the component (cropped from real artwork or a clean
  generated asset). Feed this to the image generator as a reference so the component is
  replicated faithfully instead of reinvented each time.
- `description.md` — a written description of the component's style/layout, precise enough to
  reproduce it from text and to keep the example on-brand.

Components in this set:

- **league-logo-horizontal** — the stacked "THE LEAGUE OF AMAZING PROGRAMMERS" wordmark badge.
- **league-logo-angled** — the same wordmark on an angled/diagonal banner (as on the "At His
  Command" cover).
- **approval-badge** — a circular approval stamp featuring the League robot.
- **masthead** — the big jagged-burst title treatment (e.g. red 3-D block letters on a blue
  starburst), used for the headline word on a card.

Usage: attach a component's `example.png` as a reference image and paste its `description.md`
into the prompt (or a project's `custom_additions`) so the generator reproduces it exactly.

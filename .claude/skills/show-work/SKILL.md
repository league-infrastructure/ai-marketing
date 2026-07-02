---
name: show-work
description: Make generated images and files visible to the designer in their browser. Use IMMEDIATELY whenever an image or visual artifact is created outside an open project gallery, and whenever the designer says "show me", "open it", "I can't see it", or similar.
---

# Showing Work

The designer reviews everything in their browser. An image they cannot see does not exist.
Never end a turn having produced a visual artifact that is not on their screen.

## Decision table

| What you made | How to show it |
|---|---|
| An iteration in a project | Nothing extra needed if the gallery is already open — it auto-reloads. If in doubt, or if the designer says they can't see it, call `open_project(name)` again (it reuses the server). |
| A new project | `open_project(name)` immediately after `create_project`, BEFORE the first generation. Report the URL. |
| One or a few loose images (crops, font tests, `output/` one-offs) | `open <path>` (macOS opens Preview) — fine for a single quick look. |
| Several related images to compare (font experiments, candidate crops) | Build a small HTML gallery page in the scratchpad or the relevant directory — filename captions, images at reasonable width, newest first — and `open <page>.html`. |
| An HTML page that needs fetch/auto-reload | Serve it: `python3 -m http.server <port> --bind 127.0.0.1` in the directory (background), then `open http://127.0.0.1:<port>/…`. `file://` URLs break fetch-based reload. |

## Rules

- **Default to showing, not asking.** Don't ask "want me to open it?" — open it and
  say what you opened and where.
- **Verify the open worked.** `open` and `webbrowser` return success even for a wrong
  path. Echo the exact URL/path you opened; if the designer says they don't see it, re-open
  via a different route (served URL instead of file://, or `open -a "Google Chrome" <url>`)
  rather than repeating the same call.
- **Galleries reload on state change only.** Project galleries poll `state.json` and
  reload when `version` changes. If you write iterations by hand, bump `state.json`
  and call `render_project_html` or the open tab will never update. Never add
  blind timed refresh — that caused the "blinking" bug.
- **After showing, stop and wait.** The next move is the designer's reaction.

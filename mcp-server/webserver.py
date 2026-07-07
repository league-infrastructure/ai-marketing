#!/usr/bin/env python3
"""
League Marketing — Web Server Daemon

Everything about SERVING and RENDERING project pages: the shared static HTTP server, the
HTML gallery/postcard templates, project.json/postcard-content.json persistence, and the
postcard PDF export (bleed + rotation + trim/bleed-box metadata). Runs as its own OS process,
independent of the MCP server (mcp-server/server.py) — so editing anything in this file only
ever requires restarting THIS daemon (the `restart_web_server` MCP tool does that), never the
whole MCP connection.

The MCP server writes raw image files directly to disk (that's plain file I/O, unrelated to
rendering) and then POSTs the resulting data here over HTTP so this daemon is the single
place responsible for turning project data into the HTML/PDF the designer actually sees.

Run directly for local debugging: `python3 webserver.py --port 31337`
"""

import argparse
import asyncio
import functools
import html
import json
import os
import re
import signal
import socket
import sys
import urllib.parse
from datetime import datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional

import markdown as markdown_lib
from jinja2 import Environment, FileSystemLoader

# ── Configuration ──────────────────────────────────────────────────────────

MARKETING_DIR = Path(__file__).resolve().parent.parent
PALETTES_DIR = MARKETING_DIR / "prompts" / "palettes"
PROJECTS_DIR = MARKETING_DIR / "projects"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

DEFAULT_STATIC_PORT = 31337  # fixed "weird" port so the gallery URL is stable across restarts
                              # (bookmarkable) instead of picking a fresh random port every time;
                              # falls back to a random free port only if something else owns it.
STATE_PATH = PROJECTS_DIR / ".webserver.json"  # {"pid": int, "port": int} — how server.py finds us

_PRINT_PPI = 256          # matches postcard-4x6's 1536x1024 == 6in x 4in generation resolution
_BLEED_IN = 0.125         # standard 1/8in cutting bleed, added on every side of the trim

_JINJA_ENV = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)


def _render_markdown(text: str) -> str:
    """Region text is authored as Markdown; nl2br so a single Shift+Enter newline in the
    editor becomes a real <br> (plain Markdown would otherwise need a blank line)."""
    return markdown_lib.markdown(text or "", extensions=["nl2br"])


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", (name or "").strip()).strip("-._")


def _load_project(name: str) -> Optional[dict]:
    pj = PROJECTS_DIR / _slug(name) / "project.json"
    if not pj.exists():
        return None
    try:
        return json.loads(pj.read_text())
    except Exception:
        return None


def _rel_to_project(data: dict, path: str) -> str:
    try:
        return str(Path(path).relative_to(PROJECTS_DIR / data["slug"]).as_posix())
    except Exception:
        return str(path)


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _bump_state(pdir: Path) -> int:
    """Increment and rewrite <pdir>/state.json, returning the new version. The single place
    that advances a project's live-reload counter."""
    state_path = pdir / "state.json"
    version = 0
    if state_path.exists():
        try:
            version = int(json.loads(state_path.read_text()).get("version", 0))
        except Exception:
            version = 0
    version += 1
    state_path.write_text(json.dumps({"version": version}))
    return version


def _save_project(data: dict) -> None:
    """Persist project.json, bump state.json (triggers browser reload), rewrite index.html.
    Also rewrites postcard.html when this project has a postcard-content.json, and refreshes
    the projects-home page/listing so it never goes stale."""
    pdir = PROJECTS_DIR / data["slug"]
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "project.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
    data["state_version"] = _bump_state(pdir)
    (pdir / "index.html").write_text(_render_project_html(data), encoding="utf-8")
    if _has_postcard(pdir):
        _save_postcard_html(pdir, data.get("name", ""), data["slug"], data["state_version"])
    _save_projects_home()


def _delete_iteration(slug: str, n: int) -> None:
    """Permanently delete one iteration: its image file(s) on disk and its entry in
    project.json. Refuses to delete an iteration currently used as a postcard's
    front_image/back_image, since that would silently break the postcard preview —
    the designer would need to pick a different front/back first."""
    pdir = PROJECTS_DIR / _slug(slug)
    data = _load_project(slug)
    if data is None:
        raise ValueError(f"No project '{slug}'")
    iterations = data.get("iterations", [])
    match = next((it for it in iterations if it.get("n") == n), None)
    if match is None:
        raise ValueError(f"No iteration #{n} in '{slug}'")

    images = match.get("images") or ([match["image"]] if match.get("image") else [])
    if _has_postcard(pdir):
        content = _load_postcard_content(pdir)
        in_use = {content.get("front_image"), content.get("back_image")} & set(images)
        if in_use:
            raise ValueError(
                f"Iteration #{n} is used as the postcard's front/back image ({', '.join(in_use)}) "
                "— choose a different front/back image before deleting it"
            )

    for rel in images:
        try:
            (pdir / rel).unlink(missing_ok=True)
        except Exception:
            pass

    data["iterations"] = [it for it in iterations if it.get("n") != n]
    _save_project(data)


def _render_iteration_card(it: dict) -> str:
    esc = html.escape
    n = it.get("n")
    label = esc(it.get("label") or "")
    created = esc(it.get("created") or "")
    model = esc(str(it.get("model") or ""))
    status = it.get("status", "ok")
    prompt = esc(it.get("prompt") or "")
    neg = esc(it.get("negative_prompt") or "")
    notes = esc(it.get("notes") or "")
    error = esc(str(it.get("error") or ""))
    imgs = it.get("images") or ([it["image"]] if it.get("image") else [])

    imgs_html = "".join(
        f'<a href="{esc(ip)}" target="_blank"><img class="hero" src="{esc(ip)}" alt="iteration {n}"></a>'
        for ip in imgs
    ) or f'<div class="noimg">&#9888; No image — {error or "generation failed"}</div>'

    refs_html = "".join(
        f'<a href="{esc(r)}" target="_blank"><img src="{esc(r)}"></a>'
        for r in (it.get("references") or [])
        if not str(r).startswith(("/", "http"))
    )
    refs_block = f'<div class="reflabel">references</div><div class="thumbs small">{refs_html}</div>' if refs_html else ""

    err_cls = "" if status == "ok" else "err"
    badge = "" if status == "ok" else '<span class="badge err">error</span>'
    lab = f'<span class="lab">— {label}</span>' if label else ""
    neg_block = f'<div class="dl">negative prompt</div><pre>{neg}</pre>' if neg else ""
    notes_block = f'<div class="dl">notes</div><p>{notes}</p>' if notes else ""
    error_block = f'<div class="dl">error</div><pre class="err">{error}</pre>' if error else ""

    label_attr = esc(it.get("label") or f"iteration {n}")
    return f'''
    <article class="card {err_cls}" data-iteration="{n}">
      <div class="cardhead">
        <span class="num">#{n}</span>{lab}{badge}
        <span class="meta">{created} &middot; {model}</span>
        <button class="delbtn" data-n="{n}" data-label="{label_attr}" title="Delete this iteration">&#128465; Delete</button>
      </div>
      <div class="imgwrap">{imgs_html}</div>
      {refs_block}
      <details><summary>Prompt &amp; details</summary>
        <div class="detail">
          <div class="dl">positive prompt</div><pre>{prompt}</pre>
          {neg_block}
          {notes_block}
          {error_block}
        </div>
      </details>
    </article>'''


def _render_project_html(data: dict) -> str:
    esc = html.escape
    cfg = data.get("config", {})
    chips = ""
    for k in ("style", "composition", "palette", "layout", "model"):
        v = cfg.get(k)
        if v:
            chips += f'<span class="chip"><b>{esc(k)}</b> {esc(str(v))}</span>'

    src_html = "".join(
        f'<a href="{esc(s)}" target="_blank"><img src="{esc(s)}" alt="source"></a>'
        for s in data.get("sources", [])
    )
    src_block = (
        f'<section class="sources"><h2>Source images</h2><div class="thumbs">{src_html}</div></section>'
        if src_html else ""
    )

    cards = "".join(_render_iteration_card(it) for it in reversed(data.get("iterations", [])))
    if not cards:
        cards = '<p class="empty">No iterations yet. Generate the first image to see it appear here.</p>'

    postcard_link = (
        '<p><a class="postcardlink" href="postcard.html">&#128444; Postcard front/back preview &rarr;</a></p>'
        if _has_postcard(PROJECTS_DIR / data["slug"]) else ""
    )

    return (
        _HTML_TEMPLATE
        .replace("{{NAME}}", esc(data.get("name", "")))
        .replace("{{SLUG}}", esc(data.get("slug", "")))
        .replace("{{VERSION}}", str(int(data.get("state_version", 0))))
        .replace("{{CHIPS}}", chips)
        .replace("{{THEME}}", esc(cfg.get("theme", "") or ""))
        .replace("{{SCENE}}", esc(cfg.get("scene_description", "") or ""))
        .replace("{{SOURCES}}", src_block)
        .replace("{{POSTCARD_LINK}}", postcard_link)
        .replace("{{CARDS}}", cards)
        .replace("{{GENERATED}}", esc(_now()))
    )


def _ensure_palette_symlink() -> bool:
    """Symlink projects/_palette-reference.html -> prompts/palettes/index.html so the shared
    static server (rooted at PROJECTS_DIR) can serve the palette reference page over the same
    http:// origin as everything else. Self-heals if the symlink or PROJECTS_DIR is ever
    recreated. Returns True if the link is in place and its target exists."""
    target = PALETTES_DIR / "index.html"
    if not target.exists():
        return False
    link = PROJECTS_DIR / "_palette-reference.html"
    if not link.is_symlink():
        try:
            PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
            link.symlink_to(os.path.relpath(target, PROJECTS_DIR))
        except OSError:
            return False
    return True


def _list_projects_data() -> list:
    """Scan projects/ for every project.json, returning the fields the projects-home page
    needs. Filesystem-derived so the listing can never drift from what's actually on disk."""
    projs = []
    if PROJECTS_DIR.exists():
        for d in sorted(PROJECTS_DIR.iterdir()):
            pj = d / "project.json"
            if not pj.exists():
                continue
            try:
                data = json.loads(pj.read_text())
            except Exception:
                continue
            cfg = data.get("config", {})
            iterations = data.get("iterations", [])
            slug = data.get("slug", d.name)
            # Prefer the postcard's designated front image (the designer explicitly said
            # "this one is the front") over just showing whatever was generated last — the
            # last iteration is often a back-of-card template, not the piece to lead with.
            thumb = None
            if _has_postcard(d):
                front_image = _load_postcard_content(d).get("front_image")
                if front_image:
                    thumb = f"{slug}/{front_image}"
            if not thumb:
                for it in reversed(iterations):
                    imgs = it.get("images") or ([it["image"]] if it.get("image") else [])
                    if imgs:
                        thumb = f"{slug}/{imgs[0]}"
                        break
            projs.append({
                "project": data.get("slug", d.name),
                "name": data.get("name"),
                "style": cfg.get("style"),
                "layout": cfg.get("layout"),
                "theme": cfg.get("theme"),
                "iterations": len(iterations),
                "thumbnail": thumb,
                "dir": str(d),
            })
    return projs


def _render_projects_home(projects: list) -> str:
    esc = html.escape
    cards = ""
    for p in projects:
        thumb = (
            f'<img src="{esc(p["thumbnail"])}" alt="">'
            if p.get("thumbnail") else '<div class="nothumb">no image yet</div>'
        )
        chips = ""
        for k in ("style", "layout"):
            v = p.get(k)
            if v:
                chips += f'<span class="chip"><b>{esc(k)}</b> {esc(str(v))}</span>'
        theme = esc((p.get("theme") or "")[:160])
        cards += f'''
        <a class="pcard" href="{esc(p["project"])}/index.html">
          <div class="pthumb">{thumb}</div>
          <div class="pbody">
            <h3>{esc(p.get("name") or p["project"])}</h3>
            <p class="ptheme">{theme}</p>
            <div class="chips">{chips}<span class="chip"><b>iterations</b> {p.get("iterations", 0)}</span></div>
          </div>
        </a>'''
    if not cards:
        cards = '<p class="empty">No projects yet. Create one to see it appear here.</p>'
    # The palette reference page lives under prompts/, a sibling of projects/ — outside the
    # static server's root. A file:// link doesn't work here: browsers block navigation from
    # an http(s) page to file:// as a security restriction, so it silently does nothing no
    # matter how correct the path is. _ensure_palette_symlink() below serves it through the
    # SAME static server instead via a plain relative link.
    palette_url = "_palette-reference.html" if _ensure_palette_symlink() else "#"
    return (
        _HOME_TEMPLATE
        .replace("{{CARDS}}", cards)
        .replace("{{COUNT}}", str(len(projects)))
        .replace("{{PALETTE_URL}}", esc(palette_url))
        .replace("{{GENERATED}}", esc(_now()))
    )


def _save_projects_home() -> None:
    """Rewrite the projects-home index.html + bump its state.json — but ONLY when the
    listing actually changed. This is called from every project's _save_project, so without
    this guard a burst of saves to ONE project would repeatedly bump the shared home page
    too, reloading anyone who happens to have it open — the 'aggressive reload / blinking'
    failure mode this file's other pages are careful to avoid."""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    projects = _list_projects_data()
    signature = json.dumps(projects, sort_keys=True)
    sig_path = PROJECTS_DIR / ".home-signature.json"
    if sig_path.exists() and sig_path.read_text() == signature:
        return
    sig_path.write_text(signature)
    version = _bump_state(PROJECTS_DIR)
    (PROJECTS_DIR / "index.html").write_text(
        _render_projects_home(projects).replace("{{VERSION}}", str(version)),
        encoding="utf-8",
    )


def _postcard_content_path(pdir: Path) -> Path:
    return pdir / "postcard-content.json"


def _empty_postcard_content() -> dict:
    return {
        "front_image": "", "back_image": "",
        "front_regions": [], "back_regions": [],
        "front_extra_html": "", "back_extra_html": "",
    }


def _load_postcard_content(pdir: Path) -> dict:
    """Load projects/<slug>/postcard-content.json — the source of truth for the postcard
    preview (front/back images + named, independently-editable text regions)."""
    p = _postcard_content_path(pdir)
    if not p.exists():
        return _empty_postcard_content()
    try:
        content = json.loads(p.read_text())
    except Exception:
        return _empty_postcard_content()
    content.setdefault("front_image", "")
    content.setdefault("back_image", "")
    content.setdefault("front_extra_html", "")
    content.setdefault("back_extra_html", "")
    content.setdefault("front_regions", [])
    content.setdefault("back_regions", [])
    return content


def _save_postcard_content(pdir: Path, content: dict) -> None:
    _postcard_content_path(pdir).write_text(json.dumps(content, indent=2, ensure_ascii=False))


def _save_postcard_region(slug: str, region_name: str, text: str) -> None:
    """Update one region's text (called from the browser's Enter-to-save) and re-render
    postcard.html + bump state.json so the open tab's poll loop reloads with the change."""
    pdir = PROJECTS_DIR / _slug(slug)
    if not (pdir / "project.json").exists():
        raise ValueError(f"No project '{slug}'")
    content = _load_postcard_content(pdir)
    found = False
    for side_key in ("front_regions", "back_regions"):
        for r in content.get(side_key, []):
            if r.get("name") == region_name:
                r["text"] = text
                found = True
    if not found:
        raise ValueError(f"Unknown region '{region_name}'")
    _save_postcard_content(pdir, content)
    data = _load_project(slug) or {}
    version = _bump_state(pdir)
    _save_postcard_html(pdir, data.get("name", slug), _slug(slug), version)


def _has_postcard(pdir: Path) -> bool:
    return _postcard_content_path(pdir).exists()


def _render_postcard_html(name: str, slug: str, version: int, content: dict) -> str:
    """Render postcard.html from postcard-content.json via the Jinja2 template: front + back
    pages, each a full-bleed image with named text regions (Markdown, rendered server-side)
    absolutely positioned on top, plus a labeled textarea per region so the designer can edit
    text directly in the browser."""
    def _side(label: str, image: str, regions: list, extra_html: str) -> dict:
        return {
            "label": label,
            "image": image,
            "extra_html": extra_html,
            "regions": [
                {
                    "name": r.get("name", ""),
                    "label": r.get("label", r.get("name", "")),
                    "style": r.get("style", ""),
                    "text": r.get("text", ""),
                    "rows": r.get("rows"),
                    "html": _render_markdown(r.get("text", "")),
                }
                for r in regions
            ],
        }

    return _JINJA_ENV.get_template("postcard.html.j2").render(
        name=name,
        slug=slug,
        version=version,
        sides=[
            _side("FRONT", content.get("front_image", ""), content.get("front_regions", []),
                  content.get("front_extra_html", "")),
            _side("BACK", content.get("back_image", ""), content.get("back_regions", []),
                  content.get("back_extra_html", "")),
        ],
    )


def _save_postcard_html(pdir: Path, name: str, slug: str, state_version: int) -> None:
    content = _load_postcard_content(pdir)
    (pdir / "postcard.html").write_text(
        _render_postcard_html(name, slug, state_version, content), encoding="utf-8"
    )


async def _generate_postcard_pdf_impl(name: str, out_path: str = "") -> dict:
    """Render postcard.html (front + back) to a print-ready, 2-page PDF. Each face is captured
    as a flattened raster at the true 6x4in trim size (headless Chromium via Playwright, so it
    matches the browser preview exactly), then extended by the standard 1/8in cutting bleed on
    every side (edge-replicated — see layouts/postcard-4x6.md) and rotated 90 degrees per the
    print vendor's submission requirement. Each page also gets real /TrimBox and /BleedBox
    metadata (not just bled pixels) — a preflight checker reads those boxes, not the artwork,
    to judge bleed; without them the whole bled page reads as the trim and the file looks
    bleed-free no matter how the art was drawn."""
    data = _load_project(name)
    if not data:
        return {"error": f"No project named '{name}'"}
    pdir_check = PROJECTS_DIR / data["slug"]
    content = _load_postcard_content(pdir_check)
    if not content.get("front_image") or not content.get("back_image"):
        return {"error": "Set front/back images first via set_postcard_sides."}

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {
            "error": "playwright not installed. Run: uv add playwright && uv run playwright install chromium"
        }
    import io
    import numpy as np
    from PIL import Image

    slug = data["slug"]
    port = _ensure_this_server_port()
    out = Path(out_path) if out_path else PROJECTS_DIR / slug / "postcard.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)

    bleed_px = round(_BLEED_IN * _PRINT_PPI)
    device_scale = _PRINT_PPI / 96  # CSS "in" is always 96px/in; this maps it to _PRINT_PPI

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            try:
                context = await browser.new_context(
                    viewport={"width": 900, "height": 1200},
                    device_scale_factor=device_scale,
                )
                page = await context.new_page()
                await page.goto(f"http://127.0.0.1:{port}/{slug}/postcard.html", wait_until="networkidle")
                # .page's border is an on-screen affordance (shows the page edge against the
                # dark preview background) — strip it here so the bleed pad extends the actual
                # art outward instead of smearing the border color into the print margin.
                await page.add_style_tag(content=".page{border:none !important;}")
                pages = []
                for side in ("front", "back"):
                    raw = await page.locator(f'.page[data-side="{side}"]').screenshot()
                    trimmed = np.array(Image.open(io.BytesIO(raw)).convert("RGB"))
                    bled = np.pad(trimmed, ((bleed_px, bleed_px), (bleed_px, bleed_px), (0, 0)), mode="edge")
                    pages.append(Image.fromarray(bled).rotate(-90, expand=True))
            finally:
                await browser.close()
    except Exception as e:
        return {"error": f"PDF generation failed: {e}"}

    pages[0].save(str(out), save_all=True, append_images=pages[1:], resolution=_PRINT_PPI)

    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import RectangleObject
    bleed_pt = _BLEED_IN * 72
    reader = PdfReader(str(out))
    writer = PdfWriter()
    for pdf_page in reader.pages:
        w, h = float(pdf_page.mediabox.width), float(pdf_page.mediabox.height)
        pdf_page.mediabox = RectangleObject((0, 0, w, h))
        pdf_page.bleedbox = RectangleObject((0, 0, w, h))
        pdf_page.trimbox = RectangleObject((bleed_pt, bleed_pt, w - bleed_pt, h - bleed_pt))
        writer.add_page(pdf_page)
    writer.write(str(out))

    return {
        "project": slug, "pdf": str(out), "pdf_rel": _rel_to_project(data, str(out)),
        "bleed_in": _BLEED_IN, "rotated_degrees": 90,
    }


# The port this very process is bound to (set in main() before serve_forever()). Playwright
# navigates to our own HTTP server to render postcard.html, so the PDF route needs it too.
_THIS_PORT: Optional[int] = None


def _ensure_this_server_port() -> int:
    assert _THIS_PORT is not None, "server not started yet"
    return _THIS_PORT


class _StaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # state.json is polled every ~1.5s per open tab — don't spam stderr with GETs

    def do_POST(self):
        """The write-capable routes on this otherwise GET-only static server:
        - /_home/refresh              {}                       (force a projects-home re-render)
        - /<slug>/project/save        {<full project.json>}    (persist + render index/postcard)
        - /<slug>/postcard-content/save {<full postcard-content.json>}  (persist + re-render)
        - /<slug>/postcard/save       {"region": ..., "text": ...}  (Enter-to-save in postcard.html)
        - /<slug>/iterations/delete   {"n": <int>}              (Delete button + confirm modal)
        - /<slug>/postcard/pdf        {}                        ("Generate PDF" button)
        """
        parts = [p for p in urllib.parse.urlparse(self.path).path.split("/") if p]
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = json.loads(self.rfile.read(length) or b"{}")

            if parts == ["_home", "refresh"]:
                _save_projects_home()
                result = {"ok": True}
            elif len(parts) == 3:
                slug, action = parts[0], tuple(parts[1:])
                if action == ("postcard", "save"):
                    _save_postcard_region(slug, str(body.get("region", "")), str(body.get("text", "")))
                    result = {"ok": True}
                elif action == ("iterations", "delete"):
                    _delete_iteration(slug, int(body.get("n")))
                    result = {"ok": True}
                elif action == ("postcard", "pdf"):
                    result = asyncio.run(_generate_postcard_pdf_impl(slug, str(body.get("out_path", ""))))
                    if "error" in result:
                        self._json_response(400, result)
                        return
                elif action == ("project", "save"):
                    _save_project(body)
                    result = {"ok": True, "state_version": body.get("state_version")}
                elif action == ("postcard-content", "save"):
                    pdir = PROJECTS_DIR / _slug(slug)
                    if not (pdir / "project.json").exists():
                        raise ValueError(f"No project '{slug}'")
                    _save_postcard_content(pdir, body)
                    data = _load_project(slug) or {}
                    _save_project(data)
                    result = {"ok": True}
                else:
                    self._json_response(404, {"error": "not found"})
                    return
            else:
                self._json_response(404, {"error": "not found"})
                return
        except ValueError as e:
            self._json_response(400, {"error": str(e)})
            return
        except Exception as e:
            self._json_response(400, {"error": f"bad request: {e}"})
            return
        self._json_response(200, result)

    def _json_response(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _write_state(port: int) -> None:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({"pid": os.getpid(), "port": port}))


def _cleanup_state(*_args) -> None:
    try:
        STATE_PATH.unlink(missing_ok=True)
    except Exception:
        pass
    sys.exit(0)


def main() -> None:
    global _THIS_PORT
    parser = argparse.ArgumentParser(description="League marketing static/postcard web server")
    parser.add_argument("--port", type=int, default=DEFAULT_STATIC_PORT)
    args = parser.parse_args()

    handler = functools.partial(_StaticHandler, directory=str(PROJECTS_DIR))
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
        port = args.port
    except OSError:
        port = _free_port()
        httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)

    _THIS_PORT = port
    _write_state(port)
    signal.signal(signal.SIGTERM, _cleanup_state)
    print(f"webserver: serving {PROJECTS_DIR} on http://127.0.0.1:{port}/ (pid {os.getpid()})", flush=True)
    try:
        httpd.serve_forever()
    finally:
        _cleanup_state()


# ── HTML gallery template (auto-reloads via state.json polling) ─────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{NAME}} — League Image Project</title>
<style>
 :root{--ink:#141414;--paper:#f7f4ec;--accent:#d4202a;--blue:#173a6e;--chip:#eee7d6;}
 *{box-sizing:border-box;}
 body{margin:0;background:#101317;color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;}
 .wrap{max-width:1100px;margin:0 auto;padding:24px;}
 header.top{background:var(--paper);border:3px solid var(--ink);border-radius:10px;padding:20px 24px;box-shadow:0 8px 30px rgba(0,0,0,.4);}
 h1{margin:0 0 6px;font-size:28px;}
 .theme{font-size:17px;color:#333;margin:0 0 10px;}
 .scene{font-size:14px;color:#555;margin:0 0 12px;font-style:italic;}
 .chips{display:flex;flex-wrap:wrap;gap:8px;}
 .chip{background:var(--chip);border:1px solid #cbb;border-radius:20px;padding:3px 12px;font-size:12px;}
 .chip b{color:var(--blue);text-transform:uppercase;font-size:10px;letter-spacing:.5px;margin-right:4px;}
 h2{color:#f7f4ec;font-size:15px;text-transform:uppercase;letter-spacing:1px;margin:24px 4px 10px;}
 .thumbs{display:flex;flex-wrap:wrap;gap:10px;}
 .thumbs img{height:90px;border:2px solid var(--ink);border-radius:6px;background:#fff;object-fit:cover;}
 .thumbs.small img{height:56px;}
 .card{background:var(--paper);border:3px solid var(--ink);border-radius:10px;padding:16px;margin:16px 0;box-shadow:0 6px 20px rgba(0,0,0,.35);}
 .card.err{border-color:var(--accent);}
 .cardhead{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin-bottom:12px;}
 .num{font-weight:800;font-size:20px;color:var(--accent);}
 .lab{font-weight:600;}
 .meta{margin-left:auto;font-size:12px;color:#777;}
 .badge.err{background:var(--accent);color:#fff;border-radius:4px;padding:1px 7px;font-size:11px;}
 .imgwrap{text-align:center;}
 img.hero{max-width:100%;max-height:70vh;border:2px solid var(--ink);border-radius:6px;background:#fff;}
 .noimg{padding:30px;color:var(--accent);font-weight:600;text-align:center;border:2px dashed var(--accent);border-radius:6px;}
 .reflabel,.dl{font-size:10px;text-transform:uppercase;letter-spacing:.6px;color:var(--blue);margin:12px 0 4px;font-weight:700;}
 details{margin-top:12px;}
 summary{cursor:pointer;font-size:13px;color:var(--blue);font-weight:600;}
 pre{white-space:pre-wrap;word-wrap:break-word;background:#fbfaf5;border:1px solid #ddd;border-radius:6px;padding:10px;font-size:12px;line-height:1.5;max-height:340px;overflow:auto;}
 pre.err{border-color:var(--accent);color:#a01;}
 .empty{color:#889;text-align:center;padding:40px;}
 footer{color:#667;font-size:11px;text-align:center;padding:20px;}
 .live{position:fixed;top:10px;right:12px;background:#1a1;color:#fff;font-size:11px;padding:3px 9px;border-radius:12px;opacity:.85;z-index:10;}
 .live.off{background:#555;}
 .allprojects{display:inline-block;font-size:12px;color:#9db4d8;text-decoration:none;font-weight:700;margin-bottom:10px;}
 .allprojects:hover{text-decoration:underline;}
 a.postcardlink{color:#f7f4ec;background:var(--blue);display:inline-block;margin:14px 4px;padding:6px 14px;border-radius:20px;font-size:13px;font-weight:700;text-decoration:none;}
 a.postcardlink:hover{opacity:.85;}
 .delbtn{margin-left:auto;background:none;border:1px solid var(--accent);color:var(--accent);border-radius:6px;padding:3px 10px;font-size:11px;font-weight:700;cursor:pointer;}
 .delbtn:hover{background:var(--accent);color:#fff;}
 .cardhead .meta{margin-left:0;}
 .modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:100;align-items:center;justify-content:center;}
 .modal-overlay.open{display:flex;}
 .modal-box{background:var(--paper);border-radius:10px;padding:24px 28px;max-width:380px;box-shadow:0 12px 40px rgba(0,0,0,.5);}
 .modal-box h3{margin:0 0 10px;font-size:17px;color:var(--accent);}
 .modal-box p{margin:0 0 20px;font-size:14px;line-height:1.5;color:#333;}
 .modal-actions{display:flex;gap:10px;justify-content:flex-end;}
 .modal-actions button{border-radius:6px;padding:8px 16px;font-size:13px;font-weight:700;cursor:pointer;border:1px solid #ccc;background:#fff;}
 .modal-actions button.confirm{background:var(--accent);border-color:var(--accent);color:#fff;}
 .modal-actions button.confirm:disabled{opacity:.6;cursor:default;}
 .modal-error{color:var(--accent);font-size:12px;margin-top:10px;}
</style>
</head>
<body>
<div class="live" id="live">&#9679; live</div>
<div class="wrap">
  <a class="allprojects" href="../">&larr; All projects</a>
  <header class="top">
    <h1>{{NAME}}</h1>
    <p class="theme">{{THEME}}</p>
    <p class="scene">{{SCENE}}</p>
    <div class="chips">{{CHIPS}}</div>
  </header>
  {{SOURCES}}
  {{POSTCARD_LINK}}
  <h2>Iterations</h2>
  {{CARDS}}
  <footer>Generated {{GENERATED}} &middot; this page auto-reloads when a new iteration is added</footer>
</div>
<div class="modal-overlay" id="delModal">
  <div class="modal-box">
    <h3>Delete this iteration?</h3>
    <p>Delete <strong id="delModalLabel"></strong>? This removes its image file(s) permanently and cannot be undone.</p>
    <div class="modal-actions">
      <button id="delModalCancel">Cancel</button>
      <button class="confirm" id="delModalConfirm">Delete</button>
    </div>
    <div class="modal-error" id="delModalError"></div>
  </div>
</div>
<script>
 const CURRENT_VERSION = {{VERSION}};
 const SLUG = "{{SLUG}}";
 const live = document.getElementById('live');
 // Only ever reload when state.json confirms a NEW version. We never blind-reload on a
 // timer: under file:// (fetch blocked) or with the server down we can't read the version,
 // so reloading would just flicker the page without knowing anything changed. In that case
 // show a hint and keep quietly retrying — a live server will be picked up automatically.
 async function poll(){
   let served = true;
   try{
     const r = await fetch('state.json?ts=' + Date.now(), {cache:'no-store'});
     if(r.ok){
       const s = await r.json();
       if(s.version > CURRENT_VERSION){ location.reload(); return; }
     }else{
       served = false;
     }
   }catch(e){
     served = false;
   }
   if(served){
     live.className='live'; live.innerHTML='&#9679; live';
     setTimeout(poll, 1500);
   }else{
     // No live server (e.g. opened via file://). Stop flickering; just retry slowly.
     live.className='live off'; live.innerHTML='&#9679; open via server for live reload';
     setTimeout(poll, 4000);
   }
 }
 poll();

 // Delete button + confirm modal. A destructive, irreversible action (removes the image
 // file(s) too) — always requires an explicit confirm click, never just the initial button.
 const modal = document.getElementById('delModal');
 const modalLabel = document.getElementById('delModalLabel');
 const modalConfirm = document.getElementById('delModalConfirm');
 const modalCancel = document.getElementById('delModalCancel');
 const modalError = document.getElementById('delModalError');
 let pendingN = null;

 function closeModal(){
   modal.classList.remove('open');
   pendingN = null;
   modalError.textContent = '';
   modalConfirm.disabled = false;
   modalConfirm.textContent = 'Delete';
 }

 document.querySelectorAll('.delbtn').forEach(btn => {
   btn.addEventListener('click', () => {
     pendingN = btn.dataset.n;
     modalLabel.textContent = '#' + pendingN + ' — ' + btn.dataset.label;
     modalError.textContent = '';
     modal.classList.add('open');
   });
 });
 modalCancel.addEventListener('click', closeModal);
 modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });

 modalConfirm.addEventListener('click', async () => {
   if (pendingN === null) return;
   modalConfirm.disabled = true;
   modalConfirm.textContent = 'Deleting…';
   try {
     const res = await fetch(`/${SLUG}/iterations/delete`, {
       method: 'POST',
       headers: {'Content-Type': 'application/json'},
       body: JSON.stringify({n: parseInt(pendingN, 10)})
     });
     const body = await res.json();
     if (!res.ok) throw new Error(body.error || res.statusText);
     location.reload();
   } catch (err) {
     modalError.textContent = 'Delete failed: ' + err.message;
     modalConfirm.disabled = false;
     modalConfirm.textContent = 'Delete';
   }
 });
</script>
</body>
</html>
"""


# ── Projects-home HTML template (lists every project, links to its gallery) ────────────

_HOME_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>League Image Projects</title>
<style>
 :root{--ink:#141414;--paper:#f7f4ec;--accent:#d4202a;--blue:#173a6e;--chip:#eee7d6;}
 *{box-sizing:border-box;}
 body{margin:0;background:#101317;color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;}
 .wrap{max-width:1100px;margin:0 auto;padding:24px;}
 header.top{background:var(--paper);border:3px solid var(--ink);border-radius:10px;padding:20px 24px;box-shadow:0 8px 30px rgba(0,0,0,.4);margin-bottom:20px;}
 .headrow{display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap;}
 h1{margin:0 0 6px;font-size:28px;}
 .sub{font-size:14px;color:#555;margin:0;}
 a.palettelink{color:#f7f4ec;background:var(--blue);display:inline-block;padding:6px 14px;border-radius:20px;font-size:13px;font-weight:700;text-decoration:none;white-space:nowrap;}
 a.palettelink:hover{opacity:.85;}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px;}
 .pcard{background:var(--paper);border:3px solid var(--ink);border-radius:10px;overflow:hidden;box-shadow:0 6px 20px rgba(0,0,0,.35);text-decoration:none;color:var(--ink);display:flex;flex-direction:column;transition:transform .1s;}
 .pcard:hover{transform:translateY(-2px);}
 .pthumb{height:150px;background:#e8e4d8;display:flex;align-items:center;justify-content:center;overflow:hidden;}
 .pthumb img{width:100%;height:100%;object-fit:cover;display:block;}
 .nothumb{color:#999;font-size:12px;font-style:italic;}
 .pbody{padding:12px 14px;}
 .pbody h3{margin:0 0 6px;font-size:16px;}
 .ptheme{font-size:12px;color:#555;margin:0 0 10px;line-height:1.4;}
 .chips{display:flex;flex-wrap:wrap;gap:6px;}
 .chip{background:var(--chip);border:1px solid #cbb;border-radius:20px;padding:3px 10px;font-size:11px;}
 .chip b{color:var(--blue);text-transform:uppercase;font-size:9px;letter-spacing:.5px;margin-right:4px;}
 .empty{color:#889;text-align:center;padding:60px;}
 footer{color:#667;font-size:11px;text-align:center;padding:20px;}
 .live{position:fixed;top:10px;right:12px;background:#1a1;color:#fff;font-size:11px;padding:3px 9px;border-radius:12px;opacity:.85;z-index:10;}
 .live.off{background:#555;}
</style>
</head>
<body>
<div class="live" id="live">&#9679; live</div>
<div class="wrap">
  <header class="top">
    <div class="headrow">
      <h1>League Image Projects</h1>
      <a class="palettelink" href="{{PALETTE_URL}}" target="_blank">&#127912; Palette reference &rarr;</a>
    </div>
    <p class="sub">{{COUNT}} project(s) &middot; click a card to open its gallery</p>
  </header>
  <div class="grid">{{CARDS}}</div>
  <footer>Generated {{GENERATED}} &middot; this page auto-reloads when a project changes</footer>
</div>
<script>
 const CURRENT_VERSION = {{VERSION}};
 const live = document.getElementById('live');
 async function poll(){
   let served = true;
   try{
     const r = await fetch('state.json?ts=' + Date.now(), {cache:'no-store'});
     if(r.ok){
       const s = await r.json();
       if(s.version > CURRENT_VERSION){ location.reload(); return; }
     }else{
       served = false;
     }
   }catch(e){
     served = false;
   }
   if(served){
     live.className='live'; live.innerHTML='&#9679; live';
     setTimeout(poll, 1500);
   }else{
     live.className='live off'; live.innerHTML='&#9679; open via server for live reload';
     setTimeout(poll, 4000);
   }
 }
 poll();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
League Marketing Image Generator — MCP Server

Tools for generating marketing images via OpenRouter image models and evaluating them.
Uses FastMCP for modern MCP protocol support.
"""

import base64
import html
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

# ── Configuration ──────────────────────────────────────────────────────────

# Project root = the directory containing this mcp-server/ folder. Derived from the
# file location so the server keeps working no matter where the project is moved.
MARKETING_DIR = Path(__file__).resolve().parent.parent

# Load secrets/config from the project .env so the server works regardless of
# how it is launched (e.g. spawned by an MCP client with a bare environment).
try:
    from dotenv import load_dotenv
    load_dotenv(MARKETING_DIR / ".env")
except ImportError:
    pass

PROMPTS_DIR = MARKETING_DIR / "prompts"
STYLES_DIR = PROMPTS_DIR / "styles"
COMPOSITIONS_DIR = PROMPTS_DIR / "compositions"
PALETTES_DIR = PROMPTS_DIR / "palettes"
LAYOUTS_DIR = MARKETING_DIR / "layouts"
RUBRICS_DIR = MARKETING_DIR / "rubrics"
OUTPUT_DIR = MARKETING_DIR / "output"
PROJECTS_DIR = MARKETING_DIR / "projects"

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "") or os.environ.get("OPENROUTER_API", "")
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

DEFAULT_IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "") or "openai/gpt-5.4-image-2"
DEFAULT_IMAGE_PROVIDER = os.environ.get("IMAGE_PROVIDER", "openai")  # "openai" or "openrouter"
EVALUATION_MODEL = "google/gemini-2.5-flash"

STYLES = ["pop-art", "comic-book", "manga", "dragon-ball-z", "technical-blueprint", "8bit-video-game", "graphic-novel"]
LAYOUTS = ["postcard-4x6", "business-card", "individual-cut-images", "individual-panels", "full-page-flyer"]

# Layout → image size (width x height for portrait orientation)
LAYOUT_SIZES = {
    "postcard-4x6": "1024x1536",         # 2:3 portrait postcard
    "business-card": "1024x576",          # ~7:4 landscape
    "individual-cut-images": "1024x1024", # square assets
    "individual-panels": "1024x1024",     # square default
    "full-page-flyer": "1024x1536",       # ~2:3 portrait flyer
}

# ── FastMCP Server ────────────────────────────────────────────────────────

mcp = FastMCP("League Image Generator")


# ── Prompt Assembly Logic ─────────────────────────────────────────────────

def load_prompt_file(category: str, name: str, file: str) -> str:
    """Load a prompt component file."""
    if category == "style":
        path = STYLES_DIR / name / file
    elif category == "composition":
        path = COMPOSITIONS_DIR / file
    elif category == "palette":
        path = PALETTES_DIR / file
    elif category == "layout":
        path = LAYOUTS_DIR / file
    else:
        return ""
    if not path.exists():
        return ""
    return path.read_text()


def _strip_heading(text: str) -> str:
    """Drop a leading top-level markdown title (e.g. '# Pop Art — Style') so the
    concatenated components read as one prompt rather than a stack of titles."""
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def list_compositions() -> list:
    """Return available composition names (markdown file stems)."""
    if not COMPOSITIONS_DIR.exists():
        return []
    return sorted(p.stem for p in COMPOSITIONS_DIR.glob("*.md"))


def list_palettes() -> list:
    """Return available color-palette names (markdown file stems)."""
    if not PALETTES_DIR.exists():
        return []
    return sorted(p.stem for p in PALETTES_DIR.glob("*.md"))


# ── MCP Tools ──────────────────────────────────────────────────────────────

@mcp.tool()
def list_available() -> str:
    """List all available styles, compositions, and layouts (and which style files exist)."""
    result = {"styles": {}, "compositions": list_compositions(),
              "palettes": list_palettes(), "layouts": LAYOUTS}
    for style in STYLES:
        files = {}
        for f in ["positive.md", "negative.md"]:
            p = STYLES_DIR / style / f
            files[f.replace(".md", "")] = "present" if p.exists() else "missing"
        result["styles"][style] = files
    return json.dumps(result, indent=2)


@mcp.tool()
def assemble_prompt(
    style: str,
    layout: Optional[str] = None,
    composition: Optional[str] = None,
    palette: Optional[str] = None,
    scene_description: str = "",
    custom_additions: str = "",
) -> str:
    """
    Assemble a complete image generation prompt from style, palette, layout, and composition components.

    Args:
        style: Art style (pop-art, comic-book, manga, dragon-ball-z, technical-blueprint, 8bit-video-game)
        layout: Layout format (postcard-4x6, business-card, individual-cut-images, individual-panels, full-page-flyer)
        composition: Specific composition type (extreme-close-up, arena-action, vintage-cover, etc.)
        palette: Color palette (a file stem under prompts/palettes/, e.g. "orange-blue")
        scene_description: What should be depicted in the image
        custom_additions: Any extra prompt text to append
    """
    if style not in STYLES:
        return json.dumps({"error": f"Unknown style '{style}'. Available: {STYLES}"})

    # Positive prompt = full style component + full composition component + scene +
    # layout + custom additions, concatenated as-is from the markdown files.
    positive = _strip_heading(load_prompt_file("style", style, "positive.md"))
    negative_prompt_str = _strip_heading(load_prompt_file("style", style, "negative.md"))

    parts = []
    if positive:
        parts.append(f"# Art Style\n\n{positive}")

    if palette:
        palette_md = _strip_heading(load_prompt_file("palette", "", f"{palette}.md"))
        parts.append(f"# Color Palette\n\n{palette_md or palette}")

    if composition:
        comp_md = _strip_heading(load_prompt_file("composition", "", f"{composition}.md"))
        parts.append(f"# Composition\n\n{comp_md or composition}")

    if scene_description:
        parts.append(f"# Scene\n\n{scene_description}")

    if layout:
        layout_filename = f"{layout}.md" if not layout.endswith(".md") else layout
        layout_text = load_prompt_file("layout", "", layout_filename)
        if layout_text:
            if "## Prompt Addition" in layout_text:
                layout_text = layout_text.split("## Prompt Addition")[1].strip()
            else:
                layout_text = _strip_heading(layout_text)
            parts.append(f"# Layout\n\n{layout_text}")

    if custom_additions:
        parts.append(f"# Additional Direction\n\n{custom_additions}")

    positive_prompt = "\n\n".join(parts)

    return json.dumps({
        "positive_prompt": positive_prompt,
        "negative_prompt": negative_prompt_str,
        "style": style,
        "layout": layout,
        "composition": composition,
        "palette": palette,
    }, indent=2)


@mcp.tool()
async def generate_image(
    style: str,
    layout: Optional[str] = None,
    composition: Optional[str] = None,
    palette: Optional[str] = None,
    scene_description: str = "",
    prompt: str = "",
    negative_prompt: str = "",
    model: str = DEFAULT_IMAGE_MODEL,
    reference_images: Optional[list[str]] = None,
    output_filename: str = "generated",
) -> str:
    """
    Generate an image using OpenRouter's image generation models.

    If no explicit prompt is provided, assembles one from style + layout + composition + scene.
    Saves generated images to the output/ directory.

    Args:
        style: Art style (pop-art, comic-book, manga, dragon-ball-z, technical-blueprint, 8bit-video-game)
        layout: Layout format (optional)
        composition: Composition type (optional)
        scene_description: Description of the scene/subject
        prompt: Explicit prompt (overrides assembled prompt)
        negative_prompt: Things to avoid in the image
        model: OpenRouter image model ID (default: google/gemini-3-pro-image)
        reference_images: Paths to reference images for image-to-image generation
        output_filename: Base filename for the output (without extension)
    """
    # Assemble prompt if not provided
    if not prompt and style:
        assembled = json.loads(assemble_prompt(
            style=style,
            layout=layout,
            composition=composition,
            palette=palette,
            scene_description=scene_description,
        ))
        if "error" in assembled:
            return json.dumps(assembled)
        prompt = assembled["positive_prompt"]
        if not negative_prompt:
            negative_prompt = assembled.get("negative_prompt", "")

    if not prompt:
        return json.dumps({"error": "No prompt provided or assembled"})

    # Combine with negative prompt
    full_text = prompt
    if negative_prompt:
        full_text += f"\n\nIMPORTANT — Do NOT include any of these: {negative_prompt}"

    # ── Generate (routes to OpenAI or OpenRouter) and save into output/ ──
    size = LAYOUT_SIZES.get(layout, "1024x1024")
    result = await _run_generation(
        full_text, model, reference_images, OUTPUT_DIR, output_filename, size,
    )
    return json.dumps(result, indent=2)


async def _run_generation(full_text, model, reference_images, out_dir, base_name, size="1024x1024"):
    """Route to OpenAI or OpenRouter, save resulting images into ``out_dir`` using
    ``base_name`` as the filename stem, and return a result dict (not a JSON string).

    Shared by the ``generate_image`` tool (saves to output/) and the project tools
    (save into a project's iterations/ directory)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # The OpenAI images API can't take image inputs, so it's only usable when there are
    # no reference images and the provider is explicitly OpenAI.
    if DEFAULT_IMAGE_PROVIDER == "openai" and not reference_images:
        return await _generate_openai_core(full_text, model, out_dir, base_name, size)

    if not OPENROUTER_API_KEY:
        return {"error": "OPENROUTER_API_KEY environment variable not set"}

    content = []
    if reference_images:
        for img_path in reference_images:
            if os.path.exists(img_path):
                with open(img_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()
                ext = os.path.splitext(img_path)[1].lower()
                mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                           ".webp": "image/webp", ".heic": "image/heic"}
                mime = mime_map.get(ext, "image/png")
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{img_b64}"}
                })
    content.append({"type": "text", "text": full_text})

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://league.ai",
        "X-Title": "League Marketing Image Generator",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 4096,
    }

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{OPENROUTER_BASE}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        return {"error": str(e)}

    result = {
        "model": data.get("model", model),
        "provider": "openrouter",
        "usage": data.get("usage", {}),
        "text_response": "",
        "images": [],
        "saved_paths": [],
    }

    if "choices" in data and len(data["choices"]) > 0:
        message = data["choices"][0].get("message", {})
        msg_content = message.get("content", "")

        if isinstance(msg_content, str):
            result["text_response"] = msg_content
        elif isinstance(msg_content, list):
            for item in msg_content:
                if item.get("type") == "text":
                    result["text_response"] += item.get("text", "")
                elif item.get("type") == "image_url":
                    result["images"].append(item["image_url"]["url"])
                elif item.get("type") == "image":
                    img_data = item.get("data", "")
                    mime = item.get("mime_type", "image/png")
                    result["images"].append(f"data:{mime};base64,{img_data}")

        # Gemini models return images in message.images (separate from content)
        msg_images = message.get("images", [])
        if isinstance(msg_images, list):
            for img in msg_images:
                if isinstance(img, dict) and "image_url" in img:
                    result["images"].append(img["image_url"]["url"])

    for i, img_url in enumerate(result["images"]):
        try:
            if img_url.startswith("data:"):
                header, encoded = img_url.split(",", 1)
                mime = header.split(":")[1].split(";")[0]
                ext = mime.split("/")[1] if "/" in mime else "png"
                img_data = base64.b64decode(encoded)
            elif img_url.startswith("http"):
                import urllib.request
                with urllib.request.urlopen(img_url, timeout=60) as resp:
                    img_data = resp.read()
                    content_type = resp.headers.get("content-type", "image/png")
                    ext = content_type.split("/")[1] if "/" in content_type else "png"
            else:
                continue

            name = base_name if len(result["images"]) == 1 else f"{base_name}_{i}"
            filepath = out_dir / f"{name}.{ext}"
            filepath.write_bytes(img_data)
            result["saved_paths"].append(str(filepath))
        except Exception as e:
            result["saved_paths"].append(f"Error saving image {i}: {e}")

    return result


async def _generate_openai_core(full_text, model, out_dir, base_name, size="1024x1024"):
    """Generate an image via OpenAI's images API, saving into ``out_dir``. Returns a dict."""
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        return {"error": "OPENAI_API_KEY not set for OpenAI image generation"}

    headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
    payload = {"model": model, "prompt": full_text[:4000], "n": 1, "size": size}

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/images/generations",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        return {"error": str(e)}

    if "error" in data:
        return {"error": data["error"]}

    result = {"model": model, "provider": "openai", "images": [], "saved_paths": []}
    out_dir = Path(out_dir)
    for i, img in enumerate(data.get("data", [])):
        if "b64_json" in img:
            raw = base64.b64decode(img["b64_json"])
        elif "url" in img:
            import urllib.request
            with urllib.request.urlopen(img["url"], timeout=60) as resp:
                raw = resp.read()
        else:
            continue

        suffix = f"_{i}" if len(data["data"]) > 1 else ""
        filepath = out_dir / f"{base_name}{suffix}.png"
        filepath.write_bytes(raw)
        result["saved_paths"].append(str(filepath))
        result["images"].append(str(filepath))

    return result


@mcp.tool()
async def evaluate_image(
    image_path: str,
    style: str,
    layout: Optional[str] = None,
    rubric_path: str = "",
) -> str:
    """
    Evaluate a generated image against a quality rubric using a vision model.

    Args:
        image_path: Path to the generated image file
        style: Art style to evaluate against (loads the appropriate rubric)
        layout: Layout format for additional context
        rubric_path: Path to a specific rubric file (overrides style default)
    """
    if not OPENROUTER_API_KEY:
        return json.dumps({"error": "OPENROUTER_API_KEY not set."})

    # Read the image
    if not os.path.exists(image_path):
        return json.dumps({"error": f"Image not found: {image_path}"})

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    ext = os.path.splitext(image_path)[1].lower()
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
    mime = mime_map.get(ext, "image/png")

    # Load rubric
    rubric_text = ""
    if rubric_path and os.path.exists(rubric_path):
        rubric_text = Path(rubric_path).read_text()
    elif style:
        style_rubric = RUBRICS_DIR / f"{style}.md"
        if style_rubric.exists():
            rubric_text = style_rubric.read_text()
        layout_rubric = RUBRICS_DIR / "layouts.md"
        if layout_rubric.exists():
            rubric_text += "\n\n" + layout_rubric.read_text()

    if not rubric_text:
        return json.dumps({"error": f"No rubric found for style '{style}'"})

    eval_prompt = f"""You are an expert image evaluator for a youth programming nonprofit's marketing materials.

Evaluate the attached image against this quality rubric:

{rubric_text}

ADDITIONAL CONTEXT:
- Style: {style}
- Layout: {layout or 'not specified'}

Provide your evaluation as structured JSON with these fields:
{{
  "style_fidelity": {{"score": 1-10, "justification": "..."}},
  "composition": {{"score": 1-10, "justification": "..."}},
  "technical_quality": {{"score": 1-10, "justification": "..."}},
  "content_accuracy": {{"score": 1-10, "justification": "..."}},
  "overall_score": 1-10,
  "top_3_strengths": ["...", "...", "..."],
  "top_3_issues": ["...", "...", "..."],
  "verdict": "PASS" | "REVISE" | "FAIL",
  "verdict_reason": "..."
}}

Output ONLY valid JSON, no other text."""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://league.ai",
        "X-Title": "League Image Evaluator",
    }

    payload = {
        "model": EVALUATION_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": eval_prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}}
            ]
        }],
        "max_tokens": 2048,
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{OPENROUTER_BASE}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        return json.dumps({"error": str(e)})

    evaluation_text = ""
    if "choices" in data:
        evaluation_text = data["choices"][0]["message"]["content"]

    # Try to parse as JSON, otherwise return raw
    try:
        parsed = json.loads(evaluation_text)
        parsed["image_path"] = image_path
        parsed["rubric_style"] = style
        parsed["model_used"] = data.get("model", EVALUATION_MODEL)
        return json.dumps(parsed, indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        return json.dumps({
            "image_path": image_path,
            "rubric_style": style,
            "evaluation": evaluation_text,
            "model_used": data.get("model", EVALUATION_MODEL),
        }, indent=2, ensure_ascii=False)


# ── Projects ─────────────────────────────────────────────────────────────
#
# A "project" is a directory under projects/<slug>/ holding everything for one
# marketing image job: a project.json config (style / composition / layout / theme /
# scene + source images), the generated iterations/, and an auto-reloading index.html
# gallery the user watches in a browser while iterating over chat.
#
#   projects/<slug>/
#     project.json        # config + iteration history (source of truth)
#     state.json          # {"version": N} — bumped on every write for live reload
#     index.html          # gallery, regenerated on every write
#     sources/            # copied source/reference images
#     iterations/         # iter-001.png, iter-002.png, …

import atexit

_SERVERS: dict = {}  # slug -> (subprocess.Popen, port) for open_project static servers


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


def _copy_sources(pdir: Path, source_images) -> list:
    """Copy source images into <pdir>/sources/, returning project-relative posix paths."""
    rel = []
    sdir = Path(pdir) / "sources"
    sdir.mkdir(parents=True, exist_ok=True)
    for src in source_images or []:
        sp = Path(str(src)).expanduser()
        if not sp.exists():
            continue
        dest = sdir / sp.name
        i = 1
        while dest.exists() and dest.resolve() != sp.resolve():
            dest = sdir / f"{sp.stem}-{i}{sp.suffix}"
            i += 1
        try:
            if dest.resolve() != sp.resolve():
                shutil.copy2(sp, dest)
        except Exception:
            continue
        rel.append(f"sources/{dest.name}")
    return rel


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


def _save_project(data: dict) -> None:
    """Persist project.json, bump state.json (triggers browser reload), rewrite index.html."""
    pdir = PROJECTS_DIR / data["slug"]
    pdir.mkdir(parents=True, exist_ok=True)
    data["state_version"] = int(data.get("state_version", 0)) + 1
    (pdir / "project.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
    (pdir / "state.json").write_text(json.dumps({"version": data["state_version"]}))
    (pdir / "index.html").write_text(_render_project_html(data), encoding="utf-8")


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

    return f'''
    <article class="card {err_cls}">
      <div class="cardhead">
        <span class="num">#{n}</span>{lab}{badge}
        <span class="meta">{created} &middot; {model}</span>
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
    for k in ("style", "composition", "layout", "model"):
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

    return (
        _HTML_TEMPLATE
        .replace("{{NAME}}", esc(data.get("name", "")))
        .replace("{{VERSION}}", str(int(data.get("state_version", 0))))
        .replace("{{CHIPS}}", chips)
        .replace("{{THEME}}", esc(cfg.get("theme", "") or ""))
        .replace("{{SCENE}}", esc(cfg.get("scene_description", "") or ""))
        .replace("{{SOURCES}}", src_block)
        .replace("{{CARDS}}", cards)
        .replace("{{GENERATED}}", esc(_now()))
    )


@mcp.tool()
def create_project(
    name: str,
    style: str = "",
    composition: str = "",
    layout: str = "",
    theme: str = "",
    scene_description: str = "",
    model: str = "",
    negative_prompt: str = "",
    custom_additions: str = "",
    source_images: Optional[list] = None,
) -> str:
    """Create a new image project: a directory that collects the config, source images,
    generated iterations, and an auto-reloading HTML gallery for one marketing image job.

    Args:
        name: Human-readable project name (also slugified for the directory).
        style: Default art style for this project (one of the 6 styles).
        composition: Default composition name (a file stem under prompts/compositions/).
        layout: Default layout (postcard-4x6, business-card, …).
        theme: One-line description of the project's gist/theme.
        scene_description: Default scene to depict.
        model: Default image model (falls back to the server default).
        negative_prompt: Optional negative-prompt override (else derived from the style).
        custom_additions: Extra prompt text appended by default.
        source_images: Paths to source/reference images (copied into the project).
    """
    slug = _slug(name)
    if not slug:
        return json.dumps({"error": "Invalid project name"})
    if style and style not in STYLES:
        return json.dumps({"error": f"Unknown style '{style}'. Available: {STYLES}"})
    pdir = PROJECTS_DIR / slug
    if (pdir / "project.json").exists():
        return json.dumps({"error": f"Project '{slug}' already exists. Use update_project or a new name."})

    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "iterations").mkdir(exist_ok=True)
    sources = _copy_sources(pdir, source_images)

    data = {
        "name": name,
        "slug": slug,
        "created": _now(),
        "config": {
            "style": style,
            "composition": composition,
            "layout": layout,
            "theme": theme,
            "scene_description": scene_description,
            "model": model or DEFAULT_IMAGE_MODEL,
            "negative_prompt": negative_prompt,
            "custom_additions": custom_additions,
        },
        "sources": sources,
        "iterations": [],
        "state_version": 0,
    }
    _save_project(data)
    return json.dumps({
        "project": slug,
        "dir": str(pdir),
        "html": str(pdir / "index.html"),
        "config": data["config"],
        "sources": sources,
        "next": "Call open_project to view it, then generate_project_image to iterate.",
    }, indent=2)


@mcp.tool()
def list_projects() -> str:
    """List all image projects with their style and iteration count."""
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
            projs.append({
                "project": data.get("slug", d.name),
                "name": data.get("name"),
                "style": data.get("config", {}).get("style"),
                "iterations": len(data.get("iterations", [])),
                "dir": str(d),
            })
    return json.dumps({"projects": projs}, indent=2)


@mcp.tool()
def get_project(name: str) -> str:
    """Return the full project.json (config + iteration history) for a project."""
    data = _load_project(name)
    if not data:
        return json.dumps({"error": f"No project named '{name}'"})
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
def update_project(
    name: str,
    style: Optional[str] = None,
    composition: Optional[str] = None,
    layout: Optional[str] = None,
    theme: Optional[str] = None,
    scene_description: Optional[str] = None,
    model: Optional[str] = None,
    negative_prompt: Optional[str] = None,
    custom_additions: Optional[str] = None,
    add_sources: Optional[list] = None,
) -> str:
    """Update a project's default config (any subset of fields) and/or add source images.
    Only non-null fields are changed. Rewrites the gallery HTML."""
    data = _load_project(name)
    if not data:
        return json.dumps({"error": f"No project named '{name}'"})
    if style is not None and style and style not in STYLES:
        return json.dumps({"error": f"Unknown style '{style}'. Available: {STYLES}"})
    cfg = data["config"]
    for key, val in (
        ("style", style), ("composition", composition), ("layout", layout),
        ("theme", theme), ("scene_description", scene_description), ("model", model),
        ("negative_prompt", negative_prompt), ("custom_additions", custom_additions),
    ):
        if val is not None:
            cfg[key] = val
    if add_sources:
        data.setdefault("sources", []).extend(_copy_sources(PROJECTS_DIR / data["slug"], add_sources))
    _save_project(data)
    return json.dumps({"project": data["slug"], "config": cfg, "sources": data["sources"]}, indent=2)


@mcp.tool()
async def generate_project_image(
    name: str,
    scene_description: str = "",
    custom_additions: str = "",
    prompt: str = "",
    negative_prompt: str = "",
    model: str = "",
    style: str = "",
    composition: str = "",
    layout: str = "",
    reference_images: Optional[list] = None,
    use_sources: bool = True,
    label: str = "",
    notes: str = "",
) -> str:
    """Generate the next image iteration for a project and record it in the gallery.

    The prompt is assembled from the project's config (style + composition + layout +
    scene), with any argument here overriding the stored default for this one call.
    Pass an explicit ``prompt`` to bypass assembly entirely (e.g. a hand-edited prompt).
    The project's source images are sent as references by default (use_sources=True).

    On completion the image is saved to iterations/iter-NNN.png, appended to project.json,
    and the HTML gallery is regenerated — any open browser tab auto-reloads.
    """
    data = _load_project(name)
    if not data:
        return json.dumps({"error": f"No project named '{name}'"})
    cfg = data["config"]

    eff_style = style or cfg.get("style", "")
    eff_comp = composition or cfg.get("composition", "")
    eff_layout = layout or cfg.get("layout", "")
    eff_scene = scene_description or cfg.get("scene_description", "")
    eff_custom = custom_additions or cfg.get("custom_additions", "")
    eff_model = model or cfg.get("model") or DEFAULT_IMAGE_MODEL

    if prompt:
        positive = prompt
        neg = negative_prompt or cfg.get("negative_prompt", "")
    else:
        if not eff_style:
            return json.dumps({"error": "No style set on the project or this call; cannot assemble a prompt."})
        assembled = json.loads(assemble_prompt(
            style=eff_style,
            layout=eff_layout or None,
            composition=eff_comp or None,
            scene_description=eff_scene,
            custom_additions=eff_custom,
        ))
        if "error" in assembled:
            return json.dumps(assembled)
        positive = assembled["positive_prompt"]
        neg = negative_prompt or cfg.get("negative_prompt") or assembled.get("negative_prompt", "")

    # Reference images: project sources (absolute paths) + any extra provided this call.
    refs = []
    if use_sources:
        refs.extend(str(PROJECTS_DIR / data["slug"] / s) for s in data.get("sources", []))
    if reference_images:
        refs.extend(str(r) for r in reference_images)

    full_text = positive
    if refs:
        # A source/reference photo defines the COMPOSITION, not just the subject. Whenever
        # references are attached, instruct the model to reproduce the photo's framing exactly
        # so figure count, placement, poses, and camera angle carry over — only the rendering
        # style changes.
        full_text += (
            "\n\n# Reference Composition (STRICT)\n\n"
            "A reference photograph is attached. Treat it as the exact compositional blueprint "
            "for this image. Reproduce, as closely as possible: the same camera angle and "
            "vantage point; the same number of figures and their left-to-right placement; each "
            "figure's pose, gesture, and eyeline; and the position of the key objects (desks, "
            "monitors/screens, props). Keep who-is-where identical to the photograph. Fully "
            "re-render everything in the chosen art style, but do NOT rearrange, add, or remove "
            "figures, and do NOT change the viewpoint or framing."
        )
    if neg:
        full_text += f"\n\nIMPORTANT — Do NOT include any of these: {neg}"

    n = len(data["iterations"]) + 1
    base_name = f"iter-{n:03d}"
    size = LAYOUT_SIZES.get(eff_layout, "1024x1024")
    iters_dir = PROJECTS_DIR / data["slug"] / "iterations"
    result = await _run_generation(full_text, eff_model, refs or None, iters_dir, base_name, size)

    status, err = "ok", None
    if isinstance(result, dict) and result.get("error"):
        status, err = "error", str(result["error"])
    saved_rel = [_rel_to_project(data, p) for p in (result.get("saved_paths") or [])
                 if not str(p).startswith("Error")]
    if status == "ok" and not saved_rel:
        status, err = "error", err or "No image returned by the model"

    iteration = {
        "n": n,
        "label": label,
        "created": _now(),
        "style": eff_style,
        "composition": eff_comp,
        "layout": eff_layout,
        "scene_description": eff_scene,
        "model": result.get("model", eff_model) if isinstance(result, dict) else eff_model,
        "prompt": positive,
        "negative_prompt": neg,
        "custom_additions": eff_custom,
        "references": [_rel_to_project(data, r) for r in refs],
        "images": saved_rel,
        "image": saved_rel[0] if saved_rel else None,
        "notes": notes,
        "status": status,
        "error": err,
        "text_response": result.get("text_response", "") if isinstance(result, dict) else "",
        "usage": result.get("usage", {}) if isinstance(result, dict) else {},
    }
    data["iterations"].append(iteration)
    _save_project(data)

    return json.dumps({
        "project": data["slug"],
        "iteration": n,
        "status": status,
        "error": err,
        "image": iteration["image"],
        "html": str(PROJECTS_DIR / data["slug"] / "index.html"),
        "prompt": positive,
    }, indent=2)


def _cleanup_servers():
    for proc, _ in _SERVERS.values():
        try:
            proc.terminate()
        except Exception:
            pass


atexit.register(_cleanup_servers)


@mcp.tool()
def open_project(name: str, serve: bool = True, port: int = 0) -> str:
    """Open a project's gallery in the browser.

    With serve=True (default) a small local static server is started for the project so the
    page's fetch-based auto-reload works flicker-free; the browser opens the http URL.
    With serve=False the index.html is opened directly via file:// (auto-reload falls back
    to a periodic refresh). The server is reused across calls for the same project."""
    data = _load_project(name)
    if not data:
        return json.dumps({"error": f"No project named '{name}'"})
    pdir = PROJECTS_DIR / data["slug"]
    html_path = pdir / "index.html"
    if not html_path.exists():
        _save_project(data)

    if not serve:
        url = html_path.as_uri()
        try:
            webbrowser.open(url)
        except Exception:
            pass
        return json.dumps({"url": url, "served": False, "dir": str(pdir)}, indent=2)

    existing = _SERVERS.get(data["slug"])
    if existing and existing[0].poll() is None:
        chosen = existing[1]
    else:
        chosen = port or _free_port()
        proc = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(chosen), "--bind", "127.0.0.1"],
            cwd=str(pdir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _SERVERS[data["slug"]] = (proc, chosen)

    url = f"http://127.0.0.1:{chosen}/index.html"
    try:
        webbrowser.open(url)
    except Exception:
        pass
    return json.dumps({"url": url, "served": True, "port": chosen, "dir": str(pdir)}, indent=2)


@mcp.tool()
def render_project_html(name: str) -> str:
    """Rebuild a project's index.html from project.json (e.g. after manual edits) and
    bump its state so any open browser tab reloads."""
    data = _load_project(name)
    if not data:
        return json.dumps({"error": f"No project named '{name}'"})
    _save_project(data)
    return json.dumps({"project": data["slug"], "html": str(PROJECTS_DIR / data["slug"] / "index.html")})


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
</style>
</head>
<body>
<div class="live" id="live">&#9679; live</div>
<div class="wrap">
  <header class="top">
    <h1>{{NAME}}</h1>
    <p class="theme">{{THEME}}</p>
    <p class="scene">{{SCENE}}</p>
    <div class="chips">{{CHIPS}}</div>
  </header>
  {{SOURCES}}
  <h2>Iterations</h2>
  {{CARDS}}
  <footer>Generated {{GENERATED}} &middot; this page auto-reloads when a new iteration is added</footer>
</div>
<script>
 const CURRENT_VERSION = {{VERSION}};
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
</script>
</body>
</html>
"""


# ── Entry Point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()

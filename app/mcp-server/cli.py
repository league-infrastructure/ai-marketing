#!/usr/bin/env python3
"""
League Marketing — Command-Line Tool

Every stateless operation for managing projects, generating images, and configuring
postcards. This is a plain script, not an MCP tool file — it has no schema caching, no
connection lifecycle, nothing that requires a client to reconnect before picking up a
change. Edit a subcommand's implementation and the very next invocation runs the new code.

The MCP server (server.py) keeps only the things that are genuinely stateful (the web
server daemon's process lifecycle) and a generic `run_cli` passthrough tool that calls this
script as a subprocess. Everything else — creating projects, generating images, tuning
postcard regions — lives here.

Usage: uv run python3 mcp-server/cli.py <subcommand> [options]
Run `uv run python3 mcp-server/cli.py <subcommand> --help` for a subcommand's options.
"""

import argparse
import asyncio
import base64
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

# ── Configuration ──────────────────────────────────────────────────────────

MARKETING_DIR = Path(__file__).resolve().parent.parent.parent
APP_DIR = MARKETING_DIR / "app"
IMAGES_DIR = MARKETING_DIR / "images"

try:
    from dotenv import load_dotenv
    load_dotenv(MARKETING_DIR / ".env", override=True)
except ImportError:
    pass

PROMPTS_DIR = APP_DIR / "prompts"
STYLES_DIR = PROMPTS_DIR / "styles"
COMPOSITIONS_DIR = PROMPTS_DIR / "compositions"
PALETTES_DIR = PROMPTS_DIR / "palettes"
LAYOUTS_DIR = APP_DIR / "layouts"
RUBRICS_DIR = APP_DIR / "rubrics"
OUTPUT_DIR = MARKETING_DIR / "output"
PROJECTS_DIR = MARKETING_DIR / "projects"
COMPONENTS_DIR = IMAGES_DIR / "components"

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "") or os.environ.get("OPENROUTER_API", "")
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

DEFAULT_IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "") or "openai/gpt-5.4-image-2"
DEFAULT_IMAGE_PROVIDER = os.environ.get("IMAGE_PROVIDER", "openai")  # "openai" or "openrouter"
DEFAULT_IMAGE_QUALITY = os.environ.get("IMAGE_QUALITY", "") or "high"
EVALUATION_MODEL = "google/gemini-2.5-flash"


def list_styles() -> list:
    if not STYLES_DIR.exists():
        return []
    return sorted(d.name for d in STYLES_DIR.iterdir()
                  if d.is_dir() and (d / "positive.md").exists())


def list_layouts() -> list:
    if not LAYOUTS_DIR.exists():
        return []
    return sorted(p.stem for p in LAYOUTS_DIR.glob("*.md"))


LAYOUT_SIZES = {
    "postcard-4x6": "1536x1024",
    "business-card": "1024x576",
    "individual-cut-images": "1024x1024",
    "individual-panels": "1024x1024",
    "full-page-flyer": "1024x1536",
    "type-sample": "1536x1024",
}

_PRINT_PPI = 256
_BLEED_IN = 0.125


# ── Prompt Assembly Logic ─────────────────────────────────────────────────

def load_prompt_file(category: str, name: str, file: str) -> str:
    if category == "style":
        path = STYLES_DIR / name / file
    elif category == "composition":
        path = COMPOSITIONS_DIR / file
    elif category == "palette":
        path = PALETTES_DIR / file
    elif category == "layout":
        path = LAYOUTS_DIR / file
    elif category == "component":
        path = COMPONENTS_DIR / name / file
    else:
        return ""
    if not path.exists():
        return ""
    return path.read_text()


def _strip_heading(text: str) -> str:
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def list_compositions() -> list:
    if not COMPOSITIONS_DIR.exists():
        return []
    return sorted(p.stem for p in COMPOSITIONS_DIR.glob("*.md"))


def list_palettes() -> list:
    if not PALETTES_DIR.exists():
        return []
    return sorted(p.stem for p in PALETTES_DIR.glob("*.md"))


def list_components() -> list:
    if not COMPONENTS_DIR.exists():
        return []
    return sorted(d.name for d in COMPONENTS_DIR.iterdir()
                  if d.is_dir() and (d / "description.md").exists())


def list_available() -> str:
    result = {"styles": {}, "compositions": list_compositions(),
              "palettes": list_palettes(), "layouts": list_layouts(),
              "components": list_components()}
    for style in list_styles():
        files = {}
        for f in ["positive.md", "negative.md"]:
            p = STYLES_DIR / style / f
            files[f.replace(".md", "")] = "present" if p.exists() else "missing"
        result["styles"][style] = files
    return json.dumps(result, indent=2)


def assemble_prompt(
    style: str,
    layout: Optional[str] = None,
    composition: Optional[str] = None,
    component: Optional[str] = None,
    palette: Optional[str] = None,
    scene_description: str = "",
    custom_additions: str = "",
) -> str:
    if style not in list_styles():
        return json.dumps({"error": f"Unknown style '{style}'. Available: {list_styles()}"})

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

    if component:
        comp_desc = _strip_heading(load_prompt_file("component", component, "description.md"))
        parts.append(f"# Component\n\n{comp_desc or component}")

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
        "component": component,
        "palette": palette,
    }, indent=2)


async def generate_image(
    style: str,
    layout: Optional[str] = None,
    composition: Optional[str] = None,
    palette: Optional[str] = None,
    scene_description: str = "",
    prompt: str = "",
    negative_prompt: str = "",
    model: str = DEFAULT_IMAGE_MODEL,
    reference_images: Optional[list] = None,
    output_filename: str = "generated",
) -> str:
    if not prompt and style:
        assembled = json.loads(assemble_prompt(
            style=style, layout=layout, composition=composition, palette=palette,
            scene_description=scene_description,
        ))
        if "error" in assembled:
            return json.dumps(assembled)
        prompt = assembled["positive_prompt"]
        if not negative_prompt:
            negative_prompt = assembled.get("negative_prompt", "")

    if not prompt:
        return json.dumps({"error": "No prompt provided or assembled"})

    full_text = prompt
    if negative_prompt:
        full_text += f"\n\nIMPORTANT — Do NOT include any of these: {negative_prompt}"

    size = LAYOUT_SIZES.get(layout, "1024x1024")
    result = await _run_generation(full_text, model, reference_images, OUTPUT_DIR, output_filename, size)
    return json.dumps(result, indent=2)


async def _run_generation(full_text, model, reference_images, out_dir, base_name, size="1024x1024", background=""):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if DEFAULT_IMAGE_PROVIDER == "openai":
        if reference_images:
            return await _generate_openai_edits(full_text, model, reference_images, out_dir, base_name, size, background)
        return await _generate_openai_core(full_text, model, out_dir, base_name, size, background)

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
            response = await client.post(f"{OPENROUTER_BASE}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        return {"error": str(e)}

    result = {
        "model": data.get("model", model), "provider": "openrouter", "usage": data.get("usage", {}),
        "text_response": "", "images": [], "saved_paths": [],
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


async def _generate_openai_core(full_text, model, out_dir, base_name, size="1024x1024", background=""):
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        return {"error": "OPENAI_API_KEY not set for OpenAI image generation"}

    headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
    payload = {"model": model, "prompt": full_text[:32000], "n": 1, "size": size,
               "quality": DEFAULT_IMAGE_QUALITY}
    if background:
        payload["background"] = background

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post("https://api.openai.com/v1/images/generations", headers=headers, json=payload)
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


_OPENAI_EDIT_SIZES = {"1024x1024", "1536x1024", "1024x1536"}


async def _generate_openai_edits(full_text, model, reference_images, out_dir, base_name, size="1024x1024", background=""):
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        return {"error": "OPENAI_API_KEY not set for OpenAI image generation"}
    out_dir = Path(out_dir)

    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
    files = []
    for img_path in reference_images:
        if os.path.exists(img_path):
            ext = os.path.splitext(img_path)[1].lower()
            with open(img_path, "rb") as f:
                files.append(("image[]", (os.path.basename(img_path), f.read(),
                                          mime_map.get(ext, "image/png"))))
    if not files:
        return {"error": "No readable reference images for OpenAI edits"}

    edit_size = size if size in _OPENAI_EDIT_SIZES else "auto"
    form = {"model": model, "prompt": full_text[:32000], "size": edit_size, "n": "1",
            "quality": DEFAULT_IMAGE_QUALITY}
    if background:
        form["background"] = background

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/images/edits",
                headers={"Authorization": f"Bearer {openai_key}"},
                data=form, files=files,
            )
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        return {"error": str(e)}

    if "error" in data:
        return {"error": data["error"]}

    result = {"model": model, "provider": "openai", "images": [], "saved_paths": []}
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


async def evaluate_image(
    image_path: str,
    style: str,
    layout: Optional[str] = None,
    rubric_path: str = "",
) -> str:
    if not OPENROUTER_API_KEY:
        return json.dumps({"error": "OPENROUTER_API_KEY not set."})

    if not os.path.exists(image_path):
        return json.dumps({"error": f"Image not found: {image_path}"})

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    ext = os.path.splitext(image_path)[1].lower()
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
    mime = mime_map.get(ext, "image/png")

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
            response = await client.post(f"{OPENROUTER_BASE}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        return json.dumps({"error": str(e)})

    evaluation_text = ""
    if "choices" in data:
        evaluation_text = data["choices"][0]["message"]["content"]

    try:
        parsed = json.loads(evaluation_text)
        parsed["image_path"] = image_path
        parsed["rubric_style"] = style
        parsed["model_used"] = data.get("model", EVALUATION_MODEL)
        return json.dumps(parsed, indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        return json.dumps({
            "image_path": image_path, "rubric_style": style, "evaluation": evaluation_text,
            "model_used": data.get("model", EVALUATION_MODEL),
        }, indent=2, ensure_ascii=False)


# ── Projects ─────────────────────────────────────────────────────────────

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


def _postcard_content_path(pdir: Path) -> Path:
    return pdir / "postcard-content.json"


def _empty_postcard_content() -> dict:
    return {
        "front_image": "", "back_image": "",
        "front_regions": [], "back_regions": [],
        "front_extra_html": "", "back_extra_html": "",
    }


def _load_postcard_content(pdir: Path) -> dict:
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


def _has_postcard(pdir: Path) -> bool:
    return _postcard_content_path(pdir).exists()


# ── Web server daemon lifecycle ─────────────────────────────────────────────
# Duplicated (deliberately) from server.py — both processes need to reach the daemon
# independently. See server.py's copy for the full rationale.

WEBSERVER_SCRIPT = Path(__file__).resolve().parent / "webserver.py"
DEFAULT_STATIC_PORT = 31337
WEBSERVER_STATE_PATH = PROJECTS_DIR / ".webserver.json"


def _webserver_status() -> Optional[dict]:
    if not WEBSERVER_STATE_PATH.exists():
        return None
    try:
        info = json.loads(WEBSERVER_STATE_PATH.read_text())
        pid, port = int(info["pid"]), int(info["port"])
    except Exception:
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        return None
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            pass
    except OSError:
        return None
    return {"pid": pid, "port": port}


def _spawn_webserver(port: int) -> dict:
    proc = subprocess.Popen(
        [sys.executable, str(WEBSERVER_SCRIPT), "--port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(50):
        time.sleep(0.1)
        status = _webserver_status()
        if status and status["pid"] == proc.pid:
            return status
    raise RuntimeError("web server daemon did not start within 5s")


def _ensure_webserver(port: int = 0) -> int:
    status = _webserver_status()
    if status:
        return status["port"]
    return _spawn_webserver(port or DEFAULT_STATIC_PORT)["port"]


def _webserver_post(path: str, body: dict, timeout: float = 30.0) -> dict:
    port = _ensure_webserver()
    resp = httpx.post(f"http://127.0.0.1:{port}/{path.lstrip('/')}", json=body, timeout=timeout)
    result = resp.json()
    if resp.status_code >= 400 or "error" in result:
        raise RuntimeError(result.get("error", f"web server returned {resp.status_code}"))
    return result


def restart_web_server(port: int = 0) -> str:
    status = _webserver_status()
    if status:
        try:
            os.kill(status["pid"], 15)  # SIGTERM
        except OSError:
            pass
        for _ in range(30):
            time.sleep(0.1)
            if not _webserver_status():
                break
    new_status = _spawn_webserver(port or DEFAULT_STATIC_PORT)
    return json.dumps({"restarted": True, **new_status}, indent=2)


def create_project(
    name: str, style: str = "", composition: str = "", component: str = "", palette: str = "",
    layout: str = "", theme: str = "", scene_description: str = "", model: str = "",
    negative_prompt: str = "", custom_additions: str = "", source_images: Optional[list] = None,
) -> str:
    slug = _slug(name)
    if not slug:
        return json.dumps({"error": "Invalid project name"})
    if style and style not in list_styles():
        return json.dumps({"error": f"Unknown style '{style}'. Available: {list_styles()}"})
    pdir = PROJECTS_DIR / slug
    if (pdir / "project.json").exists():
        return json.dumps({"error": f"Project '{slug}' already exists. Use update_project or a new name."})

    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "iterations").mkdir(exist_ok=True)
    sources = _copy_sources(pdir, source_images)

    data = {
        "name": name, "slug": slug, "created": _now(),
        "config": {
            "style": style, "composition": composition, "component": component, "palette": palette,
            "layout": layout, "theme": theme, "scene_description": scene_description,
            "model": model or DEFAULT_IMAGE_MODEL, "negative_prompt": negative_prompt,
            "custom_additions": custom_additions,
        },
        "sources": sources, "iterations": [], "state_version": 0,
    }
    try:
        _webserver_post(f"{slug}/project/save", data)
    except Exception as e:
        return json.dumps({"error": f"saved locally but web server failed to render: {e}"})
    return json.dumps({
        "project": slug, "dir": str(pdir), "html": str(pdir / "index.html"),
        "config": data["config"], "sources": sources,
        "next": "Call open-project to view it, then generate-project-image to iterate.",
    }, indent=2)


EMAIL_TEMPLATES_DIR = COMPONENTS_DIR / "email"


def _resolve_email_template(template: str) -> Path:
    """A bare name (e.g. 'template' or 'newsletter-v1') resolves against
    components/email/<name>.html; anything that exists as given (relative or absolute path)
    is used as-is — so both 'saved template names' and one-off paths work."""
    if not template:
        return EMAIL_TEMPLATES_DIR / "template.html"
    p = Path(template).expanduser()
    if p.exists():
        return p
    return EMAIL_TEMPLATES_DIR / (template if template.endswith(".html") else f"{template}.html")


def create_email_project(name: str, template: str = "") -> str:
    """Email projects are a different kind of project: no style/composition/palette, no AI
    generation. The designer hand-edits projects/<slug>/email.html directly (copied once from
    a components/email/ template, never edited in place there); the web server shows it as a
    live-reloading iframe instead of the image-iteration gallery. Call render-project-html
    after each edit to bump the preview."""
    slug = _slug(name)
    if not slug:
        return json.dumps({"error": "Invalid project name"})
    pdir = PROJECTS_DIR / slug
    if (pdir / "project.json").exists():
        return json.dumps({"error": f"Project '{slug}' already exists. Use a new name."})
    src = _resolve_email_template(template)
    if not src.exists():
        return json.dumps({"error": f"Template not found: {src}"})

    pdir.mkdir(parents=True, exist_ok=True)
    dest = pdir / "email.html"
    shutil.copy2(src, dest)
    try:
        template_source = str(src.relative_to(MARKETING_DIR))
    except ValueError:
        template_source = str(src)

    data = {
        "name": name, "slug": slug, "type": "email", "created": _now(),
        "template_source": template_source,
        "config": {}, "sources": [], "iterations": [], "state_version": 0,
    }
    try:
        _webserver_post(f"{slug}/project/save", data)
    except Exception as e:
        return json.dumps({"error": f"saved locally but web server failed to render: {e}"})
    return json.dumps({
        "project": slug, "dir": str(pdir), "email_html": str(dest), "template_source": template_source,
        "next": "Call open-project to view it, then edit email.html directly and call "
                "render-project-html to refresh the live preview.",
    }, indent=2)


def save_email_template(name: str, template_name: str, overwrite: bool = False) -> str:
    """Copy a finished projects/<slug>/email.html back to components/email/<template_name>.html
    so it becomes a reusable starting point for future email projects."""
    data = _load_project(name)
    if not data:
        return json.dumps({"error": f"No project named '{name}'"})
    pdir = PROJECTS_DIR / data["slug"]
    src = pdir / "email.html"
    if not src.exists():
        return json.dumps({"error": f"No email.html in project '{data['slug']}'"})
    tslug = _slug(template_name)
    if not tslug:
        return json.dumps({"error": "Invalid template name"})
    dest = EMAIL_TEMPLATES_DIR / f"{tslug}.html"
    if dest.exists() and not overwrite:
        return json.dumps({"error": f"Template '{dest.name}' already exists. Pass --overwrite to replace it."})
    EMAIL_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return json.dumps({"project": data["slug"], "template": str(dest)}, indent=2)


def _list_projects_data() -> list:
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
                "project": data.get("slug", d.name), "name": data.get("name"),
                "style": cfg.get("style"), "layout": cfg.get("layout"), "theme": cfg.get("theme"),
                "iterations": len(iterations), "thumbnail": thumb, "dir": str(d),
            })
    return projs


def list_projects() -> str:
    projs = [{k: p[k] for k in ("project", "name", "style", "iterations", "dir")}
             for p in _list_projects_data()]
    return json.dumps({"projects": projs}, indent=2)


def get_project(name: str) -> str:
    data = _load_project(name)
    if not data:
        return json.dumps({"error": f"No project named '{name}'"})
    return json.dumps(data, indent=2, ensure_ascii=False)


def update_project(
    name: str, style: Optional[str] = None, composition: Optional[str] = None,
    component: Optional[str] = None, palette: Optional[str] = None, layout: Optional[str] = None,
    theme: Optional[str] = None, scene_description: Optional[str] = None, model: Optional[str] = None,
    negative_prompt: Optional[str] = None, custom_additions: Optional[str] = None,
    background: Optional[str] = None, add_sources: Optional[list] = None,
) -> str:
    data = _load_project(name)
    if not data:
        return json.dumps({"error": f"No project named '{name}'"})
    if style is not None and style and style not in list_styles():
        return json.dumps({"error": f"Unknown style '{style}'. Available: {list_styles()}"})
    cfg = data["config"]
    for key, val in (
        ("style", style), ("composition", composition), ("component", component), ("palette", palette),
        ("layout", layout), ("theme", theme), ("scene_description", scene_description),
        ("model", model), ("negative_prompt", negative_prompt),
        ("custom_additions", custom_additions), ("background", background),
    ):
        if val is not None:
            cfg[key] = val
    if add_sources:
        data.setdefault("sources", []).extend(_copy_sources(PROJECTS_DIR / data["slug"], add_sources))
    try:
        _webserver_post(f"{data['slug']}/project/save", data)
    except Exception as e:
        return json.dumps({"error": f"web server failed to render: {e}"})
    return json.dumps({"project": data["slug"], "config": cfg, "sources": data["sources"]}, indent=2)


async def generate_project_image(
    name: str, scene_description: str = "", custom_additions: str = "", prompt: str = "",
    negative_prompt: str = "", model: str = "", style: str = "", composition: str = "",
    component: str = "", palette: str = "", layout: str = "", reference_images: Optional[list] = None,
    use_sources: bool = True, background: str = "", label: str = "", notes: str = "",
) -> str:
    data = _load_project(name)
    if not data:
        return json.dumps({"error": f"No project named '{name}'"})
    cfg = data["config"]

    eff_style = style or cfg.get("style", "")
    eff_comp = composition or cfg.get("composition", "")
    eff_component = component or cfg.get("component", "")
    eff_palette = palette or cfg.get("palette", "")
    eff_layout = layout or cfg.get("layout", "")
    eff_scene = scene_description or cfg.get("scene_description", "")
    eff_custom = custom_additions or cfg.get("custom_additions", "")
    eff_model = model or cfg.get("model") or DEFAULT_IMAGE_MODEL
    eff_background = background or cfg.get("background", "")

    if prompt:
        positive = prompt
        neg = negative_prompt or cfg.get("negative_prompt", "")
    else:
        if not eff_style:
            return json.dumps({"error": "No style set on the project or this call; cannot assemble a prompt."})
        assembled = json.loads(assemble_prompt(
            style=eff_style, layout=eff_layout or None, composition=eff_comp or None,
            component=eff_component or None, palette=eff_palette or None,
            scene_description=eff_scene, custom_additions=eff_custom,
        ))
        if "error" in assembled:
            return json.dumps(assembled)
        positive = assembled["positive_prompt"]
        neg = negative_prompt or cfg.get("negative_prompt") or assembled.get("negative_prompt", "")

    refs = []
    if use_sources:
        refs.extend(str(PROJECTS_DIR / data["slug"] / s) for s in data.get("sources", []))
    if reference_images:
        refs.extend(str(r) for r in reference_images)

    full_text = positive
    if refs:
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
    result = await _run_generation(full_text, eff_model, refs or None, iters_dir, base_name, size, eff_background)

    status, err = "ok", None
    if isinstance(result, dict) and result.get("error"):
        status, err = "error", str(result["error"])
    saved_rel = [_rel_to_project(data, p) for p in (result.get("saved_paths") or [])
                 if not str(p).startswith("Error")]
    if status == "ok" and not saved_rel:
        status, err = "error", err or "No image returned by the model"

    iteration = {
        "n": n, "label": label, "created": _now(), "style": eff_style, "composition": eff_comp,
        "component": eff_component, "palette": eff_palette, "layout": eff_layout,
        "background": eff_background, "scene_description": eff_scene,
        "model": result.get("model", eff_model) if isinstance(result, dict) else eff_model,
        "prompt": positive, "negative_prompt": neg, "custom_additions": eff_custom,
        "references": [_rel_to_project(data, r) for r in refs],
        "images": saved_rel, "image": saved_rel[0] if saved_rel else None,
        "notes": notes, "status": status, "error": err,
        "text_response": result.get("text_response", "") if isinstance(result, dict) else "",
        "usage": result.get("usage", {}) if isinstance(result, dict) else {},
    }
    data["iterations"].append(iteration)
    try:
        _webserver_post(f"{data['slug']}/project/save", data)
    except Exception as e:
        return json.dumps({"error": f"image saved but web server failed to render: {e}"})

    return json.dumps({
        "project": data["slug"], "iteration": n, "status": status, "error": err,
        "image": iteration["image"], "html": str(PROJECTS_DIR / data["slug"] / "index.html"),
        "prompt": positive,
    }, indent=2)


def open_project(name: str, serve: bool = True, port: int = 0) -> str:
    data = _load_project(name)
    if not data:
        return json.dumps({"error": f"No project named '{name}'"})
    pdir = PROJECTS_DIR / data["slug"]
    html_path = pdir / "index.html"
    if not html_path.exists():
        try:
            _webserver_post(f"{data['slug']}/project/save", data)
        except Exception as e:
            return json.dumps({"error": f"web server failed to render: {e}"})

    if not serve:
        url = html_path.as_uri()
        try:
            webbrowser.open(url)
        except Exception:
            pass
        return json.dumps({"url": url, "served": False, "dir": str(pdir)}, indent=2)

    chosen = _ensure_webserver(port)
    url = f"http://127.0.0.1:{chosen}/{data['slug']}/index.html"
    try:
        webbrowser.open(url)
    except Exception:
        pass
    return json.dumps({"url": url, "served": True, "port": chosen, "dir": str(pdir)}, indent=2)


def open_projects_home(port: int = 0) -> str:
    chosen = _ensure_webserver(port)
    try:
        _webserver_post("_home/refresh", {})
    except Exception:
        pass
    url = f"http://127.0.0.1:{chosen}/"
    try:
        webbrowser.open(url)
    except Exception:
        pass
    return json.dumps({"url": url, "served": True, "port": chosen, "dir": str(PROJECTS_DIR)}, indent=2)


def render_project_html(name: str) -> str:
    data = _load_project(name)
    if not data:
        return json.dumps({"error": f"No project named '{name}'"})
    try:
        _webserver_post(f"{data['slug']}/project/save", data)
    except Exception as e:
        return json.dumps({"error": f"web server failed to render: {e}"})
    return json.dumps({"project": data["slug"], "html": str(PROJECTS_DIR / data["slug"] / "index.html")})


def set_postcard_sides(name: str, front_image: str, back_image: str) -> str:
    data = _load_project(name)
    if not data:
        return json.dumps({"error": f"No project named '{name}'"})
    pdir = PROJECTS_DIR / data["slug"]
    for label, rel in (("front_image", front_image), ("back_image", back_image)):
        if not (pdir / rel).exists():
            return json.dumps({"error": f"{label} '{rel}' does not exist under {pdir}"})
    content = _load_postcard_content(pdir)
    content["front_image"] = front_image
    content["back_image"] = back_image
    try:
        _webserver_post(f"{data['slug']}/postcard-content/save", content)
    except Exception as e:
        return json.dumps({"error": f"web server failed to render: {e}"})
    return json.dumps({
        "project": data["slug"], "front_image": front_image, "back_image": back_image,
        "preview": str(pdir / "postcard.html"),
    }, indent=2)


def set_postcard_regions(name: str, side: str, regions: list) -> str:
    if side not in ("front", "back"):
        return json.dumps({"error": "side must be 'front' or 'back'"})
    data = _load_project(name)
    if not data:
        return json.dumps({"error": f"No project named '{name}'"})
    pdir = PROJECTS_DIR / data["slug"]
    content = _load_postcard_content(pdir)
    clean = []
    for r in regions:
        if not r.get("name"):
            return json.dumps({"error": "every region needs a unique 'name'"})
        clean.append({
            "name": r["name"], "label": r.get("label", r["name"]),
            "position": r.get("position", {}), "font": r.get("font", {}),
            "style": r.get("style", ""), "text": r.get("text", ""), "rows": r.get("rows"),
        })
    content[f"{side}_regions"] = clean
    try:
        _webserver_post(f"{data['slug']}/postcard-content/save", content)
    except Exception as e:
        return json.dumps({"error": f"web server failed to render: {e}"})
    return json.dumps({
        "project": data["slug"], "side": side, "regions": [r["name"] for r in clean],
        "preview": str(pdir / "postcard.html"),
    }, indent=2)


def update_postcard_region(name: str, side: str, region_name: str,
                            text: Optional[str] = None, position: Optional[dict] = None,
                            font: Optional[dict] = None, style: Optional[str] = None) -> str:
    """position/font are merged into whatever's already stored (only the keys you pass
    change — e.g. position={"top": "3.5in"} leaves left/width/height alone); style (the
    residual free-form CSS) is replaced wholesale, same as text, when provided."""
    if side not in ("front", "back"):
        return json.dumps({"error": "side must be 'front' or 'back'"})
    data = _load_project(name)
    if not data:
        return json.dumps({"error": f"No project named '{name}'"})
    pdir = PROJECTS_DIR / data["slug"]
    content = _load_postcard_content(pdir)
    for r in content.get(f"{side}_regions", []):
        if r.get("name") == region_name:
            if text is not None:
                r["text"] = text
            if position is not None:
                r["position"] = {**(r.get("position") or {}), **position}
            if font is not None:
                r["font"] = {**(r.get("font") or {}), **font}
            if style is not None:
                r["style"] = style
            try:
                _webserver_post(f"{data['slug']}/postcard-content/save", content)
            except Exception as e:
                return json.dumps({"error": f"web server failed to render: {e}"})
            return json.dumps({"project": data["slug"], "side": side, "region": region_name}, indent=2)
    return json.dumps({"error": f"Unknown region '{region_name}' on side '{side}'"})


def set_postcard_extra_html(name: str, side: str, html_content: str) -> str:
    if side not in ("front", "back"):
        return json.dumps({"error": "side must be 'front' or 'back'"})
    data = _load_project(name)
    if not data:
        return json.dumps({"error": f"No project named '{name}'"})
    pdir = PROJECTS_DIR / data["slug"]
    content = _load_postcard_content(pdir)
    content[f"{side}_extra_html"] = html_content
    try:
        _webserver_post(f"{data['slug']}/postcard-content/save", content)
    except Exception as e:
        return json.dumps({"error": f"web server failed to render: {e}"})
    return json.dumps({"project": data["slug"], "side": side}, indent=2)


def generate_postcard_pdf(name: str, out_path: str = "", show_marks: bool = False) -> str:
    data = _load_project(name)
    if not data:
        return json.dumps({"error": f"No project named '{name}'"})
    try:
        result = _webserver_post(
            f"{data['slug']}/postcard/pdf",
            {"out_path": out_path, "show_marks": show_marks}, timeout=120.0,
        )
    except Exception as e:
        return json.dumps({"error": str(e)})
    return json.dumps(result, indent=2)


# ── Asset & Project Catalog ─────────────────────────────────────────────────
# Two JSON indexes so Claude can find existing images by content instead of guessing paths:
# images/catalog.json for the standalone media library (stock photos, components, reference
# art) and projects/catalog.json for every image inside a generation project. Both are built
# INCREMENTALLY — catalog-images/catalog-projects only vision-categorize files not already
# keyed in the index (or changed on disk, with --rescan), up to --limit per call — so
# re-running the same command periodically is exactly how you make progress and pick up
# anything missed, rather than a single all-or-nothing pass.

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
IMAGES_CATALOG_PATH = IMAGES_DIR / "catalog.json"
PROJECTS_CATALOG_PATH = PROJECTS_DIR / "catalog.json"
CATALOG_MODEL = EVALUATION_MODEL  # same vision-capable model already used for evaluate-image

_KNOWN_STYLES = (
    "photograph", "graphic-novel", "comic-book", "manga", "pop-art", "flat-poster",
    "8bit-video-game", "dragon-ball-z", "technical-blueprint", "type-sample", "other",
)


def _load_catalog(path: Path) -> dict:
    if path.exists():
        try:
            data = json.loads(path.read_text())
            data.setdefault("entries", {})
            return data
        except Exception:
            pass
    return {"entries": {}}


def _save_catalog(path: Path, catalog: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False))


async def _vision_categorize(image_path: Path, known_style: str = "") -> dict:
    """Send one image to the vision model and get back the fixed catalog fields. known_style,
    when given (a project already records its generation style in project.json), is used
    verbatim instead of asking the model to guess it."""
    if not OPENROUTER_API_KEY:
        return {"error": "OPENROUTER_API_KEY not set."}
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    ext = image_path.suffix.lower()
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
    mime = mime_map.get(ext, "image/png")

    style_instruction = (
        f'The style is already known to be "{known_style}" — use exactly that string for "style".'
        if known_style else
        f"Classify \"style\" as one of: {', '.join(_KNOWN_STYLES)}."
    )

    prompt = f"""You are cataloging images for a youth robotics/programming education nonprofit's marketing asset library.

Look at the attached image and respond with ONLY a valid JSON object, no other text, in exactly this shape:
{{
  "description": "one or two plain factual sentences describing exactly what is shown",
  "style": "...",
  "people": "none" | "single" | "multiple",
  "about_programming": true | false,
  "about_robotics": true | false,
  "ai_altered": true | false,
  "tags": ["short", "lowercase", "keywords"]
}}

{style_instruction}
"people" counts humans in the image (not robots) — none, exactly one, or multiple.
"about_programming" is true if the image depicts or clearly relates to writing code, software, or computer programming.
"about_robotics" is true if the image depicts or clearly relates to robots or robotics hardware.
"ai_altered" is true if the image looks AI-generated or AI-illustrated/edited; false if it looks like an untouched real photograph.
"tags" should be 3-8 short keywords useful for search (subjects, setting, mood, colors)."""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://league.ai",
        "X-Title": "League Asset Cataloger",
    }
    payload = {
        "model": CATALOG_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
            ],
        }],
        "max_tokens": 500,
    }
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(f"{OPENROUTER_BASE}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        text = data["choices"][0]["message"]["content"]
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        parsed = json.loads(text)
    except Exception as e:
        return {"error": str(e)}

    if known_style:
        parsed["style"] = known_style
    parsed.setdefault("tags", [])
    return parsed


def _searchable_blob(entry: dict, extra: str = "") -> str:
    parts = [
        entry.get("description", ""), extra, entry.get("style", ""), entry.get("role", ""),
        " ".join(entry.get("tags", [])),
        "about programming" if entry.get("about_programming") else "",
        "about robotics" if entry.get("about_robotics") else "",
        {"none": "no people", "single": "one person", "multiple": "multiple people"}.get(entry.get("people"), ""),
        "ai generated ai altered ai illustrated" if entry.get("ai_altered") else "real photograph unaltered",
    ]
    return " ".join(parts).lower()


async def catalog_images(rescan: bool = False, limit: int = 25) -> str:
    """Scan images/ for image files and vision-categorize any not already in
    images/catalog.json (or changed on disk, with rescan=True), up to `limit` new/changed
    files this call — safe to just call again to keep making progress."""
    catalog = _load_catalog(IMAGES_CATALOG_PATH)
    entries = catalog["entries"]

    all_files = sorted(p for p in IMAGES_DIR.rglob("*") if p.suffix.lower() in IMAGE_EXTENSIONS)
    role_by_top = {
        "photos": "source", "stock_images": "source",
        "prior-art": "reference", "examples": "reference", "images": "reference",
        "components": "final", "assets": "final",
    }

    processed, skipped, limited, errors = 0, 0, 0, []
    for path in all_files:
        rel = str(path.relative_to(MARKETING_DIR))
        mtime = path.stat().st_mtime
        existing = entries.get(rel)
        if existing and not (rescan and existing.get("mtime") != mtime):
            skipped += 1
            continue
        if processed >= limit:
            limited += 1
            continue
        top = path.relative_to(IMAGES_DIR).parts[0]
        result = await _vision_categorize(path)
        if "error" in result:
            errors.append({"path": rel, "error": result["error"]})
            continue
        result["path"] = rel
        result["mtime"] = mtime
        result["role"] = role_by_top.get(top, "unknown")
        entries[rel] = result
        processed += 1
        _save_catalog(IMAGES_CATALOG_PATH, catalog)  # incremental save — survives interruption

    return json.dumps({
        "total_files": len(all_files), "already_cataloged": skipped, "newly_cataloged": processed,
        "remaining": limited + len(errors), "errors": errors, "catalog": str(IMAGES_CATALOG_PATH),
    }, indent=2)


async def catalog_projects(rescan: bool = False, limit: int = 25) -> str:
    """Scan every project's iterations/ (plus assets/ and sources/, if present) and
    vision-categorize any image not already in projects/catalog.json. Trusts the project's own
    config.style for its OWN generated iterations (already known, no need to guess) but lets
    vision judge sources/assets, which may be real photos or copied-in art from elsewhere."""
    catalog = _load_catalog(PROJECTS_CATALOG_PATH)
    entries = catalog["entries"]

    all_files = []  # (path, project_data, role)
    if PROJECTS_DIR.exists():
        for pdir in sorted(d for d in PROJECTS_DIR.iterdir() if d.is_dir()):
            data = _load_project(pdir.name)
            if not data:
                continue
            for sub, role in (("iterations", "iteration"), ("assets", "project-asset"), ("sources", "source")):
                subdir = pdir / sub
                if not subdir.exists():
                    continue
                for path in sorted(subdir.rglob("*")):
                    if path.suffix.lower() in IMAGE_EXTENSIONS:
                        all_files.append((path, data, role))

    processed, skipped, limited, errors = 0, 0, 0, []
    for path, data, role in all_files:
        rel = str(path.relative_to(MARKETING_DIR))
        mtime = path.stat().st_mtime
        existing = entries.get(rel)
        if existing and not (rescan and existing.get("mtime") != mtime):
            skipped += 1
            continue
        if processed >= limit:
            limited += 1
            continue
        cfg_style = (data.get("config") or {}).get("style", "")
        known_style = cfg_style if (role == "iteration" and cfg_style in _KNOWN_STYLES) else ""
        result = await _vision_categorize(path, known_style=known_style)
        if "error" in result:
            errors.append({"path": rel, "error": result["error"]})
            continue
        if role == "iteration":
            result["ai_altered"] = True  # every project iteration is AI-generated, by definition
        result["path"] = rel
        result["mtime"] = mtime
        result["role"] = role
        result["project"] = data.get("slug", "")
        result["project_name"] = data.get("name", "")
        result["project_theme"] = (data.get("config") or {}).get("theme", "")
        entries[rel] = result
        processed += 1
        _save_catalog(PROJECTS_CATALOG_PATH, catalog)

    return json.dumps({
        "total_files": len(all_files), "already_cataloged": skipped, "newly_cataloged": processed,
        "remaining": limited + len(errors), "errors": errors, "catalog": str(PROJECTS_CATALOG_PATH),
    }, indent=2)


def search_catalog(
    query: str = "", catalog: str = "both", people: str = "", about_programming: Optional[bool] = None,
    about_robotics: Optional[bool] = None, ai_altered: Optional[bool] = None, style: str = "",
    role: str = "", limit: int = 20,
) -> str:
    """Free-text + structured search over images/catalog.json and/or projects/catalog.json.
    Free text matches against each entry's description, tags, style, role, project, and
    injected phrases for its people/programming/robotics/ai_altered flags — good enough for
    queries like 'kids programming' without a real embeddings index."""
    sources = []
    if catalog in ("images", "both"):
        sources.append(("images", _load_catalog(IMAGES_CATALOG_PATH)))
    if catalog in ("projects", "both"):
        sources.append(("projects", _load_catalog(PROJECTS_CATALOG_PATH)))

    terms = [t for t in query.lower().split() if t]
    results = []
    for cat_name, cat in sources:
        for rel, entry in cat["entries"].items():
            if people and entry.get("people") != people:
                continue
            if about_programming is not None and bool(entry.get("about_programming")) != about_programming:
                continue
            if about_robotics is not None and bool(entry.get("about_robotics")) != about_robotics:
                continue
            if ai_altered is not None and bool(entry.get("ai_altered")) != ai_altered:
                continue
            if style and entry.get("style") != style:
                continue
            if role and entry.get("role") != role:
                continue
            extra = f"{entry.get('project', '')} {entry.get('project_theme', '')}"
            blob = _searchable_blob(entry, extra=extra)
            if terms and not all(t in blob for t in terms):
                continue
            score = sum(blob.count(t) for t in terms) if terms else 0
            results.append((score, {**entry, "catalog": cat_name}))

    results.sort(key=lambda r: r[0], reverse=True)
    return json.dumps({
        "query": query, "count": len(results), "results": [r[1] for r in results[:limit]],
    }, indent=2, ensure_ascii=False)


# ── CLI dispatch ─────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(prog="cli.py", description="League Marketing command-line tool")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("list-available")

    s = sub.add_parser("assemble-prompt")
    s.add_argument("--style", required=True)
    s.add_argument("--layout")
    s.add_argument("--composition")
    s.add_argument("--component")
    s.add_argument("--palette")
    s.add_argument("--scene-description", default="")
    s.add_argument("--custom-additions", default="")

    s = sub.add_parser("generate-image")
    s.add_argument("--style", required=True)
    s.add_argument("--layout")
    s.add_argument("--composition")
    s.add_argument("--palette")
    s.add_argument("--scene-description", default="")
    s.add_argument("--prompt", default="")
    s.add_argument("--negative-prompt", default="")
    s.add_argument("--model", default=DEFAULT_IMAGE_MODEL)
    s.add_argument("--reference-images", type=json.loads, default=None)
    s.add_argument("--output-filename", default="generated")

    s = sub.add_parser("evaluate-image")
    s.add_argument("--image-path", required=True)
    s.add_argument("--style", required=True)
    s.add_argument("--layout")
    s.add_argument("--rubric-path", default="")

    s = sub.add_parser("create-project")
    s.add_argument("--name", required=True)
    s.add_argument("--style", default="")
    s.add_argument("--composition", default="")
    s.add_argument("--component", default="")
    s.add_argument("--palette", default="")
    s.add_argument("--layout", default="")
    s.add_argument("--theme", default="")
    s.add_argument("--scene-description", default="")
    s.add_argument("--model", default="")
    s.add_argument("--negative-prompt", default="")
    s.add_argument("--custom-additions", default="")
    s.add_argument("--source-images", type=json.loads, default=None)

    s = sub.add_parser("create-email-project")
    s.add_argument("--name", required=True)
    s.add_argument("--template", default="",
                    help="components/email/<name>.html or a path; defaults to template.html")

    s = sub.add_parser("save-email-template")
    s.add_argument("--name", required=True)
    s.add_argument("--template-name", required=True)
    s.add_argument("--overwrite", action=argparse.BooleanOptionalAction, default=False)

    s = sub.add_parser("list-projects")

    s = sub.add_parser("get-project")
    s.add_argument("--name", required=True)

    s = sub.add_parser("update-project")
    s.add_argument("--name", required=True)
    s.add_argument("--style")
    s.add_argument("--composition")
    s.add_argument("--component")
    s.add_argument("--palette")
    s.add_argument("--layout")
    s.add_argument("--theme")
    s.add_argument("--scene-description")
    s.add_argument("--model")
    s.add_argument("--negative-prompt")
    s.add_argument("--custom-additions")
    s.add_argument("--background")
    s.add_argument("--add-sources", type=json.loads, default=None)

    s = sub.add_parser("generate-project-image")
    s.add_argument("--name", required=True)
    s.add_argument("--scene-description", default="")
    s.add_argument("--custom-additions", default="")
    s.add_argument("--prompt", default="")
    s.add_argument("--negative-prompt", default="")
    s.add_argument("--model", default="")
    s.add_argument("--style", default="")
    s.add_argument("--composition", default="")
    s.add_argument("--component", default="")
    s.add_argument("--palette", default="")
    s.add_argument("--layout", default="")
    s.add_argument("--reference-images", type=json.loads, default=None)
    s.add_argument("--use-sources", action=argparse.BooleanOptionalAction, default=True)
    s.add_argument("--background", default="")
    s.add_argument("--label", default="")
    s.add_argument("--notes", default="")

    s = sub.add_parser("open-project")
    s.add_argument("--name", required=True)
    s.add_argument("--serve", action=argparse.BooleanOptionalAction, default=True)
    s.add_argument("--port", type=int, default=0)

    s = sub.add_parser("open-projects-home")
    s.add_argument("--port", type=int, default=0)

    s = sub.add_parser("render-project-html")
    s.add_argument("--name", required=True)

    s = sub.add_parser("set-postcard-sides")
    s.add_argument("--name", required=True)
    s.add_argument("--front-image", required=True)
    s.add_argument("--back-image", required=True)

    s = sub.add_parser("set-postcard-regions")
    s.add_argument("--name", required=True)
    s.add_argument("--side", required=True, choices=["front", "back"])
    s.add_argument("--regions", type=json.loads, required=True)

    s = sub.add_parser("update-postcard-region")
    s.add_argument("--name", required=True)
    s.add_argument("--side", required=True, choices=["front", "back"])
    s.add_argument("--region-name", required=True)
    s.add_argument("--text")
    s.add_argument("--position", type=json.loads,
                    help='JSON dict, merged into the existing position, e.g. \'{"top":"3.5in"}\'')
    s.add_argument("--font", type=json.loads,
                    help='JSON dict, merged into the existing font, e.g. \'{"size":"14px"}\'')
    s.add_argument("--style", help="residual free-form CSS (color, padding, line-height, etc.)")

    s = sub.add_parser("set-postcard-extra-html")
    s.add_argument("--name", required=True)
    s.add_argument("--side", required=True, choices=["front", "back"])
    s.add_argument("--html-content", required=True)

    s = sub.add_parser("generate-postcard-pdf")
    s.add_argument("--name", required=True)
    s.add_argument("--out-path", default="")
    s.add_argument("--show-marks", action=argparse.BooleanOptionalAction, default=False)

    s = sub.add_parser("restart-web-server")
    s.add_argument("--port", type=int, default=0)

    s = sub.add_parser("catalog-images")
    s.add_argument("--rescan", action=argparse.BooleanOptionalAction, default=False)
    s.add_argument("--limit", type=int, default=25)

    s = sub.add_parser("catalog-projects")
    s.add_argument("--rescan", action=argparse.BooleanOptionalAction, default=False)
    s.add_argument("--limit", type=int, default=25)

    s = sub.add_parser("search-catalog")
    s.add_argument("--query", default="")
    s.add_argument("--catalog", choices=["images", "projects", "both"], default="both")
    s.add_argument("--people", choices=["", "none", "single", "multiple"], default="")
    s.add_argument("--about-programming", dest="about_programming",
                    action=argparse.BooleanOptionalAction, default=None)
    s.add_argument("--about-robotics", dest="about_robotics",
                    action=argparse.BooleanOptionalAction, default=None)
    s.add_argument("--ai-altered", dest="ai_altered", action=argparse.BooleanOptionalAction, default=None)
    s.add_argument("--style", default="")
    s.add_argument("--role", default="")
    s.add_argument("--limit", type=int, default=20)

    args = p.parse_args()
    a = vars(args)
    cmd = a.pop("command")

    async_commands = {"generate-image", "evaluate-image", "generate-project-image",
                       "catalog-images", "catalog-projects"}

    dispatch = {
        "list-available": lambda: list_available(),
        "assemble-prompt": lambda: assemble_prompt(**a),
        "generate-image": lambda: generate_image(**a),
        "evaluate-image": lambda: evaluate_image(**a),
        "create-project": lambda: create_project(**a),
        "create-email-project": lambda: create_email_project(**a),
        "save-email-template": lambda: save_email_template(**a),
        "list-projects": lambda: list_projects(),
        "get-project": lambda: get_project(**a),
        "update-project": lambda: update_project(**a),
        "generate-project-image": lambda: generate_project_image(**a),
        "open-project": lambda: open_project(**a),
        "open-projects-home": lambda: open_projects_home(**a),
        "render-project-html": lambda: render_project_html(**a),
        "set-postcard-sides": lambda: set_postcard_sides(**a),
        "set-postcard-regions": lambda: set_postcard_regions(**a),
        "update-postcard-region": lambda: update_postcard_region(**a),
        "set-postcard-extra-html": lambda: set_postcard_extra_html(**a),
        "generate-postcard-pdf": lambda: generate_postcard_pdf(**a),
        "restart-web-server": lambda: restart_web_server(**a),
        "catalog-images": lambda: catalog_images(**a),
        "catalog-projects": lambda: catalog_projects(**a),
        "search-catalog": lambda: search_catalog(**a),
    }

    thunk = dispatch[cmd]
    if cmd in async_commands:
        result = asyncio.run(thunk())
    else:
        result = thunk()
    print(result)


if __name__ == "__main__":
    main()

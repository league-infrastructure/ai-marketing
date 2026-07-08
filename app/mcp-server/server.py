#!/usr/bin/env python3
"""
League Marketing Image Generator — MCP Server

This process is intentionally thin. It owns exactly the things that are genuinely
stateful:
  - restart_web_server: manages the web-server daemon's process lifecycle (PID/port).

Everything else — creating projects, generating images, tuning postcard regions, PDF
export — is a stateless one-shot operation on disk state, and lives in cli.py instead,
reached through the generic run_cli passthrough tool below. That split matters because
this MCP tool surface is cached by the client at connection time: any change to a tool's
presence or signature needs a reconnect to take effect. run_cli's own signature never
changes, so cli.py can be edited and rerun freely, with no reconnect ever required —
only a change to THIS file (a new tool, a changed signature) still needs one.
"""

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

MARKETING_DIR = Path(__file__).resolve().parent.parent.parent
PROJECTS_DIR = MARKETING_DIR / "projects"
CLI_SCRIPT = Path(__file__).resolve().parent / "cli.py"

# Web server daemon lifecycle — see webserver.py and cli.py for the full rationale.
WEBSERVER_SCRIPT = Path(__file__).resolve().parent / "webserver.py"
DEFAULT_STATIC_PORT = 31337  # fixed "weird" port so the gallery URL is stable across restarts
WEBSERVER_STATE_PATH = PROJECTS_DIR / ".webserver.json"  # {"pid": int, "port": int}

mcp = FastMCP("League Image Generator")


def _webserver_status() -> Optional[dict]:
    """Return {"pid","port"} if the daemon's state file names a PID that's alive AND
    actually accepting connections on that port, else None."""
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
        start_new_session=True,  # survives independently of this process's signal group
    )
    for _ in range(50):  # ~5s
        time.sleep(0.1)
        status = _webserver_status()
        if status and status["pid"] == proc.pid:
            return status
    raise RuntimeError("web server daemon did not start within 5s")


@mcp.tool()
def restart_web_server(port: int = 0) -> str:
    """Stop and relaunch the standalone web-server daemon (mcp-server/webserver.py) as a
    fresh subprocess, picking up any code changes to webserver.py or the HTML templates it
    owns (templates/postcard.html.j2) — without restarting this MCP server. Call this after
    editing webserver.py, instead of asking the designer to restart the MCP connection."""
    status = _webserver_status()
    if status:
        try:
            os.kill(status["pid"], signal.SIGTERM)
        except OSError:
            pass
        for _ in range(30):  # ~3s
            time.sleep(0.1)
            if not _webserver_status():
                break
    new_status = _spawn_webserver(port or DEFAULT_STATIC_PORT)
    return json.dumps({"restarted": True, **new_status}, indent=2)


@mcp.tool()
def run_cli(args: list) -> str:
    """Run mcp-server/cli.py — the command-line tool that does everything stateless:
    create/update/list projects, generate images, and configure postcards (sides, text
    regions, PDF export). This tool's own signature never changes, so cli.py can be edited
    and rerun immediately with no MCP reconnect needed, unlike tools defined in this file.

    Args:
        args: Argv to pass to cli.py, e.g. ["list-projects"] or
            ["create-project", "--name", "My Project", "--style", "flat-poster"].
            Run ["<subcommand>", "--help"] to see a subcommand's options, or
            ["--help"] to list all subcommands.
    """
    try:
        proc = subprocess.run(
            [sys.executable, str(CLI_SCRIPT), *[str(a) for a in args]],
            capture_output=True, text=True, timeout=300,
        )
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "cli.py timed out after 300s"})
    if proc.returncode != 0:
        return json.dumps({
            "error": f"cli.py exited {proc.returncode}",
            "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip(),
        })
    return proc.stdout.strip()


if __name__ == "__main__":
    mcp.run()

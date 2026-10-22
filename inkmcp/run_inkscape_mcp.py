#!/usr/bin/env python3
"""
Cross-platform launcher for the Inkscape MCP server.

On first run it creates the virtual environment next to this file and installs
the requirements, then runs ``main.py`` with the environment's interpreter.
Bootstrap output goes to stderr so the MCP stdio channel stays clean.
"""

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV = HERE / "venv"


def venv_python() -> Path:
    if sys.platform == "win32":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def bootstrap() -> None:
    """Create the venv and install requirements when the interpreter is missing."""
    python = venv_python()
    if python.exists():
        return
    print("Creating Python virtual environment...", file=sys.stderr)
    subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True, stdout=sys.stderr)
    subprocess.run(
        [str(python), "-m", "pip", "install", "-r", str(HERE / "requirements.txt")],
        check=True,
        stdout=sys.stderr,
    )


def main() -> int:
    bootstrap()
    cmd = [str(venv_python()), str(HERE / "main.py")]
    if sys.platform == "win32":
        # execv on Windows spawns a new process and exits this one, which breaks
        # the stdio pipes of the MCP host; run the server as a child instead.
        return subprocess.run(cmd, cwd=HERE).returncode
    os.chdir(HERE)
    os.execv(cmd[0], cmd)
    return 0  # unreachable; keeps the signature honest


if __name__ == "__main__":
    sys.exit(main())

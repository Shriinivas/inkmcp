#!/bin/bash
# Inkscape MCP Server launcher for Linux/macOS.
# Exports the D-Bus session address, then delegates to the cross-platform
# Python launcher (venv bootstrap + server start).

set -e

# Change to script directory
cd "$(dirname "$0")"

# Ensure access to the user's D-Bus session bus
# Allow overrides if already provided in the environment
# These following exports are required for sandboxed envs like codex not for Claude
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=${XDG_RUNTIME_DIR}/bus}"

exec python3 run_inkscape_mcp.py "$@"

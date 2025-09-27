#!/bin/bash
# Inkscape MCP Server Wrapper Script
# Activates Python environment and runs the MCP server

set -e

# Change to script directory
cd "$(dirname "$0")"

# Activate Python virtual environment (create if doesn't exist)
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Ensure access to the user's D-Bus session bus
# Allow overrides if already provided in the environment
# These following exports are required for sandboxed envs like codex not for Claude
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=${XDG_RUNTIME_DIR}/bus}"

# Run the Inkscape MCP server
exec python main.py

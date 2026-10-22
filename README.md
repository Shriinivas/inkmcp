# Inkscape MCP Server

A Model Context Protocol (MCP) server that enables live control of Inkscape through natural language instructions. This allows AI assistants like Claude to directly manipulate vector graphics in real-time.

## Features

- 🎯 **Live Instance Control** - Direct manipulation of running Inkscape documents
- ⚡ **Session Bus Integration** - Real-time communication through Inkscape's GLib action bus (D-Bus on Linux, GLib's built-in session bus on Windows)
- 🚀 **Universal Element Creation** - Create any SVG element with unified syntax
- 🏗️ **Hierarchical Scene Management** - Semantic organization with automatic ID collision handling
- 📐 **Python Code Execution** - Run arbitrary inkex code in live context
- 🖼️ **Screenshot Support** - Visual feedback with viewport capture

## Platform Support

- **🐧 Linux** - Uses the D-Bus session bus and the `gdbus` tool (package `libglib2.0-bin` on Debian/Ubuntu)
- **🪟 Windows** - Talks directly to the private session bus that Inkscape's GLib auto-launches (pure Python, no `gdbus.exe`, no extra daemon). Works with the installer, portable and Microsoft Store versions; Inkscape 1.2 or newer. Tested with Inkscape 1.4 (Store)

## Quick Start

### 1. Installation

1. Download `inkmcp-extension.zip` from the latest release
2. Extract it to your Inkscape user extensions directory (shown in Inkscape under Edit > Preferences > System > User extensions):

   Linux:
   ```bash
   cd ~/.config/inkscape/extensions/
   unzip ~/Downloads/inkmcp-extension.zip
   ```

   Windows (PowerShell):
   ```powershell
   Expand-Archive "$env:USERPROFILE\Downloads\inkmcp-extension.zip" "$env:APPDATA\inkscape\extensions\"
   ```

3. Linux only: make the scripts executable
   ```bash
   cd ~/.config/inkscape/extensions/inkmcp
   chmod +x run_inkscape_mcp.sh run_inkscape_mcp.py inkmcpcli.py inkscape_mcp_server.py main.py
   ```

### 2. Start Inkscape

Launch Inkscape normally - the extension is hidden from the menu and only accessible through the action bus. (Re)start Inkscape after installing so it registers the extension action.

### 3. Connect with AI Tools

**Auto-Setup**: The first time an AI client connects, the launcher will automatically:

- Create a Python virtual environment in `<extensions dir>/inkmcp/venv/`
- Install all required dependencies from `requirements.txt`
- Start the MCP server

No manual setup required! Python 3.10+ must be installed (on Windows, make sure `python` is on `PATH`).

Launchers:

- Linux/macOS: `run_inkscape_mcp.sh` (exports the D-Bus session address, then runs the Python launcher)
- Windows: `run_inkscape_mcp.bat`
- Any platform: `python run_inkscape_mcp.py`

The Windows examples below use `C:\Users\USERNAME\AppData\Roaming\inkscape\extensions\inkmcp`; replace it with your extensions directory.

#### Claude Code

Edit your Claude configuration file:

```bash
# ~/.claude/claude-config.json
```

Linux:
```json
{
  "mcpServers": {
    "inkscape": {
      "command": "/home/USERNAME/.config/inkscape/extensions/inkmcp/run_inkscape_mcp.sh"
    }
  }
}
```

Windows:
```json
{
  "mcpServers": {
    "inkscape": {
      "command": "C:\\Users\\USERNAME\\AppData\\Roaming\\inkscape\\extensions\\inkmcp\\run_inkscape_mcp.bat"
    }
  }
}
```

#### Anthropic Claude Desktop

Update Claude desktop app settings:

Linux:
```json
{
  "mcpServers": {
    "inkscape": {
      "command": "/home/USERNAME/.config/inkscape/extensions/inkmcp/run_inkscape_mcp.sh"
    }
  }
}
```

Windows (`%APPDATA%\Claude\claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "inkscape": {
      "command": "python",
      "args": ["C:\\Users\\USERNAME\\AppData\\Roaming\\inkscape\\extensions\\inkmcp\\run_inkscape_mcp.py"]
    }
  }
}
```

#### Google Gemini/Codex

For Gemini, edit settings file:

```bash
# ~/.gemini/settings.json
```

```json
{
  "mcpServers": {
    "inkscape-mcp": {
      "command": "/home/USERNAME/.config/inkscape/extensions/inkmcp/run_inkscape_mcp.sh"
    }
  }
}
```

For Codex, edit configuration:

```bash
# ~/.codex/config.toml
```

```toml
[mcp_servers.inkscape-mcp]
command = "/home/USERNAME/.config/inkscape/extensions/inkmcp/run_inkscape_mcp.sh"
```

On Windows use the Python launcher instead:

```toml
[mcp_servers.inkscape-mcp]
command = "python"
args = ["C:\\Users\\USERNAME\\AppData\\Roaming\\inkscape\\extensions\\inkmcp\\run_inkscape_mcp.py"]
```

## Usage Examples

### With AI Assistant (Claude Code/Gemini/etc) - Requires Running Inkscape

```
"In Inkscape, draw a smooth sine wave starting at the left edge in the middle of the document and apply power stroke path effect to it"
"In Inkscape, create a beautiful logo with a radial gradient circle and elegant typography"
"In Inkscape, draw a mathematical spiral using varying circle sizes with golden ratio"
"In Inkscape, create a house illustration with gable roof, wooden door, and flower garden"
"In Inkscape, design a data visualization chart with bars with hatch fill and labels using current document size"
"In Inkscape, export the current document as high-resolution PNG for presentation"
```

## Available MCP Tools

**inkscape_operation** - Universal tool for all Inkscape operations:

- Create any SVG element (circle, rect, text, path, gradient, etc.)
- Execute Python/inkex code in live context
- Get document/selection information
- Export viewport screenshots
- Hierarchical element creation with groups
- Automatic ID collision handling

## Hybrid Execution

Execute code seamlessly across multiple Python contexts with automatic variable sharing!

### execute-hybrid CLI Command

Interleave local Python execution with Inkscape operations using magic comments:

```python
# @local
import random
points = [(random.randint(10, 200), random.randint(10, 200)) for _ in range(5)]

# @inkscape
for x, y in points:
    circle = Circle()
    circle.set("cx", str(x))
    circle.set("cy", str(y))
    svg.append(circle)
```

**Features:**

- 🔄 Full bidirectional variable flow (Local ↔ Inkscape)
- 🎯 `get_element_by_id()` helper function for reliable element lookup
- ⚠️ Full error tracebacks with fail-fast behavior

**Usage:**

```bash
python inkmcpcli.py execute-hybrid -f script.py
```

### Blender-Inkscape Addon

Transfer curves and data from Blender to Inkscape in real-time!

**Installation:**

1. Blender > Edit > Preferences > Add-ons > Install
2. Select `blender_addon_inkscape_hybrid.py`
3. Enable "Scripting: Inkscape Hybrid Execution"
4. Set INKMCP_CLI_PATH to `/path/to/inkmcp/inkmcpcli.py`

**Usage:**

```python
# @local - Runs in Blender
import bpy
curve = bpy.context.object
segs = [list(pt.co[:2]) for spline in curve.data.splines
        for pt in spline.bezier_points]

# @inkscape - Runs in Inkscape via the action bus
for x, y in segs:
    circle = Circle()
    circle.set("cx", str(x * 100))
    svg.append(circle)
```

Run with: **Text > Run Hybrid Code** (or Ctrl+Shift+H)

**Features:**

- ✨ One-click execution from Blender text editor
- 🔄 Automatic variable serialization
- ⚠️ Helpful warnings for non-serializable Blender objects
- 🎨 Real-time bezier curve transfer to Inkscape

**Example:** `blender_paste_example.py` - Complete bezier curve visualization

**Note:** Blender objects (Vectors, etc.) must be converted to lists for JSON serialization.

See `BLENDER_HYBRID_README.md` for detailed documentation.

## Technical Details

### Architecture

- **Extension**: `inkscape_mcp.py` - Inkscape extension triggered as an application action over the session bus
- **MCP Server**: `inkscape_mcp_server.py` - FastMCP server handling AI requests
- **CLI Client**: `inkmcpcli.py` - Direct command-line interface for testing
- **Operations**: `inkmcpops/` - Modular operation handlers
- **Transport**: `inkmcp/inkscape_bus.py` - calls `org.gtk.Actions` on `org.inkscape.Inkscape`; via `gdbus` on Linux, via a built-in D-Bus client (`nonce-tcp` + `DBUS_COOKIE_SHA1`) on Windows

### Communication Flow

```
AI Assistant → MCP Server → CLI Client → session bus → Inkscape Extension → Live Document
```

## Advanced Usage

### Direct CLI Usage (For Testing/Development)

```bash
# In the inkmcp directory - bypasses AI assistant for direct control

# Basic shapes
python inkmcpcli.py circle "cx=100 cy=100 r=50 fill=red"
python inkmcpcli.py rect "x=0 y=0 width=200 height=100 stroke=blue"

# Gradients
python inkmcpcli.py linearGradient "x1=0 y1=0 x2=200 y2=200 stops='[[\"0%\",\"green\"],[\"50%\",\"yellow\"],[\"100%\",\"red\"]]'"

# Code execution
python inkmcpcli.py execute-code "code='circle = inkex.Circle(); circle.set(\"cx\", \"150\"); circle.set(\"cy\", \"100\"); circle.set(\"r\", \"25\"); svg.append(circle)'"

# Document info
python inkmcpcli.py get-info

# Selection info
python inkmcpcli.py get-selection

# Export screenshot
python inkmcpcli.py export-document-image "format=png max_size=800"
```

### Arbitrary Code Execution

Execute any Python/inkex code in the live Inkscape context:

```python
# Create complex shapes programmatically
code = '''
rect = Rectangle()
rect.set('x', '10')
rect.set('y', '20')
rect.set('width', '100')
rect.set('height', '50')
rect.set('style', 'fill:blue;stroke:red;stroke-width:2')
svg.append(rect)
'''
```

## Troubleshooting

### Common Issues

1. **Cannot reach Inkscape**:
   - Linux: install the GLib tools (`sudo apt install libglib2.0-bin`, provides `gdbus`) and make sure a D-Bus session is running. A custom `gdbus` path can be set with `INKMCP_GDBUS`
   - Windows: "Inkscape is not running (no session bus service)" means no Inkscape window is open; the bus only exists while Inkscape runs. The keyring used for authentication lives in `%USERPROFILE%\.dbus-keyrings` and is created by Inkscape
2. **Extension not triggered**: Check Inkscape is running and the extension is installed; restart Inkscape after installing
3. **Python environment**: If `venv/` was created with a broken install, delete it and reconnect to rebuild it
4. **Permissions (Linux)**: Make sure scripts are executable (`chmod +x *.sh *.py`)
5. **Windows: `python` not found**: Install Python from python.org with "Add to PATH" enabled, or use the full interpreter path as `command`

### Debug Mode

```bash
# Check the bus connection (Linux)
gdbus introspect --session --dest org.inkscape.Inkscape --object-path /org/inkscape/Inkscape

# Check the bus connection (Windows, Inkscape running)
python -c "import inkscape_bus; print(len(inkscape_bus.list_actions()), 'actions')"

# Structured JSON output
python inkmcpcli.py get-info --parse-out --pretty
```

## Development

### Adding New Operations

1. Create new file in `inkmcpops/`
2. Implement `execute(svg, params)` function
3. Add corresponding MCP tool in `inkscape_mcp_server.py`

## License

[GPL-3.0](https://github.com/Shriinivas/inkmcp/blob/main/LICENSE)

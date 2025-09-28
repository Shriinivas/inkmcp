# Inkscape MCP Server

A Model Context Protocol (MCP) server that enables live control of Inkscape through natural language instructions. This allows AI assistants like Claude to directly manipulate vector graphics in real-time.

## Features

- 🎯 **Live Instance Control** - Direct manipulation of running Inkscape documents
- ⚡ **D-Bus Integration** - Real-time communication
- 📐 **Comprehensive API** - From simple shapes to complex inkex Python code
- 🖼️ **Screenshot Support** - Visual feedback with viewport capture

## Platform Support

- **⚠️ Currently Linux Only** - Uses D-Bus which is Linux-specific
- **🔮 Future**: Cross-platform support possible via TCP sockets/named pipes

## Quick Start

### 1. Installation (Linux Only)

1. Go to the [Releases page](https://github.com/Shriinivas/inkmcp/releases)
2. Download `inkmcp-extension.zip` from the latest release
3. Extract it to your Inkscape extensions directory:
   ```bash
   cd ~/.config/inkscape/extensions/
   unzip ~/Downloads/inkmcp-extension.zip
   ```


### 2. Make Scripts Executable

```bash
cd ~/.config/inkscape/extensions/inkmcp
chmod +x run_inkscape_mcp.sh inkmcpcli.py inkscape_mcp_server.py main.py
```

### 3. Start Inkscape
Launch Inkscape normally - the extension is hidden from the menu and only accessible via D-Bus.

### 4. Connect with AI Tools

**Auto-Setup**: The first time an AI client connects, it will automatically:
- Create Python virtual environment in `~/.config/inkscape/extensions/inkmcp/venv/`
- Install all required dependencies from `requirements.txt`
- Start the MCP server

No manual setup required!

#### Claude Code
Edit your Claude configuration file:
```bash
# ~/.claude/claude-config.json
```
```json
{
  "mcpServers": {
    "inkscape": {
      "command": "/home/USERNAME/.config/inkscape/extensions/inkmcp/run_inkscape_mcp.sh"
    }
  }
}
```

#### Anthropic Claude Desktop
Update Claude desktop app settings:
```json
{
  "mcpServers": {
    "inkscape": {
      "command": "/home/USERNAME/.config/inkscape/extensions/inkmcp/run_inkscape_mcp.sh"
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
    "inkscape": {
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
[mcpServers.inkscape]
command = "/home/USERNAME/.config/inkscape/extensions/inkmcp/run_inkscape_mcp.sh"
```

**Replace `USERNAME` with your actual Linux username. Example path:**
- `/home/john/.config/inkscape/extensions/inkmcp/run_inkscape_mcp.sh`

**⚠️ Remember: This currently works on Linux only due to D-Bus requirement.**

## Usage Examples

### With AI Assistant (Claude Code/Gemini/etc) - Requires Running Inkscape
```
"In Inkscape, draw a smooth sine wave starting at the left edge in the middle of the document"
"In Inkscape, create a beautiful logo with a radial gradient circle and elegant typography"
"In Inkscape, draw a mathematical spiral using varying circle sizes with golden ratio"
"In Inkscape, create a house illustration with gable roof, wooden door, and flower garden"
"In Inkscape, design a data visualization chart with gradient bars and labels using current document size"
"In Inkscape, create a sunset scene with linear gradient sky and radial gradient sun"
"In Inkscape, export the current document as high-resolution PNG for presentation"
```

## Available MCP Tools

1. **draw_shape** - Create geometric shapes (rectangle, circle, ellipse, line, polygon, text, path)
2. **create_gradient** - Create linear and radial gradients for fills and strokes
3. **get_selection_info** - Get details about currently selected objects
4. **get_document_info** - Document dimensions, viewBox, element counts
5. **get_object_info** - Detailed object information by ID/name/type
6. **get_object_property** - Get specific properties from objects
7. **execute_inkex_code** - Run arbitrary Python/inkex code in live context
8. **batch_draw** - Execute multiple drawing commands efficiently
9. **get_viewport_screenshot** - Capture current view as PNG

## Technical Details

### Architecture
- **Extension**: `inkscape_mcp.py` - Inkscape extension triggered via D-Bus
- **MCP Server**: `inkscape_mcp_server.py` - FastMCP 2.0 based server
- **CLI Client**: `inkmcpcli.py` - Direct command-line interface
- **Operations**: `inkmcpops/` - Modular operation handlers

### Communication Flow
```
AI Assistant → MCP Server → CLI Client → D-Bus → Inkscape Extension → Live Document
```

## Advanced Usage

### Direct CLI Usage (For Testing/Development)
```bash
# In the inkmcp directory - bypasses AI assistant for direct control

# Basic shapes
./inkmcpcli.py "circle cx=100 cy=100 r=50 fill=red"
./inkmcpcli.py "rectangle x=0 y=0 width=200 height=100 stroke=blue"

# Gradients (returns gradient ID for use in fills)
./inkmcpcli.py "radial-gradient cx=100 cy=100 r=50 stops='[[\"0%\",\"blue\"],[\"100%\",\"red\"]]'"
./inkmcpcli.py "linear-gradient x1=0 y1=0 x2=200 y2=200 stops='[[\"0%\",\"green\"],[\"50%\",\"yellow\"],[\"100%\",\"red\"]]'"

# Using gradients in shapes
./inkmcpcli.py "circle cx=100 cy=100 r=75 fill='url(#radialGradient1)'"

# Complex code execution
./inkmcpcli.py "execute-inkex-code code='circle = Circle(); circle.set(\"cx\", \"150\"); svg.append(circle)'"
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

### Batch Operations
```bash
./inkmcpcli.py "rectangle x=0 y=0 width=50 height=50; circle cx=100 cy=100 r=30"
```

## Troubleshooting

### Common Issues

1. **D-Bus not found**: Ensure you're on Linux with D-Bus session running
2. **Extension not triggered**: Check Inkscape is running and extension is installed
3. **Python environment**: Ensure virtual environment is activated with dependencies
4. **Permissions**: Make sure scripts are executable (`chmod +x *.sh *.py`)

### Debug Mode
```bash
# Check D-Bus connection
gdbus introspect --session --dest org.inkscape.Inkscape --object-path /org/inkscape/Inkscape

# Verbose CLI output
./inkmcpcli.py "get-info" --parse-out --pretty
```

## Development

### Adding New Operations
1. Create new file in `inkmcpops/`
2. Implement `execute(svg, params)` function
3. Add corresponding MCP tool in `inkscape_mcp_server.py`


## License

[GPL-3.0](https://github.com/Shriinivas/inkmcp/blob/main/LICENSE)


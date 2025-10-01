# Inkscape MCP Server

A Model Context Protocol (MCP) server that enables live control of Inkscape through natural language instructions. This allows AI assistants like Claude to directly manipulate vector graphics in real-time.

## Features

- 🎯 **Live Instance Control** - Direct manipulation of running Inkscape documents
- ⚡ **D-Bus Integration** - Real-time communication
- 🚀 **Universal Element Creation** - Create any SVG element with unified syntax
- 🏗️ **Hierarchical Scene Management** - Semantic organization with automatic ID collision handling
- 📐 **Python Code Execution** - Run arbitrary inkex code in live context
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

**inkscape_operation** - Universal tool for all Inkscape operations:
- Create any SVG element (circle, rect, text, path, gradient, etc.)
- Execute Python/inkex code in live context
- Get document/selection information
- Export viewport screenshots
- Hierarchical element creation with groups
- Automatic ID collision handling

## Technical Details

### Architecture
- **Extension**: `inkscape_mcp.py` - Inkscape extension triggered via D-Bus
- **MCP Server**: `inkscape_mcp_server.py` - FastMCP server handling AI requests
- **CLI Client**: `inkmcpcli.py` - Direct command-line interface for testing
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

1. **D-Bus not found**: Ensure you're on Linux with D-Bus session running
2. **Extension not triggered**: Check Inkscape is running and extension is installed
3. **Python environment**: Ensure virtual environment is activated with dependencies
4. **Permissions**: Make sure scripts are executable (`chmod +x *.sh *.py`)

### Debug Mode
```bash
# Check D-Bus connection
gdbus introspect --session --dest org.inkscape.Inkscape --object-path /org/inkscape/Inkscape

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


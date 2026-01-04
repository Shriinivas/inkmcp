# Blender-Inkscape Hybrid Execution

Run hybrid scripts that execute code in both Blender and Inkscape with seamless variable sharing.

## Setup

**IMPORTANT: Set environment variable before running Blender**
```bash
export INKMCP_CLI_PATH="/path/to/inkmcp/inkmcp/inkmcpcli.py"
blender
```

The script will auto-detect `blender_inkscape_hybrid.py` from common locations if they're in the same directory.

1. Update the path in `blender_inkscape_hybrid.py`:
   ```python
   INKMCP_CLI_PATH = "/path/to/inkmcp/inkmcpcli.py"
   ```

2. Make sure Inkscape is running with the MCP extension enabled

## Usage in Blender

### Method 1: Run from Text Editor

1. Open Blender
2. Open Text Editor (Shift+F11)
3. Load `blender_inkscape_hybrid.py`
4. Run it once (Alt+P) to register the hybrid executor
5. Create a new text file for your hybrid script
6. Write your hybrid code with magic comments:
   ```python
   # @local
   # Code here runs in Blender (has bpy, bpy.context, etc.)
   
   # @inkscape
   # Code here runs in Inkscape (has svg, Circle, etc.)
   ```
7. Load and run `blender_inkscape_hybrid.py` again
8. It will execute the active text file as a hybrid script

### Method 2: Self-Executing Script

**IMPORTANT**: Wrap your hybrid code in a triple-quoted string to prevent parsing errors.

Create a script that includes the hybrid executor:

```python
HYBRID_CODE = """
# Your hybrid code here
# @local
import bpy
vertices = [(v.co.x, v.co.y) for v in bpy.context.active_object.data.vertices[:5]]

# @inkscape
for x, y in vertices:
    circle = Circle()
    circle.set("cx", str(x * 100))
    svg.append(circle)
"""

# Execute hybrid code
exec(open('/path/to/blender_inkscape_hybrid.py').read())

if __name__ == "__main__":
    execute_hybrid(HYBRID_CODE)
```

See `blender_self_executing_example.py` for a complete working example.

## Magic Comments

- `# @local` - Execute in Blender Python context
  - Has access to: `bpy`, `bpy.context` (aliased as `C`), `bpy.data` (aliased as `D`)
  - All standard Python libraries
  
- `# @inkscape` - Execute in Inkscape Python context
  - Has access to: `svg`, `inkex`, `Circle`, `Rectangle`, etc.
  - Variables from `@local` blocks are automatically injected

## Variable Flow

Variables flow bidirectionally:
- Blender → Inkscape: Variables created in `@local` are available in `@inkscape`
- Inkscape → Blender: Currently output-only (full bidirectional coming soon)

## Example

See `blender_example.py` for a complete example that:
1. Extracts vertices from a Blender mesh
2. Creates circles in Inkscape at those positions
3. Reports back in Blender

## Limitations

- Only JSON-serializable types can be shared between contexts
- Inkscape → Blender variable flow requires CLI update (coming soon)
- Blender objects (bpy types) cannot be passed to Inkscape

## Troubleshooting

**"No text file is active"**
- Make sure you have a text file open in the Text Editor
- The script must be run from the Text Editor space

**"Failed to call Inkscape"**
- Check that INKMCP_CLI_PATH is correct
- Ensure Inkscape is running with MCP extension

**Variables not passing**
- Check that variables are JSON-serializable (no Blender/Inkscape objects)
- Use `print()` in each block to debug variable values

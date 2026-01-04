"""
Example: Blender-Inkscape Hybrid Script
This demonstrates using Blender vertices to create circles in Inkscape

Instructions:
1. Open Blender
2. Create a mesh object (e.g., a cube or sphere)
3. Select it
4. Open Text Editor
5. Load blender_inkscape_hybrid.py
6. Run it (Alt+P)
7. Then load THIS file
8. Run it (Alt+P)

The script will:
- Extract vertex positions from the active Blender object
- Create circles in Inkscape at those positions
"""

# @local
# Get vertices from active Blender object
import bpy

obj = bpy.context.active_object
if obj and obj.type == 'MESH':
    # Get first 8 vertices (or fewer if object has less)
    vertices = [(v.co.x, v.co.y, v.co.z) for v in obj.data.vertices[:8]]
    print(f"Extracted {len(vertices)} vertices from '{obj.name}'")
else:
    print("Please select a mesh object!")
    vertices = [(0, 0, 0)]  # Fallback

# @inkscape
# Create circles in Inkscape based on Blender vertices
print(f"Creating {len(vertices)} circles in Inkscape...")

for i, (x, y, z) in enumerate(vertices):
    circle = Circle()
    # Scale and offset for visibility
    circle.set("cx", str(x * 100 + 300))
    circle.set("cy", str(-y * 100 + 300))  # Flip Y for SVG
    circle.set("r", "10")
    circle.set("fill", f"hsl({i * 45}, 70%, 50%)")
    circle.set("id", f"vertex_{i}")
    svg.append(circle)

print(f"Created {len(vertices)} circles")

# @local
# Report back in Blender
import bpy
print(f"Visualization complete in Inkscape!")
print(f"Object: {obj.name if 'obj' in dir() and obj else 'N/A'}")

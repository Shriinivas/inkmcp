# Paste this directly into Blender Text Editor and run (Alt+P)
# IMPORTANT: Set INKMCP_CLI_PATH before running Blender:
#   export INKMCP_CLI_PATH=/path/to/inkmcp/inkmcp/inkmcpcli.py

# @local
import bpy
vertices = []
curve = bpy.context.object

segs = []
for spline in curve.data.splines:
    for pt_info in spline.bezier_points:
        left = pt_info.handle_left
        right = pt_info.handle_right
        pt = pt_info.co
        segs.append([left, pt, right])
        
print(list(list(co)[:2] for seg in segs for co in seg))

# @inkscape
# Access segs from Blender block
print(f"Received {len(segs)} segments from Blender")

new_id = svg.get_unique_id("circle")
circle = inkex.Circle()
circle.set("cx", "100")
circle.set("cy", "100")
circle.set("r", "30")
circle.set("fill", "blue")
circle.set("stroke", "green")
circle.set("id", new_id)
svg.append(circle)

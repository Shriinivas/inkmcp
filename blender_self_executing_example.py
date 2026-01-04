# Self-executing hybrid script for Blender
# Put your hybrid code in the HYBRID_CODE string below

HYBRID_CODE = """
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
new_id = svg.get_unique_id("circle")
circle = inkex.Circle()
circle.set("cx", "100")
circle.set("cy", "100")
circle.set("r", "30")
circle.set("fill", "blue")
circle.set("stroke", "green")
circle.set("id", new_id)
svg.append(circle)
"""

# Execute the hybrid code
# IMPORTANT: Set INKMCP_CLI_PATH environment variable before running Blender:
#   export INKMCP_CLI_PATH=/path/to/inkmcp/inkmcp/inkmcpcli.py
#   blender
import sys
import os

# Auto-detect path to blender_inkscape_hybrid.py (assumes same directory)
script_dir = os.path.dirname(os.path.abspath(__file__))
hybrid_executor = os.path.join(script_dir, 'blender_inkscape_hybrid.py')

if not os.path.exists(hybrid_executor):
    print("ERROR: Cannot find blender_inkscape_hybrid.py")
    print(f"Expected at: {hybrid_executor}")
else:
    # Import and run the executor
    exec(open(hybrid_executor).read())

# Override the main execution to use our HYBRID_CODE
if __name__ == "__main__":
    execute_hybrid(HYBRID_CODE)

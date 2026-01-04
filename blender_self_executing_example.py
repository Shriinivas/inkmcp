# Blender Bezier Curve → Inkscape SVG Path
# Select a bezier curve in Blender and run this script to create the same curve in Inkscape!
# IMPORTANT: Set INKMCP_CLI_PATH before running Blender:
#   export INKMCP_CLI_PATH=/path/to/inkmcp/inkmcp/inkmcpcli.py

# IMPORTANT: Start HYBRID_CODE with a magic comment (# @local or # @inkscape)
# to prevent the first line from being treated as executable code
HYBRID_CODE = """# @local
import bpy

# Get the selected curve object
curve = bpy.context.object

if not curve or curve.type != 'CURVE':
    print("ERROR: Please select a curve object")
    segs = []
else:
    # Extract bezier segments
    segs = []
    for spline in curve.data.splines:
        for pt_info in spline.bezier_points:
            left = list(pt_info.handle_left[:2])   # Convert to 2D
            pt = list(pt_info.co[:2])
            right = list(pt_info.handle_right[:2])
            segs.append([left, pt, right])
    
    print(f"Extracted {len(segs)} bezier points from '{curve.name}'")

# @inkscape
# Convert bezier segments to SVG path
if not segs:
    print("No curve data to process")
else:
    # Build SVG path data
    # Format: M x,y C x1,y1 x2,y2 x,y ...
    path_data = []
    
    for i, (left, pt, right) in enumerate(segs):
        if i == 0:
            # Move to first point
            path_data.append(f"M {pt[0]*100},{-pt[1]*100}")
        else:
            # Previous point's right handle, this point's left handle, this point
            prev_right = segs[i-1][2]
            path_data.append(f"C {prev_right[0]*100},{-prev_right[1]*100} {left[0]*100},{-left[1]*100} {pt[0]*100},{-pt[1]*100}")
    
    # Create path element
    path = PathElement()
    path.set("id", svg.get_unique_id("bezier_path"))
    path.set("d", " ".join(path_data))
    path.set("fill", "none")
    path.set("stroke", "blue")
    path.set("stroke-width", "2")
    svg.append(path)
    
    print(f"Created SVG path with {len(segs)} segments")

# @local
print("Bezier curve successfully transferred to Inkscape!")
"""

# Execute the hybrid code
# Derive blender_inkscape_hybrid.py path from INKMCP_CLI_PATH
import sys
import os

inkmcp_cli = os.environ.get("INKMCP_CLI_PATH")
if not inkmcp_cli:
    print("ERROR: INKMCP_CLI_PATH environment variable not set")
    print("Please run: export INKMCP_CLI_PATH=/path/to/inkmcp/inkmcp/inkmcpcli.py")
else:
    inkmcp_dir = os.path.dirname(os.path.dirname(inkmcp_cli))
    hybrid_executor = os.path.join(inkmcp_dir, "blender_inkscape_hybrid.py")

    if not os.path.exists(hybrid_executor):
        print(f"ERROR: Cannot find blender_inkscape_hybrid.py at: {hybrid_executor}")
    else:
        exec(open(hybrid_executor).read())

if __name__ == "__main__":
    execute_hybrid(HYBRID_CODE)

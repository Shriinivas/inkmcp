# Paste this directly into Blender Text Editor and run with Text > Run Hybrid Code
# IMPORTANT: Set INKMCP_CLI_PATH in addon preferences first
# Select a bezier curve in Blender before running

# @local
import bpy

# Get the selected curve object
curve = bpy.context.object

if not curve or curve.type != 'CURVE':
    print("ERROR: Please select a curve object")
    segs = []
else:
    # Extract bezier segments and convert to 2D lists
    segs = []
    for spline in curve.data.splines:
        for pt_info in spline.bezier_points:
            left = list(pt_info.handle_left[:2])   # Convert Vector to list, take x,y only
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
    scale = 100  # Scale factor for visibility
    
    for i, (left, pt, right) in enumerate(segs):
        if i == 0:
            # Move to first point
            path_data.append(f"M {pt[0]*scale},{-pt[1]*scale}")
        else:
            # Cubic bezier: previous point's right handle, this point's left handle, this point
            prev_right = segs[i-1][2]
            path_data.append(f"C {prev_right[0]*scale},{-prev_right[1]*scale} {left[0]*scale},{-left[1]*scale} {pt[0]*scale},{-pt[1]*scale}")
    
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
print(f"✓ Bezier curve '{curve.name if curve else 'N/A'}' transferred to Inkscape!")

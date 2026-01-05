# Paste this directly into Blender Text Editor and run
# Select a bezier curve in Blender before running

# @local
import bpy
from mathutils import Matrix, Vector
import numpy as np


def get_best_fit_matrix(coords):
    pts = np.array(coords)
    centroid = Vector(np.mean(pts, axis=0))
    centered = pts - np.mean(pts, axis=0)
    _, _, vh = np.linalg.svd(centered)

    # 1. Get the Normal
    normal = Vector(vh[2]).normalized()
    if normal.dot(Vector((0, 0, 1))) < 0:
        normal *= -1

    # 2. Stable Axes (Align Local X with World X)
    world_x = Vector((1, 0, 0))
    if abs(normal.dot(world_x)) > 0.9:
        world_x = Vector((0, 1, 0))

    local_x = (world_x - normal * world_x.dot(normal)).normalized()
    local_y = normal.cross(local_x).normalized()

    rot_matrix = Matrix((local_x, local_y, normal)).transposed()
    return Matrix.LocRotScale(centroid, rot_matrix, None)


# --- Execution ---
obj = bpy.context.object
curve_name = "N/A"
all_splines_data = []

if not obj or obj.type != "CURVE":
    print("ERROR: Please select a curve object")
else:
    curve_name = obj.name
    mw = obj.matrix_world

    # 1. Collect ALL world points for the Best-Fit calculation
    all_pts_world = []
    for spline in obj.data.splines:
        for p in spline.bezier_points:
            all_pts_world.extend([mw @ p.co, mw @ p.handle_left, mw @ p.handle_right])

    # 2. Calculate the Plane Matrix
    m_plane = get_best_fit_matrix(all_pts_world)
    m_plane_inv = m_plane.inverted()

    # 3. Process each spline separately
    for spline in obj.data.splines:
        if spline.type == "BEZIER":
            current_spline = {"points": [], "is_cyclic": spline.use_cyclic_u}
            for p in spline.bezier_points:
                # Transform World -> Plane Local (Z becomes 0)
                loc_l = m_plane_inv @ (mw @ p.handle_left)
                loc_co = m_plane_inv @ (mw @ p.co)
                loc_r = m_plane_inv @ (mw @ p.handle_right)

                current_spline["points"].append(
                    [[loc_l.x, loc_l.y], [loc_co.x, loc_co.y], [loc_r.x, loc_r.y]]
                )
            all_splines_data.append(current_spline)

    print(f"Extracted {len(all_splines_data)} splines from '{curve_name}'")

# @inkscape
# Create a proper composite SVG path
if not all_splines_data:
    print("No curve data to process")
else:
    path_segments = []
    scale = 100  # Scale factor for visibility

    for spline in all_splines_data:
        pts = spline["points"]
        if not pts:
            continue

        # Start the sub-path at the first point's 'co'
        start_co = pts[0][1]
        subpath = [f"M {start_co[0] * scale},{-start_co[1] * scale}"]

        # Add segments between points
        for i in range(1, len(pts)):
            prev_right = pts[i - 1][2]
            curr_left = pts[i][0]
            curr_co = pts[i][1]
            subpath.append(
                f"C {prev_right[0] * scale},{-prev_right[1] * scale} "
                f"{curr_left[0] * scale},{-curr_left[1] * scale} "
                f"{curr_co[0] * scale},{-curr_co[1] * scale}"
            )

        # Handle the closing segment if the spline is cyclic
        if spline["is_cyclic"]:
            prev_right = pts[-1][2]
            start_left = pts[0][0]
            start_co = pts[0][1]
            subpath.append(
                f"C {prev_right[0] * scale},{-prev_right[1] * scale} "
                f"{start_left[0] * scale},{-start_left[1] * scale} "
                f"{start_co[0] * scale},{-start_co[1] * scale}"
            )
            subpath.append("Z")

        path_segments.append(" ".join(subpath))

    # Join all sub-paths into one 'd' attribute
    full_path_data = " ".join(path_segments)

    # Create the SVG path element
    path = PathElement()
    path.set("id", svg.get_unique_id("blender_bezier"))
    path.set("d", full_path_data)
    path.set("fill", "none")
    path.set("stroke", "black")
    path.set("stroke-width", "1")
    svg.append(path)

# @local
if all_splines_data:
    print(f"✓ Composite Bezier curve '{curve_name}' successfully created in Inkscape!")

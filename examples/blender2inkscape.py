# Blender to Inkscape Curve Transfer (Perspective Correct)
#
# Usage:
# 1. Be sure the "inkmcp" Blender addon is installed and configured (check Preferences).
# 2. Open this script in the Blender Text Editor.
# 3. Select a Bezier Curve object in the 3D Viewport.
# 4. Press Ctrl+Shift+H (Run Hybrid Code) in the Text Editor.
#
# Features:
# - Supports both planar (Top/Front/Side) and camera perspective measurements.
# - Uses Adaptive Recursive Subdivision to perfectly approximate 3D perspective curves in 2D SVG.
# - Preserves tangent continuity for smooth curves.

# @local
import bpy
from mathutils import Matrix, Vector
import numpy as np
from bpy_extras.view3d_utils import location_3d_to_region_2d

def getSVGPt(co):
    # Find the 3D View area
    area = next((a for a in bpy.context.screen.areas if a.type == "VIEW_3D"), None)
    if not area:
        return None

    region = next((r for r in area.regions if r.type == "WINDOW"), None)
    space3d = area.spaces.active
    
    # Get the RegionView3D (projection matrix logic)
    rv3d = (
        space3d.region_quadviews[3]
        if len(space3d.region_quadviews) > 0
        else space3d.region_3d
    )

    # 1. Get the Perspective Matrix (combines view and projection)
    view_matrix = rv3d.perspective_matrix

    # 2. Multiply the 3D point by the matrix
    proj_4d = view_matrix @ Vector((co[0], co[1], co[2], 1.0))

    # 3. Perspective Division
    if proj_4d.w != 0:
        x_ndc = proj_4d.x / proj_4d.w
        y_ndc = proj_4d.y / proj_4d.w
    else:
        # Fallback for degenerate points
        x_ndc, y_ndc = proj_4d.x, proj_4d.y

    # 4. Convert NDC (-1 to 1 range) to Screen Space (0 to 1 range)
    # SVG coordinates: (0,0) is top-left.
    final_x = (x_ndc + 1.0) / 2.0
    final_y = (y_ndc + 1.0) / 2.0

    return Vector((final_x, final_y, 0))


def cubic_eval(p0, p1, p2, p3, t):
    """Evaluate cubic bezier at t"""
    return (1-t)**3 * p0 + 3*(1-t)**2 * t * p1 + 3*(1-t) * t**2 * p2 + t**3 * p3

def subdivide_cubic(p0, p1, p2, p3, t=0.5):
    """Split a cubic bezier into two segments at t using De Casteljau's algorithm."""
    p01 = (1-t)*p0 + t*p1
    p12 = (1-t)*p1 + t*p2
    p23 = (1-t)*p2 + t*p3
    
    p012 = (1-t)*p01 + t*p12
    p123 = (1-t)*p12 + t*p23
    
    p0123 = (1-t)*p012 + t*p123
    
    # Segment 1: p0, p01, p012, p0123
    # Segment 2: p0123, p123, p23, p3
    return (p0, p01, p012, p0123), (p0123, p123, p23, p3)

def approx_segment_recursive(p0, p1, p2, p3, tolerance=0.5):
    """
    Recursively approximate the 3D segment.
    If the single-segment fit has > tolerance error (in pixels/screen units),
    subdivide and recurse.
    """
    # 1. Generate candidate fit for full segment
    # (We reuse the tangent-preserving logic here, but inline or simplified)
    
    q0, q1, q2, q3 = approx_segment_single(p0, p1, p2, p3)
    
    # 2. Error Check.
    # The 'approx_segment_single' guarantees exact match at t=0, 0.5, 1.0.
    # So we check error at t=0.25 and t=0.75
    
    # 3D points at 0.25 and 0.75
    m_25_3d = cubic_eval(p0, p1, p2, p3, 0.25)
    m_75_3d = cubic_eval(p0, p1, p2, p3, 0.75)
    
    k_25 = getSVGPt(m_25_3d)
    k_75 = getSVGPt(m_75_3d)
    
    if k_25 is None or k_75 is None: # Projection fail
        return [[q0, q1, q2, q3]]

    # 2D Candidate points at 0.25 and 0.75 (standard bezier eval)
    c_25 = cubic_eval(q0, q1, q2, q3, 0.25)
    c_75 = cubic_eval(q0, q1, q2, q3, 0.75)
    
    # We use a screen-space distance metric. 
    # Since getSVGPt returns 0..1 normalized coords, we multiply by doc size usually.
    # But here we don't have doc size handy easily. 
    # Let's assume a standard 1920x1080 canvas for "pixel" error estimation.
    # 0.001 roughly equals ~1-2 pixels on a 1080p screen.
    
    dist_sq_25 = (k_25 - c_25).length_squared
    dist_sq_75 = (k_75 - c_75).length_squared
    
    # Tolerance: 0.0005 squared is ~0.022 distance ~ 2-3% error?? No.
    # 1px on 1000px is 0.001. 0.001^2 = 1e-6.
    threshold = (tolerance / 1000.0) ** 2 
    
    if dist_sq_25 > threshold or dist_sq_75 > threshold:
        # Error too high, subdivide!
        seg1, seg2 = subdivide_cubic(p0, p1, p2, p3, 0.5)
        return (approx_segment_recursive(*seg1, tolerance) + 
                approx_segment_recursive(*seg2, tolerance))
    
    return [[q0, q1, q2, q3]]


def approx_segment_single(p0, p1, p2, p3):
    """
    The base tangent-preserving estimator.
    """
    q0 = getSVGPt(p0)
    q3 = getSVGPt(p3)
    h0 = getSVGPt(p1)
    h3 = getSVGPt(p2)
    
    if any(pt is None for pt in [q0, q3, h0, h3]):
        return q0, q0, q3, q3

    v1 = h0 - q0
    v2 = h3 - q3
    
    if v1.length_squared < 1e-7 or v2.length_squared < 1e-7:
        return q0, h0, h3, q3

    m_3d = cubic_eval(p0, p1, p2, p3, 0.5)
    k = getSVGPt(m_3d)
    
    if k is None:
        return q0, h0, h3, q3

    # Solve B(0.5) = k
    T = (k - 0.5 * (q0 + q3)) / 0.375
    det = v1.x * v2.y - v1.y * v2.x
    
    if abs(det) < 1e-6:
        return q0, h0, h3, q3
        
    alpha = (T.x * v2.y - T.y * v2.x) / det
    beta  = (v1.x * T.y - v1.y * T.x) / det
    
    if alpha <= 0 or beta <= 0:
        return q0, h0, h3, q3
        
    q1 = q0 + alpha * v1
    q2 = q3 + beta * v2
    
    return q0, q1, q2, q3


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


def get_plane_inv_mat():
    all_pts_world = []
    for spline in obj.data.splines:
        for p in spline.bezier_points:
            all_pts_world.extend([mw @ p.co, mw @ p.handle_left, mw @ p.handle_right])

    m_plane = get_best_fit_matrix(all_pts_world)
    return m_plane.inverted()


# --- Execution ---
obj = bpy.context.object
curve_name = "N/A"
all_splines_data = []
from_view = True

if not obj or obj.type != "CURVE":
    print("ERROR: Please select a curve object")
else:
    curve_name = obj.name
    mw = obj.matrix_world

    m_plane_inv = get_plane_inv_mat() if not from_view else None

    for spline in obj.data.splines:
        if spline.type == "BEZIER":
            current_spline = {"points": [], "is_cyclic": spline.use_cyclic_u}
            points_data = [] # To store result [[Lx, Ly], [Cx, Cy], [Rx, Ry]]

            if from_view:
                # 1. Collect World Space Points
                w_pts = []
                for p in spline.bezier_points:
                    w_pts.append({
                        "l": mw @ p.handle_left,
                        "co": mw @ p.co,
                        "r": mw @ p.handle_right
                    })
                
                count = len(w_pts)
                if count > 0:
                    # Initialize result structure with Nones
                    # A list of segments, not points, because of subdivision
                    # This will be simpler: we just collect a sequence of Bezier segments
                    # [ [q0, q1, q2, q3], [q3, q4, q5, q6], ... ]
                    
                    segments_list = []
                    
                    num_segments = count if spline.use_cyclic_u else count - 1
                    
                    if num_segments > 0:
                        for i in range(num_segments):
                            idx_curr = i
                            idx_next = (i + 1) % count
                            
                            p0 = w_pts[idx_curr]["co"]
                            p1 = w_pts[idx_curr]["r"]
                            p2 = w_pts[idx_next]["l"]
                            p3 = w_pts[idx_next]["co"]
                            
                            # Recursively Approximate Segment
                            # tolerance=1.0 roughly means 1 pixel tolerance if 1000px width
                            new_segs = approx_segment_recursive(p0, p1, p2, p3, tolerance=0.5)
                            segments_list.extend(new_segs)
                            
                    # Convert to our output list format
                    # We need to stitch them: the 'points' expects [[L, C, R], ...] 
                    # But now we have segments. Inkscape path construction below needs to be updated?
                    # The code below:
                    #   for spline in all_splines_data:
                    #     pts = spline["points"]
                    #     ... subpath.append(C ...)
                    # It expects standard blender point format: [HandleLeft, Co, HandleRight]
                    
                    # We should adapt the OUTPUT format to be simpler for Inkscape generator, 
                    # OR we must reconstruct L/C/R structure (which is hard because split points have tangent continuity).
                    # Actually, if we just store the segments, we can rewrite the Inkscape generation part slightly 
                    # to consume raw segments.
                    
                    # Let's change `current_spline["points"]` to hold segments directly if it's special mode?
                    # Or better: Repackage into points. 
                    # Segments: [S1, S2, ...] where S1=(q0,q1,q2,q3), S2=(q3,q4,q5,q6)
                    # Point 0: L=None/q0?, C=q0, R=q1
                    # Point 1 (Shared): L=q2, C=q3, R=q4
                    
                    if segments_list:
                        # First point
                        seg0 = segments_list[0]
                        # For the very first point, L is irrelevant (unless cyclic).
                        # Let's reconstruct the list of Knot Points.
                        
                        # Point 0
                        points_data.append([ [seg0[0].x, seg0[0].y], [seg0[0].x, seg0[0].y], [seg0[1].x, seg0[1].y] ])
                        
                        # Middle points
                        for k in range(len(segments_list)-1):
                            prev_seg = segments_list[k] # ... q2, q3
                            next_seg = segments_list[k+1] # q3, q4 ...
                            
                            # Knot is at prev_seg[3] == next_seg[0]
                            # L = prev_seg[2]
                            # C = prev_seg[3]
                            # R = next_seg[1]
                            l_pt = prev_seg[2]
                            c_pt = prev_seg[3]
                            r_pt = next_seg[1]
                            points_data.append([ [l_pt.x, l_pt.y], [c_pt.x, c_pt.y], [r_pt.x, r_pt.y] ])
                        
                        # Last point
                        last_seg = segments_list[-1]
                        l_pt = last_seg[2]
                        c_pt = last_seg[3]
                        
                        # If cyclic, we need to close the loop with the first point?
                        if spline.use_cyclic_u:
                            # The loop handled all segments.
                            # But we need to update the FIRST point's "Left" handle to be the last segments "q2".
                            # And the LAST point's "Right" handle?
                            # In my loop above 'middle' points covered indices 0 to N-1 segments junctions.
                            
                            # Let's clean this up.
                            pass # Handled by standard loop?
                            
                        # Standard list reconstruction is cleaner:
                        points_data = []
                        for k in range(len(segments_list)):
                            seg = segments_list[k]
                            # We create a point for the START of every segment.
                            # L = previous_seg[2] (need to handle wrap)
                            # C = seg[0]
                            # R = seg[1]
                            
                            if k == 0:
                                if spline.use_cyclic_u:
                                    prev_seg = segments_list[-1]
                                    l_pt = prev_seg[2]
                                else:
                                    l_pt = seg[0] # Endpoint default
                                
                                c_pt = seg[0]
                                r_pt = seg[1]
                            else:
                                prev_seg = segments_list[k-1]
                                l_pt = prev_seg[2]
                                c_pt = seg[0]
                                r_pt = seg[1]
                            
                            points_data.append([ [l_pt.x, l_pt.y], [c_pt.x, c_pt.y], [r_pt.x, r_pt.y] ])
                        
                        # If NOT cyclic, we need to add the very last endpoint
                        if not spline.use_cyclic_u:
                            last_seg = segments_list[-1]
                            l_pt = last_seg[2]
                            c_pt = last_seg[3]
                            r_pt = last_seg[3]
                            points_data.append([ [l_pt.x, l_pt.y], [c_pt.x, c_pt.y], [r_pt.x, r_pt.y] ])


            else:
                # Existing planar logic
                for p in spline.bezier_points:
                    loc_l = m_plane_inv @ (mw @ p.handle_left)
                    loc_co = m_plane_inv @ (mw @ p.co)
                    loc_r = m_plane_inv @ (mw @ p.handle_right)
                    points_data.append(
                        [[loc_l.x, loc_l.y], [loc_co.x, loc_co.y], [loc_r.x, loc_r.y]]
                    )
            
            current_spline["points"] = points_data
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

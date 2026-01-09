# @inkscape
import inkex
from math import sqrt


def export_to_blender_cleaned():
    selection = svg.selection
    if not selection:
        return []

    export_data = []
    scale = 0.01

    for i, elem in enumerate(selection.values()):
        # Style and metadata setup...
        obj_data = {
            "name": elem.get_id(),
            "color": str(elem.style.get("fill", "#000000")),
            "alpha": float(elem.style.get("opacity", 1.0)),
            "z_offset": i * 0.005,
            "splines": [],
        }

        path_obj = elem.to_path_element()
        superpath = path_obj.path.to_absolute().to_superpath()

        # Check if Inkscape path actually ends with 'Z'
        path_cmds = path_obj.path.to_arrays()
        is_cyclic = len(path_cmds) > 0 and path_cmds[-1][0] == "Z"

        for subpath in superpath:
            # node format: [ [handle_in], [anchor], [handle_out] ]

            # --- THE FIX: Merge closing node if it overlaps start node ---
            if is_cyclic and len(subpath) > 1:
                p_start = subpath[0][1]
                p_end = subpath[-1][1]

                # Calculate distance between first and last anchor
                dist = sqrt((p_start[0] - p_end[0]) ** 2 + (p_start[1] - p_end[1]) ** 2)

                if dist < 0.01:  # Tolerance for floating point noise
                    # The last node is redundant.
                    # We take its 'handle_in' and give it to the first node
                    redundant_node = subpath.pop()
                    subpath[0][0] = redundant_node[0]

            current_spline_points = []
            for node in subpath:
                current_spline_points.append(
                    {
                        "co": [node[1][0] * scale, -node[1][1] * scale],
                        "l": [node[0][0] * scale, -node[0][1] * scale],
                        "r": [node[2][0] * scale, -node[2][1] * scale],
                    }
                )

            obj_data["splines"].append(
                {"points": current_spline_points, "is_cyclic": is_cyclic}
            )

        export_data.append(obj_data)
    return export_data


data = export_to_blender_cleaned()
print(repr(data))

# @local
import bpy
from mathutils import Vector


def hex_to_rgb(hex_str, alpha=1.0):
    if not hex_str.startswith("#"):
        return (0, 0, 0, alpha)
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = "".join([c * 2 for c in h])
    return [int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4)] + [alpha]


def create_blender_curves(data):
    for entry in data:
        curve_res = bpy.data.curves.new(name=entry["name"], type="CURVE")
        curve_res.dimensions = "2D"
        curve_res.fill_mode = "BOTH"
        curve_res.extrude = 0.001

        obj = bpy.data.objects.new(entry["name"], curve_res)
        bpy.context.collection.objects.link(obj)
        obj.location.z = entry["z_offset"]

        # Material setup
        mat_name = f"Ink_{entry['color']}"
        mat = bpy.data.materials.get(mat_name)
        if not mat:
            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = True
            mat.blend_method = "BLEND"
            rgba = hex_to_rgb(entry["color"], entry["alpha"])
            mat.node_tree.nodes.get("Principled BSDF").inputs[
                "Base Color"
            ].default_value = rgba
            mat.node_tree.nodes.get("Principled BSDF").inputs[
                "Alpha"
            ].default_value = entry["alpha"]
            mat.diffuse_color = rgba
        obj.data.materials.append(mat)

        for s_data in entry["splines"]:
            spline = curve_res.splines.new("BEZIER")
            pts = s_data["points"]

            # --- FIX 1: STITCH WITH TOLERANCE ---
            if s_data["is_cyclic"] and len(pts) > 1:
                while len(pts) > 2:
                    # Calculate actual distance between first and last point
                    p1 = Vector(pts[0]["co"])
                    p2 = Vector(pts[-1]["co"])

                    if (p1 - p2).length < 0.0001:  # Check for "close enough"
                        last_pt = pts.pop()
                        # Transfer the closing handle from the dropped point to the start point
                        # This ensures the curve segment between the last and first point is smooth
                        if Vector(last_pt["l"]).length > 0:
                            pts[0]["l"] = last_pt["l"]
                    else:
                        break

            spline.use_cyclic_u = s_data["is_cyclic"]
            spline.bezier_points.add(len(pts) - 1)

            for i, p_data in enumerate(pts):
                bez_p = spline.bezier_points[i]

                # --- FIX 2: SET TYPES TO FREE FIRST ---
                # This prevents Blender from auto-aligning handles during the import
                bez_p.handle_left_type = "FREE"
                bez_p.handle_right_type = "FREE"

                bez_p.co = (p_data["co"][0], p_data["co"][1], 0)
                bez_p.handle_left = (p_data["l"][0], p_data["l"][1], 0)
                bez_p.handle_right = (p_data["r"][0], p_data["r"][1], 0)

            # --- FINAL POLISH ---
            # Now safe to set alignment to smooth out the visuals
            for p in spline.bezier_points:
                dist_l = (Vector(p.co) - Vector(p.handle_left)).length
                dist_r = (Vector(p.co) - Vector(p.handle_right)).length

                if dist_l < 0.00001 and dist_r < 0.00001:
                    p.handle_left_type = "VECTOR"
                    p.handle_right_type = "VECTOR"
                else:
                    p.handle_left_type = "ALIGNED"
                    p.handle_right_type = "ALIGNED"


# Import data
create_blender_curves(data)

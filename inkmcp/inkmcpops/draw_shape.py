"""Unified shape drawing operation with dynamic object creation"""

import inkex
from inkex import (
    Rectangle,
    Circle,
    Ellipse,
    Line,
    PathElement,
    Polygon,
    Polyline,
    TextElement,
)

# Shape type to inkex class mapping
SHAPE_CLASSES = {
    "rectangle": Rectangle,
    "rect": Rectangle,
    "circle": Circle,
    "ellipse": Ellipse,
    "line": Line,
    "path": PathElement,
    "polygon": Polygon,
    "polyline": Polyline,
    "text": TextElement,
}

# Style attributes that should be handled via style object
STYLE_ATTRIBUTES = {
    "fill",
    "stroke",
    "stroke-width",
    "stroke-linecap",
    "stroke-linejoin",
    "stroke-dasharray",
    "opacity",
    "fill-opacity",
    "stroke-opacity",
}

# Special handling attributes that don't follow the standard pattern
SPECIAL_ATTRIBUTES = {
    "text_content": lambda shape, value: setattr(shape, "text", str(value)),
    "font_size": lambda shape, value: shape.style.__setitem__(
        "font-size", f"{value}px"
    ),
    "points": lambda shape, value: shape.set(
        "points",
        " ".join([f"{p[0]},{p[1]}" for p in value])
        if isinstance(value, list)
        else str(value),
    ),
    "path_data": lambda shape, value: shape.set("d", str(value)),
    "d": lambda shape, value: shape.set("d", str(value)),
}


def execute(svg, params):
    """Draw any shape with dynamic object creation and attribute setting"""
    try:
        # Get shape type and validate
        shape_type = params.get("shape_type", params.get("type", "rectangle"))
        shape_type = shape_type.lower().replace("-", "_")

        if shape_type not in SHAPE_CLASSES:
            return {
                "status": "error",
                "data": {
                    "error": f"Unsupported shape type: {shape_type}. Available: {list(SHAPE_CLASSES.keys())}"
                },
            }

        # Create shape object dynamically
        ShapeClass = SHAPE_CLASSES[shape_type]
        shape = ShapeClass()

        # Separate style and geometric attributes
        style_params = {}
        geometric_params = {}

        for key, value in params.items():
            if key in ["shape_type", "type", "action", "response_file"]:
                continue
            elif key in STYLE_ATTRIBUTES or key.replace("_", "-") in STYLE_ATTRIBUTES:
                # Convert underscores to hyphens for CSS style properties
                style_key = key.replace("_", "-")
                style_params[style_key] = value
            else:
                geometric_params[key] = value

        # Set style attributes using inkex style API
        for style_attr, value in style_params.items():
            if style_attr in ["fill", "stroke"]:
                shape.style.set_color(
                    value if value and value.lower() != "none" else "none", style_attr
                )
            else:
                shape.style[style_attr] = str(value)

        # Set geometric attributes dynamically
        for attr, value in geometric_params.items():
            # Handle special cases first
            if attr in SPECIAL_ATTRIBUTES:
                SPECIAL_ATTRIBUTES[attr](shape, value)
            else:
                # Handle unit conversion properly
                if isinstance(value, (int, float)):
                    # For numeric values, use directly as user units (CLI-friendly: no conversion)
                    shape.set(attr, str(value))
                elif isinstance(value, str) and any(
                    value.endswith(unit)
                    for unit in ["px", "mm", "cm", "in", "pt", "pc"]
                ):
                    # For string values with units, always use proper SVG conversion
                    user_unit_value = svg.unittouu(value)
                    shape.set(attr, str(user_unit_value))
                else:
                    # For unitless strings, set directly
                    shape.set(attr, str(value))

        new_id = svg.get_unique_id(shape_type)
        shape.set("id", new_id)
        # Add to document
        svg.append(shape)

        # Prepare response data
        response_data = {
            "message": f"{shape_type.title()} created successfully",
            "shape_type": shape_type,
            "attributes": geometric_params,
            "id": new_id,
            "style": style_params,
        }

        return {"status": "success", "data": response_data}

    except Exception as e:
        return {
            "status": "error",
            "data": {"error": f"Shape creation failed: {str(e)}"},
        }


"""Element mapping and dynamic class instantiation for generic SVG element creation"""

import inkex

# Fallback mapping for cases where tag name doesn't match class name
TAG_TO_CLASS_MAPPING = {
    # Shape aliases
    "rect": "Rectangle",
    "text": "TextElement",
    "path": "PathElement",
    # Group elements
    "g": "Group",
    # Other common elements
    "use": "Use",
    "image": "Image",
}

# Module categories for placement logic
DEFS_MODULES = {
    "inkex.elements._filters",  # Contains gradients, filters, patterns, etc.
}


def get_element_class(tag_name: str):
    """
    Get inkex element class from tag name using capitalization convention + fallback mapping

    Args:
        tag_name: SVG tag name (e.g., 'linearGradient', 'rect', 'circle')

    Returns:
        Element class or None if not found
    """
    # First try capitalizing first letter (inkex convention)
    capitalized_name = tag_name[0].upper() + tag_name[1:] if tag_name else ""

    # Try to get class from inkex by capitalized name
    if hasattr(inkex, capitalized_name):
        potential_class = getattr(inkex, capitalized_name)
        # Verify it's actually an element class (has Element in inheritance)
        if hasattr(potential_class, '__mro__') and any('Element' in str(cls) for cls in potential_class.__mro__):
            return potential_class

    # Fallback to explicit mapping
    mapped_class_name = TAG_TO_CLASS_MAPPING.get(tag_name)
    if mapped_class_name and hasattr(inkex, mapped_class_name):
        return getattr(inkex, mapped_class_name)

    return None


def should_place_in_defs(element_class) -> bool:
    """
    Determine if element should be placed in <defs> section based on its module

    Args:
        element_class: The inkex element class

    Returns:
        True if should be placed in defs, False for main SVG
    """
    if not element_class or not hasattr(element_class, '__module__'):
        return False

    return element_class.__module__ in DEFS_MODULES


def ensure_defs_section(svg):
    """
    Ensure the SVG document has a defs section and return it

    Args:
        svg: SVG document object

    Returns:
        The defs element
    """
    defs = svg.defs
    if defs is None:
        defs = svg.defs = inkex.Defs()
    return defs


def get_unique_id(svg, tag_name: str, custom_id: str = None) -> str:
    """
    Generate unique ID for element with collision detection and auto-increment

    Args:
        svg: SVG document
        tag_name: Tag name for prefix
        custom_id: Optional custom ID

    Returns:
        Unique ID string (auto-incremented if collision detected)
    """
    if custom_id:
        # Check for collision and auto-increment if needed
        original_id = custom_id
        counter = 1

        while svg.getElementById(custom_id) is not None:
            custom_id = f"{original_id}_{counter}"
            counter += 1

        return custom_id

    # Use tag name as prefix, converting camelCase to lowercase
    prefix = tag_name[0].lower() + tag_name[1:] if tag_name else "element"
    return svg.get_unique_id(prefix=prefix)
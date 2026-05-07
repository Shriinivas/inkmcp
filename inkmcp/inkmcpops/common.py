"""Common utilities for generic extension modules"""

from typing import Dict, Any, Iterable, Optional


def create_success_response(message: str, **data) -> Dict[str, Any]:
    """Create a standardized success response"""
    response_data = {"message": message}
    response_data.update(data)
    return {
        "status": "success",
        "data": response_data
    }


def create_error_response(error_message: str, **data) -> Dict[str, Any]:
    """Create a standardized error response"""
    response_data = {"error": error_message}
    response_data.update(data)
    return {
        "status": "error",
        "data": response_data
    }


def get_clean_tag_name(element) -> Optional[str]:
    """Return a normalized SVG tag name, skipping non-element nodes."""
    tag = getattr(element, "tag", None)
    if not isinstance(tag, str):
        return None
    return tag.split("}", 1)[-1]


def count_element_types(elements: Iterable[Any]) -> Dict[str, int]:
    """Count element types, skipping non-element nodes."""
    counts: Dict[str, int] = {}
    for element in elements:
        tag_name = get_clean_tag_name(element)
        if tag_name is None:
            continue
        counts[tag_name] = counts.get(tag_name, 0) + 1
    return counts


def get_element_info_data(element) -> Dict[str, Any]:
    """Extract comprehensive element information"""
    tag_name = get_clean_tag_name(element) or "unknown"
    element_info = {
        "id": element.get('id', 'no-id'),
        "tag": tag_name,
        "label": element.get('{http://www.inkscape.org/namespaces/inkscape}label', None),
    }

    # Get all attributes
    attributes = {}
    try:
        for key, value in element.attrib.items():
            clean_key = key.split('}')[-1]  # Remove namespace prefixes
            attributes[clean_key] = value
    except Exception:
        pass

    element_info["attributes"] = attributes

    # Parse style attributes
    style_info = {}
    style_attr = element.get('style', '')
    if style_attr:
        for style_part in style_attr.split(';'):
            if ':' in style_part:
                key, value = style_part.split(':', 1)
                style_info[key.strip()] = value.strip()

    if style_info:
        element_info["style"] = style_info

    try:
        child_count = sum(
            1 for child in list(element) if get_clean_tag_name(child) is not None
        )
        if child_count:
            element_info["child_count"] = child_count
    except Exception:
        pass

    try:
        text_content = (element.text or "").strip()
        if text_content:
            element_info["text"] = text_content
    except Exception:
        pass

    return element_info

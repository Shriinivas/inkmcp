"""Common utilities for generic extension modules"""

from typing import Dict, Any


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


def get_element_info_data(element) -> Dict[str, Any]:
    """Extract comprehensive element information"""
    element_info = {
        "id": element.get('id', 'no-id'),
        "tag": element.tag.split('}')[-1],  # Remove namespace
        "label": element.get('{http://www.inkscape.org/namespaces/inkscape}label', None),
    }

    # Get all attributes
    attributes = {}
    for key, value in element.attrib.items():
        clean_key = key.split('}')[-1]  # Remove namespace prefixes
        attributes[clean_key] = value

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

    return element_info
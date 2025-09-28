"""Common utilities and patterns for Inkscape MCP operations"""

import inkex
import os
import tempfile
import time
from lxml import etree
from typing import Dict, Any, Tuple, List, Type, Optional


def create_element_with_id(svg, element_class, prefix: str = None, custom_id: str = None):
    """
    Create an element with a unique ID following the standard pattern

    Args:
        svg: SVG document object
        element_class: The inkex element class to instantiate
        prefix: Prefix for the unique ID. If None, derives from class name
        custom_id: Optional custom ID to use instead of generated one

    Returns:
        element: The created element with ID set (use element.get('id') to get the ID)
    """
    element = element_class()

    # Auto-derive prefix from class name if not provided
    if prefix is None:
        class_name = element_class.__name__
        # Convert CamelCase to lowercase (e.g., RadialGradient -> radialGradient)
        prefix = class_name[0].lower() + class_name[1:]

    element_id = custom_id or svg.get_unique_id(prefix=prefix)
    element.set('id', element_id)
    return element


def set_element_attributes(element, svg, attributes: Dict[str, Any], skip_keys: List[str] = None):
    """
    Set element attributes following the standard pattern from draw_shape.py

    Args:
        element: The element to set attributes on
        svg: SVG document for unit conversion
        attributes: Dictionary of attributes to set
        skip_keys: List of keys to skip when setting attributes
    """
    skip_keys = skip_keys or []

    for attr, value in attributes.items():
        if attr in skip_keys:
            continue

        if isinstance(value, (int, float)):
            # For numeric values, use directly as user units
            element.set(attr, str(value))
        elif isinstance(value, str) and any(
            value.endswith(unit) for unit in ["px", "mm", "cm", "in", "pt", "pc"]
        ):
            # For string values with units, use proper SVG conversion
            user_unit_value = svg.unittouu(value)
            element.set(attr, str(user_unit_value))
        else:
            # For unitless strings, set directly
            element.set(attr, str(value))


def parse_child_elements(children_data, child_element_class: Type,
                        primary_attrs: List[str],
                        separator: str = ';') -> List:
    """
    Parse child elements from various input formats

    Args:
        children_data: Can be:
            - List format: [["value1", "value2"], ["value3", "value4"]]
            - String format: "value1,value2;value3,value4"
        child_element_class: The inkex element class to create for each child
        primary_attrs: List of primary attribute names in order (e.g., ['offset', 'stop-color'])
        separator: Separator for string format (default ';')

    Returns:
        List of child elements
    """
    children = []

    if not children_data:
        return children

    if isinstance(children_data, list):
        # Handle array format: [["value1", "value2"], ["value3", "value4"]]
        for child_info in children_data:
            if isinstance(child_info, list) and len(child_info) >= len(primary_attrs):
                child = child_element_class()

                # Set primary attributes
                for i, attr_name in enumerate(primary_attrs):
                    if i < len(child_info):
                        child.set(attr_name, str(child_info[i]))

                # Handle additional attributes if provided
                if len(child_info) > len(primary_attrs):
                    for extra_attr in child_info[len(primary_attrs):]:
                        if '=' in str(extra_attr):
                            attr_key, attr_val = str(extra_attr).split('=', 1)
                            child.set(attr_key, attr_val)

                children.append(child)

    elif isinstance(children_data, str):
        # Handle separated format: "value1,value2;value3,value4"
        child_parts = children_data.split(separator)
        for child_part in child_parts:
            child_components = child_part.split(',')
            if len(child_components) >= len(primary_attrs):
                child = child_element_class()

                # Set primary attributes
                for i, attr_name in enumerate(primary_attrs):
                    if i < len(child_components):
                        child.set(attr_name, child_components[i].strip())

                children.append(child)

    return children


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


def create_success_response(message: str, element_id: str = None, **extra_data) -> Dict[str, Any]:
    """
    Create a standardized success response

    Args:
        message: Success message
        element_id: ID of created element (if applicable)
        **extra_data: Additional data to include in response

    Returns:
        Standardized success response dictionary
    """
    data = {"message": message}
    if element_id:
        data["id"] = element_id
    data.update(extra_data)

    return {"status": "success", "data": data}


def create_error_response(error_message: str) -> Dict[str, Any]:
    """
    Create a standardized error response

    Args:
        error_message: Error message

    Returns:
        Standardized error response dictionary
    """
    return {
        "status": "error",
        "data": {"error": error_message}
    }


def get_element_info(element) -> Dict[str, Any]:
    """
    Extract standard information from an SVG element

    Args:
        element: The SVG element

    Returns:
        Dictionary with element information
    """
    info = {
        "id": element.get('id'),
        "tag": etree.QName(element).localname,
        "attributes": dict(element.attrib)
    }

    # Get bounding box if possible
    try:
        bbox = element.bounding_box()
        if bbox:
            info["bbox"] = {
                "x": bbox.left,
                "y": bbox.top,
                "width": bbox.width,
                "height": bbox.height
            }
    except:
        pass

    return info


def create_temp_file(suffix: str, prefix: str = 'inkmcp_') -> str:
    """
    Create a temporary file with timestamp

    Args:
        suffix: File extension (e.g., '.png', '.svg')
        prefix: File prefix

    Returns:
        Temporary file path
    """
    timestamp = str(int(time.time()))
    return tempfile.mktemp(suffix=suffix, prefix=f'{prefix}{timestamp}_')


def safe_file_cleanup(file_path: str) -> None:
    """
    Safely remove a file if it exists

    Args:
        file_path: Path to file to remove
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        pass  # Ignore cleanup errors


def get_file_info(file_path: str) -> Dict[str, Any]:
    """
    Get basic file information

    Args:
        file_path: Path to file

    Returns:
        Dictionary with file info
    """
    info = {"path": file_path}
    try:
        if os.path.exists(file_path):
            info["size"] = os.path.getsize(file_path)
            info["exists"] = True
        else:
            info["exists"] = False
            info["size"] = 0
    except Exception as e:
        info["error"] = str(e)
        info["exists"] = False
        info["size"] = 0

    return info


def count_elements_by_type(svg) -> Dict[str, int]:
    """
    Count elements in the document by type

    Args:
        svg: SVG document

    Returns:
        Dictionary mapping element types to counts
    """
    element_counts = {}
    for elem in svg.iter():
        tag = etree.QName(elem).localname
        element_counts[tag] = element_counts.get(tag, 0) + 1
    return element_counts


def build_command_parameters(command_type: str, required_params: Dict[str, Any], variable_params: Dict[str, Any]) -> str:
    """
    Build command string from parameters, handling both AI client and direct call formats.

    This handles the common pattern where AI clients pass a single 'params' string
    while direct calls use individual keyword arguments.

    Args:
        command_type: The command type (e.g., 'circle', 'radial-gradient')
        required_params: Dictionary of required parameters (e.g., {'stops': '...', 'gradientUnits': '...'})
        variable_params: Dictionary of variable parameters from **params or **kwargs

    Returns:
        Complete command string ready for CLI execution
    """
    if len(variable_params) == 1 and "params" in variable_params:
        # AI client passes a single 'params' string argument
        param_str = variable_params["params"]
    else:
        # Direct keyword arguments (testing/manual use)
        # Build parameters including required ones
        all_params = {}
        all_params.update(required_params)
        all_params.update(variable_params)

        param_pairs = [f"{k}={v}" for k, v in all_params.items()]
        param_str = " ".join(param_pairs)

    return f"{command_type} {param_str}".strip()
"""Get information about specific objects by ID, name, or label"""

def execute(svg, params):
    """
    Get detailed information about a specific object

    Args:
        svg: inkscape SVG document object
        params: dict with keys:
            - object_id: SVG element ID (e.g., "rect123")
            - object_name: inkscape:label attribute
            - object_type: filter by element type (rect, circle, etc.)
            - index: get nth object of specified type (0-based)

    Returns:
        dict: object information or error
    """
    try:
        target_element = None
        search_info = {}

        # Search by ID
        if params.get('object_id'):
            object_id = params['object_id']
            target_element = svg.getElementById(object_id)
            search_info['search_method'] = 'id'
            search_info['search_value'] = object_id

        # Search by name/label
        elif params.get('object_name'):
            object_name = params['object_name']
            search_info['search_method'] = 'name'
            search_info['search_value'] = object_name

            # Look for inkscape:label attribute
            for element in svg.iter():
                label = element.get('{http://www.inkscape.org/namespaces/inkscape}label')
                if label == object_name:
                    target_element = element
                    break

        # Search by type and index
        elif params.get('object_type'):
            object_type = params['object_type']
            index = int(params.get('index', 0))
            search_info['search_method'] = 'type_index'
            search_info['search_value'] = f"{object_type}[{index}]"

            # Find all elements of specified type
            elements_of_type = []
            for element in svg.iter():
                if element.tag.split('}')[-1] == object_type:  # Remove namespace
                    elements_of_type.append(element)

            if index < len(elements_of_type):
                target_element = elements_of_type[index]

        if target_element is None:
            return {
                "status": "error",
                "data": {
                    "error": f"Object not found",
                    "search_info": search_info
                }
            }

        # Extract comprehensive object information
        element_info = {
            "id": target_element.get('id', 'no-id'),
            "tag": target_element.tag.split('}')[-1],  # Remove namespace
            "label": target_element.get('{http://www.inkscape.org/namespaces/inkscape}label', None),
        }

        # Get all attributes
        attributes = {}
        for key, value in target_element.attrib.items():
            clean_key = key.split('}')[-1]  # Remove namespace prefixes
            attributes[clean_key] = value

        # Get computed properties based on element type
        properties = {}
        tag_name = element_info["tag"]

        if tag_name == "rect":
            properties.update({
                "x": float(target_element.get('x', 0)),
                "y": float(target_element.get('y', 0)),
                "width": float(target_element.get('width', 0)),
                "height": float(target_element.get('height', 0)),
                "rx": target_element.get('rx'),
                "ry": target_element.get('ry')
            })
        elif tag_name == "circle":
            properties.update({
                "cx": float(target_element.get('cx', 0)),
                "cy": float(target_element.get('cy', 0)),
                "r": float(target_element.get('r', 0))
            })
        elif tag_name == "ellipse":
            properties.update({
                "cx": float(target_element.get('cx', 0)),
                "cy": float(target_element.get('cy', 0)),
                "rx": float(target_element.get('rx', 0)),
                "ry": float(target_element.get('ry', 0))
            })
        elif tag_name == "line":
            properties.update({
                "x1": float(target_element.get('x1', 0)),
                "y1": float(target_element.get('y1', 0)),
                "x2": float(target_element.get('x2', 0)),
                "y2": float(target_element.get('y2', 0))
            })
        elif tag_name == "text":
            properties.update({
                "x": float(target_element.get('x', 0)),
                "y": float(target_element.get('y', 0)),
                "text_content": target_element.text or "",
                "font_size": target_element.get('font-size')
            })
        elif tag_name == "path":
            properties.update({
                "d": target_element.get('d', ''),
                "path_length": len(target_element.get('d', ''))
            })

        # Parse style attributes
        style_info = {}
        style_attr = target_element.get('style', '')
        if style_attr:
            for style_part in style_attr.split(';'):
                if ':' in style_part:
                    key, value = style_part.split(':', 1)
                    style_info[key.strip()] = value.strip()

        # Get bounding box if available
        try:
            bbox = target_element.bounding_box()
            bounding_box = {
                "x": bbox.left,
                "y": bbox.top,
                "width": bbox.width,
                "height": bbox.height,
                "right": bbox.right,
                "bottom": bbox.bottom
            }
        except:
            bounding_box = None

        return {
            "status": "success",
            "data": {
                "search_info": search_info,
                "element": element_info,
                "properties": properties,
                "attributes": attributes,
                "style": style_info,
                "bounding_box": bounding_box
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "data": {"error": f"Failed to get object info: {str(e)}"}
        }
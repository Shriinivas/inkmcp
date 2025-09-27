"""Get specific properties from objects by ID, name, or selection"""

def execute(svg, params):
    """
    Get specific property values from objects

    Args:
        svg: inkscape SVG document object
        params: dict with keys:
            - object_id: SVG element ID (optional)
            - object_name: inkscape:label attribute (optional)
            - object_type + index: get nth object of type (optional)
            - use_selection: use currently selected objects (default: False)
            - property: specific property to get (width, height, cx, cy, r, etc.)
            - properties: list of properties to get (alternative to single property)

    Returns:
        dict: property values or error
    """
    try:
        target_elements = []
        search_info = {}

        # Determine which objects to query
        if params.get('use_selection', False):
            # Get selected objects
            search_info['search_method'] = 'selection'
            for element in svg.selection:
                target_elements.append(element)

        elif params.get('object_id'):
            # Find by ID
            object_id = params['object_id']
            element = svg.getElementById(object_id)
            if element is not None:
                target_elements.append(element)
            search_info['search_method'] = 'id'
            search_info['search_value'] = object_id

        elif params.get('object_name'):
            # Find by name/label
            object_name = params['object_name']
            search_info['search_method'] = 'name'
            search_info['search_value'] = object_name

            for element in svg.iter():
                label = element.get('{http://www.inkscape.org/namespaces/inkscape}label')
                if label == object_name:
                    target_elements.append(element)

        elif params.get('object_type'):
            # Find by type and index
            object_type = params['object_type']
            index = int(params.get('index', 0))
            search_info['search_method'] = 'type_index'
            search_info['search_value'] = f"{object_type}[{index}]"

            elements_of_type = []
            for element in svg.iter():
                if element.tag.split('}')[-1] == object_type:
                    elements_of_type.append(element)

            if index < len(elements_of_type):
                target_elements.append(elements_of_type[index])

        if not target_elements:
            return {
                "status": "error",
                "data": {
                    "error": "No objects found matching criteria",
                    "search_info": search_info
                }
            }

        # Determine which properties to extract
        properties_to_get = []
        if params.get('property'):
            properties_to_get.append(params['property'])
        elif params.get('properties'):
            properties_to_get.extend(params['properties'])
        else:
            return {
                "status": "error",
                "data": {"error": "No property or properties specified"}
            }

        # Extract properties from each object
        results = []
        for element in target_elements:
            element_result = {
                "id": element.get('id', 'no-id'),
                "tag": element.tag.split('}')[-1],
                "label": element.get('{http://www.inkscape.org/namespaces/inkscape}label'),
                "properties": {}
            }

            for prop in properties_to_get:
                value = None

                # Handle common geometric properties
                if prop in ['x', 'y', 'width', 'height', 'cx', 'cy', 'r', 'rx', 'ry',
                           'x1', 'y1', 'x2', 'y2']:
                    raw_value = element.get(prop)
                    if raw_value is not None:
                        try:
                            # Convert to user units if it's a coordinate/dimension
                            value = svg.unittouu(raw_value)
                        except:
                            value = raw_value

                # Handle style properties
                elif prop in ['fill', 'stroke', 'stroke-width', 'opacity', 'font-size']:
                    # Check direct attribute first
                    value = element.get(prop)

                    # Check style attribute if not found
                    if value is None:
                        style_attr = element.get('style', '')
                        if style_attr:
                            for style_part in style_attr.split(';'):
                                if ':' in style_part:
                                    key, val = style_part.split(':', 1)
                                    if key.strip() == prop:
                                        value = val.strip()
                                        break

                # Handle text content
                elif prop == 'text_content':
                    value = element.text or ""

                # Handle path data
                elif prop == 'd' or prop == 'path_data':
                    value = element.get('d', '')

                # Handle bounding box properties
                elif prop in ['bbox_x', 'bbox_y', 'bbox_width', 'bbox_height']:
                    try:
                        bbox = element.bounding_box()
                        if prop == 'bbox_x':
                            value = bbox.left
                        elif prop == 'bbox_y':
                            value = bbox.top
                        elif prop == 'bbox_width':
                            value = bbox.width
                        elif prop == 'bbox_height':
                            value = bbox.height
                    except:
                        value = None

                # Fallback: get as raw attribute
                else:
                    value = element.get(prop)

                element_result["properties"][prop] = value

            results.append(element_result)

        return {
            "status": "success",
            "data": {
                "search_info": search_info,
                "object_count": len(results),
                "properties_requested": properties_to_get,
                "results": results
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "data": {"error": f"Failed to get properties: {str(e)}"}
        }
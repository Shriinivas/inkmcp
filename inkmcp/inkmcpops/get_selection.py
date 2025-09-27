"""Selection information retrieval operation"""

import inkex
from lxml import etree

def execute(svg, params):
    """Get information about currently selected elements"""
    try:
        # Get selected elements - Inkscape passes them via command line
        selected = svg.selected

        selection_info = {
            "selection": {
                "count": len(selected),
                "elements": []
            }
        }

        # Extract info for each selected element
        for elem_id, element in selected.items():
            elem_info = {
                "id": elem_id,
                "tag": etree.QName(element).localname,
                "attributes": dict(element.attrib)
            }

            # Get bounding box if possible
            try:
                bbox = element.bounding_box()
                if bbox:
                    elem_info["bbox"] = {
                        "x": bbox.left,
                        "y": bbox.top,
                        "width": bbox.width,
                        "height": bbox.height
                    }
            except:
                pass

            selection_info["selection"]["elements"].append(elem_info)

        return {
            "status": "success",
            "data": selection_info
        }

    except Exception as e:
        return {
            "status": "error",
            "data": {
                "error": f"Failed to get selection info: {str(e)}"
            }
        }
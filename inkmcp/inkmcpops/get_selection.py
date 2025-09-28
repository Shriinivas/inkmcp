"""Selection information retrieval operation"""

import inkex
import os
import sys
sys.path.append(os.path.dirname(__file__))
from operations_common import create_success_response, create_error_response, get_element_info

def execute(svg, params):
    """Get information about currently selected elements"""
    try:
        # Get selected elements - Inkscape passes them via command line
        selected = svg.selected

        # Extract info for each selected element using common function
        elements = []
        for elem_id, element in selected.items():
            elem_info = get_element_info(element)
            elements.append(elem_info)

        return create_success_response(
            message="Selection information retrieved successfully",
            selection={
                "count": len(selected),
                "elements": elements
            }
        )

    except Exception as e:
        return create_error_response(f"Failed to get selection info: {str(e)}")
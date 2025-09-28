"""Document information retrieval operation"""

import inkex
import os
import sys
sys.path.append(os.path.dirname(__file__))
from operations_common import create_success_response, count_elements_by_type

def execute(svg, params):
    """Get information about the current document"""
    # Get document dimensions
    width = svg.get('width', 'unknown')
    height = svg.get('height', 'unknown')
    viewbox = svg.get('viewBox', 'none')

    # Count elements using common function
    element_counts = count_elements_by_type(svg)

    return create_success_response(
        message="Document information retrieved successfully",
        document={
            "width": width,
            "height": height,
            "viewBox": viewbox,
            "element_counts": element_counts
        }
    )
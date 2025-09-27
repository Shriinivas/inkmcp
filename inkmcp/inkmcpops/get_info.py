"""Document information retrieval operation"""

import inkex
from lxml import etree

def execute(svg, params):
    """Get information about the current document"""
    # Get document dimensions
    width = svg.get('width', 'unknown')
    height = svg.get('height', 'unknown')
    viewbox = svg.get('viewBox', 'none')

    # Count elements
    elements = list(svg.iter())
    element_counts = {}
    for elem in elements:
        tag = etree.QName(elem).localname
        element_counts[tag] = element_counts.get(tag, 0) + 1

    info = {
        "document": {
            "width": width,
            "height": height,
            "viewBox": viewbox,
            "element_counts": element_counts
        }
    }

    return {
        "status": "success",
        "data": info
    }
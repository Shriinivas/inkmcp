"""Add gradient operations (both linear and radial)"""

import inkex
from inkex.elements._filters import RadialGradient, LinearGradient, Stop
import os
import sys
sys.path.append(os.path.dirname(__file__))
from operations_common import (
    create_element_with_id,
    set_element_attributes,
    parse_child_elements,
    ensure_defs_section,
    create_success_response,
    create_error_response
)


def execute(svg, params):
    """Add a gradient (linear or radial) to the document"""
    try:
        # Determine gradient type from gradient_type parameter
        gradient_type_param = params.get('gradient_type', '')
        if gradient_type_param == 'radial-gradient':
            gradient_class = RadialGradient
            gradient_type = 'radial'
            prefix = 'radialGradient'
        elif gradient_type_param == 'linear-gradient':
            gradient_class = LinearGradient
            gradient_type = 'linear'
            prefix = 'linearGradient'
        else:
            return create_error_response(f"Unknown gradient type: {gradient_type_param}")

        # Ensure defs section exists
        defs = ensure_defs_section(svg)

        # Create gradient with unique ID
        gradient = create_element_with_id(
            svg, gradient_class, prefix, params.get('id')
        )
        gradient_id = gradient.get('id')

        # Separate gradient attributes from special keys
        gradient_params = {}
        stops_data = None

        for key, value in params.items():
            if key in ['action', 'response_file', 'id', 'gradient_type']:
                continue
            elif key == 'stops':
                stops_data = value
            else:
                gradient_params[key] = value

        # Set default gradientUnits if not specified
        if 'gradientUnits' not in gradient_params:
            gradient_params['gradientUnits'] = 'userSpaceOnUse'

        # Set gradient attributes using common utility
        set_element_attributes(gradient, svg, gradient_params)

        # Process stops using generic child element parser
        if stops_data:
            stops = parse_child_elements(
                children_data=stops_data,
                child_element_class=Stop,
                primary_attrs=['offset', 'stop-color'],
                separator=';'
            )
            for stop in stops:
                gradient.append(stop)

        # Add gradient to defs
        defs.append(gradient)

        # Return standardized response
        return create_success_response(
            message=f"{gradient_type.title()} gradient created successfully",
            element_id=gradient_id,
            gradient_type=gradient_type,
            attributes=gradient_params,
            stops_count=len(gradient)
        )

    except Exception as e:
        return create_error_response(f"{gradient_type.title()} gradient creation failed: {str(e)}")
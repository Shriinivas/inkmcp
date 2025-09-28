"""Document export operation - similar to Blender's viewport screenshot"""

import inkex
from inkex.command import call
import os
import sys
import tempfile
sys.path.append(os.path.dirname(__file__))
from operations_common import (
    create_success_response,
    create_error_response,
    create_temp_file,
    safe_file_cleanup,
    get_file_info
)

def execute(svg, params):
    """Export current document as image or SVG using inkex command system"""
    try:
        # Get export parameters
        format_type = params.get('format', 'png')
        output_path = params.get('output_path')
        dpi = params.get('dpi', 96)

        # Generate output path if not provided using common utility
        if not output_path:
            output_path = create_temp_file(f'.{format_type}', 'inkscape_export_')

        # Save current document to temp SVG file
        temp_svg = tempfile.mktemp(suffix='.svg')

        # Write SVG using inkex's proper method
        svg.write(temp_svg)

        # Build export command using inkex.command.call
        if format_type == 'png':
            call('inkscape',
                 '--export-type=png',
                 f'--export-filename={output_path}',
                 f'--export-dpi={dpi}',
                 temp_svg)
        elif format_type == 'svg':
            call('inkscape',
                 '--export-type=svg',
                 f'--export-filename={output_path}',
                 temp_svg)
        else:
            return create_error_response(f"Unsupported format: {format_type}")

        # Clean up temp file using common utility
        safe_file_cleanup(temp_svg)

        # Get file info using common utility
        file_info = get_file_info(output_path)

        return create_success_response(
            message=f"Document exported as {format_type.upper()}",
            output_path=output_path,
            format=format_type,
            file_size=file_info.get('size', 0)
        )

    except Exception as e:
        return create_error_response(f"Export failed: {str(e)}")
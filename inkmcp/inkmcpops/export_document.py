"""Document export operation - similar to Blender's viewport screenshot"""

import inkex
from inkex.command import call
import os
import tempfile

def execute(svg, params):
    """Export current document as image or SVG using inkex command system"""
    try:
        # Get export parameters
        format_type = params.get('format', 'png')
        output_path = params.get('output_path')
        dpi = params.get('dpi', 96)

        # Generate output path if not provided
        if not output_path:
            import time
            timestamp = str(int(time.time()))
            output_path = tempfile.mktemp(suffix=f'.{format_type}', prefix=f'inkscape_export_{timestamp}_')

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
            return {
                "status": "error",
                "data": {"error": f"Unsupported format: {format_type}"}
            }

        # Clean up temp file
        if os.path.exists(temp_svg):
            os.remove(temp_svg)

        # Get file size
        file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0

        return {
            "status": "success",
            "data": {
                "message": f"Document exported as {format_type.upper()}",
                "output_path": output_path,
                "format": format_type,
                "file_size": file_size
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "data": {"error": f"Export failed: {str(e)}"}
        }
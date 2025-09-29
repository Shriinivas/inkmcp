"""Document export operations module"""

import tempfile
import base64
import os
from typing import Dict, Any
from inkex.command import call
from common import create_success_response, create_error_response


def export_document_image(extension_instance, svg, attributes: Dict[str, Any]) -> Dict[str, Any]:
    """Export document as image (like Blender viewport screenshot)"""
    try:
        # Get export parameters
        format_type = attributes.get('format', 'png')
        max_size = int(attributes.get('max_size', 800))
        return_base64_val = attributes.get('return_base64', 'true')
        if isinstance(return_base64_val, bool):
            return_base64 = return_base64_val
        else:
            return_base64 = str(return_base64_val).lower() == 'true'
        area = attributes.get('area', 'page')  # page, drawing, selection

        # Generate temp output path
        output_fd, output_path = tempfile.mkstemp(suffix=f'.{format_type}', prefix='inkscape_export_')
        os.close(output_fd)  # Close the file descriptor

        # Save current document to temp SVG file
        temp_svg_fd, temp_svg = tempfile.mkstemp(suffix='.svg')
        os.close(temp_svg_fd)  # Close the file descriptor
        with open(temp_svg, 'wb') as f:
            extension_instance.save(f)

        # Build export command
        if format_type == 'png':
            if area == 'page':
                export_area = '--export-area-page'
            elif area == 'drawing':
                export_area = '--export-area-drawing'
            else:
                export_area = '--export-area-page'

            # Calculate DPI to respect max_size
            dpi = 96  # Default
            if max_size:
                # Get page dimensions to calculate appropriate DPI
                width = float(svg.get('width', '100').replace('mm', '').replace('px', ''))
                if max_size < width:
                    dpi = int((max_size / width) * 96)

            call('inkscape',
                 '--export-type=png',
                 f'--export-filename={output_path}',
                 f'--export-dpi={dpi}',
                 export_area,
                 temp_svg)
        else:
            return create_error_response(f"Unsupported format: {format_type}")

        # Clean up temp SVG
        os.unlink(temp_svg)

        # Get file info
        file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0

        response_data = {
            "export_path": output_path,
            "format": format_type,
            "file_size": file_size,
            "area": area
        }

        # Add base64 data if requested
        if return_base64 and os.path.exists(output_path):
            with open(output_path, 'rb') as f:
                image_data = f.read()
                base64_data = base64.b64encode(image_data).decode('utf-8')
                response_data["base64_data"] = base64_data

        return create_success_response(
            f"Document exported as {format_type.upper()}",
            **response_data
        )

    except Exception as e:
        return create_error_response(f"Export failed: {str(e)}")
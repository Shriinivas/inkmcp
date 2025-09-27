"""Export document as PNG image for viewing/analysis"""

import tempfile
import subprocess
import os
import base64

def execute(svg, params):
    """
    Export the current document as a PNG image

    Args:
        svg: inkscape SVG document object
        params: dict with keys:
            - format: output format ('png', 'svg', 'pdf') - default 'png'
            - dpi: DPI for PNG export (default: 96)
            - max_size: Maximum size in pixels for largest dimension (default: 800)
            - output_path: Optional output file path (auto-generated if not provided)
            - return_base64: Return image as base64 string (default: False)
            - area: Export area ('page', 'drawing') - default 'page'

    Returns:
        dict: export result with file path or base64 data
    """
    try:
        # Get parameters with defaults
        export_format = params.get('format', 'png').lower()
        dpi = int(params.get('dpi', 96))
        max_size = int(params.get('max_size', 800))
        output_path = params.get('output_path')
        return_base64 = params.get('return_base64', False)
        area = params.get('area', 'page')

        # Validate format
        if export_format not in ['png', 'svg', 'pdf']:
            return {
                "status": "error",
                "data": {"error": f"Unsupported format: {export_format}. Use 'png', 'svg', or 'pdf'"}
            }

        # Create temporary output file if no path specified
        if not output_path:
            suffix = f'.{export_format}'
            temp_fd, output_path = tempfile.mkstemp(suffix=suffix, prefix='inkscape_export_')
            os.close(temp_fd)  # Close the file descriptor, keep the path

        # Save current document to temporary SVG file for export
        temp_svg_fd, temp_svg_path = tempfile.mkstemp(suffix='.svg', prefix='inkscape_temp_')
        try:
            with os.fdopen(temp_svg_fd, 'w') as f:
                # Write the SVG content to temp file
                svg_content = svg.tostring()
                if isinstance(svg_content, bytes):
                    svg_content = svg_content.decode('utf-8')
                f.write(svg_content)

            # Build Inkscape command line export
            cmd = ['inkscape']

            # Input file
            cmd.extend([temp_svg_path])

            # Output format and file
            if export_format == 'png':
                cmd.extend(['--export-type=png'])
                cmd.extend([f'--export-dpi={dpi}'])

                # Handle max_size constraint for PNG
                if max_size and max_size > 0:
                    cmd.extend([f'--export-width={max_size}'])

            elif export_format == 'svg':
                cmd.extend(['--export-type=svg'])
            elif export_format == 'pdf':
                cmd.extend(['--export-type=pdf'])

            # Export area
            if area == 'drawing':
                cmd.extend(['--export-area-drawing'])
            else:  # page
                cmd.extend(['--export-area-page'])

            # Output file
            cmd.extend([f'--export-filename={output_path}'])

            # Execute export command
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                return {
                    "status": "error",
                    "data": {
                        "error": f"Inkscape export failed: {result.stderr}",
                        "command": " ".join(cmd)
                    }
                }

            # Check if output file was created
            if not os.path.exists(output_path):
                return {
                    "status": "error",
                    "data": {"error": f"Export file was not created: {output_path}"}
                }

            # Get file info
            file_size = os.path.getsize(output_path)

            response_data = {
                "export_path": output_path,
                "format": export_format,
                "file_size": file_size,
                "dpi": dpi if export_format == 'png' else None,
                "area": area
            }

            # Return base64 data if requested (mainly for PNG images)
            if return_base64 and export_format == 'png':
                try:
                    with open(output_path, 'rb') as f:
                        image_data = f.read()
                        base64_data = base64.b64encode(image_data).decode('ascii')
                        response_data["base64_data"] = base64_data
                        response_data["data_size"] = len(base64_data)
                except Exception as e:
                    response_data["base64_error"] = str(e)

            return {
                "status": "success",
                "data": response_data
            }

        finally:
            # Clean up temporary SVG file
            try:
                os.unlink(temp_svg_path)
            except:
                pass

    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "data": {"error": "Export command timed out after 30 seconds"}
        }
    except Exception as e:
        return {
            "status": "error",
            "data": {"error": f"Export failed: {str(e)}"}
        }
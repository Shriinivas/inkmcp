#!/usr/bin/env python3
"""
Inkscape MCP Server
A Model Context Protocol server for controlling Inkscape via D-Bus

Provides natural language access to Inkscape drawing operations using our
proven D-Bus + JSON parameter system with modular operation architecture.
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from mcp.server.fastmcp import FastMCP, Context
from mcp.types import ImageContent

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("InkscapeMCP")

# Server configuration
DEFAULT_DBUS_SERVICE = "org.inkscape.Inkscape"
DEFAULT_DBUS_PATH = "/org/inkscape/Inkscape"
DEFAULT_DBUS_INTERFACE = "org.gtk.Actions"
DEFAULT_ACTION_NAME = "org.mcp.inkscape.draw.modular"


class InkscapeConnection:
    """Manages D-Bus connection to Inkscape"""

    def __init__(self):
        self.dbus_service = DEFAULT_DBUS_SERVICE
        self.dbus_path = DEFAULT_DBUS_PATH
        self.dbus_interface = DEFAULT_DBUS_INTERFACE
        self.action_name = DEFAULT_ACTION_NAME
        self._cli_client_path = Path(__file__).parent / "inkmcpcli.py"

    def is_available(self) -> bool:
        """Check if Inkscape is running and MCP extension is available"""
        try:
            cmd = [
                "gdbus",
                "call",
                "--session",
                "--dest",
                self.dbus_service,
                "--object-path",
                self.dbus_path,
                "--method",
                f"{self.dbus_interface}.List",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

            if result.returncode != 0:
                logger.warning("Inkscape D-Bus service not available")
                return False

            # Check if our MCP extension action is listed
            output = result.stdout
            return self.action_name in output

        except Exception as e:
            logger.error(f"Error checking Inkscape availability: {e}")
            return False

    def execute_cli_command(self, command: str) -> Dict[str, Any]:
        """Execute command using our CLI client"""
        try:
            cmd = ["python", str(self._cli_client_path), "--parse-out", command]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                logger.error(f"CLI command failed: {result.stderr}")
                return {"success": False, "error": f"Command failed: {result.stderr}"}

            # Parse JSON response from CLI
            response_data = json.loads(result.stdout)
            return {"success": True, "data": response_data}

        except subprocess.TimeoutExpired:
            logger.error("CLI command timed out")
            return {"success": False, "error": "Command timed out"}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {e}")
            return {"success": False, "error": f"Invalid response format: {e}"}
        except Exception as e:
            logger.error(f"CLI execution error: {e}")
            return {"success": False, "error": str(e)}


# Global connection instance
_inkscape_connection: Optional[InkscapeConnection] = None


def get_inkscape_connection() -> InkscapeConnection:
    """Get or create Inkscape connection"""
    global _inkscape_connection

    if _inkscape_connection is None:
        _inkscape_connection = InkscapeConnection()

    if not _inkscape_connection.is_available():
        raise Exception(
            "Inkscape is not running or MCP extension is not available. "
            "Please start Inkscape and ensure the modular MCP extension is installed."
        )

    return _inkscape_connection


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    """Manage server startup and shutdown lifecycle"""
    logger.info("InkscapeMCP server starting up")

    try:
        # Test connection on startup
        try:
            connection = get_inkscape_connection()
            logger.info("Successfully connected to Inkscape on startup")
        except Exception as e:
            logger.warning(f"Could not connect to Inkscape on startup: {e}")
            logger.warning(
                "Make sure Inkscape is running with the MCP extension before using tools"
            )

        yield {}
    finally:
        logger.info("InkscapeMCP server shut down")


# Create the MCP server
mcp = FastMCP("InkscapeMCP", lifespan=server_lifespan)

# MCP Tools


@mcp.tool()
def draw_shape(ctx: Context, shape_type: str, **params) -> str:
    """
    Draw a single shape in Inkscape with specified parameters. Preferred for basic shape creation.

    Parameters:
    - shape_type: Type of shape (rectangle, circle, ellipse, line, polygon, polyline, text, path)

    Shape parameters (provide as named parameters):
    - Rectangle: x, y, width, height (e.g. x=100, y=50, width=200, height=100)
    - Circle: cx, cy, r (e.g. cx=150, cy=150, r=75)
    - Ellipse: cx, cy, rx, ry (e.g. cx=100, cy=100, rx=50, ry=30)
    - Line: x1, y1, x2, y2 (e.g. x1=0, y1=0, x2=100, y2=100)
    - Text: x, y, text_content (e.g. x=50, y=200, text_content="Hello")
    - Styling: fill, stroke, stroke_width, opacity (e.g. fill="blue", stroke="red")

    Returns element ID for further reference. For gradient fills, use create_gradient() first.
    """
    try:
        connection = get_inkscape_connection()

        # Handle different parameter formats from Claude Code
        if len(params) == 1 and "params" in params:
            # Claude Code passes a single 'params' string argument
            param_str = params["params"]
        else:
            # Direct keyword arguments (testing/manual use)
            param_pairs = [f"{k}={v}" for k, v in params.items()]
            param_str = " ".join(param_pairs)

        command = f"{shape_type} {param_str}".strip()

        logger.info(f"Executing: {command}")
        result = connection.execute_cli_command(command)

        if not result["success"]:
            return f"Error drawing {shape_type}: {result['error']}"

        # Extract meaningful response from CLI data
        cli_data = result["data"]
        if cli_data.get("total_commands", 0) > 0:
            cmd_result = cli_data["results"][0]["result"]
            if cmd_result.get("status") == "success":
                data = cmd_result.get("data", {})
                message = data.get(
                    "message", f"{shape_type.title()} created successfully"
                )
                return f"✅ {message}"
            else:
                error = cmd_result.get("data", {}).get("error", "Unknown error")
                return f"❌ {error}"

        return f"✅ {shape_type.title()} created successfully"

    except Exception as e:
        logger.error(f"Error in draw_shape: {e}")
        return f"❌ Failed to draw {shape_type}: {str(e)}"


@mcp.tool()
def get_selection_info(ctx: Context) -> str:
    """
    Get detailed information about currently selected objects in Inkscape.

    Returns information about selected elements including IDs, types,
    attributes, and bounding boxes.
    """
    try:
        connection = get_inkscape_connection()

        result = connection.execute_cli_command("get-selection")

        if not result["success"]:
            return f"❌ Error getting selection info: {result['error']}"

        # Parse selection data
        cli_data = result["data"]
        if cli_data.get("total_commands", 0) > 0:
            cmd_result = cli_data["results"][0]["result"]
            if cmd_result.get("status") == "success":
                selection_data = cmd_result.get("data", {}).get("selection", {})
                count = selection_data.get("count", 0)
                elements = selection_data.get("elements", [])

                if count == 0:
                    return "ℹ️ No objects are currently selected"

                response = f"📋 Selection Info: {count} object(s) selected\n\n"

                for i, element in enumerate(elements, 1):
                    elem_type = element.get("tag", "unknown")
                    elem_id = element.get("id", "no-id")

                    response += f"{i}. **{elem_type.title()}** (ID: {elem_id})\n"

                    # Add bounding box info if available
                    bbox = element.get("bbox")
                    if bbox:
                        response += f"   Position: ({bbox['x']:.1f}, {bbox['y']:.1f})\n"
                        response += (
                            f"   Size: {bbox['width']:.1f} × {bbox['height']:.1f}\n"
                        )

                    # Add key attributes
                    attrs = element.get("attributes", {})
                    key_attrs = [
                        "fill",
                        "stroke",
                        "stroke-width",
                        "width",
                        "height",
                        "cx",
                        "cy",
                        "r",
                    ]
                    shown_attrs = {k: v for k, v in attrs.items() if k in key_attrs}
                    if shown_attrs:
                        attr_str = ", ".join(
                            [f"{k}: {v}" for k, v in shown_attrs.items()]
                        )
                        response += f"   Attributes: {attr_str}\n"

                    response += "\n"

                return response

        return "❌ Failed to get selection information"

    except Exception as e:
        logger.error(f"Error in get_selection_info: {e}")
        return f"❌ Failed to get selection info: {str(e)}"


@mcp.tool()
def get_document_info(ctx: Context) -> str:
    """
    Get information about the current Inkscape document.

    Returns document dimensions, viewBox, and element counts.
    """
    try:
        connection = get_inkscape_connection()

        result = connection.execute_cli_command("get-info")

        if not result["success"]:
            return f"❌ Error getting document info: {result['error']}"

        # Parse document data
        cli_data = result["data"]
        if cli_data.get("total_commands", 0) > 0:
            cmd_result = cli_data["results"][0]["result"]
            if cmd_result.get("status") == "success":
                doc_data = cmd_result.get("data", {}).get("document", {})

                width = doc_data.get("width", "unknown")
                height = doc_data.get("height", "unknown")
                viewbox = doc_data.get("viewBox", "none")
                elements = doc_data.get("element_counts", {})

                response = "📄 **Document Information**\n\n"
                response += f"**Dimensions**: {width} × {height}\n"
                response += f"**ViewBox**: {viewbox}\n\n"

                if elements:
                    response += "**Elements in document**:\n"
                    for elem_type, count in elements.items():
                        if elem_type not in [
                            "svg",
                            "namedview",
                            "defs",
                        ]:  # Skip meta elements
                            response += f"- {elem_type}: {count}\n"

                return response

        return "❌ Failed to get document information"

    except Exception as e:
        logger.error(f"Error in get_document_info: {e}")
        return f"❌ Failed to get document info: {str(e)}"


@mcp.tool()
def batch_draw(ctx: Context, commands: List[str]) -> str:
    """
    Execute multiple drawing commands in batch.

    Parameters:
    - commands: List of drawing command strings

    Example:
    batch_draw([
        "rectangle x=50 y=50 width=100 height=100 fill=red",
        "circle cx=200 cy=200 r=50 fill=blue",
        "text x=100 y=300 text_content='Batch Drawing!' font_size=16"
    ])
    """
    try:
        connection = get_inkscape_connection()

        # Join commands with semicolons for batch processing
        batch_command = "; ".join(commands)

        logger.info(f"Executing batch: {batch_command}")
        result = connection.execute_cli_command(batch_command)

        if not result["success"]:
            return f"❌ Batch drawing failed: {result['error']}"

        # Parse batch results
        cli_data = result["data"]
        total_commands = cli_data.get("total_commands", 0)
        results = cli_data.get("results", [])

        successful = 0
        failed = 0
        errors = []

        for cmd_result in results:
            if cmd_result.get("result", {}).get("status") == "success":
                successful += 1
            else:
                failed += 1
                error_msg = (
                    cmd_result.get("result", {})
                    .get("data", {})
                    .get("error", "Unknown error")
                )
                errors.append(error_msg)

        response = f"📦 **Batch Drawing Complete**\n\n"
        response += f"✅ Successful: {successful}/{total_commands}\n"

        if failed > 0:
            response += f"❌ Failed: {failed}\n\n"
            response += "**Errors**:\n"
            for i, error in enumerate(errors, 1):
                response += f"{i}. {error}\n"

        return response

    except Exception as e:
        logger.error(f"Error in batch_draw: {e}")
        return f"❌ Batch drawing failed: {str(e)}"


@mcp.tool()
def get_object_info(
    ctx: Context,
    object_id: str = "",
    object_name: str = "",
    object_type: str = "",
    index: int = 0,
) -> str:
    """
    Get detailed information about a specific object by ID, name/label, or type+index.

    Parameters:
    - object_id: SVG element ID (e.g., "rect123")
    - object_name: Inkscape label/name of the object
    - object_type: Element type (rect, circle, ellipse, etc.) with index
    - index: Which object of the specified type (0-based, used with object_type)

    Examples:
    - get_object_info(object_id="rect123")
    - get_object_info(object_name="My Rectangle")
    - get_object_info(object_type="circle", index=1)  # Second circle in document
    """
    try:
        connection = get_inkscape_connection()

        # Build command parameters
        params = []
        if object_id:
            params.append(f"object_id={object_id}")
        elif object_name:
            params.append(f"object_name='{object_name}'")
        elif object_type:
            params.append(f"object_type={object_type}")
            params.append(f"index={index}")
        else:
            return (
                "❌ Error: Must specify either object_id, object_name, or object_type"
            )

        param_str = " ".join(params)
        command = f"get-object-info {param_str}"
        logger.info(f"Executing: {command}")
        result = connection.execute_cli_command(command)

        if not result["success"]:
            return f"❌ Error getting object info: {result['error']}"

        # Extract and format response
        cli_data = result["data"]
        if cli_data.get("total_commands", 0) > 0:
            cmd_result = cli_data["results"][0]["result"]
            if cmd_result.get("status") == "success":
                data = cmd_result.get("data", {})

                element = data.get("element", {})
                properties = data.get("properties", {})
                style = data.get("style", {})
                search_info = data.get("search_info", {})

                response_parts = [
                    f"🔍 **Object Information**",
                    f"**Search**: {search_info.get('search_method', 'unknown')} = {search_info.get('search_value', 'N/A')}",
                    "",
                    f"**Element**: {element.get('tag', 'unknown')} (ID: {element.get('id', 'no-id')})",
                ]

                if element.get("label"):
                    response_parts.append(f"**Label**: {element['label']}")

                if properties:
                    response_parts.append("**Properties**:")
                    for key, value in properties.items():
                        if value is not None:
                            response_parts.append(f"- {key}: {value}")

                if style:
                    response_parts.append("**Style**:")
                    for key, value in style.items():
                        response_parts.append(f"- {key}: {value}")

                return "\n".join(response_parts)
            else:
                error = cmd_result.get("data", {}).get("error", "Unknown error")
                return f"❌ {error}"

        return "❌ No response received"

    except Exception as e:
        logger.error(f"Error in get_object_info: {e}")
        return f"❌ Error getting object info: {e}"


@mcp.tool()
def get_object_property(
    ctx: Context,
    property: str,
    object_id: str = "",
    object_name: str = "",
    object_type: str = "",
    index: int = 0,
    use_selection: bool = False,
) -> str:
    """
    Get specific property values from objects.

    Parameters:
    - property: Property name (width, height, cx, cy, r, fill, stroke, etc.)
    - object_id: Target specific object by ID
    - object_name: Target object by Inkscape label/name
    - object_type: Target object by type (with index)
    - index: Which object of the type (0-based, used with object_type)
    - use_selection: Use currently selected objects instead of specified target

    Examples:
    - get_object_property("width", object_id="rect123")
    - get_object_property("r", object_type="circle", index=0)  # First circle's radius
    - get_object_property("fill", use_selection=True)  # Fill color of selected objects
    """
    try:
        connection = get_inkscape_connection()

        # Build command parameters
        params = [f"property={property}"]

        if use_selection:
            params.append("use_selection=true")
        elif object_id:
            params.append(f"object_id={object_id}")
        elif object_name:
            params.append(f"object_name='{object_name}'")
        elif object_type:
            params.append(f"object_type={object_type}")
            params.append(f"index={index}")
        else:
            return "❌ Error: Must specify target (object_id, object_name, object_type, or use_selection=True)"

        param_str = " ".join(params)
        command = f"get-object-property {param_str}"
        logger.info(f"Executing: {command}")
        result = connection.execute_cli_command(command)

        if not result["success"]:
            return f"❌ Error getting property: {result['error']}"

        # Extract and format response
        cli_data = result["data"]
        if cli_data.get("total_commands", 0) > 0:
            cmd_result = cli_data["results"][0]["result"]
            if cmd_result.get("status") == "success":
                data = cmd_result.get("data", {})

                search_info = data.get("search_info", {})
                results = data.get("results", [])

                if not results:
                    return f"❌ No objects found"

                response_parts = [
                    f"📏 **Property: {property}**",
                    f"**Search**: {search_info.get('search_method', 'unknown')} = {search_info.get('search_value', 'N/A')}",
                    f"**Objects found**: {len(results)}",
                    "",
                ]

                for i, obj in enumerate(results):
                    obj_id = obj.get("id", "no-id")
                    obj_tag = obj.get("tag", "unknown")
                    obj_label = obj.get("label", "")
                    prop_value = obj.get("properties", {}).get(property)

                    obj_desc = f"{obj_tag} (ID: {obj_id})"
                    if obj_label:
                        obj_desc += f" [{obj_label}]"

                    response_parts.append(f"{i + 1}. **{obj_desc}**")
                    response_parts.append(f"   {property}: {prop_value}")
                    response_parts.append("")

                return "\n".join(response_parts)
            else:
                error = cmd_result.get("data", {}).get("error", "Unknown error")
                return f"❌ {error}"

        return "❌ No response received"

    except Exception as e:
        logger.error(f"Error in get_object_property: {e}")
        return f"❌ Error getting property: {e}"


@mcp.tool()
def execute_inkex_code(ctx: Context, code: str, return_output: bool = True) -> str:
    """
    Execute arbitrary Python/inkex code in the Inkscape extension context.

    ⚠️ WHEN TO USE: Complex operations, algorithms, batch processing, custom element relationships.
    ✅ PREFER: draw_shape() for shapes, create_gradient() for gradients, other specific tools when available.

    Parameters:
    - code: Python code string to execute in the inkex context
    - return_output: Whether to capture and return stdout/stderr (default: True)

    Available variables: svg, self, document (SVG instance), inkex module, math, random, json, re, os

    Key syntax patterns:
    - Elements: element.set('attribute', 'value'); svg.append(element)
    - Styling: element.set('style', 'fill:red;stroke:blue') or element.set('fill', 'red')
    - Groups: group = inkex.Group(); group.append(element); svg.append(group)
    - Transforms: element.set('transform', 'translate(10,20) scale(2)')
    - Paths: path.set('d', 'M 10,10 L 100,100')
    - Find/modify: elem = svg.getElementById('id'); elem.set('fill', 'blue') if elem else None
    - Delete: elem.getparent().remove(elem) if elem else None
    - IDs: svg.get_unique_id('prefix')

    Use when specific tools cannot achieve the desired complex manipulation.
    """
    try:
        connection = get_inkscape_connection()

        # Build command for execute-inkex-code operation
        command_parts = ["execute-inkex-code"]

        # Use base64 encoding to safely pass code through shell
        import base64

        encoded_code = base64.b64encode(code.encode("utf-8")).decode("ascii")
        command_parts.append(f"code_base64={encoded_code}")

        if not return_output:
            command_parts.append("return_output=false")

        command = " ".join(command_parts)
        logger.info(f"Executing code: {code[:100]}{'...' if len(code) > 100 else ''}")
        result = connection.execute_cli_command(command)

        if not result["success"]:
            return f"❌ Code execution failed: {result['error']}"

        # Extract and format response
        cli_data = result["data"]
        if cli_data.get("total_commands", 0) > 0:
            cmd_result = cli_data["results"][0]["result"]
            if cmd_result.get("status") == "success":
                data = cmd_result.get("data", {})

                response_parts = []

                if data.get("execution_successful"):
                    response_parts.append("✅ **Code executed successfully**")
                else:
                    response_parts.append("❌ **Code execution failed**")

                # Show output if any
                if data.get("output"):
                    response_parts.append("**Output:**")
                    response_parts.append(f"```\n{data['output']}\n```")

                # Show return value if any
                if data.get("return_value"):
                    response_parts.append(f"**Return value:** {data['return_value']}")

                # Show elements created
                elements_created = data.get("elements_created", [])
                if elements_created:
                    response_parts.append("**Elements created:**")
                    for element_info in elements_created:
                        response_parts.append(f"- {element_info}")

                # Show current element counts
                element_counts = data.get("current_element_counts", {})
                if element_counts:
                    response_parts.append("**Current document elements:**")
                    for tag, count in sorted(element_counts.items()):
                        if tag not in [
                            "svg",
                            "namedview",
                            "defs",
                        ]:  # Skip structural elements
                            response_parts.append(f"- {tag}: {count}")

                # Show errors if any
                if data.get("errors"):
                    response_parts.append("**Errors:**")
                    response_parts.append(f"```\n{data['errors']}\n```")

                return (
                    "\n".join(response_parts)
                    if response_parts
                    else "✅ Code executed successfully"
                )
            else:
                error = cmd_result.get("data", {}).get("error", "Unknown error")
                return f"❌ {error}"

        return "❌ No response received"

    except Exception as e:
        logger.error(f"Error in execute_inkex_code: {e}")
        return f"❌ Error executing code: {e}"


@mcp.tool()
def get_viewport_screenshot(ctx: Context, max_size: int = 800) -> Union[str, ImageContent]:
    """
    Capture a screenshot of the current Inkscape document and return it as a displayable image.

    Parameters:
    - max_size: Maximum size in pixels for the largest dimension (default: 800)

    Returns the actual screenshot image that can be displayed directly by AI clients.
    """
    try:
        connection = get_inkscape_connection()

        # Export document as PNG with base64 return
        command = f"export-document-image format=png max_size={max_size} return_base64=true area=page"
        logger.info(f"Executing screenshot export with max_size={max_size}")
        result = connection.execute_cli_command(command)

        if not result["success"]:
            return f"❌ Screenshot export failed: {result['error']}"

        # Extract response data
        cli_data = result["data"]
        if cli_data.get("total_commands", 0) > 0:
            cmd_result = cli_data["results"][0]["result"]
            if cmd_result.get("status") == "success":
                data = cmd_result.get("data", {})

                # Check if we got base64 data
                if "base64_data" in data:
                    # Return the actual image content that AI clients can display
                    base64_data = data.get("base64_data", "")
                    export_path = data.get("export_path", "unknown")
                    file_size = data.get("file_size", 0)

                    # Create and return the image object directly
                    return ImageContent(
                        type="image",
                        data=base64_data,
                        mimeType="image/png"
                    )
                else:
                    # Fallback: return file path info
                    export_path = data.get("export_path", "unknown")
                    file_size = data.get("file_size", 0)
                    return f"📸 **Screenshot exported**\n\n**File**: {export_path}\n**Size**: {file_size} bytes\n**DPI**: {data.get('dpi', 96)}"

            else:
                error = cmd_result.get("data", {}).get("error", "Unknown error")
                return f"❌ {error}"

        return "❌ No response received"

    except Exception as e:
        logger.error(f"Error in get_viewport_screenshot: {e}")
        return f"❌ Error capturing screenshot: {e}"


@mcp.tool()
def create_gradient(
    ctx: Context,
    gradient_type: str,
    stops: str,
    gradient_units: str = "userSpaceOnUse",
    **additional_params
) -> str:
    """
    Create a gradient definition (linear or radial) that can be used to fill or stroke SVG elements.

    Parameters:
    - gradient_type: Either "linear" or "radial"
    - stops: Gradient color stops as JSON string (e.g. '[["0%","blue"],["100%","red"]]')
    - gradient_units: Coordinate system, "userSpaceOnUse" (default) or "objectBoundingBox"

    For LINEAR gradients, optionally provide:
    - x1, y1, x2, y2: Start and end coordinates (e.g. x1=0, y1=0, x2=100, y2=100)
    - If not provided, SVG uses defaults (horizontal gradient)

    For RADIAL gradients, optionally provide:
    - cx, cy, r: Center coordinates and radius (e.g. cx=100, cy=100, r=50)
    - fx, fy: Optional focal point (e.g. fx=90, fy=90)
    - If not provided, SVG uses defaults (centered gradient)

    Additional: gradientTransform, spreadMethod, etc. as named parameters.

    Returns element ID of created gradient for use in fill="url(#gradientId)".

    Examples:
    - Linear: create_gradient("linear", '[["0%","green"],["100%","red"]]', x1=0, y1=0, x2=100, y2=100)
    - Radial: create_gradient("radial", '[["0%","blue"],["100%","red"]]', cx=100, cy=100, r=50)
    """
    try:
        connection = get_inkscape_connection()

        # Validate gradient type
        if gradient_type not in ["linear", "radial"]:
            return f"❌ Invalid gradient_type: {gradient_type}. Use 'linear' or 'radial'."

        # Build command parameters
        params = {
            "stops": stops,
            "gradientUnits": gradient_units
        }
        params.update(additional_params)

        # Build command string
        param_parts = []
        for key, value in params.items():
            if isinstance(value, str) and (' ' in value or '"' in value):
                param_parts.append(f"{key}='{value}'")
            else:
                param_parts.append(f"{key}={value}")

        command = f"{gradient_type}-gradient {' '.join(param_parts)}"
        result = connection.execute_cli_command(command)

        if not result["success"]:
            return f"❌ Error creating {gradient_type} gradient: {result['error']}"

        # Parse response
        cli_data = result["data"]
        if cli_data.get("total_commands", 0) > 0:
            cmd_result = cli_data["results"][0]["result"]
            if cmd_result.get("status") == "success":
                data = cmd_result.get("data", {})
                gradient_id = data.get("id", "unknown")
                stops_count = data.get("stops_count", 0)

                # Format response based on gradient type
                if gradient_type == "radial":
                    cx = additional_params.get("cx", "?")
                    cy = additional_params.get("cy", "?")
                    r = additional_params.get("r", "?")
                    return f"✅ **Radial gradient created**\n**ID**: `{gradient_id}`\n**Center**: ({cx}, {cy})\n**Radius**: {r}\n**Stops**: {stops_count}\n**Usage**: `fill=\"url(#{gradient_id})\"`"
                else:  # linear
                    x1 = additional_params.get("x1", "?")
                    y1 = additional_params.get("y1", "?")
                    x2 = additional_params.get("x2", "?")
                    y2 = additional_params.get("y2", "?")
                    return f"✅ **Linear gradient created**\n**ID**: `{gradient_id}`\n**Start**: ({x1}, {y1})\n**End**: ({x2}, {y2})\n**Stops**: {stops_count}\n**Usage**: `fill=\"url(#{gradient_id})\"`"
            else:
                error = cmd_result.get("data", {}).get("error", "Unknown error")
                return f"❌ {error}"

        return "❌ No response received"

    except Exception as e:
        logger.error(f"Error in create_gradient: {e}")
        return f"❌ Error creating {gradient_type} gradient: {e}"


def main():
    """Run the Inkscape MCP server"""
    logger.info("Starting Inkscape MCP Server...")
    mcp.run()


if __name__ == "__main__":
    main()

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
from typing import Any, AsyncIterator, Dict, List, Optional

from mcp.server.fastmcp import FastMCP, Context

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
    Draw a shape in Inkscape with specified parameters.

    Parameters:
    - shape_type: Type of shape (rectangle, circle, ellipse, line, polygon, polyline, text, path)
    - **params: Shape-specific parameters (x, y, width, height, cx, cy, r, fill, stroke, etc.)

    Examples:
    - Rectangle: draw_shape("rectangle", x=100, y=50, width=200, height=100, fill="lightblue")
    - Circle: draw_shape("circle", cx=150, cy=150, r=75, stroke="red", stroke_width=3)
    - Text: draw_shape("text", x=50, y=200, text_content="Hello World!", font_size=18, fill="blue")
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

    This provides the same flexibility as Blender MCP - you can run any Python code
    with full access to the inkex API and SVG document manipulation.

    Parameters:
    - code: Python code string to execute in the inkex context
    - return_output: Whether to capture and return stdout/stderr (default: True)

    Available in execution context:
    - svg, self, document: The current SVG document/extension instance
    - inkex module: import inkex (Rectangle, Circle, Ellipse, Polygon, etc.)
    - Python libraries: math, random, json, re, os

    CRITICAL SYNTAX PATTERNS:

    - Create elements with appropriate group and identifiable IDs, e.g. creating simple tree - create group (id: tree1)
      with trunk (rectangle id: tree1-trunk), foliage (circles with ids foliage-1, foliage-2, foliage-3 etc.)

    self refers to SvgDocumentElement here
    - document = self
    - rootElem = self.root

    Shape Creation (use .set() method):
    - rect = inkex.Rectangle(); rect.set('x', '10'); rect.set('width', '100'); svg.append(rect)
    - circle = inkex.Circle(); circle.set('cx', '50'); circle.set('r', '25'); svg.append(circle)
    - poly = inkex.Polygon(); poly.set('points', '0,0 100,0 50,50'); svg.append(poly)

    Styling (NOT dicts - use strings or individual properties):
    - element.set('style', 'fill:#ff0000;stroke:#000000;stroke-width:2')
    - element.set('fill', '#ff0000'); element.set('stroke', '#000000')

    Gradients (proper Inkscape gradient definition):
    - Linear: grad = inkex.LinearGradient(); grad.set('id', 'myGrad'); defs.append(grad)
    - Radial: rgrad = inkex.RadialGradient(); rgrad.set('xlink:href', '#myGrad'); rgrad.set('gradientUnits', 'userSpaceOnUse'); rgrad.set('cx', '100'); defs.append(rgrad)
    - Usage: element.set('style', 'fill:url(#gradientId);stroke:none')

    Finding/Modifying Elements:
    - elem = svg.getElementById('my-id'); elem.set('fill', 'blue') if elem is not None else None
    - for e in svg.iter(): e.set('opacity', '0.5') if e.tag.endswith('circle') else None

    Deleting Elements (use 'is not None' check):
    - elem = svg.getElementById('my-id')
    - if elem is not None: elem.getparent().remove(elem)

    Coordinate System: 1 user unit = 1mm in document coordinates
    Groups: group = inkex.Group(); group.append(shape); svg.append(group)
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
def get_viewport_screenshot(ctx: Context, max_size: int = 800) -> str:
    """
    Capture a screenshot of the current Inkscape document.

    Parameters:
    - max_size: Maximum size in pixels for the largest dimension (default: 800)

    Returns the screenshot as an Image.
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
                    # Return file path info and suggest viewing the exported file
                    export_path = data.get("export_path", "unknown")
                    file_size = data.get("file_size", 0)
                    data_size = data.get("data_size", 0)

                    return f"📸 **Screenshot captured successfully**\n\n**File**: {export_path}\n**Size**: {file_size} bytes\n**Image Data**: {data_size} chars (base64)\n**DPI**: {data.get('dpi', 96)}\n**Format**: PNG\n\n*Screenshot saved as PNG file*"
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


def main():
    """Run the Inkscape MCP server"""
    logger.info("Starting Inkscape MCP Server...")
    mcp.run()


if __name__ == "__main__":
    main()

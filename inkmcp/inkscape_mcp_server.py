#!/usr/bin/env python3
"""
Inkscape MCP Server
Model Context Protocol server for controlling Inkscape via D-Bus extension

Provides access to Inkscape operations through a unified tool interface
for SVG element creation, document manipulation, and code execution.
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
DEFAULT_ACTION_NAME = "org.khema.inkscape.mcp"


class InkscapeConnection:
    """Manages D-Bus connection to Inkscape"""

    def __init__(self):
        self.dbus_service = DEFAULT_DBUS_SERVICE
        self.dbus_path = DEFAULT_DBUS_PATH
        self.dbus_interface = DEFAULT_DBUS_INTERFACE
        self.action_name = DEFAULT_ACTION_NAME
        self._client_path = Path(__file__).parent / "inkmcpcli.py"

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

            # Check if our generic MCP extension action is listed
            output = result.stdout
            return self.action_name in output

        except Exception as e:
            logger.error(f"Error checking Inkscape availability: {e}")
            return False

    def execute_operation(self, operation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute operation using CLI client"""
        try:
            # Write operation data to temporary file
            params_file = os.path.join(tempfile.gettempdir(), "mcp_params.json")

            with open(params_file, "w") as f:
                json.dump(operation_data, f)

            # Execute via D-Bus
            cmd = [
                "gdbus",
                "call",
                "--session",
                "--dest",
                self.dbus_service,
                "--object-path",
                self.dbus_path,
                "--method",
                f"{self.dbus_interface}.Activate",
                self.action_name,
                "[]",
                "{}",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                logger.error(f"D-Bus command failed: {result.stderr}")
                return {
                    "status": "error",
                    "data": {"error": f"D-Bus call failed: {result.stderr}"},
                }

            # Read response from response file
            response_file = operation_data.get("response_file")
            if response_file and os.path.exists(response_file):
                try:
                    with open(response_file, "r") as f:
                        response_data = json.load(f)
                    os.remove(response_file)  # Clean up
                    return response_data
                except Exception as e:
                    logger.error(f"Failed to read response file: {e}")
                    return {
                        "status": "error",
                        "data": {"error": f"Response file error: {e}"},
                    }
            else:
                # Assume success if no response file specified
                return {"status": "success", "data": {"message": "Operation completed"}}

        except subprocess.TimeoutExpired:
            logger.error("Operation timed out")
            return {"status": "error", "data": {"error": "Operation timed out"}}
        except Exception as e:
            logger.error(f"Operation execution error: {e}")
            return {"status": "error", "data": {"error": str(e)}}


# Global connection instance
_inkscape_connection: Optional[InkscapeConnection] = None


def get_inkscape_connection() -> InkscapeConnection:
    """Get or create Inkscape connection"""
    global _inkscape_connection

    if _inkscape_connection is None:
        _inkscape_connection = InkscapeConnection()

    if not _inkscape_connection.is_available():
        raise Exception(
            "Inkscape is not running or generic MCP extension is not available. "
            "Please start Inkscape and ensure the generic MCP extension is installed."
        )

    return _inkscape_connection


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    """Manage server startup and shutdown lifecycle"""
    logger.info("Inkscape MCP server starting up")

    try:
        # Test connection on startup
        try:
            connection = get_inkscape_connection()
            logger.info("Successfully connected to Inkscape on startup")
        except Exception as e:
            logger.warning(f"Could not connect to Inkscape on startup: {e}")
            logger.warning(
                "Make sure Inkscape is running with the generic MCP extension before using tools"
            )

        yield {}
    finally:
        logger.info("Inkscape MCP server shut down")


# Create the MCP server
mcp = FastMCP("InkscapeMCP", lifespan=server_lifespan)


def format_response(result: Dict[str, Any]) -> str:
    """Format operation result for clean AI client display"""
    if result.get("status") == "success":
        data = result.get("data", {})
        message = data.get("message", "Operation completed successfully")

        # Add relevant details based on operation type
        details = []

        # Element creation details
        if "id" in data:
            details.append(f"**ID**: `{data['id']}`")
        if "tag" in data:
            details.append(f"**Type**: {data['tag']}")

        # Selection/info details
        if "count" in data:
            details.append(f"**Count**: {data['count']}")
        if "elements" in data:
            elements = data["elements"]
            if elements:
                details.append(f"**Elements**: {len(elements)} items")
                # Show first few elements
                for i, elem in enumerate(elements[:3]):
                    elem_desc = (
                        f"{elem.get('tag', 'unknown')} ({elem.get('id', 'no-id')})"
                    )
                    details.append(f"  {i + 1}. {elem_desc}")
                if len(elements) > 3:
                    details.append(f"  ... and {len(elements) - 3} more")

        # Export details
        if "export_path" in data:
            details.append(f"**File**: {data['export_path']}")
        if "file_size" in data:
            details.append(f"**Size**: {data['file_size']} bytes")

        # Code execution details
        if "execution_successful" in data:
            if data["execution_successful"]:
                details.append("**Execution**: ✅ Success")
            else:
                details.append("**Execution**: ❌ Failed")
        if "elements_created" in data and data["elements_created"]:
            details.append(f"**Created**: {len(data['elements_created'])} elements")

        # ID mapping (requested → actual)
        if "id_mapping" in data and data["id_mapping"]:
            details.append("**Element IDs** (requested → actual):")
            for requested_id, actual_id in data["id_mapping"].items():
                if requested_id == actual_id:
                    details.append(f"  {requested_id} ✓")
                else:
                    details.append(
                        f"  {requested_id} → {actual_id} (collision resolved)"
                    )

        # Warning for missing IDs
        if "generated_ids" in data and data["generated_ids"]:
            details.append("⚠️  **WARNING: Elements created without IDs**")
            details.append(
                "For better scene management, always specify 'id' for elements:"
            )
            for gen_id in data["generated_ids"]:
                # Extract element type from generated ID (e.g., "circle2863" → "circle")
                elem_type = "".join(c for c in gen_id if c.isalpha())
                details.append(f"  {gen_id} (use: {elem_type} id=my_name ...)")
            details.append(
                "This enables later modification with execute-code commands."
            )

        # Build final response with appropriate emoji
        # Check if this is a failed code execution
        is_code_failure = (
            "execution_successful" in data and
            data["execution_successful"] == False
        )

        emoji = "❌" if is_code_failure else "✅"

        if details:
            return f"{emoji} {message}\n\n" + "\n".join(details)
        else:
            return f"{emoji} {message}"

    else:
        error = result.get("data", {}).get("error", "Unknown error")
        return f"❌ {error}"


@mcp.tool()
def inkscape_operation(ctx: Context, command: str) -> Union[str, ImageContent]:
    """
    Execute any Inkscape operation using the extension system.

    CRITICAL SYNTAX RULES - READ CAREFULLY:
    1. Single string parameter with space-separated key=value pairs
    2. Children use special bracket syntax: children=[{tag attr=val attr=val}, {tag attr=val}]
    3. NOT JSON objects - use space-separated attributes inside braces
    4. Use 'svg' variable in execute-code, NOT 'self.svg'

    Parameter: command (str) - Command string following exact syntax below

    ═══ BASIC ELEMENTS ═══
    MANDATORY: Always specify id for every element to enable later modification:
    ✅ CORRECT: "rect id=main_rect x=100 y=50 width=200 height=100 fill=blue stroke=black stroke-width=2"
    ✅ CORRECT: "circle id=logo_circle cx=150 cy=150 r=75 fill=#ff0000"
    ✅ CORRECT: "text id=title_text x=50 y=100 text='Hello World' font-size=16 fill=black"

    ❌ WRONG: "rect x=100 y=50 width=200" - Missing id! Always specify id for element management
    ❌ WRONG: {"rect": {"x": 100, "y": 50}} - This is JSON, we don't use JSON!

    ═══ NESTED ELEMENTS (Groups) ═══
    Groups with children - ALWAYS specify id for parent and ALL children:
    ✅ CORRECT: "g id=house children=[{rect id=house_body x=100 y=200 width=200 height=150 fill=#F5DEB3}, {path id=house_roof d='M 90,200 L 200,100 L 310,200 Z' fill=#A52A2A}]"

    ❌ WRONG: "g children=[{rect x=100 y=200}]" - Missing id for group and rect!
    ❌ WRONG: "g children=[{\"rect\": {\"x\": 100}}]" - Don't use JSON syntax!
    ❌ WRONG: "g children=[rect x=100 y=200]" - Missing braces around each child!

    ═══ CODE EXECUTION ═══
    Execute Python code - use 'svg' variable, not 'self.svg':
    CRITICAL: inkex elements require .set() method with string values, NOT constructor arguments!

    ✅ CORRECT: "execute-code code='rect = inkex.Rectangle(); rect.set(\"x\", \"100\"); rect.set(\"y\", \"100\"); rect.set(\"width\", \"100\"); rect.set(\"height\", \"100\"); rect.set(\"fill\", \"blue\"); svg.append(rect)'"
    ✅ CORRECT: "execute-code code='circle = inkex.Circle(); circle.set(\"cx\", \"150\"); circle.set(\"cy\", \"100\"); circle.set(\"r\", \"20\"); svg.append(circle)'"

    Single-line code (use semicolons for multiple statements):
    ✅ CORRECT: "execute-code code='order=[\"el1\",\"el2\"]; for oid in order: el=svg.getElementById(oid); if el: parent=el.getparent(); parent.remove(el); svg.append(el)'"

    Multiline code (MUST be properly quoted with single quotes):
    ✅ CORRECT: "execute-code code='for i in range(3):\n    circle = inkex.Circle()\n    circle.set(\"cx\", str(i*50+100))\n    circle.set(\"cy\", \"100\")\n    circle.set(\"r\", \"20\")\n    svg.append(circle)'"

    Element reordering pattern:
    ✅ CORRECT: "execute-code code='el=svg.getElementById(\"my_element\"); if el: parent=el.getparent(); parent.remove(el); svg.append(el)'"

    Element modification patterns:
    ✅ CORRECT: "execute-code code='el=svg.getElementById(\"house_body\"); el.set(\"fill\", \"brown\") if el else None'"

    ❌ WRONG: "execute-code code='self.svg.append(...)'" - Use 'svg' not 'self.svg'!
    ❌ WRONG: "execute-code code='rect = inkex.Rectangle(x=100, y=100)'" - Constructor args don't work!
    ❌ WRONG: "execute-code code='circle = inkex.Circle(cx=100, cy=100, r=20)'" - Use .set() method!
    ❌ WRONG: Unquoted multiline code - Always wrap multiline code in single quotes!

    ═══ INFO & EXPORT OPERATIONS ═══
    ✅ "get-selection" - Get info about selected objects
    ✅ "get-info" - Get document information
    ✅ "export-document-image format=png return_base64=true" - Screenshot

    ═══ GRADIENTS ═══
    ✅ "linearGradient stops='[[\"0%\",\"red\"],[\"100%\",\"blue\"]]' x1=0 y1=0 x2=100 y2=100"

    ═══ ID MANAGEMENT ═══
    ALWAYS specify id for every element - this enables later modification and scene management:
    - Input: "g id=scene children=[{rect id=house x=0 y=0}, {circle id=sun cx=100 cy=50}]"
    - Returns: {"id_mapping": {"scene": "scene", "house": "house", "sun": "sun"}}
    - Collision handling: If "house" exists, creates "house_1" and returns {"house": "house_1"}

    Benefits of using IDs:
    - Direct access: svg.getElementById("house") in later execute-code commands
    - Scene management: Modify specific elements by ID
    - Clear organization: Hierarchical naming (house_body, house_roof, etc.)

    ═══ SEMANTIC SCENE ORGANIZATION ═══
    When creating complex scenes, use hierarchical grouping with descriptive IDs:

    Example - Creating a park scene with tree:
    ✅ "g id=park_scene children=[{g id=tree1 children=[{rect id=trunk1 x=100 y=200 width=20 height=60 fill=brown}, {circle id=foliage1_1 cx=110 cy=180 r=25 fill=green}, {circle id=foliage1_2 cx=105 cy=175 r=20 fill=darkgreen}]}, {g id=house children=[{rect id=house_body x=200 y=180 width=80 height=60 fill=beige}, {polygon id=house_roof points='195,180 240,150 285,180' fill=red}]}]"

    ID Naming Examples:
    - Scene: id=park_scene, id=city_view, id=landscape
    - Objects: id=tree1, id=tree2, id=house, id=car1
    - Parts: id=trunk1, id=house_body, id=car1_wheel_left
    - Sub-parts: id=foliage1_1, id=foliage1_2, id=house_window1

    Later Modification Examples:
    - Change trunk color: execute-code code="svg.getElementById('trunk1').set('fill', 'darkbrown')"
    - Move entire tree: execute-code code="svg.getElementById('tree1').set('transform', 'translate(50,0)')"
    - Add details: execute-code code="svg.getElementById('house').append(new_window_element)"

    REMEMBER: Space-separated key=value pairs, NOT JSON! Use 'svg' in code, NOT 'self.svg'!
    """
    try:
        connection = get_inkscape_connection()

        # Create unique response file for this operation
        response_fd, response_file = tempfile.mkstemp(
            suffix=".json", prefix="mcp_response_"
        )
        os.close(response_fd)

        # Parse the command string using the same logic as our client
        from refactor.generic_client import parse_command_string

        parsed_data = parse_command_string(command)

        # Add response file to the operation data
        parsed_data["response_file"] = response_file

        logger.info(f"Executing command: {command}")
        logger.debug(f"Parsed data: {parsed_data}")

        result = connection.execute_operation(parsed_data)

        # Handle image export special case
        if (
            parsed_data.get("tag") == "export-document-image"
            and result.get("status") == "success"
            and "base64_data" in result.get("data", {})
        ):
            # Return actual image for viewport screenshot
            base64_data = result["data"]["base64_data"]
            return ImageContent(type="image", data=base64_data, mimeType="image/png")

        # Format and return text response
        return format_response(result)

    except Exception as e:
        logger.error(f"Error in inkscape_operation: {e}")
        return f"❌ Operation failed: {str(e)}"
    finally:
        # Clean up response file if it exists
        try:
            if "response_file" in locals() and os.path.exists(response_file):
                os.remove(response_file)
        except:
            pass


def main():
    """Run the Inkscape MCP server"""
    logger.info("Starting Inkscape MCP Server...")
    mcp.run()


if __name__ == "__main__":
    main()


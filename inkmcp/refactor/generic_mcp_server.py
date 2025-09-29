#!/usr/bin/env python3
"""
Generic Inkscape MCP Server
A streamlined Model Context Protocol server for controlling Inkscape via our refactored generic extension

Provides natural language access to all Inkscape operations through a single unified tool
that dynamically handles any SVG element or operation type with clean JSON structure.
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
logger = logging.getLogger("GenericInkscapeMCP")

# Server configuration
DEFAULT_DBUS_SERVICE = "org.inkscape.Inkscape"
DEFAULT_DBUS_PATH = "/org/inkscape/Inkscape"
DEFAULT_DBUS_INTERFACE = "org.gtk.Actions"
DEFAULT_ACTION_NAME = "org.mcp.inkscape.draw.generic"


class InkscapeConnection:
    """Manages D-Bus connection to Inkscape using the generic extension"""

    def __init__(self):
        self.dbus_service = DEFAULT_DBUS_SERVICE
        self.dbus_path = DEFAULT_DBUS_PATH
        self.dbus_interface = DEFAULT_DBUS_INTERFACE
        self.action_name = DEFAULT_ACTION_NAME
        self._client_path = Path(__file__).parent / "generic_client.py"

    def is_available(self) -> bool:
        """Check if Inkscape is running and generic MCP extension is available"""
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
        """Execute operation using our generic client"""
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
                "{}"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                logger.error(f"D-Bus command failed: {result.stderr}")
                return {"status": "error", "data": {"error": f"D-Bus call failed: {result.stderr}"}}

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
                    return {"status": "error", "data": {"error": f"Response file error: {e}"}}
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
    logger.info("Generic Inkscape MCP server starting up")

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
        logger.info("Generic Inkscape MCP server shut down")


# Create the MCP server
mcp = FastMCP("GenericInkscapeMCP", lifespan=server_lifespan)


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
                    elem_desc = f"{elem.get('tag', 'unknown')} ({elem.get('id', 'no-id')})"
                    details.append(f"  {i+1}. {elem_desc}")
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

        # ID mapping details (new feature)
        if "id_mapping" in data and data["id_mapping"]:
            details.append("**ID Mappings**:")
            for map_id, actual_id in data["id_mapping"].items():
                details.append(f"  {map_id} → {actual_id}")

        # Build final response
        if details:
            return f"✅ {message}\n\n" + "\n".join(details)
        else:
            return f"✅ {message}"

    else:
        error = result.get("data", {}).get("error", "Unknown error")
        return f"❌ {error}"


@mcp.tool()
def inkscape_operation(ctx: Context, command: str) -> Union[str, ImageContent]:
    """
    Execute any Inkscape operation using the generic extension system.

    This unified tool handles all SVG operations dynamically using a single string command
    with consistent syntax for all operations - element creation, document queries, exports, and code execution.

    Parameter:
    - command: Operation command string with space-separated key=value parameters

    ELEMENT CREATION:
    Create any SVG element with attributes and nested children:
    - "rect x=100 y=50 width=200 height=100 fill=blue"
    - "circle cx=150 cy=150 r=75 fill='url(#myGradient)'"
    - "g map_id=myGroup children=[{rect map_id=rect_1 x=0 y=0 width=50 height=50}, {circle map_id=circle_1 cx=25 cy=25 r=20}]"

    GRADIENT CREATION:
    - "linearGradient map_id=grad1 stops='[[\"0%\",\"red\"],[\"100%\",\"blue\"]]' x1=0 y1=0 x2=100 y2=100"
    - "radialGradient map_id=grad2 stops='[[\"0%\",\"white\"],[\"100%\",\"black\"]]' cx=100 cy=100 r=50"

    INFORMATION OPERATIONS:
    - "get-selection" - Get info about currently selected objects
    - "get-info" - Get document dimensions and element counts
    - "get-info-by-id id=element_id" - Get specific element information

    EXPORT OPERATIONS:
    - "export-document-image format=png return_base64=true" - Screenshot as base64 image
    - "export-document-image format=svg area=selection" - Export selection as SVG file

    CODE EXECUTION:
    - "execute-code code='for i in range(3): svg.append(inkex.Rectangle(x=i*50, y=0, width=40, height=40))'"

    ID MAPPING SYSTEM:
    Use map_id parameter to assign logical IDs that get mapped to actual generated IDs:
    - Client sends: "g map_id=header children=[{rect map_id=bg x=0 y=0}, {text map_id=title text='Hello'}]"
    - Server returns: {"id_mapping": {"header": "g_123", "bg": "rect_456", "title": "text_789"}}
    - All map_ids within a single command must be unique

    SYNTAX RULES:
    - Parameters: key=value separated by spaces
    - Quotes: Use single or double quotes for values with spaces/special chars
    - Children: Use children=[{...}, {...}] for nested elements
    - Lists: JSON format for arrays like stops='[["0%","red"],["100%","blue"]]'

    Returns consistent formatted responses with operation results and ID mappings for element creation.
    """
    try:
        connection = get_inkscape_connection()

        # Create unique response file for this operation
        response_fd, response_file = tempfile.mkstemp(suffix='.json', prefix='mcp_response_')
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
        if (parsed_data.get("tag") == "export-document-image" and
            result.get("status") == "success" and
            "base64_data" in result.get("data", {})):

            # Return actual image for viewport screenshot
            base64_data = result["data"]["base64_data"]
            return ImageContent(
                type="image",
                data=base64_data,
                mimeType="image/png"
            )

        # Format and return text response
        return format_response(result)

    except Exception as e:
        logger.error(f"Error in inkscape_operation: {e}")
        return f"❌ Operation failed: {str(e)}"
    finally:
        # Clean up response file if it exists
        try:
            if 'response_file' in locals() and os.path.exists(response_file):
                os.remove(response_file)
        except:
            pass


def main():
    """Run the Generic Inkscape MCP server"""
    logger.info("Starting Generic Inkscape MCP Server...")
    mcp.run()


if __name__ == "__main__":
    main()
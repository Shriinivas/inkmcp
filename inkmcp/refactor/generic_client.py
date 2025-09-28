#!/usr/bin/env python3
"""
Generic Inkscape MCP Client
Command-line interface for creating any SVG element via D-Bus MCP extension with unified parsing

Usage:
    python generic_client.py <tag> '<attributes>'

Attribute Format:
    - Basic: key=value (e.g., cx=100, fill=red)
    - Quoted values: key="value with spaces" or key='value with spaces'
    - Children: children=[{tag 'attr1=val1 attr2=val2'}, {tag 'attr3=val3'}]

Basic Shape Examples:
    python generic_client.py circle 'cx=100 cy=100 r=50 fill=red'
    python generic_client.py rect 'x=10 y=10 width=100 height=50 fill=blue'
    python generic_client.py text 'x=50 y=50 font-size=14 content="Hello World"'

Linear Gradient Examples:
    # userSpaceOnUse (shows immediately)
    python generic_client.py linearGradient "x1=0 y1=0 x2=300 y2=0 gradientUnits=userSpaceOnUse children=[{stop 'offset=\"0%\" stop-color=\"purple\"'}, {stop 'offset=\"100%\" stop-color=\"orange\"'}]"

    # objectBoundingBox (may need nudge to refresh)
    python generic_client.py linearGradient "x1=0 y1=0 x2=1 y2=1 gradientUnits=objectBoundingBox children=[{stop 'offset=\"0%\" stop-color=\"cyan\"'}, {stop 'offset=\"100%\" stop-color=\"magenta\"'}]"

Radial Gradient Examples:
    # userSpaceOnUse
    python generic_client.py radialGradient "cx=150 cy=150 r=80 gradientUnits=userSpaceOnUse children=[{stop 'offset=\"0%\" stop-color=\"white\"'}, {stop 'offset=\"100%\" stop-color=\"black\"'}]"

    # objectBoundingBox
    python generic_client.py radialGradient "cx=0.5 cy=0.5 r=0.7 gradientUnits=objectBoundingBox children=[{stop 'offset=\"0%\" stop-color=\"gold\"'}, {stop 'offset=\"100%\" stop-color=\"darkred\"'}]"

Applying Gradients to Shapes:
    python generic_client.py circle "cx=100 cy=100 r=50 fill=url(#linearGradient123)"
    python generic_client.py rect "x=10 y=10 width=100 height=80 fill=url(#radialGradient456)"

Complex Nested Examples:
    # Group with multiple children
    python generic_client.py g "id=\"my-group\" children=[{circle 'cx=50 cy=50 r=25 fill=red'}, {rect 'x=0 y=0 width=20 height=20 fill=blue'}]"

Quoting Guidelines:
    - Use double quotes for outer shell string: "..."
    - Use single quotes for attribute values inside children: '...'
    - Escape quotes when needed: 'content=\"Hello World\"'
    - For spaces in values: 'font-family=\"Arial Black\"'

Supported Elements:
    - All standard SVG elements (circle, rect, line, path, text, g, etc.)
    - Gradient elements (linearGradient, radialGradient with stops)
    - Dynamic class mapping: tag → Capitalized inkex class (e.g., linearGradient → LinearGradient)

Known Issue: objectBoundingBox gradients require manual nudge to refresh visibility in Inkscape UI
- This is an Inkscape rendering quirk, not a client implementation issue
- userSpaceOnUse gradients display immediately without refresh issues
- Workaround: Use userSpaceOnUse coordinate system for immediate visibility
- TODO: Investigate programmatic fix for objectBoundingBox refresh issue
"""

import argparse
import sys
import json
import tempfile
import os
import subprocess
import re
from typing import Dict, List, Any, Optional, Union


class GenericInkscapeClient:
    """D-Bus client for generic SVG element creation"""

    def __init__(self):
        self.dbus_service = "org.inkscape.Inkscape"
        self.dbus_path = "/org/inkscape/Inkscape"
        self.dbus_interface = "org.gtk.Actions"
        self.action_name = "org.mcp.inkscape.draw.generic"

    def parse_children_array(self, children_str: str) -> List[Dict[str, Any]]:
        """
        Parse children array string into list of element data

        Args:
            children_str: String like "[{stop 'offset=\"0%\"'}, {circle 'cx=10'}]"

        Returns:
            List of element data dictionaries
        """
        children = []

        # Remove outer brackets
        if children_str.startswith('[') and children_str.endswith(']'):
            inner = children_str[1:-1].strip()

            if not inner:
                return children

            # Simple approach: find balanced braces
            child_strings = []
            current = ""
            brace_count = 0
            i = 0

            while i < len(inner):
                char = inner[i]

                if char == '{':
                    if brace_count == 0:
                        # Start of new child
                        current = char
                    else:
                        current += char
                    brace_count += 1
                elif char == '}':
                    current += char
                    brace_count -= 1
                    if brace_count == 0:
                        # End of current child
                        child_strings.append(current.strip())
                        current = ""
                        # Skip comma and whitespace
                        i += 1
                        while i < len(inner) and inner[i] in [',', ' ', '\t', '\n']:
                            i += 1
                        i -= 1  # Compensate for the loop increment
                elif brace_count > 0:
                    # Inside braces, collect everything
                    current += char

                i += 1

            # Add any remaining content
            if current.strip():
                child_strings.append(current.strip())

            # Parse each child string
            for child_str in child_strings:
                if child_str.startswith('{') and child_str.endswith('}'):
                    child_content = child_str[1:-1].strip()
                    # Parse as "tag attributes"
                    child_data = self.parse_tag_and_attributes(child_content)
                    if child_data:
                        children.append(child_data)

        return children

    def parse_tag_and_attributes(self, content: str) -> Dict[str, Any]:
        """
        Parse content like "stop 'offset=\"0%\" stop-color=\"blue\"'" into element data

        Args:
            content: String with tag followed by attributes

        Returns:
            Element data dictionary or None if parsing fails
        """
        content = content.strip()
        if not content:
            return None

        # Split into tag and attributes
        parts = content.split(None, 1)  # Split on first whitespace
        if not parts:
            return None

        tag = parts[0]
        attr_str = parts[1] if len(parts) > 1 else ""

        # Parse attributes using existing logic
        attributes = self.parse_attributes(attr_str)

        element_data = {
            "tag": tag,
            "attributes": attributes
        }

        # Handle nested children recursively
        if 'children' in attributes:
            children_value = attributes.pop('children')
            if isinstance(children_value, str):
                element_data["children"] = self.parse_children_array(children_value)
            else:
                element_data["children"] = children_value

        return element_data

    def parse_attributes(self, param_str: str) -> Dict[str, Any]:
        """
        Parse parameter string into attributes dictionary

        Args:
            param_str: Parameter string like "x1=0 y1=0 fill=blue children=[{...}]"

        Returns:
            Dictionary with parsed attributes
        """
        if not param_str.strip():
            return {}

        attributes = {}

        # Enhanced regex to handle quoted values, arrays, and objects
        param_pattern = r'(\w+(?:[_-]\w+)*)=("([^"]*)"|\'([^\']*)\'|(\[(?:[^\[\]]|\{[^}]*\}|\[[^\]]*\])*\])|([^\s,=]+))'
        raw_matches = re.findall(param_pattern, param_str)

        for match in raw_matches:
            key = match[0]

            # Extract value from capture groups
            if match[2]:  # double-quoted
                value = match[2]
            elif match[3]:  # single-quoted
                value = match[3]
            elif match[4]:  # array (children)
                value = match[4]
            else:  # unquoted
                value = match[5] if match[5] else match[1]

            # Handle children arrays specially
            if key == 'children' and isinstance(value, str) and value.startswith('['):
                attributes[key] = value  # Keep as string for further processing
            elif value.lower() in ['true', 'false']:
                attributes[key] = value.lower() == 'true'
            elif value.lower() in ['none', 'null']:
                attributes[key] = None
            else:
                attributes[key] = value

        return attributes

    def build_element_data(self, tag: str, param_str: str) -> Dict[str, Any]:
        """
        Build element data structure from tag and parameters

        Args:
            tag: SVG tag name (e.g., 'linearGradient', 'circle')
            param_str: Parameter string

        Returns:
            Element data dictionary
        """
        # Use the unified parsing approach
        full_content = f"{tag} {param_str}".strip()
        return self.parse_tag_and_attributes(full_content)

    def execute_command(self, element_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute command via D-Bus"""
        try:
            # Create temporary response file for reverse communication (like original system)
            response_file = tempfile.mktemp(suffix='.json', prefix='inkmcp_response_')
            element_data['response_file'] = response_file

            # Write parameters to fixed JSON file (like original system)
            params_file = os.path.join(tempfile.gettempdir(), "mcp_params.json")
            with open(params_file, 'w') as f:
                json.dump(element_data, f)

            # Execute D-Bus command (like original system)
            cmd = [
                "gdbus", "call",
                "--session",
                "--dest", self.dbus_service,
                "--object-path", self.dbus_path,
                "--method", f"{self.dbus_interface}.Activate",
                self.action_name,
                "[]", "{}"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"D-Bus command failed: {result.stderr}"
                }

            # Read response from response file (like original system)
            if os.path.exists(response_file):
                try:
                    with open(response_file, 'r') as f:
                        response = json.load(f)
                    os.remove(response_file)
                    return {"success": True, "response": response}
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Failed to read response: {str(e)}"
                    }

            return {"success": True, "output": result.stdout}

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Command timed out after 30 seconds"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Execution failed: {str(e)}"
            }

    def format_response(self, result: Dict[str, Any]) -> str:
        """Format the response for display"""
        if not result.get("success"):
            return f"❌ Error: {result.get('error', 'Unknown error')}"

        # Check if we have a proper response from response file
        if "response" in result:
            response_data = result["response"]
            if response_data.get("status") == "success":
                data = response_data.get("data", {})
                element_id = data.get("id", "unknown")
                message = data.get("message", "Element created successfully")
                return f"✅ {message}\n**ID**: `{element_id}`"
            else:
                error = response_data.get("data", {}).get("error", "Unknown error")
                return f"❌ Error: {error}"

        # Fallback to raw output parsing
        try:
            output = result.get("output", "")
            # D-Bus returns output in format like "('result_here',)"
            if output.startswith("('") and output.endswith("',)"):
                output = output[2:-3]  # Remove D-Bus wrapping

            response_data = json.loads(output)

            if response_data.get("status") == "success":
                data = response_data.get("data", {})
                element_id = data.get("id", "unknown")
                message = data.get("message", "Element created successfully")
                return f"✅ {message}\n**ID**: `{element_id}`"
            else:
                error = response_data.get("data", {}).get("error", "Unknown error")
                return f"❌ Error: {error}"

        except (json.JSONDecodeError, KeyError):
            # Return raw output if parsing fails
            return result.get("output", "Command completed")


def main():
    parser = argparse.ArgumentParser(
        description="Generic Inkscape MCP Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a circle
  python generic_client.py circle "cx=100 cy=100 r=50 fill=blue"

  # Create a linear gradient with stops
  python generic_client.py linearGradient "x1=0 y1=0 x2=100 y2=100 children=[{\"tag\":\"stop\",\"attributes\":{\"offset\":\"0%\",\"stop-color\":\"blue\"}},{\"tag\":\"stop\",\"attributes\":{\"offset\":\"100%\",\"stop-color\":\"red\"}}]"

  # Get selection info
  python generic_client.py get-selection ""

  # Get document info
  python generic_client.py get-info ""
        """
    )

    parser.add_argument("tag", help="SVG tag name or info action")
    parser.add_argument("params", nargs="?", default="", help="Parameters string")

    args = parser.parse_args()

    client = GenericInkscapeClient()

    try:
        # Build element data
        element_data = client.build_element_data(args.tag, args.params)

        # Execute command
        result = client.execute_command(element_data)

        # Format and display response
        response = client.format_response(result)
        print(response)

        return 0 if result.get("success") else 1

    except Exception as e:
        print(f"❌ Client error: {str(e)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
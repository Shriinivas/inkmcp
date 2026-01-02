#!/usr/bin/env python3
"""
Inkscape MCP Client
Command-line interface for creating any SVG element via D-Bus MCP extension with unified parsing

Usage:
    python inkmcpcli.py <tag> '<attributes>'

Attribute Format:
    - Basic: key=value (e.g., cx=100, fill=red)
    - Quoted values: key="value with spaces" or key='value with spaces'
    - Children: children=[{tag 'attr1=val1 attr2=val2'}, {tag 'attr3=val3'}]

Basic Shape Examples:
    python inkmcpcli.py circle 'cx=100 cy=100 r=50 fill=red'
    python inkmcpcli.py rect 'x=10 y=10 width=100 height=50 fill=blue'
    python inkmcpcli.py text 'x=50 y=50 font-size=14 content="Hello World"'

Linear Gradient Examples:
    # userSpaceOnUse (shows immediately)
    python inkmcpcli.py linearGradient "x1=0 y1=0 x2=300 y2=0 gradientUnits=userSpaceOnUse children=[{stop 'offset=\"0%\" stop-color=\"purple\"'}, {stop 'offset=\"100%\" stop-color=\"orange\"'}]"

    # objectBoundingBox (may need nudge to refresh)
    python inkmcpcli.py linearGradient "x1=0 y1=0 x2=1 y2=1 gradientUnits=objectBoundingBox children=[{stop 'offset=\"0%\" stop-color=\"cyan\"'}, {stop 'offset=\"100%\" stop-color=\"magenta\"'}]"

Radial Gradient Examples:
    # userSpaceOnUse
    python inkmcpcli.py radialGradient "cx=150 cy=150 r=80 gradientUnits=userSpaceOnUse children=[{stop 'offset=\"0%\" stop-color=\"white\"'}, {stop 'offset=\"100%\" stop-color=\"black\"'}]"

    # objectBoundingBox
    python inkmcpcli.py radialGradient "cx=0.5 cy=0.5 r=0.7 gradientUnits=objectBoundingBox children=[{stop 'offset=\"0%\" stop-color=\"gold\"'}, {stop 'offset=\"100%\" stop-color=\"darkred\"'}]"

Applying Gradients to Shapes:
    python inkmcpcli.py circle "cx=100 cy=100 r=50 fill=url(#linearGradient123)"
    python inkmcpcli.py rect "x=10 y=10 width=100 height=80 fill=url(#radialGradient456)"

Complex Nested Examples:
    # Group with multiple children
    python inkmcpcli.py g "id=\"my-group\" children=[{circle 'cx=50 cy=50 r=25 fill=red'}, {rect 'x=0 y=0 width=20 height=20 fill=blue'}]"

Quoting Guidelines:
    - Use double quotes for outer shell string: "..."
    - Use single quotes for attribute values inside children: '...'
    - Escape quotes when needed: 'content=\"Hello World\"'
    - For spaces in values: 'font-family=\"Arial Black\"'

Info Functions:
    python inkmcpcli.py get-selection ""
    python inkmcpcli.py get-info ""
    python inkmcpcli.py get-info-by-id "id=rect1"
    python inkmcpcli.py export-document-image "format=png max_size=400 area=page"
    python inkmcpcli.py execute-code "code='circle = Circle(); circle.set(\"r\", \"50\"); svg.append(circle)'"

Supported Elements:
    - All standard SVG elements (circle, rect, line, path, text, g, etc.)
    - Gradient elements (linearGradient, radialGradient with stops)
    - Info functions (get-selection, get-info, get-info-by-id, export-document-image)
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
from typing import Dict, List, Any


def strip_python_comments(code: str) -> str:
    """
    Strip comments from Python code for more efficient transmission.
    Removes:
    - Lines starting with # (full-line comments)
    - Inline comments (# at end of line)
    
    Preserves:
    - # characters inside strings
    - # characters in certain contexts (like f-strings, format strings)
    
    Args:
        code: Python code string
    
    Returns:
        Code with comments removed
    """
    if not code.strip():
        return code
    
    lines = code.split('\n')
    cleaned_lines = []
    
    for line in lines:
        stripped = line.lstrip()
        
        # Skip full-line comments
        if stripped.startswith('#'):
            continue
        
        # Handle inline comments - simple approach that works for most cases
        # Remove everything after # if it's not inside quotes
        in_single_quote = False
        in_double_quote = False
        escape_next = False
        cleaned_line = []
        
        for i, char in enumerate(line):
            if escape_next:
                cleaned_line.append(char)
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                cleaned_line.append(char)
                continue
            
            if char == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
                cleaned_line.append(char)
            elif char == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
                cleaned_line.append(char)
            elif char == '#' and not in_single_quote and not in_double_quote:
                # Found inline comment, stop here
                break
            else:
                cleaned_line.append(char)
        
        result_line = ''.join(cleaned_line).rstrip()
        
        # Only add non-empty lines
        if result_line:
            cleaned_lines.append(result_line)
    
    return '\n'.join(cleaned_lines)


def parse_hybrid_blocks(code: str) -> List[tuple[str, str]]:
    """
    Parse code into blocks based on magic comments.
    
    Magic comments:
        # @local - Switch to local execution context
        # @inkscape - Switch to Inkscape execution context
    
    Default: unmarked code at start is 'local'
    
    Args:
        code: Python code with optional magic comments
    
    Returns:
        List of (block_type, code_string) tuples
        block_type is either 'local' or 'inkscape'
    """
    lines = code.split('\n')
    blocks = []
    current_type = 'local'  # Default to local
    current_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        # Check for magic comments
        if stripped == '# @local':
            # Save current block if it has content
            if current_lines:
                blocks.append((current_type, '\n'.join(current_lines)))
                current_lines = []
            current_type = 'local'
        elif stripped == '# @inkscape':
            # Save current block if it has content
            if current_lines:
                blocks.append((current_type, '\n'.join(current_lines)))
                current_lines = []
            current_type = 'inkscape'
        else:
            # Regular code line
            current_lines.append(line)
    
    # Add final block if it has content
    if current_lines:
        blocks.append((current_type, '\n'.join(current_lines)))
    
    return blocks


def serialize_context_variables(local_vars: Dict[str, Any], exclude_names: set = None) -> Dict[str, Any]:
    """
    Extract JSON-serializable variables from local execution context.
    
    Args:
        local_vars: Dictionary of local variables from exec()
        exclude_names: Set of variable names to exclude (default: builtins and private)
    
    Returns:
        Dictionary of serializable variables
    
    Raises:
        TypeError: If a variable that should be serialized is not JSON-compatible
    """
    if exclude_names is None:
        exclude_names = {'__builtins__', '__name__', '__doc__', '__package__',
                        '__loader__', '__spec__', '__annotations__', '__cached__',
                        '__file__'}
    
    serializable = {}
    
    for key, value in local_vars.items():
        # Skip private/magic variables and excluded names
        if key.startswith('_') or key in exclude_names:
            continue
        
        # Skip module types automatically (both stdlib and user imports)
        if type(value).__name__ == 'module':
            continue
        
        # Test JSON serializability
        try:
            json.dumps(value)
            serializable[key] = value
        except (TypeError, ValueError) as e:
            # Provide helpful error message for other non-serializable types
            type_name = type(value).__name__
            module = type(value).__module__
            full_type = f"{module}.{type_name}" if module != 'builtins' else type_name
            
            error_msg = (
                f"Variable '{key}' is not JSON-serializable\n"
                f"  Type: {full_type}\n"
                f"  Hint: Convert to a JSON-compatible type before using in @inkscape block\n"
                f"  Example: {key}_list = list({key}) or {key}_dict = dict({key})"
            )
            raise TypeError(error_msg) from e
    
    return serializable


def execute_hybrid_code(client: 'InkscapeClient', code: str, args) -> Dict[str, Any]:
    """
    Execute hybrid code with interleaved local and Inkscape execution.
    
    Execution flow:
    1. Parse code into blocks (local/inkscape)
    2. Execute each block in sequence
    3. For local blocks: execute locally, capture serializable variables
    4. For inkscape blocks: inject variables, execute via D-Bus, capture results
    5. Continue until all blocks executed
    
    Args:
        client: InkscapeClient instance
        code: Hybrid code with magic comments
        args: Command line arguments
    
    Returns:
        Result dictionary with execution details
    """
    import io
    from contextlib import redirect_stdout, redirect_stderr
    
    # Parse code into blocks
    blocks = parse_hybrid_blocks(code)
    
    if not blocks:
        return {
            "success": False,
            "error": "No code blocks found"
        }
    
    # Shared context for variables
    shared_context = {}
    
    # Track all outputs
    all_local_output = []
    all_inkscape_results = []
    combined_errors = []
    
    # Execute each block
    for block_idx, (block_type, block_code) in enumerate(blocks):
        if not block_code.strip():
            continue
        
        if block_type == 'local':
            # Execute locally
            try:
                # Set up local execution environment with standard modules
                injected_names = {'json', 're', 'os', 'sys', '__builtins__'}
                local_env = {
                    '__builtins__': __builtins__,
                    'json': json,
                    're': re,
                    'os': os,
                    'sys': sys,
                }
                
                # Inject shared context (from previous blocks)
                local_env.update(shared_context)
                
                # Capture output
                stdout_capture = io.StringIO()
                stderr_capture = io.StringIO()
                
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    exec(block_code, local_env)
                
                # Capture output
                stdout_out = stdout_capture.getvalue()
                stderr_out = stderr_capture.getvalue()
                
                if stdout_out:
                    all_local_output.append(stdout_out)
                if stderr_out:
                    combined_errors.append(f"[Local Block {block_idx + 1} stderr]\\n{stderr_out}")
                
                # Update shared context with new/modified variables
                # Exclude system modules we injected
                exclude_set = injected_names.copy()
                # Also exclude previously shared variables to avoid re-processing
                # (they're already in shared_context)
                serializable = serialize_context_variables(local_env, exclude_names=exclude_set)
                shared_context.update(serializable)
                
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Local execution error in block {block_idx + 1}: {str(e)}",
                    "block_type": "local",
                    "block_index": block_idx + 1
                }
        
        elif block_type == 'inkscape':
            # Execute in Inkscape via D-Bus
            try:
                # Strip comments from Inkscape code
                cleaned_code = strip_python_comments(block_code)
                
                # Build element data for execute-code
                # We need to inject the shared context as variable assignments
                context_injection = []
                for key, value in shared_context.items():
                    # Serialize the value as Python literal
                    context_injection.append(f"{key} = {json.dumps(value)}")
                
                # Combine context injection with user code
                full_inkscape_code = '\n'.join(context_injection) + '\n' + cleaned_code if context_injection else cleaned_code
                
                # Build execute-code command
                element_data = {
                    'tag': 'execute-code',
                    'attributes': {
                        'code': full_inkscape_code,
                        'return_output': True
                    }
                }
                
                # Execute via D-Bus
                result = client.execute_command(element_data)
                
                if not result.get('success'):
                    return {
                        "success": False,
                        "error": f"Inkscape execution error in block {block_idx + 1}: {result.get('error', 'Unknown error')}",
                        "block_type": "inkscape",
                        "block_index": block_idx + 1
                    }
                
                # Extract inkscape result data
                response_data = result.get('response', {})
                if response_data.get('status') == 'success':
                    data = response_data.get('data', {})
                    
                    # Store inkscape result for next local block
                    inkscape_result = {
                        'success': True,
                        'execution_successful': data.get('execution_successful', False),
                        'id_mapping': data.get('id_mapping', {}),
                        'elements_created': data.get('elements_created', []),
                        'output': data.get('output', ''),
                        'errors': data.get('errors'),
                        'element_counts': data.get('current_element_counts', {})
                    }
                    
                    shared_context['inkscape_result'] = inkscape_result
                    all_inkscape_results.append(inkscape_result)
                    
                    if not inkscape_result['execution_successful']:
                        combined_errors.append(f"[Inkscape Block {block_idx + 1}] {inkscape_result.get('errors', '')}")
                else:
                    return {
                        "success": False,
                        "error": f"Inkscape block {block_idx + 1} failed: {response_data.get('data', {}).get('error', 'Unknown error')}",
                        "block_type": "inkscape",
                        "block_index": block_idx + 1
                    }
                    
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error executing Inkscape block {block_idx + 1}: {str(e)}",
                    "block_type": "inkscape",
                    "block_index": block_idx + 1
                }
    
    # Build final result
    final_output = '\n\n'.join(all_local_output) if all_local_output else ''
    final_errors = '\n'.join(combined_errors) if combined_errors else None
    
    return {
        "success": True,
        "response": {
            "status": "success",
            "data": {
                "message": f"Hybrid execution completed ({len(blocks)} blocks)",
                "blocks_executed": len(blocks),
                "local_output": final_output,
                "inkscape_results": all_inkscape_results,
                "errors": final_errors,
                "execution_successful": final_errors is None
            }
        }
    }


def parse_children_array(children_str: str) -> List[Dict[str, Any]]:
    """
    Parse children array string like "[{rect 'x=0 y=0'}, {circle 'cx=25 cy=25'}]"

    Args:
        children_str: String containing children array

    Returns:
        List of parsed child element dictionaries
    """
    if not children_str.strip():
        return []

    children_str = children_str.strip()

    # Remove outer brackets
    if children_str.startswith('[') and children_str.endswith(']'):
        children_str = children_str[1:-1].strip()

    if not children_str:
        return []

    children = []
    brace_count = 0
    current_child = ""
    i = 0

    while i < len(children_str):
        char = children_str[i]

        if char == '{':
            brace_count += 1
            if brace_count == 1:
                current_child = ""  # Start new child, don't include opening brace
                i += 1
                continue

        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                # End of current child, parse it
                if current_child.strip():
                    child_data = parse_tag_and_attributes(current_child.strip())
                    if child_data:
                        children.append(child_data)
                current_child = ""
                i += 1
                continue

        elif char == ',' and brace_count == 0:
            # Skip commas between top-level children
            i += 1
            continue

        if brace_count > 0:
            current_child += char

        i += 1

    # Handle any remaining child
    if current_child.strip():
        child_data = parse_tag_and_attributes(current_child.strip())
        if child_data:
            children.append(child_data)

    return children


def parse_tag_and_attributes(content: str) -> Dict[str, Any] | None:
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
    attributes = parse_attributes(attr_str)

    element_data = {
        "tag": tag,
        "attributes": attributes
    }

    # Handle nested children recursively
    if 'children' in attributes:
        children_value = attributes.pop('children')
        if isinstance(children_value, str):
            element_data["children"] = parse_children_array(children_value)
        else:
            element_data["children"] = children_value

    return element_data


def parse_attributes(param_str: str) -> Dict[str, Any]:
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

    # Enhanced regex to handle quoted values, arrays, and objects (including multiline)
    # Pattern explanation:
    # - (\w+(?:[:-]\w+)*) : key name with optional hyphens/underscores/colons (for namespaces)
    # - = : equals sign
    # - Group of alternatives for value:
    #   - "([^"]*)" : double quoted content (group 2)
    #   - '([^']*)' : single quoted content (group 3)
    #   - (\[(?:[^\[\]]|\{[^}]*\}|\[[^\]]*\])*\]) : array content (group 4)
    #   - ([^\s,=]+) : unquoted content (group 5)
    param_pattern = r'(\w+(?:[:-]\w+)*)=("([^"]*)"|\'([^\']*)\'|(\[(?:[^\[\]]|\{[^}]*\}|\[[^\]]*\])*\])|([^\s,=]+))'
    raw_matches = re.findall(param_pattern, param_str, re.DOTALL)

    for match in raw_matches:
        key = match[0]
        full_value = match[1]

        # Extract the actual value based on quoting type
        if full_value.startswith('"') and full_value.endswith('"'):
            value = match[2]  # Double quoted content
        elif full_value.startswith("'") and full_value.endswith("'"):
            value = match[3]  # Single quoted content
        elif full_value.startswith('['):
            value = match[4]  # Array content (keep as string for later parsing)
        else:
            value = match[5]  # Unquoted content

        # Handle special array values
        if key == 'children' and isinstance(value, str) and value.startswith('['):
            # Keep as string for later recursive parsing
            attributes[key] = value
        elif value.startswith('[') and value.endswith(']'):
            # Try to parse as JSON array
            try:
                attributes[key] = json.loads(value)
            except json.JSONDecodeError:
                # Keep as string if JSON parsing fails
                attributes[key] = value
        else:
            attributes[key] = value

    return attributes


class InkscapeClient:
    """D-Bus client for SVG element creation"""

    def __init__(self):
        self.dbus_service = "org.inkscape.Inkscape"
        self.dbus_path = "/org/inkscape/Inkscape"
        self.dbus_interface = "org.gtk.Actions"
        self.action_name = "org.khema.inkscape.mcp"




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
        result = parse_tag_and_attributes(full_content)
        return result if result is not None else {"tag": tag, "attributes": {}}

    def execute_command(self, element_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute command via D-Bus"""
        try:
            # Create temporary response file for reverse communication (like original system)
            response_fd, response_file = tempfile.mkstemp(suffix='.json', prefix='inkmcp_response_')
            os.close(response_fd)  # Close the file descriptor, we just need the path
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

    def format_response(self, result: Dict[str, Any], tag: str = "") -> str:
        """Format the response for display - minimal output by default"""
        if not result.get("success"):
            return f"Error: {result.get('error', 'Unknown error')}"

        # Check if we have a proper response from response file
        if "response" in result:
            response_data = result["response"]
            if response_data.get("status") == "success":
                data = response_data.get("data", {})
                
                # For execute-code, only show the actual output from print statements
                if tag == "execute-code":
                    if not data.get("execution_successful", True):
                        # Show errors for failed execution
                        errors = data.get("errors", "Unknown error")
                        return f"Error: {errors}"
                    else:
                        # Only return the output from print() statements
                        output = data.get("output", "").strip()
                        return output if output else ""  # Empty string if no output
                
                # For other operations, minimal success message
                message = data.get("message", "Success")
                element_id = data.get("id")
                if element_id:
                    return f"{message} (id: {element_id})"
                return message
            else:
                error = response_data.get("data", {}).get("error", "Unknown error")
                return f"Error: {error}"

        # Fallback to raw output parsing
        try:
            output = result.get("output", "")
            # D-Bus returns output in format like "('result_here',)"
            if output.startswith("('") and output.endswith("',)"):
                output = output[2:-3]  # Remove D-Bus wrapping

            response_data = json.loads(output)

            if response_data.get("status") == "success":
                data = response_data.get("data", {})
                
                # For execute-code, only show the actual output from print statements
                if tag == "execute-code":
                    if not data.get("execution_successful", True):
                        errors = data.get("errors", "Unknown error")
                        return f"Error: {errors}"
                    else:
                        output = data.get("output", "").strip()
                        return output if output else ""
                
                # For other operations, minimal success message
                message = data.get("message", "Success")
                element_id = data.get("id")
                if element_id:
                    return f"{message} (id: {element_id})"
                return message
            else:
                error = response_data.get("data", {}).get("error", "Unknown error")
                return f"Error: {error}"

        except (json.JSONDecodeError, KeyError):
            return "Success"


def main():
    parser = argparse.ArgumentParser(
        description="Inkscape MCP Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a circle
  python inkmcpcli.py circle "cx=100 cy=100 r=50 fill=blue"

  # Create a linear gradient with stops
  python inkmcpcli.py linearGradient "x1=0 y1=0 x2=100 y2=100 children=[{\"tag\":\"stop\",\"attributes\":{\"offset\":\"0%\",\"stop-color\":\"blue\"}},{\"tag\":\"stop\",\"attributes\":{\"offset\":\"100%\",\"stop-color\":\"red\"}}]"

  # Execute code from string (multiline requires quotes)
  python inkmcpcli.py execute-code "code='for i in range(3): print(i)'"

  # Execute code from file (file contains Python code)
  python inkmcpcli.py execute-code -f my_script.py

  # Execute batch commands from file (file contains multiple command lines)
  python inkmcpcli.py batch -f batch_commands.txt

  # Execute hybrid code (interleaved local and Inkscape execution)
  python inkmcpcli.py execute-hybrid -f hybrid_script.py

  # Use file for parameters (file content replaces parameter string)
  python inkmcpcli.py circle -f circle_params.txt

  # Get selection info
  python inkmcpcli.py get-selection ""

  # Get document info
  python inkmcpcli.py get-info ""
        """
    )

    parser.add_argument("tag", help="SVG tag name or info action")
    parser.add_argument("params", nargs="?", default="", help="Parameters string")
    parser.add_argument("-f", "--file", help="Read parameters from file")
    parser.add_argument("--parse-out", action="store_true", help="Parse and return structured JSON response")
    parser.add_argument("--pretty", action="store_true", help="Pretty print JSON output")

    args = parser.parse_args()

    client = InkscapeClient()

    try:
        # Initialize params
        params = args.params

        # Handle file input
        if args.file:
            if not os.path.exists(args.file):
                print(f"❌ File not found: {args.file}", file=sys.stderr)
                return 1

            with open(args.file, 'r') as f:
                file_content = f.read().strip()

            if args.tag == "execute-hybrid":
                # For execute-hybrid, treat file content as hybrid Python code
                if params.strip():
                    print("❌ Cannot use parameters with execute-hybrid -f option", file=sys.stderr)
                    return 1
                
                # Execute hybrid code
                result = execute_hybrid_code(client, file_content, args)
                
                # Format and display response based on flags
                if args.parse_out or args.pretty:
                    # JSON output
                    if args.pretty:
                        print(json.dumps(result, indent=2))
                    else:
                        print(json.dumps(result))
                else:
                    # Minimal human-readable format
                    if result.get('success'):
                        data = result.get('response', {}).get('data', {})
                        output = data.get('local_output', '')
                        if output:
                            print(output)
                        # Show summary
                        print(f"\n{data.get('message', 'Hybrid execution completed')}")
                    else:
                        print(f"Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
                
                return 0 if result.get('success') else 1
                
            elif args.tag == "execute-code":
                # For execute-code, treat file content as Python code
                if params.strip() and 'code=' in params:
                    print("❌ Cannot use both -f option and code= parameter", file=sys.stderr)
                    return 1

                # Strip comments from code for efficiency
                cleaned_code = strip_python_comments(file_content)
                
                # Build code parameter from file content
                if params.strip():
                    params = f"{params} code='{cleaned_code}'"
                else:
                    params = f"code='{cleaned_code}'"
                # Note: execution happens in the unified path below (line ~618)
            elif args.tag == "batch":
                # For batch command, treat file as batch of command lines
                if params.strip():
                    print("❌ Cannot use parameters with batch command", file=sys.stderr)
                    return 1

                # Process each line as a separate command
                lines = [line.strip() for line in file_content.split('\n') if line.strip()]

                # Handle batch output
                if args.parse_out:
                    # Structured JSON output for batch
                    batch_results = []
                    for line_num, line in enumerate(lines, 1):
                        try:
                            element_data = parse_tag_and_attributes(line)
                            if element_data:
                                result = client.execute_command(element_data)
                                batch_results.append({
                                    "line": line_num,
                                    "command": line,
                                    "result": result
                                })
                            else:
                                batch_results.append({
                                    "line": line_num,
                                    "command": line,
                                    "result": {"success": False, "error": "Failed to parse command"}
                                })
                        except Exception as e:
                            batch_results.append({
                                "line": line_num,
                                "command": line,
                                "result": {"success": False, "error": str(e)}
                            })

                    output = {
                        "total_commands": len(batch_results),
                        "results": batch_results
                    }

                    if args.pretty:
                        print(json.dumps(output, indent=2))
                    else:
                        print(json.dumps(output))

                    all_success = all(r["result"].get("success", False) for r in batch_results)
                    return 0 if all_success else 1
                else:
                    # Human-readable output for batch
                    results = []
                    for line_num, line in enumerate(lines, 1):
                        try:
                            element_data = parse_tag_and_attributes(line)
                            if element_data:
                                # Strip comments if this is execute-code
                                if element_data.get('tag') == 'execute-code' and 'code' in element_data.get('attributes', {}):
                                    element_data['attributes']['code'] = strip_python_comments(element_data['attributes']['code'])
                                
                                result = client.execute_command(element_data)
                                results.append(f"Line {line_num}: {client.format_response(result, element_data.get('tag', ''))}")
                            else:
                                results.append(f"Line {line_num}: ❌ Failed to parse command: {line}")
                        except Exception as e:
                            results.append(f"Line {line_num}: ❌ Error: {str(e)}")

                    for result_line in results:
                        print(result_line)

                    # Return success if all commands succeeded
                    all_success = all("❌" not in result_line for result_line in results)
                    return 0 if all_success else 1
            else:
                # For other commands with -f, file content replaces params
                if params.strip():
                    print("❌ Cannot use both -f option and parameters", file=sys.stderr)
                    return 1
                params = file_content

        # Single command execution (either no file, or execute-code with file already processed)
        # Build element data
        element_data = client.build_element_data(args.tag, params)
        
        # Strip comments if this is execute-code command
        if args.tag == 'execute-code' and 'code' in element_data.get('attributes', {}):
            element_data['attributes']['code'] = strip_python_comments(element_data['attributes']['code'])

        # Execute command
        result = client.execute_command(element_data)

        # Format and display response
        if args.parse_out or args.pretty:
            # Structured JSON output
            output = {
                "command": f"{args.tag} {params}".strip(),
                "tag": args.tag,
                "params": params,
                "result": result
            }
            if args.pretty:
                print(json.dumps(output, indent=2))
            else:
                print(json.dumps(output))
        else:
            # Minimal human-readable format
            output = client.format_response(result, args.tag)
            if output:  # Only print if there's output
                print(output)

        return 0 if result.get("success") else 1

    except Exception as e:
        print(f"❌ Client error: {str(e)}", file=sys.stderr)
        return 1


def parse_command_string(command: str) -> Dict[str, Any]:
    """
    Standalone function to parse command string for server use

    Args:
        command: Command string like "rect x=100 y=50 width=200 height=100"
                or "g map_id=myGroup children=[{rect map_id=r1 x=0 y=0}]"

    Returns:
        Parsed element data dictionary
    """
    result = parse_tag_and_attributes(command)
    return result if result is not None else {"tag": "", "attributes": {}}


if __name__ == "__main__":
    sys.exit(main())
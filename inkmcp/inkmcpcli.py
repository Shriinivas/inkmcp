#!/usr/bin/env python3
"""
Inkscape MCP CLI Client
Command-line interface for controlling Inkscape via D-Bus MCP extension

Usage:
    python inkmcpcli.py "circle cx=100 cy=200 r=50 fill=#ff0000"
    python inkmcpcli.py -i commands.txt
    echo "rect x=0 y=0 width=100 height=100" | python inkmcpcli.py
    python inkmcpcli.py --parse-out "get-selection"
"""

import argparse
import sys
import json
import tempfile
import os
import subprocess
import re
from typing import Dict, List, Any, Optional

class InkscapeMCPClient:
    """D-Bus client for Inkscape MCP extension"""

    def __init__(self):
        self.dbus_service = "org.inkscape.Inkscape"
        self.dbus_path = "/org/inkscape/Inkscape"
        self.dbus_interface = "org.gtk.Actions"
        self.action_name = "org.mcp.inkscape.draw.modular"

    def parse_command(self, command_str: str) -> Dict[str, Any]:
        """Parse command string into parameters dictionary"""
        command_str = command_str.strip()
        if not command_str:
            return {}

        # Split command into parts
        parts = command_str.split(None, 1)
        if not parts:
            return {}

        # First part is the action/shape type
        action_part = parts[0]
        params = {}

        # Determine action type
        if action_part in ['get-selection', 'get-info', 'export-document', 'get-object-info', 'get-object-property', 'export-document-image']:
            params['action'] = action_part
        elif action_part == 'execute-inkex-code':
            params['action'] = 'execute-inkex-code'
        elif action_part in ['rectangle', 'rect', 'circle', 'ellipse', 'line', 'polygon', 'polyline', 'text', 'path']:
            params['action'] = 'draw-shape'
            params['shape_type'] = action_part
        elif action_part in ['radial-gradient', 'linear-gradient']:
            params['action'] = 'add-gradient'
            params['gradient_type'] = action_part
        else:
            # Assume it's a custom action
            params['action'] = action_part

        # Parse remaining parameters if any
        if len(parts) > 1:
            param_str = parts[1]

            # Parse key=value pairs
            # Handle quoted values and various formats - improved regex for quoted strings
            param_pattern = r'(\w+(?:[_-]\w+)*)=("([^"]*)"|\'([^\']*)\'|(\[[^\]]*\])|([^\s]+))'
            raw_matches = re.findall(param_pattern, param_str)

            # Process matches to extract the actual value from the capture groups
            matches = []
            for match in raw_matches:
                key = match[0]
                # match[1] is the full value, match[2] is double-quoted, match[3] is single-quoted,
                # match[4] is bracketed, match[5] is unquoted
                if match[2]:  # double-quoted
                    value = match[2]
                elif match[3]:  # single-quoted
                    value = match[3]
                elif match[4]:  # bracketed (arrays)
                    value = match[4]
                else:  # unquoted
                    value = match[5] if match[5] else match[1]
                matches.append((key, value))

            for key, value in matches:
                # Unescape common bash escape sequences
                value = value.replace('\\!', '!').replace('\\$', '$').replace('\\\\', '\\')

                # Try to convert to appropriate type
                if value.lower() in ['true', 'false']:
                    params[key] = value.lower() == 'true'
                elif value.lower() in ['none', 'null']:
                    params[key] = None
                elif value.startswith('[') and value.endswith(']'):
                    # Handle array format like points=[[100,50],[150,100]]
                    try:
                        params[key] = json.loads(value)
                    except:
                        params[key] = value
                elif value.replace('.', '').replace('-', '').isdigit():
                    # Numeric value
                    if '.' in value:
                        params[key] = float(value)
                    else:
                        params[key] = int(value)
                else:
                    params[key] = value

        # Handle base64-encoded code parameter
        if 'code_base64' in params:
            import base64
            try:
                decoded_code = base64.b64decode(params['code_base64']).decode('utf-8')
                params['code'] = decoded_code
                del params['code_base64']  # Remove the base64 version
            except Exception as e:
                print(f"Error decoding base64 code: {e}", file=sys.stderr)

        return params

    def execute_command(self, params: Dict[str, Any], parse_response: bool = False) -> Optional[Dict[str, Any]]:
        """Execute a single command via D-Bus"""
        try:
            # Create temporary response file for reverse communication
            response_file = None
            if parse_response or params.get('action') in ['get-selection', 'get-info', 'export-document', 'execute-inkex-code']:
                response_file = tempfile.mktemp(suffix='.json', prefix='inkmcp_response_')
                params['response_file'] = response_file

            # Write parameters to JSON file
            params_file = os.path.join(tempfile.gettempdir(), "mcp_params.json")
            with open(params_file, 'w') as f:
                json.dump(params, f)

            # Execute D-Bus command
            cmd = [
                'gdbus', 'call',
                '--session',
                '--dest', self.dbus_service,
                '--object-path', self.dbus_path,
                '--method', f'{self.dbus_interface}.Activate',
                self.action_name,
                '[]', '{}'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                return {
                    "status": "error",
                    "data": {"error": f"D-Bus call failed: {result.stderr}"}
                }

            # Read response if available
            if response_file and os.path.exists(response_file):
                try:
                    with open(response_file, 'r') as f:
                        response = json.load(f)
                    os.remove(response_file)
                    return response
                except Exception as e:
                    return {
                        "status": "error",
                        "data": {"error": f"Failed to read response: {str(e)}"}
                    }

            # Default success response
            return {
                "status": "success",
                "data": {"message": "Command executed successfully"}
            }

        except Exception as e:
            return {
                "status": "error",
                "data": {"error": f"Command execution failed: {str(e)}"}
            }

    def process_commands(self, commands: List[str], parse_output: bool = False) -> List[Dict[str, Any]]:
        """Process multiple commands"""
        results = []

        for command_str in commands:
            command_str = command_str.strip()
            if not command_str or command_str.startswith('#'):
                continue

            params = self.parse_command(command_str)
            if not params:
                continue

            result = self.execute_command(params, parse_output)
            results.append({
                "command": command_str,
                "params": params,
                "result": result
            })

        return results

def main():
    parser = argparse.ArgumentParser(
        description="Inkscape MCP CLI Client - Control Inkscape via D-Bus",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Draw shapes
  python inkmcpcli.py "circle cx=100 cy=200 r=50 fill=#ff0000"
  python inkmcpcli.py "rect x=10 y=10 width=100 height=50 stroke=blue"
  python inkmcpcli.py "polygon points=[[0,0],[100,0],[50,50]] fill=green"

  # Create gradients
  python inkmcpcli.py "radial-gradient cx=100 cy=100 r=50 stops='[[\"0%\",\"blue\"],[\"100%\",\"red\"]]'"
  python inkmcpcli.py "linear-gradient x1=0 y1=0 x2=200 y2=200 stops='[[\"0%\",\"green\"],[\"100%\",\"red\"]]'"

  # Use gradients in shapes
  python inkmcpcli.py "circle cx=100 cy=100 r=75 fill='url(#radialGradient1)'"

  # Get information (with parsed output)
  python inkmcpcli.py --parse-out "get-selection"
  python inkmcpcli.py --parse-out "get-info"

  # Batch processing
  python inkmcpcli.py "rect x=0 y=0 width=50 height=50; circle cx=100 cy=100 r=30"

  # From file
  python inkmcpcli.py -i commands.txt

  # From stdin
  echo "circle cx=200 cy=200 r=75 fill=yellow" | python inkmcpcli.py
        """
    )

    parser.add_argument('commands', nargs='*', help='Command string(s) to execute')
    parser.add_argument('-i', '--input', help='Read commands from file')
    parser.add_argument('--parse-out', action='store_true',
                       help='Parse and return structured JSON response')
    parser.add_argument('--pretty', action='store_true',
                       help='Pretty print JSON output')

    args = parser.parse_args()

    client = InkscapeMCPClient()
    commands = []

    # Determine input source
    if args.input:
        # Read from file
        try:
            with open(args.input, 'r') as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading file {args.input}: {e}", file=sys.stderr)
            return 1
    elif args.commands:
        # From command line arguments
        content = ' '.join(args.commands)
    elif not sys.stdin.isatty():
        # From stdin
        content = sys.stdin.read()
    else:
        parser.print_help()
        return 1

    # Split commands by newline or semicolon, but handle execute-inkex-code specially
    if content.strip().startswith('execute-inkex-code'):
        # Don't split execute-inkex-code commands - treat the whole thing as one command
        commands = [content.strip()]
    else:
        # Normal splitting for other commands
        raw_commands = re.split(r'[;\n]', content)
        commands = [cmd.strip() for cmd in raw_commands if cmd.strip()]

    if not commands:
        print("No commands to execute", file=sys.stderr)
        return 1

    # Process commands
    results = client.process_commands(commands, args.parse_out)

    # Output results
    if args.parse_out:
        # Structured output
        output = {
            "total_commands": len(results),
            "results": results
        }
    else:
        # Simple success/error output
        output = []
        for result in results:
            status = result['result'].get('status', 'unknown')
            data = result['result'].get('data', {})

            # Check for execution errors in execute-inkex-code
            if result['params'].get('action') == 'execute-inkex-code' and not data.get('execution_successful', True):
                status = 'error'
                message = data.get('errors', 'Code execution failed')
            else:
                message = data.get('message', 'No message')

            output.append({
                "command": result['command'],
                "status": status,
                "message": message
            })

    # Print JSON output
    if args.pretty:
        print(json.dumps(output, indent=2))
    else:
        print(json.dumps(output))

    # Return appropriate exit code
    errors = [r for r in results if r['result'].get('status') == 'error']
    return 1 if errors else 0

if __name__ == '__main__':
    sys.exit(main())
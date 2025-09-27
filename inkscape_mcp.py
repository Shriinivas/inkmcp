#!/usr/bin/env python3
"""
Inkscape MCP Drawing Extension - Modular Architecture
Provides drawing actions that can be called via D-Bus for live document manipulation
Parameters are read from /tmp/mcp_params.json
Operations are handled by modular components in mcpoperations/ folder
"""

import inkex
import json
import os
import sys
import importlib.util

class InkscapeMCPDrawModular(inkex.EffectExtension):
    """Extension providing MCP drawing actions via D-Bus with modular operations"""

    def add_arguments(self, pars):
        # No GUI parameters needed - we read from JSON file
        pass

    def effect(self):
        """Execute the requested action based on JSON parameters"""
        import tempfile
        params_file = os.path.join(tempfile.gettempdir(), "mcp_params.json")

        # Check if this is a manual invocation (no params file)
        if not os.path.exists(params_file):
            inkex.errormsg(f"⚠️ Inkscape MCP Extension\n\nThis extension is designed for programmatic use via D-Bus.\nParameters should be provided in {params_file}\n\nNot intended for manual invocation.")
            return

        try:
            # Read parameters from JSON file
            with open(params_file, 'r') as f:
                params = json.load(f)

            # Clean up the params file after reading
            os.remove(params_file)

            action = params.get('action', 'unknown')

            # Execute operation using modular system
            result = self.execute_operation(action, params)

            # Write response to file for reverse communication if requested
            response_file = params.get('response_file')
            if response_file:
                self.write_response(result, response_file)

            # Minimal output - avoid complex messages that cause parsing issues
            if result.get('status') != 'success':
                error = result.get('data', {}).get('error', 'Unknown error')
                inkex.errormsg(f"MCP Error: {error}")

        except json.JSONDecodeError as e:
            inkex.errormsg(f"Invalid JSON in params file")
        except Exception as e:
            inkex.errormsg(f"MCP Action failed")

    def execute_operation(self, action, params):
        """Execute operation using modular system"""
        try:
            # Convert action name to module format
            # e.g., "draw-rectangle" -> "draw_rectangle"
            module_name = action.replace('-', '_')

            # Get the directory of this script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            operation_path = os.path.join(script_dir, 'inkmcp', 'inkmcpops', f'{module_name}.py')

            # Check if operation module exists
            if not os.path.exists(operation_path):
                return {
                    "status": "error",
                    "data": {"error": f"Operation '{action}' not found"}
                }

            # Dynamic import of operation module
            spec = importlib.util.spec_from_file_location(module_name, operation_path)
            operation_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(operation_module)

            # Execute the operation
            if hasattr(operation_module, 'execute'):
                return operation_module.execute(self.svg, params)
            else:
                return {
                    "status": "error",
                    "data": {"error": f"Operation '{action}' missing execute function"}
                }

        except Exception as e:
            return {
                "status": "error",
                "data": {"error": f"Operation execution failed: {str(e)}"}
            }

    def write_response(self, data, response_file):
        """Write response data to JSON file for reverse communication"""
        try:
            with open(response_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            pass  # Silently fail to avoid parsing issues

if __name__ == '__main__':
    InkscapeMCPDrawModular().run()
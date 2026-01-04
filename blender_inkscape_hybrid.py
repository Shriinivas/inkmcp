# Blender-Inkscape Hybrid Execution
# Run this script in Blender's text editor to enable hybrid Blender/Inkscape execution.
#
# Usage:
# 1. Open Blender Text Editor
# 2. Load or paste your hybrid script
# 3. Add magic comments:
#    # @local - Execute in Blender (has bpy, bpy.context, etc.)
#    # @inkscape - Execute in Inkscape via inkmcpcli
# 4. Run this script to execute the hybrid code
#
# Example:
#     # @local
#     import bpy
#     obj = bpy.context.active_object
#     vertices = [(v.co.x, v.co.y, 0) for v in obj.data.vertices[:5]]
#     
#     # @inkscape
#     for i, (x, y, z) in enumerate(vertices):
#         circle = Circle()
#         circle.set("cx", str(x * 100))
#         circle.set("cy", str(y * 100))
#         circle.set("r", "5")
#         circle.set("fill", "red")
#         svg.append(circle)


import bpy
import subprocess
import json
import sys
import os
from typing import List, Tuple, Dict, Any
import io
from contextlib import redirect_stdout, redirect_stderr

# Path to inkmcpcli.py
# Set via environment variable: export INKMCP_CLI_PATH=/path/to/inkmcpcli.py
# Or it will auto-detect from common locations
INKMCP_CLI_PATH = os.environ.get('INKMCP_CLI_PATH')

if not INKMCP_CLI_PATH:
    # Try to auto-detect
    script_dir = os.path.dirname(os.path.abspath(__file__))
    possible_paths = [
        os.path.join(script_dir, 'inkmcp', 'inkmcpcli.py'),  # Same repo
        os.path.join(script_dir, '..', 'inkmcp', 'inkmcpcli.py'),  # Parent dir
        os.path.expanduser('~/inkmcp/inkmcp/inkmcpcli.py'),  # Home dir
    ]
    for path in possible_paths:
        if os.path.exists(path):
            INKMCP_CLI_PATH = path
            break

if not INKMCP_CLI_PATH or not os.path.exists(INKMCP_CLI_PATH):
    print("ERROR: Cannot find inkmcpcli.py")
    print("Please set INKMCP_CLI_PATH environment variable:")
    print("  export INKMCP_CLI_PATH=/path/to/inkmcp/inkmcpcli.py")
    INKMCP_CLI_PATH = None  # Will cause clear error on first use


def parse_hybrid_blocks(code: str) -> List[Tuple[str, str]]:
    """Parse code into blocks based on magic comments."""
    lines = code.split('\n')
    blocks = []
    current_type = 'local'  # Default to local (Blender)
    current_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        if stripped == '# @local':
            if current_lines:
                blocks.append((current_type, '\n'.join(current_lines)))
                current_lines = []
            current_type = 'local'
        elif stripped == '# @inkscape':
            if current_lines:
                blocks.append((current_type, '\n'.join(current_lines)))
                current_lines = []
            current_type = 'inkscape'
        else:
            current_lines.append(line)
    
    if current_lines:
        blocks.append((current_type, '\n'.join(current_lines)))
    
    return blocks


def serialize_variables(local_vars: Dict[str, Any], exclude_names: set = None) -> Dict[str, Any]:
    """Extract JSON-serializable variables."""
    if exclude_names is None:
        exclude_names = {'__builtins__', '__name__', '__doc__', 'bpy', 'C', 'D'}
    
    serializable = {}
    
    for key, value in local_vars.items():
        if key.startswith('_') or key in exclude_names:
            continue
        
        # Skip modules and non-serializable types
        if type(value).__name__ in ('module', 'function', 'type', 'builtin_function_or_method', 'bpy_struct'):
            continue
        
        try:
            json.dumps(value)
            serializable[key] = value
        except (TypeError, ValueError):
            pass
    
    return serializable


def execute_inkscape_block(code: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    """Execute code block in Inkscape via inkmcpcli."""
    # Inject variables as code
    var_injections = [f"{key} = {repr(value)}" for key, value in variables.items()]
    full_code = '\n'.join(var_injections) + '\n' + code if var_injections else code
    
    # Call inkmcpcli
    try:
        result = subprocess.run(
            [sys.executable, INKMCP_CLI_PATH, 'execute-code', '--pretty', f"code='{full_code}'"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return {
                'success': False,
                'error': result.stderr or result.stdout,
                'variables': {}
            }
        
        # Parse JSON response
        try:
            response = json.loads(result.stdout)
            return {
                'success': response.get('success', False),
                'output': response.get('response', {}).get('data', {}).get('output', ''),
                'error': response.get('error'),
                'variables': {}  # Inkscape doesn't return variables yet via CLI
            }
        except json.JSONDecodeError:
            return {
                'success': False,
                'error': f"Failed to parse Inkscape response: {result.stdout}",
                'variables': {}
            }
            
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': "Inkscape execution timed out",
            'variables': {}
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Failed to call Inkscape: {str(e)}",
            'variables': {}
        }


def execute_hybrid(code: str):
    """Execute hybrid Blender/Inkscape code."""
    blocks = parse_hybrid_blocks(code)
    
    if not blocks:
        print("No code blocks found")
        return
    
    shared_context = {}
    
    for block_idx, (block_type, block_code) in enumerate(blocks, 1):
        if not block_code.strip():
            continue
        
        if block_type == 'local':
            # Execute in Blender context
            try:
                local_env = {
                    '__builtins__': __builtins__,
                    'bpy': bpy,
                    'C': bpy.context,
                    'D': bpy.data,
                }
                local_env.update(shared_context)
                
                # Capture output
                stdout_capture = io.StringIO()
                
                with redirect_stdout(stdout_capture):
                    exec(block_code, local_env)
                
                output = stdout_capture.getvalue()
                if output:
                    print(f"[Blender Block {block_idx}]")
                    print(output.rstrip())
                
                # Update shared context
                serializable = serialize_variables(local_env)
                shared_context.update(serializable)
                
            except Exception as e:
                import traceback
                print(f"Error in Blender block {block_idx}:", file=sys.stderr)
                traceback.print_exc()
                return
        
        elif block_type == 'inkscape':
            # Execute in Inkscape via CLI
            print(f"[Inkscape Block {block_idx}] Executing...")
            result = execute_inkscape_block(block_code, shared_context)
            
            if not result['success']:
                print(f"Error in Inkscape block {block_idx}:", file=sys.stderr)
                print(result.get('error', 'Unknown error'), file=sys.stderr)
                return
            
            if result.get('output'):
                print(result['output'].rstrip())
            
            # Update context with Inkscape variables (if available)
            shared_context.update(result.get('variables', {}))
    
    print("\nHybrid execution completed successfully!")


# Main execution
if __name__ == "__main__":
    # Get the active text in Blender's text editor
    if bpy.context.space_data and bpy.context.space_data.type == 'TEXT_EDITOR':
        text = bpy.context.space_data.text
        if text:
            code = text.as_string()
            execute_hybrid(code)
        else:
            print("No text file is active in the text editor")
    else:
        print("This script must be run from Blender's text editor")

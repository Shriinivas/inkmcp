"""Code execution operations module"""

import io
import traceback
from contextlib import redirect_stdout, redirect_stderr
from typing import Dict, Any
from .common import create_success_response, create_error_response


def execute_code(extension_instance, svg, attributes: Dict[str, Any]) -> Dict[str, Any]:
    """Execute arbitrary Python/inkex code in extension context"""
    try:
        code = attributes.get('code', '')
        if not code.strip():
            return create_error_response("No code provided")

        return_output = attributes.get('return_output', True)

        # Set up execution context following inkex patterns
        execution_globals = {
            '__builtins__': __builtins__,
            'svg': svg,
            'self': extension_instance,  # Reference to extension instance
            'document': svg,  # Alias for convenience
        }

        # Add inkex module and common classes
        try:
            import inkex
            from inkex import Rectangle, Circle, Ellipse, Line, PathElement, Polygon, Polyline, TextElement
            from inkex import Group, Layer, Use, Image, Marker, Gradient, Defs
            from inkex import Transform, Style, Color, Vector2d
            from inkex.paths import Path, Move, Line as PathLine, Curve, Arc
            from inkex.elements._base import ShapeElement

            execution_globals.update({
                'inkex': inkex,
                # Shape elements (most common)
                'Rectangle': Rectangle,
                'Circle': Circle,
                'Ellipse': Ellipse,
                'Line': Line,
                'PathElement': PathElement,
                'Polygon': Polygon,
                'Polyline': Polyline,
                'TextElement': TextElement,
                # Structural elements
                'Group': Group,
                'Layer': Layer,
                'Use': Use,
                'Image': Image,
                'Marker': Marker,
                'Gradient': Gradient,
                'Defs': Defs,
                # Utility classes
                'Transform': Transform,
                'Style': Style,
                'Color': Color,
                'Vector2d': Vector2d,
                # Path elements
                'Path': Path,
                'Move': Move,
                'PathLine': PathLine,
                'Curve': Curve,
                'Arc': Arc,
                # Base classes
                'ShapeElement': ShapeElement,
            })
        except ImportError as e:
            execution_globals['import_error'] = str(e)

        # Add common Python libraries
        try:
            import math
            import random
            import json
            import re
            import os
            execution_globals.update({
                'math': math,
                'random': random,
                'json': json,
                're': re,
                'os': os,
            })
        except ImportError:
            pass

        # Add helper functions
        def get_element_by_id(element_id):
            """Helper function to find element by ID using iteration (getElementById doesn't work reliably)"""
            for elem in svg.iter():
                if elem.get('id') == element_id:
                    return elem
            return None
        
        execution_globals['get_element_by_id'] = get_element_by_id

        execution_locals = {}

        # Capture output if requested
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        result_data = {
            "code_executed": code,
            "output": "",
            "errors": "",
            "return_value": None,
            "execution_successful": False,
            "elements_created": []
        }

        # Count elements before execution
        elements_before = len(list(svg.iter()))

        try:
            if return_output:
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    # Execute the code in the extension context
                    exec(code, execution_globals, execution_locals)
            else:
                # Execute without capturing output
                exec(code, execution_globals, execution_locals)

            result_data["execution_successful"] = True

            # Capture any return value
            if 'result' in execution_locals:
                result_data["return_value"] = str(execution_locals['result'])

        except Exception as e:
            error_traceback = traceback.format_exc()
            result_data["errors"] = f"Execution error: {str(e)}\n\nTraceback:\n{error_traceback}"
            result_data["execution_successful"] = False

        # Get captured output
        if return_output:
            stdout_content = stdout_capture.getvalue()
            stderr_content = stderr_capture.getvalue()

            if stdout_content:
                result_data["output"] = stdout_content
            if stderr_content and not result_data["errors"]:
                result_data["errors"] = stderr_content

        # Count elements after execution and detect new ones
        try:
            elements_after = len(list(svg.iter()))
            if elements_after > elements_before:
                result_data["elements_created"] = [f"{elements_after - elements_before} new elements added"]

            # Get element counts by type
            element_counts = {}
            for element in svg.iter():
                tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag
                element_counts[tag] = element_counts.get(tag, 0) + 1

            result_data["current_element_counts"] = element_counts
        except Exception as e:
            result_data["element_count_error"] = str(e)

        # Determine message based on execution success
        message = "Code executed successfully" if result_data["execution_successful"] else "Code execution failed"

        return create_success_response(message, **result_data)

    except Exception as e:
        return create_error_response(
            f"Failed to execute code: {str(e)}",
            traceback=traceback.format_exc()
        )
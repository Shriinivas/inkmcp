#!/usr/bin/env python3
"""
Inkscape Extension for dynamic SVG element creation
Handles any SVG element through dynamic class instantiation
"""

import inkex
import json
import os
import tempfile
from typing import Dict, Any, List
from inkmcp.inkmcpops.element_mapping import (
    get_element_class,
    should_place_in_defs,
    ensure_defs_section,
    get_unique_id,
)
from inkmcp.inkmcpops.common import get_element_info_data
from inkmcp.inkmcpops.export_operations import export_document_image
from inkmcp.inkmcpops.execute_operations import execute_code


class ElementCreator(inkex.EffectExtension):
    """Extension for creating any SVG element dynamically"""

    def add_arguments(self, pars):
        """Add command line arguments"""
        # No parameters needed - use fixed file path like original system
        pass

    # def errormsg(self, msg):
    #     """Override errormsg to prevent UI dialogs - silent operation only"""
    #     # Don't call parent errormsg to avoid UI dialogs
    #     pass

    # def debug(self, msg):
    #     """Override debug to suppress debug messages"""
    #     # Suppress all debug output to avoid UI interference
    #     pass

    def create_element_recursive(
        self, svg, element_data: Dict[str, Any], id_mapping: Dict[str, str] | None = None, generated_ids: List[str] | None = None
    ) -> inkex.BaseElement:
        """
        Create SVG element recursively with children and track ID mappings

        Args:
            svg: SVG document
            element_data: Element data with tag, attributes, and children
            id_mapping: Dictionary to collect requested_id -> actual_id mappings
            generated_ids: List to collect auto-generated IDs

        Returns:
            Created SVG element
        """
        if id_mapping is None:
            id_mapping = {}
        if generated_ids is None:
            generated_ids = []

        tag = element_data.get("tag", "")
        attributes = element_data.get("attributes", {})
        children = element_data.get("children", [])

        # Get element class dynamically
        ElementClass = get_element_class(tag)
        if not ElementClass:
            raise ValueError(f"Unknown SVG element: {tag}")

        # Create element instance
        element = ElementClass()

        # Handle ID parameter - track both requested and generated
        requested_id = attributes.get("id")

        if requested_id:
            # Use requested ID (with collision auto-increment)
            actual_id = get_unique_id(svg, tag, requested_id)
            # Track mapping for response
            id_mapping[requested_id] = actual_id
        else:
            # No ID specified - auto-generate and track
            actual_id = get_unique_id(svg, tag, None)
            generated_ids.append(actual_id)

        element.set("id", actual_id)

        # Set all attributes except id (already handled)
        for attr_name, attr_value in attributes.items():
            if attr_name != "id":
                element.set(attr_name, str(attr_value))

        # Process children recursively with same tracking lists
        for child_data in children:
            child_element = self.create_element_recursive(svg, child_data, id_mapping, generated_ids)
            element.append(child_element)

        return element

    def handle_info_action(
        self, svg, action: str, attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle info/query actions that don't create elements

        Args:
            svg: SVG document
            action: Action name (e.g., 'get-selection', 'get-info')
            attributes: Action parameters

        Returns:
            Response data
        """
        try:
            if action == "get-selection":
                return self.get_selection_info()
            elif action == "get-info":
                return self.get_document_info(svg)
            elif action == "get-info-by-id":
                element_id = attributes.get("id", "")
                return self.get_element_info(svg, element_id)
            elif action == "export-document-image":
                return export_document_image(self, svg, attributes)
            elif action == "execute-code":
                return execute_code(self, svg, attributes)
            else:
                return {
                    "status": "error",
                    "data": {"error": f"Unknown info action: {action}"},
                }
        except Exception as e:
            return {
                "status": "error",
                "data": {"error": f"Info action failed: {str(e)}"},
            }

    def get_selection_info(self) -> Dict[str, Any]:
        """Get information about current selection"""
        try:
            # Get selected elements - Inkscape passes them via self.svg.selected
            selected = self.svg.selected

            # Extract info for each selected element
            elements = []
            for elem_id, element in selected.items():
                elem_info = get_element_info_data(element)
                elements.append(elem_info)

            return {
                "status": "success",
                "data": {
                    "message": "Selection information retrieved successfully",
                    "count": len(selected),
                    "elements": elements,
                },
            }
        except Exception as e:
            return {
                "status": "error",
                "data": {"error": f"Failed to get selection info: {str(e)}"},
            }

    def get_document_info(self, svg) -> Dict[str, Any]:
        """Get document information"""
        try:
            viewbox = svg.get("viewBox", "0 0 100 100").split()
            width = svg.get("width", "unknown")
            height = svg.get("height", "unknown")

            # Count elements by type
            element_counts = {}
            for elem in svg.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                element_counts[tag] = element_counts.get(tag, 0) + 1

            return {
                "status": "success",
                "data": {
                    "message": "Document information",
                    "dimensions": {"width": width, "height": height},
                    "viewBox": viewbox,
                    "elementCounts": element_counts,
                },
            }
        except Exception as e:
            return {
                "status": "error",
                "data": {"error": f"Failed to get document info: {str(e)}"},
            }

    def get_element_info(self, svg, element_id: str) -> Dict[str, Any]:
        """Get information about specific element"""
        try:
            element = svg.getElementById(element_id)
            if element is None:
                return {
                    "status": "error",
                    "data": {"error": f"Element not found: {element_id}"},
                }

            element_info = get_element_info_data(element)
            return {
                "status": "success",
                "data": {
                    "message": f"Element information for {element_id}",
                    **element_info,
                },
            }
        except Exception as e:
            return {
                "status": "error",
                "data": {"error": f"Failed to get element info: {str(e)}"},
            }

    def write_response(self, response_data: Dict[str, Any], response_file_path: str):
        """Write response to response file (like original system)"""
        try:
            with open(response_file_path, "w") as f:
                json.dump(response_data, f)
        except Exception:
            # Silent failure - avoid any output that could interfere with Inkscape
            pass

    def effect(self):
        """Main extension entry point"""
        element_data = {}  # Initialize to avoid unbound variable
        try:
            # Read JSON data from fixed file path (like original system)
            params_file = os.path.join(tempfile.gettempdir(), "mcp_params.json")
            if not os.path.exists(params_file):
                response = {
                    "status": "error",
                    "data": {"error": "No parameters file found"},
                }
                self.write_response(response, "/tmp/error_response.json")
                return

            with open(params_file, "r") as f:
                element_data = json.load(f)

            # Clean up the params file after reading (like original system)
            os.remove(params_file)

            tag = element_data.get("tag", "")

            # Try to create as SVG element first
            ElementClass = get_element_class(tag)

            if ElementClass:
                # Create SVG element with ID tracking
                id_mapping = {}
                generated_ids = []
                element = self.create_element_recursive(self.svg, element_data, id_mapping, generated_ids)

                # Determine placement
                if should_place_in_defs(ElementClass):
                    defs = ensure_defs_section(self.svg)
                    defs.append(element)
                else:
                    self.svg.append(element)

                # Build response data
                response_data = {
                    "message": f"{tag} created successfully",
                    "id": element.get("id"),
                    "tag": tag,
                    "attributes": dict(element.attrib),
                }

                # Add ID information to response
                total_elements = len(id_mapping) + len(generated_ids)

                if id_mapping:
                    response_data["id_mapping"] = id_mapping

                if generated_ids:
                    response_data["generated_ids"] = generated_ids

                # Update message to reflect multiple elements if needed
                if total_elements > 1:
                    response_data["message"] = f"{total_elements} elements created successfully"

                response = {
                    "status": "success",
                    "data": response_data,
                }

            else:
                # Handle as info action
                attributes = element_data.get("attributes", {})
                response = self.handle_info_action(self.svg, tag, attributes)

            # Write response to response file if provided (like original system)
            response_file = element_data.get("response_file")
            if response_file:
                self.write_response(response, response_file)

        except Exception as e:
            error_response = {
                "status": "error",
                "data": {"error": f"Extension failed: {str(e)}"},
            }
            # Try to write error to response file if available
            try:
                response_file = element_data.get("response_file")
                if response_file:
                    self.write_response(error_response, response_file)
            except:
                pass  # Silent error handling


def main():
    """Main entry point"""
    extension = ElementCreator()
    extension.run()


if __name__ == "__main__":
    main()


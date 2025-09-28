#!/usr/bin/env python3
"""
Generic Inkscape Extension for dynamic SVG element creation
Handles any SVG element through dynamic class instantiation
"""

import inkex
import json
import os
import sys
import tempfile
import time
from typing import Dict, Any, List, Optional
from element_mapping import get_element_class, should_place_in_defs, ensure_defs_section, get_unique_id


class GenericElementCreator(inkex.EffectExtension):
    """Generic extension for creating any SVG element dynamically"""

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

    def create_element_recursive(self, svg, element_data: Dict[str, Any]) -> inkex.BaseElement:
        """
        Create SVG element recursively with children

        Args:
            svg: SVG document
            element_data: Element data with tag, attributes, and children

        Returns:
            Created SVG element
        """
        tag = element_data.get("tag", "")
        attributes = element_data.get("attributes", {})
        children = element_data.get("children", [])

        # Get element class dynamically
        ElementClass = get_element_class(tag)
        if not ElementClass:
            raise ValueError(f"Unknown SVG element: {tag}")

        # Create element instance
        element = ElementClass()

        # Set unique ID
        custom_id = attributes.get("id")
        element_id = get_unique_id(svg, tag, custom_id)
        element.set('id', element_id)

        # Set all attributes
        for attr_name, attr_value in attributes.items():
            if attr_name != "id":  # ID already set
                element.set(attr_name, str(attr_value))

        # Process children recursively
        for child_data in children:
            child_element = self.create_element_recursive(svg, child_data)
            element.append(child_element)

        return element

    def handle_info_action(self, svg, action: str, attributes: Dict[str, Any]) -> Dict[str, Any]:
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
                return self.get_selection_info(svg)
            elif action == "get-info":
                return self.get_document_info(svg)
            elif action == "get-info-by-id":
                element_id = attributes.get("id", "")
                return self.get_element_info(svg, element_id)
            else:
                return {
                    "status": "error",
                    "data": {"error": f"Unknown info action: {action}"}
                }
        except Exception as e:
            return {
                "status": "error",
                "data": {"error": f"Info action failed: {str(e)}"}
            }

    def get_selection_info(self, svg) -> Dict[str, Any]:
        """Get information about current selection"""
        # For now, return placeholder - would need selection tracking
        return {
            "status": "success",
            "data": {
                "message": "Selection info (placeholder)",
                "count": 0,
                "elements": []
            }
        }

    def get_document_info(self, svg) -> Dict[str, Any]:
        """Get document information"""
        try:
            viewbox = svg.get('viewBox', '0 0 100 100').split()
            width = svg.get('width', 'unknown')
            height = svg.get('height', 'unknown')

            # Count elements by type
            element_counts = {}
            for elem in svg.iter():
                tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                element_counts[tag] = element_counts.get(tag, 0) + 1

            return {
                "status": "success",
                "data": {
                    "message": "Document information",
                    "dimensions": {"width": width, "height": height},
                    "viewBox": viewbox,
                    "elementCounts": element_counts
                }
            }
        except Exception as e:
            return {
                "status": "error",
                "data": {"error": f"Failed to get document info: {str(e)}"}
            }

    def get_element_info(self, svg, element_id: str) -> Dict[str, Any]:
        """Get information about specific element"""
        try:
            element = svg.getElementById(element_id)
            if not element:
                return {
                    "status": "error",
                    "data": {"error": f"Element not found: {element_id}"}
                }

            return {
                "status": "success",
                "data": {
                    "message": f"Element information for {element_id}",
                    "id": element_id,
                    "tag": element.tag.split('}')[-1] if '}' in element.tag else element.tag,
                    "attributes": dict(element.attrib)
                }
            }
        except Exception as e:
            return {
                "status": "error",
                "data": {"error": f"Failed to get element info: {str(e)}"}
            }

    def write_response(self, response_data: Dict[str, Any], response_file_path: str):
        """Write response to response file (like original system)"""
        try:
            with open(response_file_path, 'w') as f:
                json.dump(response_data, f)
        except Exception:
            # Silent failure - avoid any output that could interfere with Inkscape
            pass

    def effect(self):
        """Main extension entry point"""
        try:
            # Read JSON data from fixed file path (like original system)
            params_file = os.path.join(tempfile.gettempdir(), "mcp_params.json")
            if not os.path.exists(params_file):
                response = {
                    "status": "error",
                    "data": {"error": "No parameters file found"}
                }
                self.write_response(response, "/tmp/error_response.json")
                return

            with open(params_file, 'r') as f:
                element_data = json.load(f)

            # Clean up the params file after reading (like original system)
            os.remove(params_file)

            tag = element_data.get("tag", "")

            # Try to create as SVG element first
            ElementClass = get_element_class(tag)

            if ElementClass:
                # Create SVG element
                element = self.create_element_recursive(self.svg, element_data)

                # Determine placement
                if should_place_in_defs(ElementClass):
                    defs = ensure_defs_section(self.svg)
                    defs.append(element)
                else:
                    self.svg.append(element)


                response = {
                    "status": "success",
                    "data": {
                        "message": f"{tag} created successfully",
                        "id": element.get('id'),
                        "tag": tag,
                        "attributes": dict(element.attrib)
                    }
                }

            else:
                # Handle as info action
                attributes = element_data.get("attributes", {})
                response = self.handle_info_action(self.svg, tag, attributes)

            # Write response to response file if provided (like original system)
            response_file = element_data.get('response_file')
            if response_file:
                self.write_response(response, response_file)

        except Exception as e:
            error_response = {
                "status": "error",
                "data": {"error": f"Extension failed: {str(e)}"}
            }
            # Try to write error to response file if available
            try:
                response_file = element_data.get('response_file') if 'element_data' in locals() else None
                if response_file:
                    self.write_response(error_response, response_file)
            except:
                pass  # Silent error handling


def main():
    """Main entry point"""
    extension = GenericElementCreator()
    extension.run()


if __name__ == "__main__":
    main()
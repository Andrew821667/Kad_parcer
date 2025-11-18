"""Example plugin: XML exporter.

This is an example plugin that demonstrates how to create a custom exporter.
"""

import xml.etree.ElementTree as ET
from typing import Any

from src.plugins.base import ExporterPlugin


class XMLExporterPlugin(ExporterPlugin):
    """XML exporter plugin."""

    @property
    def name(self) -> str:
        """Plugin name."""
        return "xml_exporter"

    @property
    def version(self) -> str:
        """Plugin version."""
        return "1.0.0"

    @property
    def description(self) -> str:
        """Plugin description."""
        return "Export data to XML format"

    @property
    def author(self) -> str:
        """Plugin author."""
        return "KAD Parser Team"

    async def initialize(self) -> None:
        """Initialize plugin."""
        pass

    async def cleanup(self) -> None:
        """Cleanup plugin resources."""
        pass

    async def export(self, data: list[dict[str, Any]], format_options: dict[str, Any]) -> bytes:
        """Export data to XML format.

        Args:
            data: Data to export
            format_options: Format-specific options

        Returns:
            XML data as bytes
        """
        # Create root element
        root_name = format_options.get("root_element", "data")
        item_name = format_options.get("item_element", "item")

        root = ET.Element(root_name)

        # Add items
        for item in data:
            item_element = ET.SubElement(root, item_name)
            self._dict_to_xml(item, item_element)

        # Convert to string
        tree = ET.ElementTree(root)
        xml_str = ET.tostring(tree.getroot(), encoding="unicode", xml_declaration=True)

        return xml_str.encode("utf-8")

    def _dict_to_xml(self, data: dict[str, Any], parent: ET.Element) -> None:
        """Convert dictionary to XML elements.

        Args:
            data: Dictionary data
            parent: Parent XML element
        """
        for key, value in data.items():
            if isinstance(value, dict):
                child = ET.SubElement(parent, str(key))
                self._dict_to_xml(value, child)
            elif isinstance(value, list):
                for item in value:
                    child = ET.SubElement(parent, str(key))
                    if isinstance(item, dict):
                        self._dict_to_xml(item, child)
                    else:
                        child.text = str(item)
            else:
                child = ET.SubElement(parent, str(key))
                child.text = str(value) if value is not None else ""

    def get_file_extension(self) -> str:
        """Get file extension for this export format."""
        return ".xml"

    def get_mime_type(self) -> str:
        """Get MIME type for this export format."""
        return "application/xml"

    def supports_content_type(self, content_type: str) -> bool:
        """Check if this parser supports the given content type."""
        return False

"""Example plugin: Data enrichment processor.

This is an example plugin that demonstrates how to create a data processor.
"""

from typing import Any

from src.plugins.base import PluginHook, ProcessorPlugin


class DataEnrichmentPlugin(ProcessorPlugin):
    """Data enrichment processor plugin."""

    @property
    def name(self) -> str:
        """Plugin name."""
        return "data_enrichment"

    @property
    def version(self) -> str:
        """Plugin version."""
        return "1.0.0"

    @property
    def description(self) -> str:
        """Plugin description."""
        return "Enrich case data with additional computed fields"

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

    def get_hooks(self) -> list[PluginHook]:
        """Get list of hooks this plugin subscribes to."""
        return [PluginHook.AFTER_SCRAPE, PluginHook.BEFORE_SAVE]

    async def on_hook(self, hook: PluginHook, context: dict[str, Any]) -> dict[str, Any]:
        """Handle hook event.

        Args:
            hook: Hook type
            context: Hook context data

        Returns:
            Modified context data
        """
        if hook == PluginHook.AFTER_SCRAPE:
            # Add computed fields to scraped data
            if "case" in context:
                case_data = context["case"]

                # Add case age in days
                if "filing_date" in case_data:
                    from datetime import datetime

                    filing_date = datetime.fromisoformat(case_data["filing_date"])
                    age_days = (datetime.utcnow() - filing_date).days
                    case_data["age_days"] = age_days

                # Add participant count
                if "participants" in context:
                    case_data["participant_count"] = len(context["participants"])

                # Add document count
                if "documents" in context:
                    case_data["document_count"] = len(context["documents"])

        return context

    async def process(self, data: dict[str, Any]) -> dict[str, Any]:
        """Process data.

        Args:
            data: Input data

        Returns:
            Processed data
        """
        # Add metadata
        from datetime import datetime

        data["_enriched_at"] = datetime.utcnow().isoformat()
        data["_enriched_by"] = self.name

        return data

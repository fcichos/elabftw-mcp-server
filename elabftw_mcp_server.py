#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "mcp>=1.0.0",
#     "httpx>=0.25.0",
#     "anyio>=4.0.0",
#     "python-dotenv>=1.0.0",
# ]
# ///
"""
MCP Server for elabFTW - Electronic Lab Notebook

This server provides tools to interact with an elabFTW instance,
allowing retrieval and creation of experiments.

Configuration:
    Set the following environment variables:
    - ELABFTW_API_URL: The base URL for the elabFTW API (e.g., https://your-server.example.com/api/v2)
    - ELABFTW_API_KEY: Your elabFTW API key

Usage:
    Run directly: python elabftw_mcp_server.py
    Or configure in Claude Desktop / Ollama MCP settings
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

# Load environment variables from .env file if present
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, use environment variables directly

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    TextContent,
    Tool,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("elabftw-mcp")

# Configuration from environment variables
API_BASE_URL = os.getenv("ELABFTW_API_URL", "https://your-server.example.com/api/v2")
API_KEY = os.getenv("ELABFTW_API_KEY", "")

# SSL verification - set to False for self-signed certificates (common in lab setups)
# For production, you should use proper certificates and set this to True
VERIFY_SSL = os.getenv("ELABFTW_VERIFY_SSL", "false").lower() == "true"

# Lab Prompt: the content the LLM uses as its guidance for eLabFTW interactions
LAB_PROMPT = """
You are an AI lab assistant integrated with an eLabFTW notebook and its resources (files, datasets, instruments, protocols, wiki). Your goals are to: find, summarize, cross‑reference, and transform information in eLabFTW; draft well‑structured experiments, protocols, summaries, and reports in the user's style; and reason over experiments, items, tags, and attachments.

Always behave as a domain‑aware assistant for an experimental soft‑matter/biophysics group, using precise technical language and concise answers. If information in eLabFTW is missing or ambiguous, say what is missing, never invent IDs or results, and suggest which search, tag, or experiment could resolve it.

Treat eLabFTW as the source of truth for experiment entries and metadata, items, attachments, and wiki/protocol pages. For data‑dependent questions: infer relevant experiments/items/tags/wiki pages, suggest concise search queries (title fragment, tag, item name, date range), then summarize clearly, extract structured information (tables, parameter lists, timelines), and highlight discrepancies or trends. If a request is too broad, propose narrower scopes (project, tag, PI, date range, instrument).

When answering, refer explicitly to the mention experiment titles/IDs and item names or catalog numbers when useful, and note conflicting entries with a suggestion of which looks more reliable (latest, approved, or more complete). For analysis questions, describe plots or tables that could be made from attached data, compare conditions across experiments, and suggest derived quantities and how to compute them.

For new or improved entries, output markdown text ready to paste into eLabFTW:
- experiments with "Objective", "Materials", "Methods", "Results", "Analysis", "Notes"
- protocols with numbered steps, safety notes, and parameter ranges
- items with concise searchable descriptions and key fields
- templates with parameterized structures with placeholders like <sample_id> or <laser_power_mW>

Keep answers compact and technically dense, avoiding generic commentary. For safety‑critical topics (instrument limits, dosing, hazards), give conservative guidance and point back to official or lab‑recorded protocols. When providing code, give minimal clear scripts assuming data has been exported locally.

If a request is under‑specified, ask targeted clarification (project/tag, date range, instrument, status such as approved vs draft) and prefer stepwise, interactive refinement over a single large answer.

You are now connected to eLabFTW via an MCP server that can query experiments, items, and wiki pages by IDs, titles, tags, and date ranges, access attachments, and return markdown content for entries.
"""


class ElabFTWClient:
    """Client for interacting with elabFTW API."""

    def __init__(self, base_url: str, api_key: str, verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.verify_ssl = verify_ssl
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }

    def _get_client(self) -> httpx.Client:
        """Create an HTTP client with proper configuration."""
        return httpx.Client(
            headers=self.headers,
            verify=self.verify_ssl,
            timeout=30.0,
        )

    def list_experiments(
        self,
        limit: int = 15,
        offset: int = 0,
        search: Optional[str] = None,
        owner: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        List experiments from elabFTW.

        Args:
            limit: Maximum number of experiments to return (default: 15)
            offset: Number of experiments to skip (for pagination)
            search: Optional search query to filter experiments
            owner: Optional user ID(s) to filter by owner (can be comma-separated like "2,3")

        Returns:
            Dictionary containing list of experiments
        """
        params = {"limit": limit, "offset": offset}
        if search:
            params["q"] = search
        if owner:
            params["owner"] = owner

        with self._get_client() as client:
            response = client.get(
                f"{self.base_url}/experiments",
                params=params,
            )
            response.raise_for_status()
            return response.json()

    def get_experiment(self, experiment_id: int) -> dict[str, Any]:
        """
        Get a specific experiment by ID.

        Args:
            experiment_id: The ID of the experiment to retrieve

        Returns:
            Dictionary containing experiment details
        """
        with self._get_client() as client:
            response = client.get(f"{self.base_url}/experiments/{experiment_id}")
            response.raise_for_status()
            return response.json()

    def create_experiment(
        self,
        title: str,
        body: str = "",
        template: Optional[int] = None,
        category: Optional[int] = None,
        tags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Create a new experiment.

        Args:
            title: Title of the experiment
            body: Body/content of the experiment (HTML supported)
            template: Template ID to use (-1 for empty, 0 for team template, or specific ID).
                      Required by some elabFTW instances with force_exp_tpl enabled.
            category: Optional category ID for the experiment
            tags: Optional list of tags

        Returns:
            Dictionary containing the created experiment info
        """
        # Create the experiment with all parameters in JSON body per API spec
        with self._get_client() as client:
            # Build the JSON body for POST request
            create_data: dict[str, Any] = {
                "title": title,
                "body": body,
            }
            if template is not None:
                create_data["template"] = template
            if category is not None:
                create_data["category"] = category

            response = client.post(
                f"{self.base_url}/experiments",
                json=create_data,
            )
            response.raise_for_status()

            # Get the location header which contains the new experiment URL
            location = response.headers.get("location", "")
            # Extract the experiment ID from the location
            experiment_id = int(location.split("/")[-1])

            # Add tags if provided
            if tags:
                for tag in tags:
                    client.post(
                        f"{self.base_url}/experiments/{experiment_id}/tags",
                        json={"tag": tag},
                    )

            # Return the created experiment
            return self.get_experiment(experiment_id)

    def update_experiment(
        self,
        experiment_id: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        category: Optional[int] = None,
        status: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Update an existing experiment.

        Note: You can update the category of an existing experiment using the
        'category' parameter. Use list_experiment_categories to find valid IDs.

        Args:
            experiment_id: The ID of the experiment to update
            title: New title (optional)
            body: New body/content (optional)
            category: New category ID (optional) - use list_experiment_categories to find IDs
            status: New status ID (optional)

        Returns:
            Dictionary containing the updated experiment info
        """
        update_data = {}
        if title is not None:
            update_data["title"] = title
        if body is not None:
            update_data["body"] = body
        if category is not None:
            update_data["category"] = category
        if status is not None:
            update_data["status"] = status

        if not update_data:
            raise ValueError("At least one field must be provided for update")

        with self._get_client() as client:
            response = client.patch(
                f"{self.base_url}/experiments/{experiment_id}",
                json=update_data,
            )
            response.raise_for_status()
            return self.get_experiment(experiment_id)

    def add_tag_to_experiment(self, experiment_id: int, tag: str) -> dict[str, Any]:
        """
        Add a tag to an experiment.

        Args:
            experiment_id: The ID of the experiment
            tag: The tag to add

        Returns:
            Success message
        """
        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/experiments/{experiment_id}/tags",
                json={"tag": tag},
            )
            response.raise_for_status()
            return {
                "status": "success",
                "message": f"Tag '{tag}' added to experiment {experiment_id}",
            }

    def remove_tag_from_experiment(
        self, experiment_id: int, tag_id: int
    ) -> dict[str, Any]:
        """
        Remove a tag from an experiment.

        Args:
            experiment_id: The ID of the experiment
            tag_id: The ID of the tag to remove

        Returns:
            Success message
        """
        with self._get_client() as client:
            response = client.delete(
                f"{self.base_url}/experiments/{experiment_id}/tags/{tag_id}",
            )
            response.raise_for_status()
            return {
                "status": "success",
                "message": f"Tag {tag_id} removed from experiment {experiment_id}",
            }

    def set_experiment_status(
        self,
        experiment_id: int,
        status_id: int,
    ) -> dict[str, Any]:
        """
        Set the status of an experiment (e.g., Running, Success, Need to be redone).

        Args:
            experiment_id: The ID of the experiment
            status_id: The status ID to set

        Returns:
            Dictionary containing the updated experiment info
        """
        with self._get_client() as client:
            response = client.patch(
                f"{self.base_url}/experiments/{experiment_id}",
                json={"status": status_id},
            )
            response.raise_for_status()
            return self.get_experiment(experiment_id)

    def link_item_to_experiment(
        self,
        experiment_id: int,
        link_id: int,
        link_type: str = "experiments",
    ) -> dict[str, Any]:
        """
        Link another experiment or database item to an experiment.

        Args:
            experiment_id: The ID of the experiment
            link_id: The ID of the item to link
            link_type: Either "experiments" or "items"

        Returns:
            Success message
        """
        if link_type not in ("experiments", "items"):
            raise ValueError("link_type must be 'experiments' or 'items'")

        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/experiments/{experiment_id}/{link_type}_links/{link_id}",
            )
            response.raise_for_status()
            return {
                "status": "success",
                "message": f"Linked {link_type[:-1]} {link_id} to experiment {experiment_id}",
            }

    def upload_attachment(
        self,
        experiment_id: int,
        file_path: str,
        comment: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Upload a file attachment to an experiment.

        Args:
            experiment_id: The ID of the experiment
            file_path: Path to the file to upload
            comment: Optional comment for the attachment

        Returns:
            Dictionary with upload result
        """
        import os

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        with self._get_client() as client:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                data = {}
                if comment:
                    data["comment"] = comment

                # Need to remove Content-Type header for multipart upload
                headers = {"Authorization": self.api_key}
                response = client.post(
                    f"{self.base_url}/experiments/{experiment_id}/uploads",
                    files=files,
                    data=data,
                    headers=headers,
                )
                response.raise_for_status()
                return {
                    "status": "success",
                    "message": f"File '{os.path.basename(file_path)}' uploaded to experiment {experiment_id}",
                }

    def list_experiment_templates(
        self,
        limit: int = 15,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        List available experiment templates.

        Templates define the initial content/structure of new experiments.
        Use the 'template' parameter when creating experiments.

        Args:
            limit: Maximum number of templates to return (default: 15)
            offset: Number of templates to skip (for pagination)

        Returns:
            List of available experiment templates
        """
        params = {"limit": limit, "offset": offset}

        with self._get_client() as client:
            response = client.get(
                f"{self.base_url}/experiments_templates",
                params=params,
            )
            response.raise_for_status()
            return response.json()

    def list_experiment_categories(
        self,
        team_id: int = 1,
    ) -> list[dict[str, Any]]:
        """
        List available experiment categories for a team.

        Categories are used to classify experiments (distinct from templates).
        Use the 'category' parameter when creating experiments.

        Args:
            team_id: The team ID to get categories for (default: 1)

        Returns:
            List of experiment categories with id, title, and color
        """
        with self._get_client() as client:
            response = client.get(
                f"{self.base_url}/teams/{team_id}/experiments_categories",
            )
            response.raise_for_status()
            return response.json()

    def delete_experiment(self, experiment_id: int) -> dict[str, Any]:
        """
        Delete an experiment (soft-delete).

        The experiment will be marked as deleted but can potentially be restored
        by an administrator.

        Args:
            experiment_id: The ID of the experiment to delete

        Returns:
            Success message
        """
        with self._get_client() as client:
            response = client.delete(
                f"{self.base_url}/experiments/{experiment_id}",
            )
            response.raise_for_status()
            return {
                "status": "success",
                "message": f"Experiment {experiment_id} has been deleted",
            }

    # ==================== ITEMS/RESOURCES METHODS ====================

    def list_items(
        self,
        limit: int = 15,
        offset: int = 0,
        search: Optional[str] = None,
        category: Optional[int] = None,
        owner: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        List database items (resources) from elabFTW.

        Items are used to store resources like chemicals, equipment, setups,
        reagents, cell lines, plasmids, etc.

        Args:
            limit: Maximum number of items to return (default: 15)
            offset: Number of items to skip (for pagination)
            search: Optional search query to filter items
            category: Optional category ID to filter items by type
            owner: Optional user ID(s) to filter by owner (can be comma-separated like "2,3")

        Returns:
            List of items
        """
        params = {"limit": limit, "offset": offset}
        if search:
            params["q"] = search
        if category is not None:
            params["cat"] = category
        if owner:
            params["owner"] = owner

        with self._get_client() as client:
            response = client.get(
                f"{self.base_url}/items",
                params=params,
            )
            response.raise_for_status()
            return response.json()

    def get_item(self, item_id: int) -> dict[str, Any]:
        """
        Get a specific database item by ID.

        Args:
            item_id: The ID of the item to retrieve

        Returns:
            Dictionary containing item details
        """
        with self._get_client() as client:
            response = client.get(f"{self.base_url}/items/{item_id}")
            response.raise_for_status()
            return response.json()

    def create_item(
        self,
        category: int,
        title: Optional[str] = None,
        body: str = "",
        tags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Create a new database item (resource) in elabFTW.

        Args:
            category: Category/type ID for the item (required). Use list_items_types to find valid IDs.
            title: Title of the new item (optional, will use category default if not provided)
            body: Body/content of the item. HTML formatting is supported.
            tags: Optional list of tags to add to the item

        Returns:
            Dictionary with created item info including ID
        """
        # Create the item with category
        data = {"category_id": category}

        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/items",
                json=data,
            )
            response.raise_for_status()

            # Get the created item ID from the Location header
            location = response.headers.get("Location", "")
            item_id = int(location.split("/")[-1]) if location else None

            if item_id is None:
                return {
                    "status": "error",
                    "message": "Could not determine created item ID",
                }

            # Now update with title and body if provided
            update_data = {}
            if title:
                update_data["title"] = title
            if body:
                update_data["body"] = body

            if update_data:
                patch_response = client.patch(
                    f"{self.base_url}/items/{item_id}",
                    json=update_data,
                )
                patch_response.raise_for_status()

            # Add tags if provided
            if tags:
                for tag in tags:
                    try:
                        client.post(
                            f"{self.base_url}/items/{item_id}/tags",
                            json={"tag": tag},
                        )
                    except httpx.HTTPStatusError:
                        pass  # Tag might already exist

            # Return the created item info
            return {
                "status": "success",
                "item_id": item_id,
                "title": title or "(default from category)",
                "message": f"Item created successfully with ID {item_id}",
            }

    def update_item(
        self,
        item_id: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        category: Optional[int] = None,
        rating: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Update an existing database item.

        Args:
            item_id: The ID of the item to update
            title: New title for the item
            body: New body/content for the item
            category: New category ID for the item
            rating: Rating for the item (0-5)

        Returns:
            Success message with updated fields
        """
        data = {}
        if title is not None:
            data["title"] = title
        if body is not None:
            data["body"] = body
        if category is not None:
            data["category_id"] = category
        if rating is not None:
            data["rating"] = rating

        if not data:
            return {
                "status": "error",
                "message": "No fields to update. Provide at least one of: title, body, category, rating",
            }

        with self._get_client() as client:
            response = client.patch(
                f"{self.base_url}/items/{item_id}",
                json=data,
            )
            response.raise_for_status()
            return {
                "status": "success",
                "message": f"Item {item_id} updated successfully",
                "updated_fields": list(data.keys()),
            }

    def delete_item(self, item_id: int) -> dict[str, Any]:
        """
        Delete a database item (soft-delete).

        Args:
            item_id: The ID of the item to delete

        Returns:
            Success message
        """
        with self._get_client() as client:
            response = client.delete(
                f"{self.base_url}/items/{item_id}",
            )
            response.raise_for_status()
            return {
                "status": "success",
                "message": f"Item {item_id} has been deleted",
            }

    def list_items_types(
        self,
        team_id: int = 1,
    ) -> list[dict[str, Any]]:
        """
        List available item types/categories for a team.

        Item types define what kinds of resources you can store (e.g., Chemicals,
        Equipment, Plasmids, Cell Lines, etc.).

        Args:
            team_id: The team ID to get item types for (default: 1)

        Returns:
            List of item types with id, title, color, and other metadata
        """
        with self._get_client() as client:
            response = client.get(
                f"{self.base_url}/teams/{team_id}/items_types",
            )
            response.raise_for_status()
            return response.json()

    def add_tag_to_item(self, item_id: int, tag: str) -> dict[str, Any]:
        """
        Add a tag to a database item.

        Args:
            item_id: The ID of the item
            tag: The tag text to add

        Returns:
            Success message
        """
        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/items/{item_id}/tags",
                json={"tag": tag},
            )
            response.raise_for_status()
            return {
                "status": "success",
                "message": f"Tag '{tag}' added to item {item_id}",
            }

    def remove_tag_from_item(self, item_id: int, tag_id: int) -> dict[str, Any]:
        """
        Remove a tag from a database item.

        Args:
            item_id: The ID of the item
            tag_id: The ID of the tag to remove

        Returns:
            Success message
        """
        with self._get_client() as client:
            response = client.delete(
                f"{self.base_url}/items/{item_id}/tags/{tag_id}",
            )
            response.raise_for_status()
            return {
                "status": "success",
                "message": f"Tag {tag_id} removed from item {item_id}",
            }

    def upload_attachment_to_item(
        self,
        item_id: int,
        file_path: str,
        comment: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Upload a file attachment to a database item.

        Args:
            item_id: The ID of the item
            file_path: Path to the file to upload
            comment: Optional comment for the attachment

        Returns:
            Dictionary with upload result
        """
        import os

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        with self._get_client() as client:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                data = {}
                if comment:
                    data["comment"] = comment

                headers = {"Authorization": self.api_key}
                response = client.post(
                    f"{self.base_url}/items/{item_id}/uploads",
                    files=files,
                    data=data,
                    headers=headers,
                )
                response.raise_for_status()
                return {
                    "status": "success",
                    "message": f"File '{os.path.basename(file_path)}' uploaded to item {item_id}",
                }

    def link_item_to_item(
        self,
        item_id: int,
        link_id: int,
        link_type: str = "items",
    ) -> dict[str, Any]:
        """
        Link another item or experiment to a database item.

        Args:
            item_id: The ID of the item to add the link to
            link_id: The ID of the item or experiment to link
            link_type: Either "items" or "experiments"

        Returns:
            Success message
        """
        if link_type not in ("experiments", "items"):
            raise ValueError("link_type must be 'experiments' or 'items'")

        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/items/{item_id}/{link_type}_links/{link_id}",
            )
            response.raise_for_status()
            return {
                "status": "success",
                "message": f"Linked {link_type[:-1]} {link_id} to item {item_id}",
            }

    # ==================== BOOKING/EVENTS METHODS ====================

    def list_events(
        self,
        limit: int = 50,
        offset: int = 0,
        start: Optional[str] = None,
        end: Optional[str] = None,
        item_id: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        List booking events from elabFTW.

        Args:
            limit: Maximum number of events to return (default: 50)
            offset: Number of events to skip (for pagination)
            start: Filter events starting after this datetime (ISO format)
            end: Filter events ending before this datetime (ISO format)
            item_id: Filter events for specific item

        Returns:
            List of booking events
        """
        params = {"limit": limit, "offset": offset}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if item_id:
            params["item"] = item_id

        with self._get_client() as client:
            response = client.get(
                f"{self.base_url}/events",
                params=params,
            )
            response.raise_for_status()
            return response.json()

    def get_event(self, event_id: int) -> dict[str, Any]:
        """
        Get a specific booking event by ID.

        Args:
            event_id: The ID of the event to retrieve

        Returns:
            Dictionary containing event details
        """
        with self._get_client() as client:
            response = client.get(f"{self.base_url}/events/{event_id}")
            response.raise_for_status()
            return response.json()

    def create_booking(
        self,
        item_id: int,
        start: str,
        end: str,
        title: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create a new booking for an item.

        Args:
            item_id: The ID of the item to book
            start: Start datetime in ISO format (e.g., "2024-01-15T09:00:00")
            end: End datetime in ISO format (e.g., "2024-01-15T17:00:00")
            title: Optional title for the booking

        Returns:
            Dictionary with created booking details
        """
        data = {
            "item": item_id,
            "start": start,
            "end": end,
        }
        if title:
            data["title"] = title

        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/events",
                json=data,
            )
            response.raise_for_status()

            # Try to get the created event ID from Location header
            location = response.headers.get("location", "")
            if location:
                event_id = int(location.split("/")[-1])
                return self.get_event(event_id)

            return {
                "status": "success",
                "message": "Booking created successfully",
            }

    def update_booking(
        self,
        event_id: int,
        start: Optional[str] = None,
        end: Optional[str] = None,
        title: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Update an existing booking.

        Args:
            event_id: The ID of the event to update
            start: New start datetime in ISO format
            end: New end datetime in ISO format
            title: New title

        Returns:
            Dictionary containing updated booking info
        """
        data = {}
        if start is not None:
            data["start"] = start
        if end is not None:
            data["end"] = end
        if title is not None:
            data["title"] = title

        if not data:
            raise ValueError("At least one field must be provided for update")

        with self._get_client() as client:
            response = client.patch(
                f"{self.base_url}/events/{event_id}",
                json=data,
            )
            response.raise_for_status()
            return self.get_event(event_id)

    def delete_booking(self, event_id: int) -> dict[str, Any]:
        """
        Cancel/delete a booking.

        Args:
            event_id: The ID of the event to delete

        Returns:
            Success message
        """
        with self._get_client() as client:
            response = client.delete(f"{self.base_url}/events/{event_id}")
            response.raise_for_status()
            return {
                "status": "success",
                "message": f"Booking {event_id} has been cancelled",
            }


# Initialize the MCP server
server = Server("elabftw-mcp")

# Initialize the elabFTW client
elabftw_client = ElabFTWClient(API_BASE_URL, API_KEY, VERIFY_SSL)


@server.list_prompts()
async def list_prompts() -> list[Prompt]:
    """List available prompts for elabFTW interactions."""
    return [
        Prompt(
            name="elabftw-overview",
            description="Get an overview of available elabFTW operations and how to use this MCP server",
            arguments=[],
        ),
        Prompt(
            name="create-experiment-guide",
            description="Step-by-step guide for creating a new experiment in elabFTW",
            arguments=[
                PromptArgument(
                    name="title",
                    description="The title for your new experiment",
                    required=False,
                ),
            ],
        ),
        Prompt(
            name="manage-resources-guide",
            description="Guide for managing resources/items (reagents, equipment, samples) in elabFTW",
            arguments=[],
        ),
        Prompt(
            name="search-experiments",
            description="Help with searching and filtering experiments",
            arguments=[
                PromptArgument(
                    name="search_term",
                    description="What you're looking for in experiments",
                    required=False,
                ),
            ],
        ),
    ]


@server.get_prompt()
async def get_prompt(
    name: str, arguments: dict[str, str] | None = None
) -> GetPromptResult:
    """Get a specific prompt by name."""

    if name == "elabftw-overview":
        return GetPromptResult(
            description="Overview of elabFTW MCP Server capabilities",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text="""# elabFTW MCP Server Overview

This MCP server provides tools to interact with elabFTW, an electronic lab notebook system.

## Available Operations

### Experiments
- **list_experiments** - List all experiments (with optional search)
- **get_experiment** - Get details of a specific experiment by ID
- **create_experiment** - Create a new experiment (can use templates and categories)
- **update_experiment** - Update an existing experiment's title, body, or metadata
- **delete_experiment** - Delete an experiment
- **set_experiment_status** - Change experiment status (running, completed, etc.)
- **add_tag_to_experiment** / **remove_tag_from_experiment** - Manage experiment tags
- **link_item_to_experiment** - Link a resource/item to an experiment
- **upload_attachment** - Upload a file attachment to an experiment

### Resources/Items (Database Items)
- **list_items** - List all items/resources
- **get_item** - Get details of a specific item
- **create_item** - Create a new resource/item
- **update_item** - Update an existing item
- **delete_item** - Delete an item
- **add_tag_to_item** / **remove_tag_from_item** - Manage item tags
- **upload_attachment_to_item** - Upload a file to an item
- **link_item_to_item** - Link items together

### Templates & Categories
- **list_experiment_templates** - List available experiment templates (for structure)
- **list_experiment_categories** - List experiment categories (for classification)
- **list_items_types** - List available item/resource types

## Quick Start
1. Use `list_experiments` to see existing experiments
2. Use `list_experiment_templates` and `list_experiment_categories` before creating experiments
3. Use `create_experiment` with a template ID and category ID for best results

Please tell me what you'd like to do with elabFTW!""",
                    ),
                ),
            ],
        )

    elif name == "create-experiment-guide":
        title = (
            arguments.get("title", "[Your Experiment Title]")
            if arguments
            else "[Your Experiment Title]"
        )
        return GetPromptResult(
            description="Guide for creating a new experiment",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"""# Creating a New Experiment in elabFTW

I want to create a new experiment with the title: **{title}**

## Steps to follow:

### Step 1: Check available templates
First, list the available experiment templates to see what structures are available:
- Use `list_experiment_templates` tool

### Step 2: Check available categories
Then, list the experiment categories for classification:
- Use `list_experiment_categories` tool

### Step 3: Create the experiment
Create the experiment using:
- Use `create_experiment` tool with:
  - `title`: "{title}"
  - `template`: (optional) ID from step 1
  - `category`: (optional) ID from step 2
  - `body`: (optional) HTML content for the experiment body
  - `tags`: (optional) list of tags like ["tag1", "tag2"]

### Step 4: Add more details (optional)
After creation, you can:
- Use `update_experiment` to modify content
- Use `add_tag_to_experiment` to add more tags
- Use `upload_attachment` to attach files
- Use `link_item_to_experiment` to link resources

Please start by listing the available templates and categories, then create the experiment.""",
                    ),
                ),
            ],
        )

    elif name == "manage-resources-guide":
        return GetPromptResult(
            description="Guide for managing resources/items in elabFTW",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text="""# Managing Resources/Items in elabFTW

Resources (also called "Items" or "Database Items") in elabFTW are used to track:
- Reagents and chemicals
- Equipment and instruments
- Samples and specimens
- Protocols and procedures
- Any other lab resources

## Available Operations

### Viewing Resources
- `list_items` - List all items (can filter by category with `cat` parameter)
- `get_item` - Get detailed information about a specific item
- `list_items_types` - See available item categories/types

### Creating Resources
- `create_item` - Create a new resource
  - Required: `category_id` (get from list_items_types)
  - Optional: `title`, `body` (HTML content), `tags`

### Updating Resources
- `update_item` - Modify an existing item's title, body, or category
- `add_tag_to_item` / `remove_tag_from_item` - Manage tags
- `upload_attachment_to_item` - Attach files (images, documents, etc.)

### Linking Resources
- `link_item_to_experiment` - Link a resource to an experiment
- `link_item_to_item` - Link resources together (e.g., reagent to protocol)

## Common Workflow
1. First, use `list_items_types` to see available resource categories
2. Create items with `create_item` using the appropriate category
3. Link items to experiments as needed

What would you like to do with resources/items?""",
                    ),
                ),
            ],
        )

    elif name == "search-experiments":
        search_term = arguments.get("search_term", "") if arguments else ""
        if search_term:
            return GetPromptResult(
                description=f"Help searching for experiments related to: {search_term}",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=f"""# Searching Experiments in elabFTW

I want to find experiments related to: **{search_term}**

## Search Options

Use the `list_experiments` tool with:
- `search`: "{search_term}" - Search in titles and content
- `limit`: Number of results to return (default: 15)
- `offset`: For pagination

## Example
Search for experiments containing "{search_term}":
```
list_experiments(search="{search_term}", limit=20)
```

## Tips
- The search looks in experiment titles and body content
- Use specific keywords for better results
- You can combine with `get_experiment` to see full details of interesting results

Please search for experiments related to "{search_term}".""",
                        ),
                    ),
                ],
            )
        else:
            return GetPromptResult(
                description="Help with searching experiments",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text="""# Searching Experiments in elabFTW

## How to Search

Use the `list_experiments` tool with these parameters:
- `search`: Text to search for in titles and content
- `limit`: Maximum number of results (default: 15, max: 100)
- `offset`: Skip this many results (for pagination)

## Examples

1. **Basic search**:
   `list_experiments(search="PCR")`

2. **Get more results**:
   `list_experiments(search="protein", limit=50)`

3. **Pagination** (get next page):
   `list_experiments(search="analysis", limit=15, offset=15)`

## After Finding Experiments

Once you find an experiment of interest:
- Use `get_experiment(experiment_id=ID)` for full details
- The full details include body content, tags, attachments, and linked items

What would you like to search for?""",
                        ),
                    ),
                ],
            )

    else:
        raise ValueError(f"Unknown prompt: {name}")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools for elabFTW interactions."""
    return [
        Tool(
            name="lab_prompt_elabftw",
            description="Return the integrated eLabFTW lab prompt content for LLM guidance. This provides the system prompt that defines how the AI assistant should behave when working with eLabFTW data.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="list_experiment_templates",
            description="List available experiment TEMPLATES from elabFTW. Templates define the initial structure/content of experiments. Use the returned 'id' as the 'template' parameter when creating experiments. Note: This is DIFFERENT from categories - use list_experiment_categories for classification categories.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of templates to return (default: 15)",
                        "default": 15,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of templates to skip for pagination (default: 0)",
                        "default": 0,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="list_experiment_categories",
            description="List available experiment CATEGORIES from elabFTW. Categories are used to classify/organize experiments (e.g., 'PCR', 'Western Blot'). Use the returned 'id' as the 'category' parameter when creating or updating experiments. Note: This is DIFFERENT from templates.",
            inputSchema={
                "type": "object",
                "properties": {
                    "team_id": {
                        "type": "integer",
                        "description": "Team ID to get categories for (default: 1)",
                        "default": 1,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="delete_experiment",
            description="Delete an experiment (soft-delete). The experiment will be marked as deleted but may be recoverable by an administrator. Use with caution!",
            inputSchema={
                "type": "object",
                "properties": {
                    "experiment_id": {
                        "type": "integer",
                        "description": "The unique ID of the experiment to delete",
                    },
                },
                "required": ["experiment_id"],
            },
        ),
        Tool(
            name="list_experiments",
            description="List experiments from elabFTW. Returns a list of experiments with their basic info (ID, title, date, etc.). Supports pagination, search, and filtering by owner.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of experiments to return (default: 15, max: 100)",
                        "default": 15,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of experiments to skip for pagination (default: 0)",
                        "default": 0,
                    },
                    "search": {
                        "type": "string",
                        "description": "Optional search query to filter experiments by title or content",
                    },
                    "owner": {
                        "type": "string",
                        "description": "Optional user ID(s) to filter experiments by owner. Can be a single ID like '2' or multiple comma-separated IDs like '2,3'",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_experiment",
            description="Get detailed information about a specific experiment by its ID. Returns full experiment data including title, body, metadata, tags, etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "experiment_id": {
                        "type": "integer",
                        "description": "The unique ID of the experiment to retrieve",
                    },
                },
                "required": ["experiment_id"],
            },
        ),
        Tool(
            name="create_experiment",
            description="Create a new experiment in elabFTW. The experiment will be created with the given title and optional body content. HTML formatting is supported in the body.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Title of the new experiment",
                    },
                    "body": {
                        "type": "string",
                        "description": "Body/content of the experiment. HTML formatting is supported.",
                        "default": "",
                    },
                    "template": {
                        "type": "integer",
                        "description": "Template ID to use for the experiment structure (-1 for empty body, 0 for team template, or specific template ID). Use list_experiment_templates to see available templates. Required by some elabFTW instances. NOTE: This is different from 'category'!",
                    },
                    "category": {
                        "type": "integer",
                        "description": "Category ID to classify the experiment (e.g., PCR, Western Blot). Use list_experiment_categories to find valid category IDs. NOTE: This is different from 'template'!",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of tags to add to the experiment",
                    },
                },
                "required": ["title"],
            },
        ),
        Tool(
            name="update_experiment",
            description="Update an existing experiment. You can update the title, body, or category. At least one field must be provided.",
            inputSchema={
                "type": "object",
                "properties": {
                    "experiment_id": {
                        "type": "integer",
                        "description": "The unique ID of the experiment to update",
                    },
                    "title": {
                        "type": "string",
                        "description": "New title for the experiment",
                    },
                    "body": {
                        "type": "string",
                        "description": "New body/content for the experiment. HTML formatting is supported.",
                    },
                    "category": {
                        "type": "integer",
                        "description": "New category ID for the experiment. Use list_experiment_categories to find valid IDs.",
                    },
                    "status": {
                        "type": "integer",
                        "description": "New status ID for the experiment.",
                    },
                },
                "required": ["experiment_id"],
            },
        ),
        Tool(
            name="add_tag",
            description="Add a tag to an existing experiment.",
            inputSchema={
                "type": "object",
                "properties": {
                    "experiment_id": {
                        "type": "integer",
                        "description": "The unique ID of the experiment",
                    },
                    "tag": {
                        "type": "string",
                        "description": "The tag to add to the experiment",
                    },
                },
                "required": ["experiment_id", "tag"],
            },
        ),
        Tool(
            name="remove_tag",
            description="Remove a tag from an existing experiment.",
            inputSchema={
                "type": "object",
                "properties": {
                    "experiment_id": {
                        "type": "integer",
                        "description": "The unique ID of the experiment",
                    },
                    "tag_id": {
                        "type": "integer",
                        "description": "The ID of the tag to remove (can be found in experiment details)",
                    },
                },
                "required": ["experiment_id", "tag_id"],
            },
        ),
        Tool(
            name="set_experiment_status",
            description="Set the status of an experiment (e.g., Running, Success, Need to be redone). Status IDs depend on your elabFTW configuration.",
            inputSchema={
                "type": "object",
                "properties": {
                    "experiment_id": {
                        "type": "integer",
                        "description": "The unique ID of the experiment",
                    },
                    "status_id": {
                        "type": "integer",
                        "description": "The status ID to set (depends on your elabFTW configuration)",
                    },
                },
                "required": ["experiment_id", "status_id"],
            },
        ),
        Tool(
            name="link_item",
            description="Link another experiment or database item to an experiment. Useful for creating relationships between entries.",
            inputSchema={
                "type": "object",
                "properties": {
                    "experiment_id": {
                        "type": "integer",
                        "description": "The unique ID of the experiment to add the link to",
                    },
                    "link_id": {
                        "type": "integer",
                        "description": "The ID of the experiment or item to link",
                    },
                    "link_type": {
                        "type": "string",
                        "enum": ["experiments", "items"],
                        "description": "Type of link: 'experiments' to link another experiment, 'items' to link a database item",
                        "default": "experiments",
                    },
                },
                "required": ["experiment_id", "link_id"],
            },
        ),
        Tool(
            name="upload_attachment",
            description="Upload a file attachment to an experiment. The file must exist on the local filesystem.",
            inputSchema={
                "type": "object",
                "properties": {
                    "experiment_id": {
                        "type": "integer",
                        "description": "The unique ID of the experiment",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "The full path to the file to upload",
                    },
                    "comment": {
                        "type": "string",
                        "description": "Optional comment to attach to the uploaded file",
                    },
                },
                "required": ["experiment_id", "file_path"],
            },
        ),
        # ==================== ITEMS/RESOURCES TOOLS ====================
        Tool(
            name="list_items",
            description="List database items (resources) from elabFTW. Items can be equipment, chemicals, cell lines, etc. Returns list with basic info. Supports filtering by owner.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of items to return (default: 15, max: 100)",
                        "default": 15,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of items to skip for pagination (default: 0)",
                        "default": 0,
                    },
                    "search": {
                        "type": "string",
                        "description": "Optional search query to filter items by title or content",
                    },
                    "category": {
                        "type": "integer",
                        "description": "Optional category ID to filter items by type/category",
                    },
                    "owner": {
                        "type": "string",
                        "description": "Optional user ID(s) to filter items by owner. Can be a single ID like '2' or multiple comma-separated IDs like '2,3'",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_item",
            description="Get detailed information about a specific database item (resource) by its ID. Returns full item data including title, body, metadata, tags, linked items, etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "integer",
                        "description": "The unique ID of the item to retrieve",
                    },
                },
                "required": ["item_id"],
            },
        ),
        Tool(
            name="create_item",
            description="Create a new database item (resource) in elabFTW. Use this to add chemicals, equipment, setups, reagents, etc. to your lab inventory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "integer",
                        "description": "Category/type ID for the item (REQUIRED). Use list_items_types to find valid IDs (e.g., Chemicals, Equipment, Setups).",
                    },
                    "title": {
                        "type": "string",
                        "description": "Title of the new item (e.g., chemical name, equipment name)",
                    },
                    "body": {
                        "type": "string",
                        "description": "Body/content of the item. HTML formatting is supported. Can include specifications, notes, safety info, etc.",
                        "default": "",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of tags to add to the item",
                    },
                },
                "required": ["category"],
            },
        ),
        Tool(
            name="update_item",
            description="Update an existing database item (resource). You can update the title, body, category, or rating.",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "integer",
                        "description": "The unique ID of the item to update",
                    },
                    "title": {
                        "type": "string",
                        "description": "New title for the item",
                    },
                    "body": {
                        "type": "string",
                        "description": "New body/content for the item. HTML formatting is supported.",
                    },
                    "category": {
                        "type": "integer",
                        "description": "New category/type ID for the item. Use list_items_types to find valid IDs.",
                    },
                    "rating": {
                        "type": "integer",
                        "description": "Rating for the item (0-5). Useful for rating reagent quality, equipment reliability, etc.",
                    },
                },
                "required": ["item_id"],
            },
        ),
        Tool(
            name="delete_item",
            description="Delete a database item (soft-delete). The item will be marked as deleted but may be recoverable by an administrator. Use with caution!",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "integer",
                        "description": "The unique ID of the item to delete",
                    },
                },
                "required": ["item_id"],
            },
        ),
        Tool(
            name="list_items_types",
            description="List available item types/categories for database items. Item types define what kinds of resources you can store (e.g., Chemicals, Equipment, Plasmids, Cell Lines, Setups). Use the returned 'id' as the 'category' parameter when creating or filtering items.",
            inputSchema={
                "type": "object",
                "properties": {
                    "team_id": {
                        "type": "integer",
                        "description": "Team ID to get item types for (default: 1)",
                        "default": 1,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="add_item_tag",
            description="Add a tag to an existing database item.",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "integer",
                        "description": "The unique ID of the item",
                    },
                    "tag": {
                        "type": "string",
                        "description": "The tag to add to the item",
                    },
                },
                "required": ["item_id", "tag"],
            },
        ),
        Tool(
            name="remove_item_tag",
            description="Remove a tag from an existing database item.",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "integer",
                        "description": "The unique ID of the item",
                    },
                    "tag_id": {
                        "type": "integer",
                        "description": "The ID of the tag to remove (can be found in item details)",
                    },
                },
                "required": ["item_id", "tag_id"],
            },
        ),
        Tool(
            name="upload_item_attachment",
            description="Upload a file attachment to a database item. Useful for attaching datasheets, manuals, certificates, etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "integer",
                        "description": "The unique ID of the item",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "The full path to the file to upload",
                    },
                    "comment": {
                        "type": "string",
                        "description": "Optional comment to attach to the uploaded file",
                    },
                },
                "required": ["item_id", "file_path"],
            },
        ),
        Tool(
            name="link_to_item",
            description="Link another item or experiment to a database item. Useful for connecting related resources (e.g., linking a chemical to the equipment it's used with).",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "integer",
                        "description": "The unique ID of the item to add the link to",
                    },
                    "link_id": {
                        "type": "integer",
                        "description": "The ID of the item or experiment to link",
                    },
                    "link_type": {
                        "type": "string",
                        "enum": ["items", "experiments"],
                        "description": "Type of link: 'items' to link another database item, 'experiments' to link an experiment",
                        "default": "items",
                    },
                },
                "required": ["item_id", "link_id"],
            },
        ),
        # ==================== BOOKING/EVENTS TOOLS ====================
        Tool(
            name="list_bookings",
            description="List booking events/reservations for equipment and setups. Shows scheduled use of bookable items. Returns event details including item, user, time, and duration.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of bookings to return (default: 50)",
                        "default": 50,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of bookings to skip for pagination (default: 0)",
                        "default": 0,
                    },
                    "start": {
                        "type": "string",
                        "description": "Filter bookings starting after this datetime (ISO format: 2024-01-15T09:00:00)",
                    },
                    "end": {
                        "type": "string",
                        "description": "Filter bookings ending before this datetime (ISO format: 2024-01-15T17:00:00)",
                    },
                    "item_id": {
                        "type": "integer",
                        "description": "Filter bookings for a specific item/equipment",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_booking",
            description="Get detailed information about a specific booking by its ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "integer",
                        "description": "The unique ID of the booking/event",
                    },
                },
                "required": ["event_id"],
            },
        ),
        Tool(
            name="create_booking",
            description="Book/reserve an item (equipment, setup, etc.) for a specific time period. The item must have is_bookable=1. Use list_items to find bookable items.",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "integer",
                        "description": "The ID of the item to book (must be bookable)",
                    },
                    "start": {
                        "type": "string",
                        "description": "Start datetime in ISO 8601 format (e.g., '2024-01-15T09:00:00' or '2024-01-15T09:00:00+01:00')",
                    },
                    "end": {
                        "type": "string",
                        "description": "End datetime in ISO 8601 format (e.g., '2024-01-15T17:00:00' or '2024-01-15T17:00:00+01:00')",
                    },
                    "title": {
                        "type": "string",
                        "description": "Optional title/description for the booking (e.g., 'Sample preparation experiment')",
                    },
                },
                "required": ["item_id", "start", "end"],
            },
        ),
        Tool(
            name="update_booking",
            description="Update an existing booking (change time or title). Only the booking creator or admins can modify bookings. Subject to cancellation policies.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "integer",
                        "description": "The ID of the booking to update",
                    },
                    "start": {
                        "type": "string",
                        "description": "New start datetime in ISO 8601 format",
                    },
                    "end": {
                        "type": "string",
                        "description": "New end datetime in ISO 8601 format",
                    },
                    "title": {
                        "type": "string",
                        "description": "New title for the booking",
                    },
                },
                "required": ["event_id"],
            },
        ),
        Tool(
            name="cancel_booking",
            description="Cancel/delete a booking. Permissions and cancellation policies (book_is_cancellable, book_cancel_minutes) may apply. Only the booking creator or admins can cancel.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "integer",
                        "description": "The ID of the booking to cancel",
                    },
                },
                "required": ["event_id"],
            },
        ),
        Tool(
            name="get_bookable_items",
            description="List all items that can be booked (is_bookable=1) with their booking settings like max duration, overlap rules, and cancellation policies. Use this to find what equipment/setups are available for booking.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of items to return (default: 50)",
                        "default": 50,
                    },
                },
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls for elabFTW operations."""

    # Return the lab prompt content when requested (no API key needed)
    if name == "lab_prompt_elabftw":
        return [
            TextContent(
                type="text",
                text=LAB_PROMPT.strip(),
            )
        ]

    if not API_KEY:
        return [
            TextContent(
                type="text",
                text="Error: ELABFTW_API_KEY environment variable is not set. Please configure your API key.",
            )
        ]

    try:
        if name == "list_experiment_templates":
            limit = arguments.get("limit", 15)
            offset = arguments.get("offset", 0)

            result = elabftw_client.list_experiment_templates(
                limit=min(limit, 100),
                offset=offset,
            )

            if isinstance(result, list):
                templates_info = []
                for tpl in result:
                    tpl_info = {
                        "id": tpl.get("id"),
                        "title": tpl.get("title"),
                        "created_at": tpl.get("created_at"),
                        "modified_at": tpl.get("modified_at"),
                    }
                    templates_info.append(tpl_info)

                return [
                    TextContent(
                        type="text",
                        text=f"Found {len(templates_info)} experiment TEMPLATES:\n\n{json.dumps(templates_info, indent=2)}\n\nUse the 'id' as the 'template' parameter when creating a new experiment.\n\nNOTE: Templates define experiment structure. For classification categories, use list_experiment_categories instead.",
                    )
                ]
            else:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(result, indent=2),
                    )
                ]

        elif name == "list_experiment_categories":
            team_id = arguments.get("team_id", 1)

            result = elabftw_client.list_experiment_categories(team_id=team_id)

            if isinstance(result, list):
                categories_info = []
                for cat in result:
                    cat_info = {
                        "id": cat.get("id"),
                        "title": cat.get("title"),
                        "color": cat.get("color"),
                        "is_default": cat.get("is_default"),
                    }
                    categories_info.append(cat_info)

                return [
                    TextContent(
                        type="text",
                        text=f"Found {len(categories_info)} experiment CATEGORIES:\n\n{json.dumps(categories_info, indent=2)}\n\nUse the 'id' as the 'category' parameter when creating or updating experiments.\n\nNOTE: Categories classify experiments. For experiment structure/templates, use list_experiment_templates instead.",
                    )
                ]
            else:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(result, indent=2),
                    )
                ]

        elif name == "delete_experiment":
            experiment_id = arguments["experiment_id"]

            result = elabftw_client.delete_experiment(experiment_id)

            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        elif name == "list_experiments":
            limit = arguments.get("limit", 15)
            offset = arguments.get("offset", 0)
            search = arguments.get("search")
            owner = arguments.get("owner")

            result = elabftw_client.list_experiments(
                limit=min(limit, 100),  # Cap at 100
                offset=offset,
                search=search,
                owner=owner,
            )

            # Format the output nicely
            if isinstance(result, list):
                experiments_info = []
                for exp in result:
                    exp_info = {
                        "id": exp.get("id"),
                        "title": exp.get("title"),
                        "created_at": exp.get("created_at"),
                        "modified_at": exp.get("modified_at"),
                        "category": exp.get("category"),
                        "status": exp.get("status"),
                        "owner": exp.get("userid"),
                        "owner_name": exp.get("fullname"),
                    }
                    experiments_info.append(exp_info)

                return [
                    TextContent(
                        type="text",
                        text=f"Found {len(experiments_info)} experiments:\n\n{json.dumps(experiments_info, indent=2)}",
                    )
                ]
            else:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(result, indent=2),
                    )
                ]

        elif name == "get_experiment":
            experiment_id = arguments["experiment_id"]
            result = elabftw_client.get_experiment(experiment_id)

            return [
                TextContent(
                    type="text",
                    text=f"Experiment {experiment_id}:\n\n{json.dumps(result, indent=2)}",
                )
            ]

        elif name == "create_experiment":
            title = arguments["title"]
            body = arguments.get("body", "")
            template = arguments.get("template")
            category = arguments.get("category")
            tags = arguments.get("tags")

            result = elabftw_client.create_experiment(
                title=title,
                body=body,
                template=template,
                category=category,
                tags=tags,
            )

            return [
                TextContent(
                    type="text",
                    text=f"Successfully created experiment:\n\n{json.dumps(result, indent=2)}",
                )
            ]

        elif name == "update_experiment":
            experiment_id = arguments["experiment_id"]
            title = arguments.get("title")
            body = arguments.get("body")
            category = arguments.get("category")
            status = arguments.get("status")

            result = elabftw_client.update_experiment(
                experiment_id=experiment_id,
                title=title,
                body=body,
                category=category,
                status=status,
            )

            return [
                TextContent(
                    type="text",
                    text=f"Successfully updated experiment {experiment_id}:\n\n{json.dumps(result, indent=2)}",
                )
            ]

        elif name == "add_tag":
            experiment_id = arguments["experiment_id"]
            tag = arguments["tag"]

            result = elabftw_client.add_tag_to_experiment(experiment_id, tag)

            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        elif name == "remove_tag":
            experiment_id = arguments["experiment_id"]
            tag_id = arguments["tag_id"]

            result = elabftw_client.remove_tag_from_experiment(experiment_id, tag_id)

            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        elif name == "set_experiment_status":
            experiment_id = arguments["experiment_id"]
            status_id = arguments["status_id"]

            result = elabftw_client.set_experiment_status(experiment_id, status_id)

            return [
                TextContent(
                    type="text",
                    text=f"Successfully updated status for experiment {experiment_id}:\n\n{json.dumps(result, indent=2)}",
                )
            ]

        elif name == "link_item":
            experiment_id = arguments["experiment_id"]
            link_id = arguments["link_id"]
            link_type = arguments.get("link_type", "experiments")

            result = elabftw_client.link_item_to_experiment(
                experiment_id, link_id, link_type
            )

            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        elif name == "upload_attachment":
            experiment_id = arguments["experiment_id"]
            file_path = arguments["file_path"]
            comment = arguments.get("comment")

            result = elabftw_client.upload_attachment(experiment_id, file_path, comment)

            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        # ==================== ITEMS/RESOURCES HANDLERS ====================

        elif name == "list_items":
            limit = arguments.get("limit", 15)
            offset = arguments.get("offset", 0)
            search = arguments.get("search")
            category = arguments.get("category")
            owner = arguments.get("owner")

            result = elabftw_client.list_items(
                limit=min(limit, 100),
                offset=offset,
                search=search,
                category=category,
                owner=owner,
            )

            if isinstance(result, list):
                items_info = []
                for item in result:
                    item_info = {
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "category": item.get("category"),
                        "category_title": item.get("category_title"),
                        "created_at": item.get("created_at"),
                        "modified_at": item.get("modified_at"),
                        "rating": item.get("rating"),
                        "owner": item.get("userid"),
                        "owner_name": item.get("fullname"),
                    }
                    items_info.append(item_info)

                return [
                    TextContent(
                        type="text",
                        text=f"Found {len(items_info)} items (resources):\n\n{json.dumps(items_info, indent=2)}",
                    )
                ]
            else:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(result, indent=2),
                    )
                ]

        elif name == "get_item":
            item_id = arguments["item_id"]
            result = elabftw_client.get_item(item_id)

            return [
                TextContent(
                    type="text",
                    text=f"Item {item_id}:\n\n{json.dumps(result, indent=2)}",
                )
            ]

        elif name == "create_item":
            category = arguments["category"]
            title = arguments.get("title")
            body = arguments.get("body", "")
            tags = arguments.get("tags")

            result = elabftw_client.create_item(
                category=category,
                title=title,
                body=body,
                tags=tags,
            )

            return [
                TextContent(
                    type="text",
                    text=f"Successfully created item:\n\n{json.dumps(result, indent=2)}",
                )
            ]

        elif name == "update_item":
            item_id = arguments["item_id"]
            title = arguments.get("title")
            body = arguments.get("body")
            category = arguments.get("category")
            rating = arguments.get("rating")

            result = elabftw_client.update_item(
                item_id=item_id,
                title=title,
                body=body,
                category=category,
                rating=rating,
            )

            return [
                TextContent(
                    type="text",
                    text=f"Successfully updated item {item_id}:\n\n{json.dumps(result, indent=2)}",
                )
            ]

        elif name == "delete_item":
            item_id = arguments["item_id"]

            result = elabftw_client.delete_item(item_id)

            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        elif name == "list_items_types":
            team_id = arguments.get("team_id", 1)

            result = elabftw_client.list_items_types(team_id=team_id)

            if isinstance(result, list):
                types_info = []
                for item_type in result:
                    type_info = {
                        "id": item_type.get("id"),
                        "title": item_type.get("title"),
                        "color": item_type.get("color"),
                        "body": item_type.get("body", "")[:100] + "..."
                        if len(item_type.get("body", "")) > 100
                        else item_type.get("body", ""),
                    }
                    types_info.append(type_info)

                return [
                    TextContent(
                        type="text",
                        text=f"Found {len(types_info)} item types/categories:\n\n{json.dumps(types_info, indent=2)}\n\nUse the 'id' as the 'category' parameter when creating items or filtering the item list.",
                    )
                ]
            else:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(result, indent=2),
                    )
                ]

        elif name == "add_item_tag":
            item_id = arguments["item_id"]
            tag = arguments["tag"]

            result = elabftw_client.add_tag_to_item(item_id, tag)

            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        elif name == "remove_item_tag":
            item_id = arguments["item_id"]
            tag_id = arguments["tag_id"]

            result = elabftw_client.remove_tag_from_item(item_id, tag_id)

            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        elif name == "upload_item_attachment":
            item_id = arguments["item_id"]
            file_path = arguments["file_path"]
            comment = arguments.get("comment")

            result = elabftw_client.upload_attachment_to_item(
                item_id, file_path, comment
            )

            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        elif name == "link_to_item":
            item_id = arguments["item_id"]
            link_id = arguments["link_id"]
            link_type = arguments.get("link_type", "items")

            result = elabftw_client.link_item_to_item(item_id, link_id, link_type)

            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        # ==================== BOOKING/EVENTS HANDLERS ====================

        elif name == "list_bookings":
            limit = arguments.get("limit", 50)
            offset = arguments.get("offset", 0)
            start = arguments.get("start")
            end = arguments.get("end")
            item_id = arguments.get("item_id")

            result = elabftw_client.list_events(
                limit=limit,
                offset=offset,
                start=start,
                end=end,
                item_id=item_id,
            )

            if isinstance(result, list):
                bookings_info = []
                for event in result:
                    booking_info = {
                        "id": event.get("id"),
                        "title": event.get("title"),
                        "item_id": event.get("items_id"),
                        "item_title": event.get("item_title"),
                        "start": event.get("start"),
                        "end": event.get("end"),
                        "user": event.get("fullname"),
                        "user_id": event.get("userid"),
                        "duration_minutes": event.get("event_duration_minutes"),
                        "is_cancellable": event.get("book_is_cancellable"),
                    }
                    bookings_info.append(booking_info)

                return [
                    TextContent(
                        type="text",
                        text=f"Found {len(bookings_info)} bookings:\n\n{json.dumps(bookings_info, indent=2)}",
                    )
                ]
            else:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(result, indent=2),
                    )
                ]

        elif name == "get_booking":
            event_id = arguments["event_id"]
            result = elabftw_client.get_event(event_id)

            return [
                TextContent(
                    type="text",
                    text=f"Booking {event_id}:\n\n{json.dumps(result, indent=2)}",
                )
            ]

        elif name == "create_booking":
            item_id = arguments["item_id"]
            start = arguments["start"]
            end = arguments["end"]
            title = arguments.get("title")

            result = elabftw_client.create_booking(
                item_id=item_id,
                start=start,
                end=end,
                title=title,
            )

            return [
                TextContent(
                    type="text",
                    text=f"Successfully created booking:\n\n{json.dumps(result, indent=2)}",
                )
            ]

        elif name == "update_booking":
            event_id = arguments["event_id"]
            start = arguments.get("start")
            end = arguments.get("end")
            title = arguments.get("title")

            result = elabftw_client.update_booking(
                event_id=event_id,
                start=start,
                end=end,
                title=title,
            )

            return [
                TextContent(
                    type="text",
                    text=f"Successfully updated booking:\n\n{json.dumps(result, indent=2)}",
                )
            ]

        elif name == "cancel_booking":
            event_id = arguments["event_id"]

            result = elabftw_client.delete_booking(event_id)

            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        elif name == "get_bookable_items":
            limit = arguments.get("limit", 50)

            # Get all items and filter for bookable ones
            all_items = elabftw_client.list_items(limit=limit)

            bookable_items = []
            for item in all_items:
                if item.get("is_bookable") == 1:
                    # Get full details to show booking settings
                    full_item = elabftw_client.get_item(item["id"])
                    bookable_info = {
                        "id": full_item.get("id"),
                        "title": full_item.get("title"),
                        "category": full_item.get("category_title"),
                        "max_duration_minutes": full_item.get("book_max_minutes")
                        or "unlimited",
                        "max_concurrent_slots": full_item.get("book_max_slots")
                        or "unlimited",
                        "can_overlap": bool(full_item.get("book_can_overlap")),
                        "is_cancellable": bool(full_item.get("book_is_cancellable")),
                        "cancel_advance_minutes": full_item.get("book_cancel_minutes"),
                        "can_book_in_past": bool(
                            full_item.get("book_users_can_in_past")
                        ),
                    }
                    bookable_items.append(bookable_info)

            return [
                TextContent(
                    type="text",
                    text=f"Found {len(bookable_items)} bookable items:\n\n{json.dumps(bookable_items, indent=2)}",
                )
            ]

        else:
            return [
                TextContent(
                    type="text",
                    text=f"Unknown tool: {name}",
                )
            ]

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP Error {e.response.status_code}: {e.response.text}"
        logger.error(error_msg)
        return [
            TextContent(
                type="text",
                text=f"Error communicating with elabFTW: {error_msg}",
            )
        ]
    except httpx.RequestError as e:
        error_msg = f"Request Error: {str(e)}"
        logger.error(error_msg)
        return [
            TextContent(
                type="text",
                text=f"Error connecting to elabFTW server: {error_msg}\n\nPlease check that:\n1. The ELABFTW_API_URL is correct\n2. The server is reachable\n3. SSL certificates are properly configured (or set ELABFTW_VERIFY_SSL=false for self-signed certs)",
            )
        ]
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return [
            TextContent(
                type="text",
                text=f"An unexpected error occurred: {error_msg}",
            )
        ]


async def main():
    """Run the MCP server."""
    logger.info("Starting elabFTW MCP Server...")
    logger.info(f"API URL: {API_BASE_URL}")
    logger.info(f"SSL Verification: {VERIFY_SSL}")

    if not API_KEY:
        logger.warning(
            "ELABFTW_API_KEY is not set! Please set it before using the server."
        )

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

"""
Booking functionality implementation for elabFTW MCP Server

This file contains the complete implementation for adding booking/scheduling
features to the MCP server. Copy these sections into elabftw_mcp_server.py:

1. Add the methods to the ElabFTWClient class
2. Add the tools to list_tools()
3. Add the handlers to call_tool()

Based on API exploration showing:
- /events endpoint exists and works
- Items have booking-related fields (is_bookable, book_max_minutes, etc.)
- Events have structure: id, title, start, end, item_id, user info, etc.
"""

# ============================================================================
# SECTION 1: Add these methods to the ElabFTWClient class
# ============================================================================


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


# ============================================================================
# SECTION 2: Add these tools to the list_tools() function
# ============================================================================

BOOKING_TOOLS = [
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


# ============================================================================
# SECTION 3: Add these handlers to the call_tool() function
# ============================================================================

BOOKING_HANDLERS = """
    # ==================== BOOKING HANDLERS ====================

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
                    "max_duration_minutes": full_item.get("book_max_minutes") or "unlimited",
                    "max_concurrent_slots": full_item.get("book_max_slots") or "unlimited",
                    "can_overlap": bool(full_item.get("book_can_overlap")),
                    "is_cancellable": bool(full_item.get("book_is_cancellable")),
                    "cancel_advance_minutes": full_item.get("book_cancel_minutes"),
                    "can_book_in_past": bool(full_item.get("book_users_can_in_past")),
                }
                bookable_items.append(bookable_info)

        return [
            TextContent(
                type="text",
                text=f"Found {len(bookable_items)} bookable items:\n\n{json.dumps(bookable_items, indent=2)}",
            )
        ]
"""

# ============================================================================
# INTEGRATION INSTRUCTIONS
# ============================================================================

"""
To integrate this into elabftw_mcp_server.py:

1. Add the methods from SECTION 1 to the ElabFTWClient class
   (after the existing methods like delete_item, link_item_to_item, etc.)

2. Add the tools from SECTION 2 (BOOKING_TOOLS list) to the return statement
   in the list_tools() function (before the closing bracket)

3. Add the handlers from SECTION 3 to the call_tool() function
   (before the final else clause that returns "Unknown tool")

4. Test the implementation:
   python explore_api.py  # Verify /events endpoint still works
   npx @modelcontextprotocol/inspector python elabftw_mcp_server.py

5. Example usage:
   - "List all bookings for the next week"
   - "Show me bookable equipment"
   - "Book item 1234 from 2024-01-15T09:00:00 to 2024-01-15T17:00:00"
   - "Cancel booking 42"
"""

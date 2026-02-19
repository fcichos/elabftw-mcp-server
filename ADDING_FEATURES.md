# Adding New Features to elabFTW MCP Server

This guide shows how to discover and implement new features using the elabFTW API.

## Discovery Process

### 1. Explore the API

Use the included `explore_api.py` script to discover endpoints:

```bash
python explore_api.py
```

This script will:
- Test known endpoints to verify connectivity
- Try potential endpoint names related to your feature
- Examine data structures for relevant fields
- Report what exists and what doesn't

### 2. Check the Swagger UI

Visit your elabFTW instance's API documentation:
```
https://your-server/api/v2/
```

This provides the official API specification with all endpoints, parameters, and schemas.

### 3. Study the elabFTW Source Code

For complex features, check the source:
```
https://github.com/elabftw/elabftw
```

Look in `src/controllers/ApiController.php` and related API files.

## Example: Adding Booking Functionality

### What We Discovered

From `explore_api.py`, we found:

1. **`/events` endpoint** - Returns booking events (GET)
   - Fields: `id`, `title`, `start`, `end`, `userid`, `fullname`, `items_id`, `book_is_cancellable`, etc.
   - Returns 213 events in the test instance

2. **Item booking fields** - Items have built-in booking properties:
   - `is_bookable` (0 or 1) - Whether the item can be booked
   - `book_max_minutes` - Maximum booking duration
   - `book_max_slots` - Maximum concurrent bookings
   - `book_can_overlap` - Whether bookings can overlap
   - `book_is_cancellable` - Whether users can cancel bookings
   - `book_cancel_minutes` - How far in advance cancellation is allowed
   - `book_users_can_in_past` - Whether past bookings are allowed
   - `canbook` - Permissions object for who can book

3. **Expected endpoints** (based on RESTful patterns):
   - `GET /events` - List all bookings/events ✓ (confirmed working)
   - `GET /events/{id}` - Get specific event (likely exists)
   - `POST /events` - Create a new booking (likely exists)
   - `PATCH /events/{id}` - Update a booking (likely exists)
   - `DELETE /events/{id}` - Cancel/delete a booking (likely exists)
   - `GET /items/{id}` - Already implemented, returns booking settings

### Implementation Steps

#### Step 1: Add methods to ElabFTWClient class

```python
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
        limit: Maximum number of events to return
        offset: Number of events to skip (pagination)
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
        event_id: The ID of the event
    
    Returns:
        Event details
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
        Created booking details
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
        
        # Get location header for the new event ID
        location = response.headers.get("location", "")
        if location:
            event_id = int(location.split("/")[-1])
            return self.get_event(event_id)
        
        return {"status": "success", "message": "Booking created"}

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
        start: New start datetime
        end: New end datetime
        title: New title
    
    Returns:
        Updated booking details
    """
    data = {}
    if start:
        data["start"] = start
    if end:
        data["end"] = end
    if title:
        data["title"] = title
    
    if not data:
        raise ValueError("At least one field must be provided")
    
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
```

#### Step 2: Add tool definitions in list_tools()

```python
Tool(
    name="list_bookings",
    description="List booking events/reservations for equipment and setups. Shows scheduled use of bookable items.",
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
                "description": "Number of bookings to skip for pagination",
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
    name="create_booking",
    description="Book/reserve an item (equipment, setup, etc.) for a specific time period. The item must have is_bookable=1.",
    inputSchema={
        "type": "object",
        "properties": {
            "item_id": {
                "type": "integer",
                "description": "The ID of the item to book (must be bookable)",
            },
            "start": {
                "type": "string",
                "description": "Start datetime in ISO format (e.g., '2024-01-15T09:00:00')",
            },
            "end": {
                "type": "string",
                "description": "End datetime in ISO format (e.g., '2024-01-15T17:00:00')",
            },
            "title": {
                "type": "string",
                "description": "Optional title/description for the booking",
            },
        },
        "required": ["item_id", "start", "end"],
    },
),
Tool(
    name="update_booking",
    description="Update an existing booking (change time or title). Only the booking creator or admins can do this.",
    inputSchema={
        "type": "object",
        "properties": {
            "event_id": {
                "type": "integer",
                "description": "The ID of the booking to update",
            },
            "start": {
                "type": "string",
                "description": "New start datetime in ISO format",
            },
            "end": {
                "type": "string",
                "description": "New end datetime in ISO format",
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
    description="Cancel/delete a booking. Permissions and cancellation policies (book_is_cancellable, book_cancel_minutes) may apply.",
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
    description="List all items that can be booked (is_bookable=1) with their booking settings.",
    inputSchema={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of items to return",
                "default": 50,
            },
        },
        "required": [],
    },
),
```

#### Step 3: Add handlers in call_tool()

```python
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
                "max_duration_minutes": full_item.get("book_max_minutes"),
                "max_concurrent_slots": full_item.get("book_max_slots"),
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
```

#### Step 4: Test the implementation

```python
# Test script
python explore_api.py  # Verify /events endpoint works

# Then test via MCP inspector
npx @modelcontextprotocol/inspector python elabftw_mcp_server.py

# Try the new tools:
# - list_bookings
# - get_bookable_items
# - create_booking (with item_id, start, end)
# - cancel_booking
```

## General Pattern for Adding Features

1. **Discover** - Use `explore_api.py` or Swagger UI
2. **Implement Client Method** - Add to `ElabFTWClient` class
3. **Define Tool** - Add to `list_tools()`
4. **Add Handler** - Add case in `call_tool()`
5. **Test** - Use MCP inspector or Claude Desktop
6. **Document** - Update README.md with new capabilities

## Tips

- **Start simple** - Implement GET endpoints first (read-only)
- **Check permissions** - Not all users can access all endpoints
- **Handle errors** - elabFTW returns helpful error messages
- **Use types** - Python type hints help catch issues early
- **Format output** - Make tool responses user-friendly
- **Test thoroughly** - Use a test elabFTW instance, not production

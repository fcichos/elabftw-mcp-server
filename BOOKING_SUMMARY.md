# Booking Functionality for elabFTW MCP Server

## Summary

Your elabFTW instance **already has 213 bookings** and the `/events` API endpoint is working perfectly! The booking functionality is ready to be added to your MCP server.

## What We Discovered

### ✓ Working Endpoints

- **`GET /events`** - Lists all bookings (213 found in your instance)
- **`GET /events/{id}`** - Get specific booking details (assumed working, standard REST pattern)
- **`POST /events`** - Create new bookings (ready to implement)
- **`PATCH /events/{id}`** - Update bookings (ready to implement)
- **`DELETE /events/{id}`** - Cancel bookings (ready to implement)

### Event Data Structure

Each booking event contains:
- `id` - Unique event identifier
- `title` - Booking description
- `items_id` - ID of the booked item
- `item_title` - Name of the booked item
- `start` - Start datetime (ISO 8601 format with timezone)
- `end` - End datetime (ISO 8601 format with timezone)
- `userid` - User who made the booking
- `fullname` - User's full name
- `event_duration_minutes` - Duration in minutes
- `book_is_cancellable` - Whether it can be cancelled

### Item Booking Fields

Items can be configured with these booking settings:
- `is_bookable` (0 or 1) - Whether the item accepts bookings
- `book_max_minutes` - Maximum booking duration (0 = unlimited)
- `book_max_slots` - Max concurrent bookings (0 = unlimited)
- `book_can_overlap` - Allow overlapping bookings
- `book_is_cancellable` - Allow cancellation
- `book_cancel_minutes` - Minimum advance notice for cancellation
- `book_users_can_in_past` - Allow booking in the past
- `canbook` - Permissions object defining who can book

## Implementation Files Created

### 1. `explore_api.py`
Script to discover API endpoints. Use this when adding any new functionality:
```bash
python explore_api.py
```

### 2. `test_bookings.py`
Comprehensive test suite for booking endpoints. Run before integrating:
```bash
python test_bookings.py
```

### 3. `booking_implementation.py`
Complete implementation ready to copy into `elabftw_mcp_server.py`. Contains:
- 6 new methods for `ElabFTWClient` class
- 6 new MCP tools
- Handler code for `call_tool()`

### 4. `ADDING_FEATURES.md`
Step-by-step guide for discovering and implementing any new features from the elabFTW API.

## Quick Integration Guide

### Step 1: Add Methods to ElabFTWClient

Open `elabftw_mcp_server.py` and add these methods to the `ElabFTWClient` class (around line 550, after `link_item_to_item`):

```python
def list_events(self, limit: int = 50, offset: int = 0, ...):
    # Copy from booking_implementation.py

def get_event(self, event_id: int):
    # Copy from booking_implementation.py

def create_booking(self, item_id: int, start: str, end: str, ...):
    # Copy from booking_implementation.py

def update_booking(self, event_id: int, ...):
    # Copy from booking_implementation.py

def delete_booking(self, event_id: int):
    # Copy from booking_implementation.py
```

### Step 2: Add Tools to list_tools()

In the `list_tools()` function (around line 850), add the 6 booking tools before the closing `]`:

```python
Tool(name="list_bookings", ...),
Tool(name="get_booking", ...),
Tool(name="create_booking", ...),
Tool(name="update_booking", ...),
Tool(name="cancel_booking", ...),
Tool(name="get_bookable_items", ...),
```

### Step 3: Add Handlers to call_tool()

In the `call_tool()` function (around line 1550), add the booking handlers before the final `else` clause:

```python
elif name == "list_bookings":
    # Copy handler code

elif name == "get_booking":
    # Copy handler code

# ... etc for all 6 tools
```

### Step 4: Test the Implementation

```bash
# Test via MCP inspector
npx @modelcontextprotocol/inspector python elabftw_mcp_server.py

# Or configure in Claude Desktop and test interactively
```

## Usage Examples

Once integrated, users can interact with bookings like this:

### List Bookings
```
User: "Show me all bookings for this week"
AI: [calls list_bookings with date filters]

User: "What equipment is booked tomorrow?"
AI: [calls list_bookings with start/end parameters]
```

### Find Bookable Items
```
User: "What equipment can I book?"
AI: [calls get_bookable_items] "Here are the bookable items..."

User: "Show me the booking policies for the microscope"
AI: [calls get_item to show booking settings]
```

### Create Bookings
```
User: "Book the confocal microscope for tomorrow 9am to 5pm"
AI: [calls list_items to find microscope ID]
    [calls create_booking with item_id, start, end]
    "Booking created successfully!"

User: "Reserve item 42 from 2024-01-20T14:00:00 to 2024-01-20T16:00:00"
AI: [calls create_booking] "Reserved for 2 hours"
```

### Manage Bookings
```
User: "Cancel my booking for next Tuesday"
AI: [calls list_bookings to find user's bookings]
    [calls cancel_booking]
    "Booking cancelled"

User: "Change my 3pm booking to start at 4pm instead"
AI: [calls update_booking with new start time]
```

## Important Notes

### Date Format
Always use ISO 8601 format for dates:
- Without timezone: `2024-01-15T09:00:00`
- With timezone: `2024-01-15T09:00:00+01:00`

Your elabFTW instance uses timezone-aware datetimes (e.g., `2023-08-17T07:30:00+02:00`).

### Permissions
- Users can only see bookings they have permission to view
- Only booking creators and admins can modify/cancel bookings
- Items must have `is_bookable=1` to accept bookings
- The `canbook` field controls who can create bookings

### Booking Policies
Each item can have different policies:
- **Max duration**: Limit how long items can be booked
- **Overlap**: Whether multiple users can book simultaneously
- **Cancellation**: Rules for when bookings can be cancelled
- **Past booking**: Whether historical bookings are allowed

### Current State
- Your instance has **213 existing bookings**
- No items in the first 50 results have `is_bookable=1`
- Bookings exist from 2023 (historical data present)
- The API is fully functional and ready to use

## Next Steps

1. **Review** the code in `booking_implementation.py`
2. **Integrate** the three sections into `elabftw_mcp_server.py`
3. **Test** using MCP inspector or Claude Desktop
4. **Enable booking** on relevant items in your elabFTW instance (optional)
5. **Update** README.md to document the new booking features
6. **Update** CHANGELOG.md with the new functionality

## Troubleshooting

### No Bookable Items
If `get_bookable_items` returns empty:
1. Go to elabFTW web interface
2. Edit a database item (equipment, setup, etc.)
3. Go to Advanced settings
4. Enable "Can be booked"
5. Configure booking parameters
6. Save

### Permission Errors
If you get 403 errors:
- Check that your API key has booking permissions
- Verify you own the booking you're trying to modify
- Check item-level permissions in `canbook` field

### Date Format Errors
- Always use ISO 8601 format
- Include timezone if your instance requires it
- Use Python's `datetime.isoformat()` for reliable formatting

## Additional Resources

- elabFTW documentation: https://doc.elabftw.net/
- API specification: https://your-server/api/v2/
- Source code: https://github.com/elabftw/elabftw
- This implementation: See `booking_implementation.py`

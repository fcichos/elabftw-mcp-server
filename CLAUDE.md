# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an MCP (Model Context Protocol) server that provides tools for AI assistants to interact with elabFTW, an open-source electronic lab notebook system. The server is implemented as a single Python file (`elabftw_mcp_server.py`, ~2200 lines) that exposes tools for managing experiments, database items (resources like chemicals, equipment, samples), and bookings/events.

## Development Commands

### Running the Server

```bash
# Direct execution (stdio mode for MCP)
python elabftw_mcp_server.py

# With environment variables
ELABFTW_API_URL="https://your-server/api/v2" \
ELABFTW_API_KEY="your-key" \
ELABFTW_VERIFY_SSL="false" \
python elabftw_mcp_server.py

# Testing with MCP inspector
npx @modelcontextprotocol/inspector python elabftw_mcp_server.py
```

### Environment Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your elabFTW API URL and key
```

## Architecture

### Single-File Design

The entire MCP server is in `elabftw_mcp_server.py` (~2200 lines). This is intentional for simplicity and easy deployment.

### Core Components

1. **ElabFTWClient** (class): HTTP client wrapper for elabFTW API v2
   - Handles authentication via API key in headers
   - Uses synchronous `httpx.Client` (not AsyncClient)
   - Supports SSL verification toggle for self-signed certificates
   - All API methods return dicts or raise `httpx.HTTPStatusError`/`httpx.RequestError`

2. **MCP Server** (uses `mcp` library):
   - Implements MCP protocol via stdio
   - Exposes ~40+ tools for experiments, items, and bookings
   - Provides 4 prompts for user guidance
   - All handlers are async despite using sync HTTP client (this is acceptable)

3. **Tool Categories**:
   - **Experiments**: CRUD, tagging, status, linking, attachments, templates, categories
   - **Items/Resources**: CRUD, tagging, linking, attachments, item types
   - **Bookings/Events**: CRUD for scheduling equipment/resources
   - **Lab Prompt**: Returns domain-specific guidance for AI assistant behavior

### Key Design Patterns

- **Tool naming**: Experiment tools use simple names (`list_experiments`, `create_experiment`), while item tools are prefixed (`list_items`, `create_item`, `add_item_tag`)
- **Template vs Category**: These are distinct concepts in elabFTW:
  - **Templates** (`template` parameter): Define initial structure/content of experiments
  - **Categories** (`category` parameter): Classify/organize experiments (like tags)
  - The code explicitly warns about this distinction in tool descriptions
- **Owner filtering**: Both experiments and items support filtering by owner user ID(s), accepting single IDs or comma-separated lists
- **Soft deletes**: Delete operations are soft-deletes (recoverable by admins)

### Error Handling Strategy

The `call_tool` handler catches three error types:
1. `httpx.HTTPStatusError`: HTTP errors from elabFTW API (returns status code + response text)
2. `httpx.RequestError`: Connection/network errors (includes SSL troubleshooting hints)
3. `Exception`: Catch-all for unexpected errors

### Critical API Quirks

- **Item creation**: Two-step process - POST with `category_id` creates item, then PATCH to set title/body
- **File uploads**: Must remove Content-Type header, use multipart/form-data with Authorization header only
- **Pagination**: Use `limit` (max 100) and `offset` parameters
- **Links**: Different endpoints for linking - `experiments_links` vs `items_links`
- **Bookings**: Items must have `is_bookable=1` field set; bookings use ISO datetime format (e.g., `2024-01-15T09:00:00`)

## Configuration

### Environment Variables

- `ELABFTW_API_URL`: Base URL for elabFTW API v2 (e.g., `https://server:3148/api/v2`)
- `ELABFTW_API_KEY`: API key from elabFTW (format: `<userid>-<hex-string>`)
- `ELABFTW_VERIFY_SSL`: Set to `"false"` for self-signed certificates (common in lab environments)

### SSL Certificate Handling

Many lab elabFTW instances use self-signed certificates. The server defaults to `ELABFTW_VERIFY_SSL=false` for this reason. In production with valid certificates, set to `"true"`.

## Important Implementation Details

### The LAB_PROMPT Constant

The `LAB_PROMPT` variable (~1000 lines) contains a comprehensive system prompt for AI behavior when working with elabFTW data:
- Domain-specific guidance (soft-matter/biophysics lab)
- Markdown templates for experiments, protocols, items
- Best practices for searching and analyzing lab data
- Safety and technical precision requirements

Returned by `lab_prompt_elabftw` tool as context for LLM interactions.

### Async/Sync Mixing

The MCP server handlers are `async` functions (required by MCP protocol), but the `ElabFTWClient` uses synchronous `httpx.Client`. This is acceptable because:
- MCP tools are I/O-bound operations
- Each tool call completes before the next
- No concurrent HTTP requests are made

If adding concurrent operations, consider switching to `httpx.AsyncClient`.

### Tool Schema Definitions

Tool input schemas are defined inline in `list_tools()`. When modifying:
- Keep descriptions clear and explicit about template vs category distinction
- Include examples in descriptions where helpful
- Mark required parameters accurately (elabFTW API can be strict)
- Default values should match API expectations (e.g., `limit=15`)

## Common Modification Scenarios

### Adding a New Tool

1. Add method to `ElabFTWClient` class (sync, using `self._get_client()`)
2. Add tool definition in `list_tools()` with proper JSON schema
3. Add handler in `call_tool()` function
4. Handle errors appropriately (httpx.HTTPStatusError, httpx.RequestError)
5. Format output as JSON or user-friendly text

### Modifying API Behavior

The elabFTW API v2 is RESTful and well-documented. Key endpoints:
- `/experiments` - Experiment CRUD
- `/items` - Database item CRUD
- `/events` - Booking/event CRUD
- `/experiments_templates` - Experiment templates
- `/teams/{id}/experiments_categories` - Experiment categories
- `/teams/{id}/items_types` - Item type definitions

API documentation available at `<server>/api/v2/` (Swagger UI)

### Testing Changes

Since there are no automated tests, manual testing is required:
1. Use MCP inspector: `npx @modelcontextprotocol/inspector python elabftw_mcp_server.py`
2. Configure in Claude Desktop and test real interactions
3. Test with actual elabFTW instance (respect lab data - use test account)

## Dependencies

- **mcp** (>=1.0.0): Model Context Protocol SDK
- **httpx** (>=0.25.0): HTTP client (sync and async support)
- **anyio** (>=4.0.0): Async I/O compatibility layer
- **python-dotenv** (>=1.0.0): Environment variable loading from .env files

All dependencies use permissive versions (`>=`) to allow updates.

## File Structure

```
.
├── elabftw_mcp_server.py      # Main server (all code here, ~2200 lines)
├── explore_api.py             # API discovery/testing script
├── test_bookings.py           # Booking functionality test script
├── booking_implementation.py  # Ready-to-integrate booking code
├── .env                       # Local config (gitignored)
├── .env.example               # Config template
├── requirements.txt           # pip dependencies
├── pyproject.toml             # Python project metadata
├── README.md                  # User documentation
├── ADDING_FEATURES.md         # Guide for adding new features
└── mcp-config.json            # Example MCP configuration
```

## Adding New Features

### Discovery Process

Use the included helper scripts to discover and test API endpoints:

```bash
# Discover available API endpoints
python explore_api.py

# Test booking functionality specifically
python test_bookings.py
```

`explore_api.py` systematically tests endpoints and examines data structures. Use it before implementing new features.

### Implementation Pattern

See `ADDING_FEATURES.md` for detailed guide. The general pattern:

1. **Discover** - Run `explore_api.py` or check Swagger UI at `<server>/api/v2/`
2. **Test** - Create a test script (see `test_bookings.py` as example)
3. **Implement** - Add methods to `ElabFTWClient`, tools to `list_tools()`, handlers to `call_tool()`
4. **Verify** - Test with MCP inspector before deploying

### Example: Booking Functionality

Booking/scheduling functionality has been integrated:
- Endpoints: `/events` (list, get, create, update, delete)
- Tools: `list_events`, `get_event`, `create_booking`, `update_booking`, `delete_booking`
- Status: Fully implemented and working
- Reference: See `ADDING_FEATURES.md` for the implementation pattern

## Security Considerations

- The `.env` file contains the API key and should NEVER be committed
- The `.env.example` file currently contains a real API key - this should be removed/sanitized
- SSL verification can be disabled for lab environments but should be enabled in production
- API keys have user-level permissions in elabFTW - scope appropriately

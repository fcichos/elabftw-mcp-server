# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an MCP (Model Context Protocol) server that provides tools for AI assistants to interact with elabFTW, an open-source electronic lab notebook system. The server is implemented as a single Python file (`elabftw_mcp_server.py`, ~3000 lines) that exposes 45 tools for managing experiments, database items (resources like chemicals, equipment, samples), bookings/events, steps, comments, file attachments, and PubChem chemical import.

## Development Commands

### Running the Server

```bash
# Preferred: uv handles dependencies automatically (reads inline script metadata)
uv run elabftw_mcp_server.py

# Testing with MCP inspector
npx @modelcontextprotocol/inspector uv run elabftw_mcp_server.py
```

**Note:** The `venv/` directory is empty. Use `uv run` — it installs into `.venv` from `pyproject.toml` automatically. Do not use `pip install` or `python` directly.

### Environment Setup

```bash
# uv installs dependencies on first run — no manual setup needed
cp .env.example .env
# Edit .env with your elabFTW API URL and key
```

### Claude Desktop Configuration

The server is registered in `~/Library/Application Support/Claude/claude_desktop_config.json` as:
```json
"elabftw": {
  "command": "uv",
  "args": ["run", "--script", "/path/to/elabftw_mcp_server.py"],
  "env": { "ELABFTW_API_URL": "...", "ELABFTW_API_KEY": "...", "ELABFTW_VERIFY_SSL": "false" }
}
```
After editing the server file, restart Claude Desktop to reload.

## Architecture

### Single-File Design

The entire MCP server is in `elabftw_mcp_server.py` (~3000 lines). This is intentional for simplicity and easy deployment.

### Core Components

1. **ElabFTWClient** (class): HTTP client wrapper for elabFTW API v2
   - Handles authentication via API key in headers
   - Uses synchronous `httpx.Client` (not AsyncClient)
   - Supports SSL verification toggle for self-signed certificates
   - All API methods return dicts or raise `httpx.HTTPStatusError`/`httpx.RequestError`

2. **MCP Server** (uses `mcp` library):
   - Implements MCP protocol via stdio
   - Exposes **45 tools** across 7 categories
   - Provides 4 prompts for user guidance
   - All handlers are async despite using sync HTTP client (this is acceptable)

3. **Tool Categories** (45 tools total):
   - **Experiments**: CRUD, tagging, status, linking, templates, categories
   - **Items/Resources**: CRUD, tagging, linking, item types
   - **Bookings/Events**: CRUD for scheduling equipment/resources
   - **Uploads**: List attachments for experiments and items (with download URL)
   - **Steps**: Checklist steps for experiments and items (create, update, delete)
   - **Comments**: Discussion threads on experiments and items (list, create, delete)
   - **PubChem**: Compound lookup by name/CAS/InChIKey; auto-create Chemical items
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
- **Upload download**: `GET /uploads/{id}` returns metadata JSON, not binary. Use the `download_url` field (requires browser session) to retrieve the actual file
- **Step `finished` field**: PATCH with `finished: 1` returns HTTP 500 on current server — server-side bug; mark steps complete via web UI only
- **Comment IDs**: The `Location` header after POST returns a different ID than the `id` field in GET responses. Always use `id` from `list_*_comments` for deletion
- **PubChem client**: `lookup_pubchem` uses a plain `httpx.Client` (no SSL config, no API key) since it calls the public PubChem REST API, not elabFTW

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
├── elabftw_mcp_server.py      # Main server (all code here, ~3000 lines)
├── explore_api.py             # API discovery/testing script
├── test_bookings.py           # Booking functionality test script
├── booking_implementation.py  # Reference booking implementation
├── .env                       # Local config (gitignored)
├── .env.example               # Config template
├── requirements.txt           # pip dependencies
├── pyproject.toml             # Python project metadata (used by uv)
├── .venv/                     # uv-managed virtual environment (auto-created)
├── README.md                  # User documentation
├── ADDING_FEATURES.md         # Guide for adding new features
└── mcp-config.json            # Example MCP configuration
```

## Adding New Features

### Discovery Process

Write a standalone script using the same `httpx.Client` pattern as `ElabFTWClient`, probe candidate endpoints, inspect response shapes, and test write operations before implementing. See `explore_api.py` and `test_bookings.py` as examples.

```bash
uv run explore_api.py
```

### Implementation Pattern

1. **Discover** - Probe endpoints in a temp script; check Swagger UI at `<server>/api/v2/`
2. **Test** - Confirm create/update/delete responses and status codes
3. **Implement** - Add method to `ElabFTWClient`, tool definition to `list_tools()`, handler to `call_tool()`
4. **Verify** - Import the module and call the client method directly, then test via MCP inspector

### Implemented Features

| Feature group | Tools | Notes |
|---|---|---|
| Experiments | `list`, `get`, `create`, `update`, `delete`, `set_status`, `add/remove_tag`, `link_item`, `upload_attachment` | |
| Items/Resources | `list`, `get`, `create`, `update`, `delete`, `add/remove_tag`, `link_item_to_item`, `upload_attachment_to_item` | |
| Metadata | `list_experiment_templates`, `list_experiment_categories`, `list_items_types` | |
| Bookings | `list_bookings`, `get_booking`, `create_booking`, `update_booking`, `cancel_booking`, `get_bookable_items` | Items need `is_bookable=1` |
| Uploads | `list_experiment_uploads`, `list_item_uploads` | Returns metadata + download URL; binary download requires browser session |
| Steps | `add/update/delete_experiment_step`, `add/update/delete_item_step` | `finished` field not patchable (server bug) |
| Comments | `list/add/delete_experiment_comment`, `list/add/delete_item_comment` | Use `id` from list, not location header |
| PubChem | `lookup_pubchem`, `create_chemical_from_pubchem` | Calls public PubChem REST API |
| Lab Prompt | `lab_prompt_elabftw` | Returns `LAB_PROMPT` constant |

## Security Considerations

- The `.env` file contains the API key and should NEVER be committed
- The `.env.example` file currently contains a real API key - this should be removed/sanitized
- SSL verification can be disabled for lab environments but should be enabled in production
- API keys have user-level permissions in elabFTW - scope appropriately

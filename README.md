# elabFTW MCP Server

A Model Context Protocol (MCP) server for interacting with [elabFTW](https://www.elabftw.net/) - an open-source electronic lab notebook.

This server allows AI assistants like Claude (via Claude Desktop) or local LLMs (via Ollama) to read and write experiments and database items (resources) in your elabFTW instance.

## Features

### Experiments
- **List Experiments**: Browse experiments with pagination, search, and owner filtering
- **Get Experiment Details**: Retrieve full experiment data including body, tags, and metadata
- **Create Experiments**: Create new experiments with title, body (HTML supported), templates, categories, and tags
- **Update Experiments**: Modify existing experiments (title, body, category, status)
- **Delete Experiments**: Soft-delete experiments
- **Tag Management**: Add and remove tags from experiments
- **Link Items**: Link experiments to other experiments or database items
- **Upload Attachments**: Attach files to experiments
- **List Templates & Categories**: Discover available experiment templates and categories

### Database Items (Resources)
- **List Items**: Browse resources (chemicals, equipment, setups, etc.) with search, category, and owner filtering
- **Get Item Details**: Retrieve full item data including body, tags, and linked items
- **Create Items**: Add new resources to your lab inventory
- **Update Items**: Modify existing items (title, body, category, rating)
- **Delete Items**: Soft-delete items
- **Tag Management**: Add and remove tags from items
- **Upload Attachments**: Attach files (datasheets, manuals, certificates) to items
- **Link Items**: Connect items to other items or experiments
- **List Item Types**: Discover available item categories (Chemicals, Equipment, Setups, etc.)

## Prerequisites

- Python 3.10 or higher
- An elabFTW server instance
- An API key from your elabFTW account

## Installation

### 1. Clone or Download

```bash
git clone <repository-url>
cd elabftw-mcp
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
ELABFTW_API_URL=https://your-elabftw-server/api/v2
ELABFTW_API_KEY=your-api-key-here
ELABFTW_VERIFY_SSL=false
```

#### Getting Your API Key

1. Log into your elabFTW instance
2. Click on your user menu (top right)
3. Go to **User Panel** → **API Keys**
4. Create a new API key with appropriate permissions
5. Copy the key immediately (it won't be shown again)

## Usage

### With Claude Desktop

Add the server to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "elabftw": {
      "command": "python",
      "args": ["/absolute/path/to/elabftw_mcp_server.py"],
      "env": {
        "ELABFTW_API_URL": "https://your-elabftw-server/api/v2",
        "ELABFTW_API_KEY": "your-api-key-here",
        "ELABFTW_VERIFY_SSL": "false"
      }
    }
  }
}
```

Restart Claude Desktop after making changes.

### With Ollama (via mcp-bridge or similar)

For Ollama integration, you can use tools like [mcp-bridge](https://github.com/SecretiveShell/MCP-Bridge) or similar MCP-to-OpenAI adapters:

```bash
# Start the MCP server
export ELABFTW_API_URL="https://your-elabftw-server/api/v2"
export ELABFTW_API_KEY="your-api-key-here"
export ELABFTW_VERIFY_SSL="false"

python elabftw_mcp_server.py
```

### Standalone Testing

You can test the server directly using the MCP inspector:

```bash
npx @modelcontextprotocol/inspector python elabftw_mcp_server.py
```

## Available Tools

### Experiment Tools

#### `list_experiments`

List experiments from your elabFTW instance.

**Parameters:**
- `limit` (optional, int): Maximum number of experiments to return (default: 15, max: 100)
- `offset` (optional, int): Number of experiments to skip for pagination
- `search` (optional, string): Search query to filter experiments
- `owner` (optional, string): Filter by owner user ID(s). Can be single ID like "2" or comma-separated like "2,3"

**Example prompts:** 
- "List my recent experiments"
- "Search for experiments about PCR"
- "Show experiments created by user 5"
- "List experiments from users 3 and 7"

#### `get_experiment`

Get detailed information about a specific experiment.

**Parameters:**
- `experiment_id` (required, int): The unique ID of the experiment

**Example prompt:** "Show me the details of experiment 42"

#### `create_experiment`

Create a new experiment.

**Parameters:**
- `title` (required, string): Title of the experiment
- `body` (optional, string): Content/body of the experiment (HTML supported)
- `template` (optional, int): Template ID for initial structure (-1 for empty, 0 for team default)
- `category` (optional, int): Category ID for classification
- `tags` (optional, array of strings): Tags to add

**Example prompt:** "Create a new experiment titled 'Western Blot Analysis' with tags 'protein' and 'analysis'"

#### `update_experiment`

Update an existing experiment.

**Parameters:**
- `experiment_id` (required, int): The ID of the experiment to update
- `title` (optional, string): New title
- `body` (optional, string): New body/content
- `category` (optional, int): New category ID
- `status` (optional, int): New status ID

**Example prompt:** "Update experiment 42 with new results section"

#### `delete_experiment`

Delete an experiment (soft-delete).

**Parameters:**
- `experiment_id` (required, int): The experiment ID to delete

#### `add_tag`

Add a tag to an experiment.

**Parameters:**
- `experiment_id` (required, int): The experiment ID
- `tag` (required, string): The tag to add

#### `remove_tag`

Remove a tag from an experiment.

**Parameters:**
- `experiment_id` (required, int): The experiment ID
- `tag_id` (required, int): The tag ID to remove

#### `set_experiment_status`

Set the status of an experiment.

**Parameters:**
- `experiment_id` (required, int): The experiment ID
- `status_id` (required, int): The status ID to set

#### `link_item`

Link an experiment or database item to an experiment.

**Parameters:**
- `experiment_id` (required, int): The experiment to link to
- `link_id` (required, int): The ID of the item/experiment to link
- `link_type` (optional, string): "experiments" or "items" (default: "experiments")

#### `upload_attachment`

Upload a file to an experiment.

**Parameters:**
- `experiment_id` (required, int): The experiment ID
- `file_path` (required, string): Path to the file
- `comment` (optional, string): Comment for the attachment

#### `list_experiment_templates`

List available experiment templates.

**Parameters:**
- `limit` (optional, int): Maximum templates to return
- `offset` (optional, int): Pagination offset

#### `list_experiment_categories`

List available experiment categories.

**Parameters:**
- `team_id` (optional, int): Team ID (default: 1)

---

### Database Item (Resource) Tools

#### `list_items`

List database items (resources) like chemicals, equipment, setups, etc.

**Parameters:**
- `limit` (optional, int): Maximum number of items to return (default: 15, max: 100)
- `offset` (optional, int): Number of items to skip for pagination
- `search` (optional, string): Search query to filter items
- `category` (optional, int): Category/type ID to filter by
- `owner` (optional, string): Filter by owner user ID(s). Can be single ID like "2" or comma-separated like "2,3"

**Example prompts:** 
- "List all chemicals in the database"
- "Search for items containing 'sodium'"
- "Show equipment owned by user 4"
- "List resources created by users 2 or 5"

#### `get_item`

Get detailed information about a specific database item.

**Parameters:**
- `item_id` (required, int): The unique ID of the item

**Example prompt:** "Show me the details of item 15" or "Get info about the NaCl entry"

#### `create_item`

Create a new database item (resource).

**Parameters:**
- `category` (required, int): Category/type ID (use `list_items_types` to find valid IDs)
- `title` (optional, string): Title of the item (e.g., chemical name, equipment name)
- `body` (optional, string): Content (HTML supported) - specifications, notes, safety info
- `tags` (optional, array of strings): Tags to add

**Example prompts:** 
- "Create a new chemical entry for Sodium Chloride"
- "Add a new equipment item for the centrifuge"
- "Create a setup entry for the PCR workstation"

#### `update_item`

Update an existing database item.

**Parameters:**
- `item_id` (required, int): The ID of the item to update
- `title` (optional, string): New title
- `body` (optional, string): New body/content
- `category` (optional, int): New category/type ID
- `rating` (optional, int): Rating 0-5 (useful for quality/reliability ratings)

**Example prompt:** "Update item 15 with new safety information"

#### `delete_item`

Delete a database item (soft-delete).

**Parameters:**
- `item_id` (required, int): The item ID to delete

#### `list_items_types`

List available item types/categories (e.g., Chemicals, Equipment, Plasmids, Setups).

**Parameters:**
- `team_id` (optional, int): Team ID (default: 1)

**Example prompt:** "What types of items can I store in the database?"

#### `add_item_tag`

Add a tag to a database item.

**Parameters:**
- `item_id` (required, int): The item ID
- `tag` (required, string): The tag to add

#### `remove_item_tag`

Remove a tag from a database item.

**Parameters:**
- `item_id` (required, int): The item ID
- `tag_id` (required, int): The tag ID to remove

#### `upload_item_attachment`

Upload a file to a database item (datasheets, manuals, certificates, etc.).

**Parameters:**
- `item_id` (required, int): The item ID
- `file_path` (required, string): Path to the file
- `comment` (optional, string): Comment for the attachment

**Example prompt:** "Upload the safety datasheet to the NaCl item"

#### `link_to_item`

Link another item or experiment to a database item.

**Parameters:**
- `item_id` (required, int): The item to link to
- `link_id` (required, int): The ID of the item/experiment to link
- `link_type` (optional, string): "items" or "experiments" (default: "items")

**Example prompt:** "Link the centrifuge equipment to this protocol"

## Example Workflows

### Managing Lab Inventory

```
You: "What types of items can I store in the database?"
AI: [calls list_items_types] "You can store: Chemicals, Equipment, Plasmids, Cell Lines, Setups..."

You: "Create a new chemical entry for DMSO with purity 99.9%"
AI: [calls create_item] "Created DMSO entry with ID 123"

You: "Add a tag 'solvent' to that chemical"
AI: [calls add_item_tag] "Tag 'solvent' added to item 123"
```

### Filtering by Owner

```
You: "Show me all experiments created by user 5"
AI: [calls list_experiments with owner="5"] "Found 12 experiments by user 5..."

You: "List chemicals added by users 3 or 7"
AI: [calls list_items with owner="3,7"] "Found 8 items created by users 3 and 7..."

You: "Show experiments from Sarah"
AI: "I'll need the user ID. Let me list users first..." [determines user ID] "Found Sarah is user 5" [calls list_experiments with owner="5"]
```

### Linking Resources to Experiments

```
You: "Show me my recent experiments"
AI: [calls list_experiments] "Here are your experiments..."

You: "Link the DMSO chemical (item 123) to experiment 45"
AI: [calls link_item] "Successfully linked item 123 to experiment 45"
```

### Finding Equipment and Setups

```
You: "Search for all setups related to PCR"
AI: [calls list_items with search="PCR"] "Found 3 PCR-related setups..."

You: "Get details on setup 78"
AI: [calls get_item] "Setup 78: PCR Workstation - includes thermal cycler, pipettes..."
```

## SSL Certificate Issues

If your elabFTW server uses a self-signed certificate (common in lab setups), set:

```env
ELABFTW_VERIFY_SSL=false
```

For production environments with valid SSL certificates, set this to `true`.

## Troubleshooting

### "Connection refused" errors
- Verify the server URL is correct
- Check if the server is accessible from your machine
- Ensure firewall rules allow the connection

### "401 Unauthorized" errors
- Verify your API key is correct
- Check if the API key has the necessary permissions
- Ensure the API key hasn't expired

### "SSL Certificate errors"
- Set `ELABFTW_VERIFY_SSL=false` for self-signed certificates
- Or install the server's CA certificate on your system

### Server not appearing in Claude Desktop
- Verify the path to the Python script is absolute
- Check Claude Desktop logs for errors
- Ensure Python is in your PATH or use the full path to the Python executable

### "Category ID required" errors when creating items
- Database items require a category/type. Use `list_items_types` first to find valid category IDs

## Security Considerations

- **Never commit your `.env` file** or API keys to version control
- Use environment variables or secure secret management for API keys
- In production, always use `ELABFTW_VERIFY_SSL=true` with valid certificates
- API keys should have minimal necessary permissions

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- [elabFTW](https://www.elabftw.net/) - The excellent open-source electronic lab notebook
- [Model Context Protocol](https://modelcontextprotocol.io/) - The protocol enabling AI-tool integration

# noapi-google-search-mcp

**Google Search for Local LLMs — No API Key Required**

An MCP (Model Context Protocol) server that gives your local LLM real Google search and page fetching abilities using headless Chromium via Playwright. No Google API key, no Custom Search Engine setup, no usage limits — just real Google results.

Works with LM Studio, Claude Desktop, and any MCP-compatible client.

## Why This Instead of API-Based Alternatives?

| | **noapi-google-search-mcp** | API-based MCP servers |
|---|---|---|
| API key required | No | Yes (Google CSE API) |
| Cost | Free | Paid after 100 queries/day |
| Setup time | `pip install` + go | Create Google Cloud project, enable API, get key, configure CSE |
| Results quality | Real Google results | Custom Search Engine (different ranking) |
| JavaScript pages | Renders them (Chromium) | Cannot render JS |
| Page fetching | Built-in `visit_page` tool | Usually separate |

## Features

- **`google_search`** — Search Google and get structured results (titles, URLs, snippets)
- **`visit_page`** — Fetch any URL and extract readable text content
- Headless Chromium renders JavaScript-heavy pages
- Consent banner auto-dismissal
- Smart content extraction (strips nav, ads, footers)
- Zero configuration — no API keys, no environment variables

## Installation

```bash
pip install noapi-google-search-mcp
playwright install chromium
```

## Usage

### LM Studio

Add to `~/.lmstudio/mcp.json`:

```json
{
  "mcpServers": {
    "google-search": {
      "command": "noapi-google-search-mcp",
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

### Claude Desktop

Add to your Claude Desktop config:

```json
{
  "mcpServers": {
    "google-search": {
      "command": "noapi-google-search-mcp"
    }
  }
}
```

### As a CLI

```bash
noapi-google-search-mcp
```

Or:

```bash
python -m google_search_mcp
```

## Development

```bash
git clone https://github.com/VincentKaufmann/google-search-mcp.git
cd google-search-mcp
pip install -e .
playwright install chromium
```

## License

MIT

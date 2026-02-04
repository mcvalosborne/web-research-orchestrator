# Setup Guide

Complete setup instructions for the web research skill.

## Quick Start (No Setup Required)

The basic methodology works immediately with built-in tools:
- `WebSearch` - General web searches
- `WebFetch` - Fetch and parse web pages
- `Task` tool - Spawn Haiku subagents

**Test it:**
```
"Research the top 5 CRM tools and compare their pricing"
```

## Enhanced Setup

Adding MCP servers dramatically improves capabilities.

### 1. Brave Search MCP

**Why:** Privacy-focused search with its own index, better for technical queries.

**Get API Key:**
1. Go to https://brave.com/search/api/
2. Create free account (2,000 queries/month free)
3. Generate API key

**Install:**
```bash
claude mcp add brave-search -- npx -y @anthropic-ai/brave-search-mcp
```

**Or add to `~/.claude/settings.json`:**
```json
{
  "mcpServers": {
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/brave-search-mcp"],
      "env": {
        "BRAVE_API_KEY": "YOUR_KEY_HERE"
      }
    }
  }
}
```

### 2. Firecrawl MCP

**Why:** Handles JavaScript-rendered pages, anti-bot measures, structured extraction.

**Get API Key:**
1. Go to https://firecrawl.dev/app/api-keys
2. Create free account (500 credits free)
3. Generate API key

**Install:**
```bash
claude mcp add firecrawl -- npx -y firecrawl-mcp
```

**Or add to settings:**
```json
{
  "mcpServers": {
    "firecrawl": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": {
        "FIRECRAWL_API_KEY": "YOUR_KEY_HERE"
      }
    }
  }
}
```

### 3. Fetch MCP (Alternative)

**Why:** Simple alternative to WebFetch with more output formats.

```bash
claude mcp add fetch -- npx -y @anthropic-ai/fetch-mcp
```

## Environment Variables

Create `~/.claude/.env.local`:

```bash
# Search APIs
BRAVE_API_KEY=your_brave_key_here

# Scraping Services
FIRECRAWL_API_KEY=your_firecrawl_key_here

# Optional
SERP_API_KEY=your_serp_api_key
BING_SEARCH_API_KEY=your_bing_key
```

## Model Configuration

### Task Tool Model Selection

```
Task tool parameters:
- model: "haiku"  # Cost-effective workers
- model: "sonnet" # Complex extraction
- model: "opus"   # Strategy/synthesis only
```

### Cost Comparison

| Model | Input/1M | Output/1M | Best For |
|-------|----------|-----------|----------|
| Haiku 3.5 | $0.25 | $1.25 | URL fetching, extraction |
| Sonnet 4 | $3.00 | $15.00 | Complex parsing |
| Opus 4 | $15.00 | $75.00 | Strategy, synthesis |

## Verification

After setup, verify tools:

```bash
# Check MCP servers
/mcp

# Search for web tools
ToolSearch: "web scraping"

# Test functionality
"Use Firecrawl to scrape https://example.com"
```

## Troubleshooting

### "Tool not found"
Restart Claude Code after adding MCP servers.

### "API key invalid"
1. Check key is set in environment
2. Verify key hasn't expired
3. Check rate limits

### "Blocked by website"
```
Fallback: WebFetch → Firecrawl → Alternative source
```

### "Haiku model not available"
Use `model: "sonnet"` as workaround (costs more).

## Cost Monitoring

Track usage:
- Brave: https://brave.com/search/api/dashboard
- Firecrawl: https://firecrawl.dev/app/dashboard
- Claude: Anthropic console

## Security Notes

1. Never commit API keys
2. Respect robots.txt
3. Rate limit yourself
4. Store data securely
5. Check terms of service

# Web Research Orchestrator

A Claude skill for advanced web research and data extraction using multi-model orchestration.

## Overview

This skill transforms Claude into a research orchestrator that:
- **Plans** research strategy using Opus/Sonnet
- **Executes** data gathering via parallel Haiku subagents
- **Synthesizes** results into structured JSON output

### Cost Efficiency

By delegating URL fetching to Haiku workers instead of using Opus directly:
- 20 URLs with Opus: ~$0.30
- 20 URLs with Haiku workers: ~$0.01
- **Savings: 97%**

## Quick Start

### Option 1: Streamlit GUI (Recommended)

Run the visual interface:

```bash
cd gui
pip install -r requirements.txt
streamlit run app.py
```

Features:
- 🔍 Auto-discover sources or use custom URLs
- ⚡ Parallel Haiku workers with progress tracking
- 📊 View results in tables
- 📥 Export to JSON, CSV, or Markdown

### Option 2: Claude Desktop App

1. Download `SKILL.md`
2. Open Claude Desktop → Skills → Upload a skill
3. Select the file

### Option 3: Claude Code (CLI)

Copy the skill folder to your Claude skills directory:

```bash
cp -r web-research-orchestrator ~/.claude/skills/
```

## Usage

Trigger the skill with prompts like:
- "Research pricing for the top 5 CRM tools"
- "Gather competitive intelligence on [company]"
- "Extract data from these URLs: [list]"
- "Find industry statistics for [topic]"

## Files

| File | Description |
|------|-------------|
| `gui/` | **Streamlit GUI application** |
| `gui/app.py` | Main Streamlit app |
| `gui/requirements.txt` | Python dependencies |
| `SKILL.md` | Main skill file (uploadable to Claude Desktop) |
| `docs/methodology.md` | Detailed methodology documentation |
| `docs/setup.md` | MCP server setup instructions |
| `prompts/extraction.md` | Data extraction prompt templates |
| `prompts/discovery.md` | Source discovery prompt templates |
| `prompts/synthesis.md` | Result synthesis prompt templates |
| `prompts/workers.md` | Haiku worker prompt templates |
| `examples/` | Worked examples for common use cases |
| `schema.json` | JSON schema for research output |

## Optional MCP Servers

Enhance capabilities with these MCP servers:

| Server | Purpose | Free Tier |
|--------|---------|-----------|
| [Brave Search](https://brave.com/search/api/) | Privacy-focused search | 2,000 queries/mo |
| [Firecrawl](https://firecrawl.dev/) | JS rendering, anti-bot | 500 credits |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR                         │
│                  (Opus / Sonnet)                        │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   PLAN      │→ │   BATCH     │→ │  SYNTHESIZE │     │
│  │  Research   │  │   Work      │  │   Results   │     │
│  └─────────────┘  └──────┬──────┘  └─────────────┘     │
└──────────────────────────┼──────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │   Haiku    │  │   Haiku    │  │   Haiku    │
    │  Worker 1  │  │  Worker 2  │  │  Worker N  │
    └────────────┘  └────────────┘  └────────────┘
           │               │               │
           ▼               ▼               ▼
        Source A       Source B       Source N
```

## License

MIT License - feel free to use, modify, and share.

## Author

Created for use with [Claude Code](https://claude.ai/claude-code) and Claude Desktop.

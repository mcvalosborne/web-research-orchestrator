# Web Research Orchestrator

A Claude skill for advanced web research and data extraction using multi-model orchestration with **multi-strategy extraction** and **Pydantic validation**.

## Overview

This skill transforms Claude into a research orchestrator that:
- **Plans** research strategy using Opus/Sonnet
- **Executes** data gathering via parallel Haiku subagents
- **Validates** data with Pydantic schemas
- **Synthesizes** results into structured JSON output

### Key Features

| Feature | Description | Benefit |
|---------|-------------|---------|
| Multi-Strategy Extraction | CSS/Regex → LLM fallback | 60% cost reduction |
| Pydantic Validation | Type-safe data validation | Higher data quality |
| Cost Tracking | Per-agent token tracking | Budget visibility |
| Parallel Workers | Concurrent Haiku subagents | Faster research |
| Auto-Recovery | Fallback strategies on failure | Better success rates |

### Cost Efficiency

By using multi-strategy extraction (CSS/Regex before LLM):

| Approach | 20 URLs Cost | Savings |
|----------|-------------|---------|
| Opus-only | ~$0.39 | - |
| Haiku workers | ~$0.03 | 92% |
| Multi-strategy + Haiku | ~$0.01 | 97% |

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
- ⚡ Multi-strategy extraction (CSS → Regex → LLM)
- ✅ Pydantic data validation
- 💰 Real-time cost tracking
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

## Multi-Strategy Extraction

The orchestrator uses a **cost-optimized extraction pipeline**:

```
┌────────────────────────────────────────────────────────────┐
│                  EXTRACTION PIPELINE                        │
├────────────────────────────────────────────────────────────┤
│  1. CSS/XPath Selectors    [FREE]   ~10ms                  │
│     - [class*="price"], h1, meta[og:title]                 │
│                                                             │
│  2. Regex Patterns         [FREE]   ~5ms                   │
│     - Prices, emails, dates, percentages                   │
│                                                             │
│  3. LLM Extraction         [$$]     ~2-5s                  │
│     - Only for missing/complex fields                      │
└────────────────────────────────────────────────────────────┘
```

**Result**: 60-90% of extractions complete without LLM calls.

## Data Validation

All extracted data passes through Pydantic validation:

```python
class PriceData(BaseModel):
    amount: float = Field(..., gt=0)  # Must be positive
    currency: str = Field(pattern=r"^[A-Z]{3}$")

class ProductData(BaseModel):
    name: str = Field(..., min_length=1)
    price: Optional[PriceData] = None
    features: list[str] = Field(default_factory=list)
```

This catches:
- Invalid formats (dates, prices, URLs)
- Illogical values (negative prices)
- Type mismatches
- Missing required fields

## Files

| File | Description |
|------|-------------|
| `gui/` | **Streamlit GUI application** |
| `gui/app.py` | Main Streamlit app |
| `gui/extraction.py` | Multi-strategy extraction module |
| `gui/requirements.txt` | Python dependencies |
| `SKILL.md` | Main skill file (uploadable to Claude Desktop) |
| `docs/methodology.md` | Detailed methodology documentation |
| `docs/best-practices.md` | **Research & best practices** |
| `docs/setup.md` | MCP server setup instructions |
| `prompts/` | Prompt templates |
| `examples/` | Worked examples |
| `schema.json` | JSON schema for research output |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (Sonnet)                     │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   PLAN      │→ │   BATCH     │→ │  SYNTHESIZE │         │
│  │  Research   │  │   Work      │  │   Results   │         │
│  └─────────────┘  └──────┬──────┘  └─────────────┘         │
└──────────────────────────┼──────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │   Haiku    │  │   Haiku    │  │   Haiku    │
    │  Worker 1  │  │  Worker 2  │  │  Worker N  │
    │            │  │            │  │            │
    │ CSS/Regex  │  │ CSS/Regex  │  │ CSS/Regex  │
    │     ↓      │  │     ↓      │  │     ↓      │
    │ LLM (opt)  │  │ LLM (opt)  │  │ LLM (opt)  │
    └────────────┘  └────────────┘  └────────────┘
           │               │               │
           ▼               ▼               ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │  Pydantic  │  │  Pydantic  │  │  Pydantic  │
    │ Validation │  │ Validation │  │ Validation │
    └────────────┘  └────────────┘  └────────────┘
```

## Optional Integrations

| Service | Purpose | Free Tier |
|---------|---------|-----------|
| [Brave Search](https://brave.com/search/api/) | Web search | 2,000 queries/mo |
| [Firecrawl](https://firecrawl.dev/) | JS rendering, anti-bot | 500 credits |

## Cost Tracking

Every research session tracks:
- **Actual cost**: What you paid
- **Opus equivalent**: What it would cost with Opus-only
- **Savings**: Dollar amount and percentage saved
- **Breakdown**: Cost per agent type (orchestrator/worker/analyst)

Example output:
```
💰 Cost Summary
├── Actual Cost:      $0.0089
├── Opus Equivalent:  $0.4413
├── Savings:          $0.4324 (98.0%)
└── Total Tokens:     12,450
```

## Best Practices

See [docs/best-practices.md](docs/best-practices.md) for:
- Multi-strategy extraction methodology
- Pydantic validation patterns
- Multi-agent architecture design
- Cost optimization strategies
- Data quality assurance
- Tool recommendations

## License

MIT License - feel free to use, modify, and share.

## Author

Created for use with [Claude Code](https://claude.ai/claude-code) and Claude Desktop.

## References

- [ScrapeGraphAI](https://github.com/ScrapeGraphAI/Scrapegraph-ai) - Graph-based LLM scraping
- [Crawl4AI](https://github.com/unclecode/crawl4ai) - LLM-optimized crawler
- [Zyte QA Guide](https://www.zyte.com/blog/guide-to-web-data-extraction-qa-validation-techniques/) - Data validation
- [Pydantic](https://docs.pydantic.dev/) - Data validation library

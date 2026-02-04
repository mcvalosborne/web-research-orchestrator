---
name: web-research-orchestrator
description: Advanced web research using multi-model hierarchy (Opus/Sonnet for strategy, Haiku for execution), parallel subagents, and structured data extraction. Best for competitive intelligence, trend research, and cross-source data gathering.
---

# Web Research Orchestrator

## Trigger

Use this skill when the user asks to:
- Research a topic across multiple web sources
- Scrape data from websites or web pages
- Gather competitive intelligence
- Extract structured data from web content
- Build a dataset from online sources

## Core Philosophy

**Treat Claude as an ORCHESTRATOR, not a worker.**

You don't fetch URLs directly - you spawn workers. You don't parse HTML - you delegate. Your job is:
1. Plan the research strategy
2. Identify targets
3. Batch work to cost-effective subagents
4. Validate and synthesize results

## Phase 1: Research Planning

### Define Scope

```
1. WHAT data do we need?
   - Specific fields/attributes
   - Data format requirements
   - Volume expectations

2. WHERE might this data exist?
   - Known authoritative sources
   - Potential discovery queries
   - Alternative data sources

3. WHY does this approach make sense?
   - Is web scraping the best method?
   - Are there APIs available instead?
```

### Source Discovery

```
DISCOVERY HIERARCHY:

1. Web Search → Find relevant URLs
   - Cast wide net with varied queries
   - Note domain patterns

2. Site-specific searches
   - site:example.com [query]
   - Look for directories, listings

3. API Detection
   - Check robots.txt, sitemap.xml
   - Look for /api/ endpoints
```

## Phase 2: Tool Selection

```
TIER 1: Search & Discovery
├── WebSearch (native)
├── Brave Search MCP
└── Search APIs

TIER 2: Content Extraction
├── WebFetch (native)
├── Firecrawl MCP (JS, anti-bot)
└── Browser Plugin

TIER 3: Parallel Execution
├── Task tool → Haiku subagents
└── Bash → curl/wget
```

| Scenario | Primary Tool | Fallback |
|----------|--------------|----------|
| Simple static page | WebFetch | Firecrawl |
| JavaScript-heavy | Firecrawl | Browser |
| Batch URLs (10+) | Task + Haiku | Sequential |

## Phase 3: Execution

### Multi-Source Pattern (Recommended)

```
[Orchestrator] ───┬──→ [Haiku 1] → Source A
                  ├──→ [Haiku 2] → Source B
                  ├──→ [Haiku 3] → Source C
                  └──→ [Haiku N] → Source N

Synthesize ←──── JSON responses
```

### Worker Prompt Template

```
TASK: Extract structured data from [URL]

SCHEMA:
{
  "field1": "description",
  "field2": "description"
}

INSTRUCTIONS:
1. Fetch URL using WebFetch
2. Extract data matching schema
3. Return ONLY valid JSON
4. If field not found, use null
5. If inaccessible, return {"error": "reason"}
```

### Task Tool Parameters

```
- subagent_type: "general-purpose"
- model: "haiku"  # Critical for cost
- run_in_background: true
- prompt: Include URLs, schema, output format
```

## Phase 4: Output Format

```json
{
  "research_topic": "string",
  "query_date": "ISO8601",
  "sources_checked": ["url1", "url2"],
  "results": [
    {
      "source": "url",
      "data": { ...fields... },
      "confidence": "high|medium|low"
    }
  ],
  "summary": "brief synthesis",
  "gaps": ["what couldn't be found"]
}
```

## Phase 5: Fallback Chain

```
WebFetch fails → Try Firecrawl MCP
Firecrawl fails → Try Browser plugin
Browser fails → Mark inaccessible, find alternatives
Rate limited → Backoff, retry, try alternative
```

## Cost Optimization

```
RULES:
- Never use Opus for fetching URLs
- Batch 10-20 URLs per Haiku worker
- Use search APIs for discovery
- Reserve Opus for synthesis only

SAVINGS:
- 20 URLs with Opus: ~$0.30
- 20 URLs with Haiku: ~$0.01
```

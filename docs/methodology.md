# Research Methodology

Detailed documentation of the web research orchestration methodology.

## Core Concept: Orchestration Over Execution

The fundamental insight is that Claude should act as an **orchestrator**, not a worker. This means:

| Traditional Approach | Orchestrator Approach |
|---------------------|----------------------|
| Claude fetches each URL | Claude spawns workers to fetch |
| Sequential processing | Parallel execution |
| High cost (Opus for everything) | Low cost (Haiku for grunt work) |
| Slow | Fast |

## The Multi-Model Hierarchy

```
OPUS / SONNET (Orchestrator)
├── Strategic planning
├── Query design
├── Result synthesis
└── Quality assessment

HAIKU (Workers)
├── URL fetching
├── Data extraction
├── Schema mapping
└── Error reporting
```

### Why This Works

1. **Cost**: Haiku is 60x cheaper than Opus per token
2. **Speed**: Parallel workers complete faster than sequential
3. **Quality**: Opus focuses on high-value synthesis work
4. **Reliability**: Failed workers don't block others

## Phase Details

### Phase 1: Research Planning

Before any data collection, establish:

#### 1.1 Data Requirements
- What specific fields do we need?
- What format should output take?
- How much data is expected?

#### 1.2 Source Strategy
- What are known authoritative sources?
- What search queries will find more?
- Are there APIs we should use instead?

#### 1.3 Ethical Considerations
- Check robots.txt for each domain
- Respect rate limits
- Consider terms of service
- Handle PII appropriately

### Phase 2: Source Discovery

Use a tiered search approach:

```
Tier 1: Broad Web Search
├── General topic queries
├── Varied phrasings
└── Note promising domains

Tier 2: Site-Specific Search
├── site:domain.com [query]
├── Look for structured data
└── Find sitemaps/directories

Tier 3: API Detection
├── Check /robots.txt
├── Look for /api/ paths
├── Search "[site] API documentation"
└── Check for RSS/JSON feeds
```

### Phase 3: Tool Selection

Choose tools based on the target:

| Target Type | Recommended Tool | Notes |
|-------------|-----------------|-------|
| Static HTML | WebFetch | Fast, free |
| JavaScript SPA | Firecrawl | Renders JS |
| Anti-bot protected | Firecrawl | Handles blocks |
| Simple API | Bash curl | Direct and fast |
| Batch of URLs | Task + Haiku | Parallel workers |

### Phase 4: Batch Execution

#### Worker Design

Each Haiku worker should:
1. Receive a clear, specific task
2. Have explicit success criteria
3. Return structured JSON
4. Handle errors gracefully

#### Batch Sizing

| Job Size | Workers | URLs/Worker |
|----------|---------|-------------|
| 1-10 URLs | 2-3 | 3-5 |
| 10-50 URLs | 5-10 | 5-10 |
| 50-200 URLs | 10-20 | 10-15 |
| 200+ URLs | Consider infrastructure | - |

### Phase 5: Result Synthesis

The orchestrator's most important job:

1. **Aggregate** all worker results
2. **Validate** data quality
3. **Deduplicate** overlapping data
4. **Cross-reference** between sources
5. **Identify** gaps and conflicts
6. **Synthesize** into final output

### Phase 6: Quality Assessment

Rate the research output:

| Dimension | High | Medium | Low |
|-----------|------|--------|-----|
| Completeness | >90% fields | 60-90% | <60% |
| Source Agreement | 3+ sources agree | 2 sources | 1 source |
| Freshness | <1 month old | <1 year | >1 year |
| Authority | Official sources | Reputable | Unknown |

## Fallback Strategies

When primary methods fail:

```
WebFetch blocked (403)
└── Try Firecrawl MCP
    └── Try alternative source
        └── Mark as inaccessible

JavaScript required
└── Use Firecrawl
    └── Note limitation

Rate limited (429)
└── Wait and retry with backoff
    └── Reduce batch size
        └── Try tomorrow

Login required
└── Mark as inaccessible
└── Search for public alternatives
```

## Cost Optimization

### Token Economics

| Model | Input $/1M | Output $/1M |
|-------|-----------|-------------|
| Haiku 3.5 | $0.25 | $1.25 |
| Sonnet 4 | $3.00 | $15.00 |
| Opus 4 | $15.00 | $75.00 |

### Optimization Rules

1. **Never** use Opus for URL fetching
2. **Batch** 10-20 URLs per Haiku worker
3. **Cache** results for repeat research
4. **Use** search APIs for discovery (cheap)
5. **Reserve** Opus for synthesis only

### Example Savings

Research task: 20 product pages

| Approach | Estimated Cost |
|----------|---------------|
| All Opus | $0.30 |
| Opus + Haiku workers | $0.01 |
| **Savings** | **97%** |

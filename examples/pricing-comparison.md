# Example: Competitive SaaS Pricing Analysis

**Goal:** Compare pricing across 5 project management tools

---

## Phase 1: Discovery

**User Request:**
```
Research pricing for Asana, Monday, Notion, ClickUp, and Linear
```

**Orchestrator Actions:**
```
SEARCH QUERIES:
- "Asana pricing plans"
- "Monday.com pricing"
- "Notion pricing"
- "ClickUp pricing"
- "Linear pricing"

DISCOVERED URLS:
1. https://asana.com/pricing
2. https://monday.com/pricing
3. https://notion.so/pricing
4. https://clickup.com/pricing
5. https://linear.app/pricing
```

---

## Phase 2: Batch Extraction

**Task Tool Invocations (5 parallel Haiku workers):**

```
Task 1:
- subagent_type: "general-purpose"
- model: "haiku"
- prompt: "Extract pricing from https://asana.com/pricing

  SCHEMA:
  {
    'product': 'Asana',
    'plans': [{
      'name': 'Plan name',
      'price_monthly': number,
      'price_yearly': number,
      'currency': 'USD',
      'features': ['list'],
      'limits': ['user limits, etc']
    }]
  }

  Return only valid JSON."

Task 2-5: Same pattern for other products
```

---

## Phase 3: Worker Results

**Worker 1 Output (Asana):**
```json
{
  "product": "Asana",
  "plans": [
    {
      "name": "Basic",
      "price_monthly": 0,
      "price_yearly": 0,
      "currency": "USD",
      "features": ["Task management", "Board view", "Calendar view"],
      "limits": ["Up to 10 users"]
    },
    {
      "name": "Premium",
      "price_monthly": 10.99,
      "price_yearly": 10.99,
      "currency": "USD",
      "features": ["Timeline", "Workflow builder", "Forms"],
      "limits": ["Unlimited users"]
    },
    {
      "name": "Business",
      "price_monthly": 24.99,
      "price_yearly": 24.99,
      "currency": "USD",
      "features": ["Portfolios", "Goals", "Workload"],
      "limits": ["Unlimited users"]
    }
  ]
}
```

---

## Phase 4: Aggregated Results

```json
{
  "research_topic": "Project Management Tool Pricing",
  "query_date": "2024-01-15T10:30:00Z",
  "sources_checked": [
    "https://asana.com/pricing",
    "https://monday.com/pricing",
    "https://notion.so/pricing",
    "https://clickup.com/pricing",
    "https://linear.app/pricing"
  ],
  "results": [
    {
      "product": "Asana",
      "has_free_tier": true,
      "entry_price": 10.99,
      "enterprise_price": 24.99,
      "billing": "per user/month"
    },
    {
      "product": "Monday",
      "has_free_tier": true,
      "entry_price": 9.00,
      "enterprise_price": 19.00,
      "billing": "per user/month"
    },
    {
      "product": "Notion",
      "has_free_tier": true,
      "entry_price": 8.00,
      "enterprise_price": 15.00,
      "billing": "per user/month"
    },
    {
      "product": "ClickUp",
      "has_free_tier": true,
      "entry_price": 7.00,
      "enterprise_price": 12.00,
      "billing": "per user/month"
    },
    {
      "product": "Linear",
      "has_free_tier": true,
      "entry_price": 8.00,
      "enterprise_price": 14.00,
      "billing": "per user/month"
    }
  ],
  "summary": "All 5 tools offer free tiers. ClickUp is most affordable at $7/user. Asana is most expensive at $10.99/user entry level. Enterprise pricing ranges from $12-25/user.",
  "methodology": "Direct extraction from official pricing pages"
}
```

---

## Phase 5: Synthesis

### Comparison Matrix

| Product | Free Tier | Entry Price | Business Price | Best For |
|---------|-----------|-------------|----------------|----------|
| Asana | Yes (10 users) | $10.99 | $24.99 | Enterprises |
| Monday | Yes (2 users) | $9.00 | $19.00 | Visual teams |
| Notion | Yes | $8.00 | $15.00 | Docs + PM |
| ClickUp | Yes | $7.00 | $12.00 | Budget-conscious |
| Linear | Yes | $8.00 | $14.00 | Dev teams |

### Key Findings

- **Most Affordable:** ClickUp ($7/user entry, $12/user business)
- **Most Expensive:** Asana ($10.99/user entry, $24.99/user business)
- **Best Free Tier:** Asana (10 users) or Notion (unlimited guests)
- **All offer annual discounts** of 15-20%

### Cost Estimate (50-person team, business tier)

| Product | Monthly Cost | Annual Cost |
|---------|-------------|-------------|
| ClickUp | $600 | $6,000 |
| Linear | $700 | $7,000 |
| Notion | $750 | $7,500 |
| Monday | $950 | $9,500 |
| Asana | $1,250 | $12,500 |

---

## Execution Stats

- **Total Time:** ~45 seconds
- **Workers Used:** 5 Haiku agents
- **Estimated Cost:** $0.008
- **Alternative (Opus only):** $0.25
- **Savings:** 97%

# Synthesis Prompts

Prompts for combining and validating research results.

---

## Multi-Source Synthesis

```
Synthesize findings from these research results:

[PASTE_AGGREGATED_WORKER_RESULTS]

CREATE:
1. Executive Summary (3-5 sentences)
2. Key Findings (bullet points)
3. Data Confidence Assessment
4. Conflicting Information (if any)
5. Gaps and Limitations
6. Source Quality Matrix

Output as markdown with proper citations.
```

---

## Data Validation

```
Validate and clean this extracted dataset:

[RAW_DATA]

VALIDATION RULES:
1. Remove exact duplicates
2. Flag potential duplicates (fuzzy match)
3. Validate data types (prices are numbers, dates are valid, etc.)
4. Check for outliers
5. Assess completeness per field

OUTPUT:
{
  "validated_data": [...],
  "removed_duplicates": N,
  "flagged_items": [...with reasons...],
  "completeness_report": {
    "field1": "95% complete",
    ...
  },
  "quality_score": "X/100"
}
```

---

## Cross-Source Comparison

```
Compare data from multiple sources on [TOPIC]:

SOURCE DATA:
[PASTE_MULTI_SOURCE_DATA]

ANALYSIS:
1. Where do sources agree?
2. Where do sources conflict?
3. Which source is most authoritative for each data point?
4. What's the consensus value for key metrics?

OUTPUT:
{
  "consensus_findings": [...],
  "conflicts": [
    {
      "data_point": "",
      "source_a_value": "",
      "source_b_value": "",
      "recommended": "",
      "reasoning": ""
    }
  ],
  "source_reliability_ranking": [...]
}
```

---

## Gap Analysis

```
Analyze what's missing from this research:

RESEARCH GOAL: [ORIGINAL_GOAL]

DATA COLLECTED:
[SUMMARY_OF_COLLECTED_DATA]

IDENTIFY:
1. What questions remain unanswered?
2. What data points are incomplete?
3. What sources couldn't be accessed?
4. What additional searches might help?

OUTPUT:
{
  "answered_questions": [...],
  "unanswered_questions": [...],
  "incomplete_data": [
    {"field": "", "completeness": "%", "missing_from": [...]}
  ],
  "suggested_followup": [
    {"query": "", "expected_to_find": ""}
  ]
}
```

---

## Trend Synthesis

```
Synthesize trend data from multiple sources:

TIME SERIES DATA:
[PASTE_TEMPORAL_DATA]

ANALYSIS:
1. Identify overall trend direction
2. Note significant inflection points
3. Calculate growth rates where possible
4. Assess prediction reliability

OUTPUT:
{
  "trend_summary": "Description of overall trend",
  "direction": "increasing/decreasing/stable/volatile",
  "key_inflections": [
    {"date": "", "event": "", "impact": ""}
  ],
  "metrics": {
    "cagr": "",
    "yoy_growth": "",
    "peak": {"value": "", "date": ""},
    "trough": {"value": "", "date": ""}
  },
  "forecast_confidence": "high/medium/low",
  "data_quality_notes": ""
}
```

---

## Competitive Matrix Synthesis

```
Create a competitive comparison matrix from:

PRODUCT DATA:
[PASTE_MULTI_PRODUCT_DATA]

CREATE:
1. Feature comparison matrix
2. Pricing comparison table
3. Strengths/weaknesses per product
4. Best fit recommendations by use case

OUTPUT FORMAT:
{
  "feature_matrix": {
    "features": ["f1", "f2", "f3"],
    "products": {
      "Product A": [true, false, true],
      "Product B": [true, true, false]
    }
  },
  "pricing_comparison": [...],
  "analysis": {
    "Product A": {"strengths": [...], "weaknesses": [...]},
    ...
  },
  "recommendations": {
    "best_for_startups": "",
    "best_for_enterprise": "",
    "best_value": "",
    "most_features": ""
  }
}
```

---

## Quality Assessment

```
Assess the quality of this research output:

[RESEARCH_OUTPUT]

ASSESSMENT CRITERIA:
1. Completeness (% of expected data found)
2. Accuracy (do values seem reasonable?)
3. Freshness (how recent is the data?)
4. Source Authority (how trustworthy are sources?)
5. Consistency (do sources agree?)

OUTPUT:
{
  "scores": {
    "completeness": X/5,
    "accuracy": X/5,
    "freshness": X/5,
    "authority": X/5,
    "consistency": X/5
  },
  "overall_score": X/25,
  "grade": "A/B/C/D/F",
  "strengths": [...],
  "weaknesses": [...],
  "recommendations": [...]
}
```

---

## Executive Summary Generator

```
Generate an executive summary from this research:

[FULL_RESEARCH_OUTPUT]

REQUIREMENTS:
- Maximum 5 bullet points
- Lead with the most important finding
- Include key numbers/statistics
- Note confidence level
- Mention significant caveats

FORMAT:
## Executive Summary

**Key Finding:** [One sentence headline]

- [Bullet 1 - most important]
- [Bullet 2]
- [Bullet 3]
- [Bullet 4]
- [Bullet 5]

**Confidence:** [High/Medium/Low] - [Brief explanation]

**Caveats:** [Key limitations to note]
```

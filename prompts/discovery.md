# Discovery Prompts

Prompts for finding and identifying research sources.

---

## General Topic Research

```
Research [TOPIC] and find the most authoritative sources.

1. Use WebSearch to find 10-15 relevant URLs
2. Prioritize: academic sources > official sites > reputable news > blogs
3. Return a list with: URL, source type, authority level (1-5), brief description

Focus on sources from the last [TIME_PERIOD].
```

---

## Competitive Analysis Discovery

```
Find publicly available information about [COMPANY/PRODUCT]:

SEARCH QUERIES:
- "[company] pricing"
- "[company] features comparison"
- "[company] reviews"
- "[company] alternatives"
- site:[company.com] pricing OR plans

Return URLs organized by information type.
```

---

## Data Source Identification

```
I need to find sources for [DATA_TYPE] data.

Look for:
1. Official government/industry databases
2. Research reports and whitepapers
3. News articles with statistics
4. Company reports/filings
5. API endpoints that might provide this data

Prioritize structured, machine-readable sources.
```

---

## API Discovery

```
Check if [DOMAIN] has any accessible APIs:

1. Check [domain]/robots.txt for api paths
2. Check [domain]/sitemap.xml
3. Look for /api/, /v1/, /graphql endpoints
4. Check developer documentation links
5. Search for "[domain] API documentation"

Return any discovered endpoints with access requirements.
```

---

## Historical Data Research

```
Find historical data for [METRIC] from [START_DATE] to [END_DATE].

SOURCES TO CHECK:
1. Internet Archive (archive.org) snapshots
2. Government statistical databases
3. Academic repositories
4. Industry reports
5. Press releases with dated figures

For each data point, record:
- Value
- Date/period
- Source
- Methodology (if known)
```

---

## Industry/Market Discovery

```
Find authoritative sources for [INDUSTRY] market data:

SEARCH STRATEGY:

Tier 1 - Reports:
- "[industry] market report 2024 PDF"
- "[industry] statistics 2024"
- "site:mckinsey.com [industry]"
- "site:gartner.com [industry]"

Tier 2 - News:
- "[industry] market size 2024"
- "[industry] growth forecast"

Tier 3 - Academic:
- "site:ncbi.nlm.nih.gov [industry]"
- "site:arxiv.org [industry]"

Return sources grouped by authority level.
```

---

## Social Proof Discovery

```
Find public reviews and sentiment sources for [PRODUCT/COMPANY]:

PLATFORMS TO CHECK:
- G2, Capterra, TrustRadius (B2B)
- Amazon, Yelp (Consumer)
- Reddit, Twitter/X (Social)
- App stores (Mobile)
- Glassdoor (Employer)

For each platform, note:
- URL to reviews
- Approximate review count
- Overall rating if visible
- Accessibility (public/login required)
```

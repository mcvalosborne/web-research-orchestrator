# Extraction Prompts

Prompts for extracting structured data from web sources.

---

## Single Page Extraction

```
Extract structured data from this URL: [URL]

EXTRACTION SCHEMA:
{
  "title": "Page title",
  "main_content": "Primary text content",
  "key_facts": ["Array of key facts/statistics"],
  "dates_mentioned": ["Any dates referenced"],
  "entities": ["Companies, people, products mentioned"],
  "links": ["Relevant outbound links"]
}

Return clean JSON only. Use null for missing fields.
```

---

## Product/Pricing Extraction

```
Extract product and pricing information from: [URL]

SCHEMA:
{
  "products": [
    {
      "name": "Product name",
      "price": "Numeric price",
      "currency": "USD/EUR/etc",
      "billing_period": "monthly/yearly/one-time",
      "features": ["List of included features"],
      "limitations": ["Any noted restrictions"]
    }
  ],
  "source_url": "[URL]",
  "extracted_at": "[ISO timestamp]"
}
```

---

## Article/News Extraction

```
Extract key information from this article: [URL]

SCHEMA:
{
  "headline": "Article title",
  "publication": "Source name",
  "author": "Author name if available",
  "date_published": "Publication date",
  "summary": "2-3 sentence summary",
  "key_claims": ["Main claims or findings"],
  "statistics": ["Any numbers/data cited"],
  "quotes": ["Notable quotes with attribution"],
  "sources_cited": ["Sources mentioned in article"]
}
```

---

## Directory/Listing Extraction

```
Extract all items from this directory/listing page: [URL]

For each item, capture:
{
  "name": "Item name",
  "description": "Brief description",
  "url": "Link to detail page",
  "category": "Category if shown",
  "metadata": { ...any additional visible fields... }
}

Return as JSON array. Note if pagination exists.
```

---

## Company Profile Extraction

```
Extract company information from: [URL]

SCHEMA:
{
  "company_name": "Official name",
  "description": "What they do",
  "founded": "Year founded",
  "headquarters": "Location",
  "employees": "Employee count or range",
  "funding": "Funding amount if available",
  "products": ["Main products/services"],
  "leadership": [{"name": "", "title": ""}],
  "contact": {
    "website": "",
    "email": "",
    "phone": ""
  }
}
```

---

## Review/Sentiment Extraction

```
Extract review data from: [URL]

SCHEMA:
{
  "platform": "Review platform name",
  "product_reviewed": "Product/company name",
  "overall_rating": "X/5 or X/10",
  "review_count": "Number of reviews",
  "rating_breakdown": {
    "5_star": "count or %",
    "4_star": "",
    "3_star": "",
    "2_star": "",
    "1_star": ""
  },
  "common_pros": ["Frequently mentioned positives"],
  "common_cons": ["Frequently mentioned negatives"],
  "sample_reviews": [
    {
      "rating": "",
      "title": "",
      "snippet": "Brief excerpt",
      "date": ""
    }
  ]
}
```

---

## Job Listing Extraction

```
Extract job listing data from: [URL]

SCHEMA:
{
  "job_title": "Position title",
  "company": "Hiring company",
  "location": "Job location",
  "remote": "true/false/hybrid",
  "salary_range": {
    "min": "",
    "max": "",
    "currency": ""
  },
  "experience_required": "Years or level",
  "skills_required": ["List of skills"],
  "benefits": ["Listed benefits"],
  "posted_date": "When posted",
  "application_url": "Apply link"
}
```

---

## Event/Conference Extraction

```
Extract event information from: [URL]

SCHEMA:
{
  "event_name": "Official name",
  "dates": {
    "start": "Start date",
    "end": "End date"
  },
  "location": {
    "venue": "",
    "city": "",
    "country": "",
    "virtual": "true/false"
  },
  "description": "Event description",
  "speakers": ["Notable speakers"],
  "topics": ["Main topics/tracks"],
  "pricing": [
    {"tier": "", "price": "", "includes": []}
  ],
  "registration_url": ""
}
```

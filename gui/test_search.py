#!/usr/bin/env python3
"""Test the research flow."""

import os
import json
import anthropic
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set up path
import sys
sys.path.insert(0, '.')

# Check for API key
api_key = os.environ.get('ANTHROPIC_API_KEY')
if not api_key:
    # Try to read from secrets
    try:
        import tomllib
        with open('.streamlit/secrets.toml', 'rb') as f:
            secrets = tomllib.load(f)
            api_key = secrets.get('ANTHROPIC_API_KEY', '')
    except:
        pass

if not api_key:
    print("❌ No API key found. Set ANTHROPIC_API_KEY or add to .streamlit/secrets.toml")
    exit(1)

client = anthropic.Anthropic(api_key=api_key)

# Import extraction if available
try:
    from extraction import MultiStrategyExtractor, fetch_html_sync
    EXTRACTION_AVAILABLE = True
except ImportError:
    EXTRACTION_AVAILABLE = False
    print("⚠️ Extraction module not available, using LLM only")

print("🔬 Research Assistant - Test Search")
print("=" * 50)

query = "Compare pricing for Notion vs Obsidian vs Roam Research"
print(f"\n📝 Query: {query}\n")

# Step 1: Understand query
print("1️⃣ Understanding request...")
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1000,
    messages=[{"role": "user", "content": f"""Analyze this research request:

"{query}"

Return JSON:
{{
    "clear": true/false,
    "type": "pricing|comparison|features|general",
    "subjects": ["what to research"],
    "data_needed": ["specific data points"],
    "clarification": "question if unclear, or null",
    "schema": {{"field": "what to extract"}}
}}"""}]
)
text = response.content[0].text
if "```" in text:
    text = text.split("```")[1].replace("json", "").strip()
parsed = json.loads(text)
print(f"   Type: {parsed.get('type')}")
print(f"   Subjects: {parsed.get('subjects')}")
print(f"   Schema: {list(parsed.get('schema', {}).keys())}")

# Step 2: Find sources
print("\n2️⃣ Finding sources...")
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1500,
    messages=[{"role": "user", "content": f"""Find 6 URLs for researching: {query}
Subjects: {', '.join(parsed.get('subjects', []))}

Return JSON array: [{{"url": "...", "title": "...", "type": "official|review|news"}}]"""}]
)
text = response.content[0].text
if "```" in text:
    text = text.split("```")[1].replace("json", "").strip()
sources = json.loads(text)
print(f"   Found {len(sources)} sources:")
for s in sources[:4]:
    print(f"   • {s.get('title', s.get('url', 'Unknown'))[:50]}")

# Step 3: Extract data
print("\n3️⃣ Extracting data...")
schema = parsed.get('schema', {'name': 'Name', 'price': 'Price'})

def extract(url_info):
    url = url_info['url']
    html = None

    if EXTRACTION_AVAILABLE:
        try:
            html, _ = fetch_html_sync(url, timeout=8)
            if html:
                extractor = MultiStrategyExtractor(html, url)
                result = extractor.extract_all(schema)
                if result.confidence >= 0.5:
                    print(f"   ✅ {url[:40]}... (fast extraction)")
                    return {**result.data, '_url': url, '_method': 'fast', '_ok': True}
        except:
            pass

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            messages=[{"role": "user", "content": f"""Extract from {url}:
{f'Content: {html[:2000]}' if html else ''}
Schema: {json.dumps(schema)}
Return JSON."""}]
        )
        text = response.content[0].text
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        data = json.loads(text)
        print(f"   ✅ {url[:40]}... (LLM)")
        return {**data, '_url': url, '_method': 'llm', '_ok': True}
    except Exception as e:
        print(f"   ❌ {url[:40]}... ({e})")
        return {'_url': url, '_error': str(e), '_ok': False}

results = []
with ThreadPoolExecutor(max_workers=4) as ex:
    futures = {ex.submit(extract, s): s for s in sources}
    for future in as_completed(futures):
        results.append(future.result())

successful = sum(1 for r in results if r.get('_ok'))
print(f"\n   Extracted: {successful}/{len(results)} successful")

# Step 4: Synthesize
print("\n4️⃣ Synthesizing findings...")
good = [r for r in results if r.get('_ok')]

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=2000,
    messages=[{"role": "user", "content": f"""Synthesize research on: {query}

Data ({len(good)} sources):
{json.dumps(good, indent=2)}

Return JSON:
{{
    "summary": "2-3 sentence summary",
    "findings": ["key finding 1", "key finding 2"],
    "table": {{"headers": ["Name", "Price", ...], "rows": [["A", "$10", ...], ...]}},
    "recommendation": "brief recommendation"
}}"""}]
)
text = response.content[0].text
if "```" in text:
    text = text.split("```")[1].replace("json", "").strip()
synthesis = json.loads(text)

# Print results
print("\n" + "=" * 50)
print("📊 RESULTS")
print("=" * 50)

print(f"\n📝 Summary:\n{synthesis.get('summary', 'N/A')}")

if synthesis.get('findings'):
    print("\n🔍 Key Findings:")
    for f in synthesis['findings']:
        print(f"   • {f}")

if synthesis.get('table'):
    table = synthesis['table']
    if table.get('headers') and table.get('rows'):
        print("\n📋 Comparison:")
        headers = table['headers']
        print("   " + " | ".join(h[:15].ljust(15) for h in headers))
        print("   " + "-" * (17 * len(headers)))
        for row in table['rows'][:5]:
            print("   " + " | ".join(str(c)[:15].ljust(15) for c in row))

if synthesis.get('recommendation'):
    print(f"\n💡 Recommendation:\n   {synthesis['recommendation']}")

print("\n✅ Test complete!")

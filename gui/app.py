"""
Web Research Orchestrator - Streamlit GUI
A visual interface for running multi-model web research with Claude.
"""

import streamlit as st
import anthropic
import json
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import os

# Page config
st.set_page_config(
    page_title="Web Research Orchestrator",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(90deg, #e94560, #ff6b6b);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .subtitle {
        color: #888;
        font-size: 1.1rem;
        margin-top: 0;
    }
    .metric-card {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 20px;
        border: 1px solid #333;
    }
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #e94560, #ff6b6b);
    }
    .result-card {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        border-left: 4px solid #e94560;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if 'research_history' not in st.session_state:
        st.session_state.research_history = []
    if 'current_results' not in st.session_state:
        st.session_state.current_results = None
    if 'api_key' not in st.session_state:
        st.session_state.api_key = os.environ.get('ANTHROPIC_API_KEY', '')


def get_client():
    """Get Anthropic client."""
    api_key = st.session_state.api_key or os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)


def run_haiku_worker(client, url: str, schema: dict, worker_id: int, model: str = "claude-3-5-haiku-20241022") -> dict:
    """Run a worker to extract data from a URL."""
    prompt = f"""You are a data extraction worker. Extract structured data from this URL.

URL: {url}

EXTRACTION SCHEMA:
{json.dumps(schema, indent=2)}

INSTRUCTIONS:
1. Analyze the content from the URL
2. Extract data matching the schema
3. Return ONLY valid JSON
4. Use null for missing fields
5. If you cannot access the content, return {{"error": "reason", "url": "{url}"}}

Return only the JSON object, no other text."""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text.strip()

        # Try to parse JSON from response
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        result = json.loads(result_text)
        result['_worker_id'] = worker_id
        result['_url'] = url
        result['_success'] = 'error' not in result
        result['_attempt'] = 1
        return result

    except json.JSONDecodeError:
        return {
            '_worker_id': worker_id,
            '_url': url,
            '_success': False,
            '_attempt': 1,
            'error': 'Failed to parse response as JSON',
            'raw_response': result_text[:500] if 'result_text' in locals() else 'No response'
        }
    except Exception as e:
        return {
            '_worker_id': worker_id,
            '_url': url,
            '_success': False,
            '_attempt': 1,
            'error': str(e)
        }


def run_discovery_search(client, topic: str, num_results: int = 10, model: str = "claude-sonnet-4-20250514") -> list:
    """Use Claude to generate relevant search queries and find URLs."""
    prompt = f"""You are a research assistant. For the topic below, provide a list of {num_results} specific, real URLs that would be valuable sources for research.

TOPIC: {topic}

Return ONLY a JSON array of objects with this format:
[
  {{"url": "https://example.com/page", "title": "Page Title", "type": "official|news|research|blog", "relevance": "high|medium"}}
]

Focus on:
- Official company/product pages
- Reputable news sources
- Industry reports
- Documentation

Return only the JSON array, no other text."""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text.strip()

        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        return json.loads(result_text)

    except Exception as e:
        st.error(f"Discovery search failed: {e}")
        return []


def analyze_failures_and_get_recovery_strategy(client, topic: str, failed_results: list, schema: dict, model: str = "claude-sonnet-4-20250514") -> dict:
    """Analyze why extractions failed and generate recovery strategies."""

    failures_summary = []
    for r in failed_results:
        failures_summary.append({
            "url": r.get('_url', 'unknown'),
            "error": r.get('error', 'unknown error')
        })

    prompt = f"""You are a research strategist. The initial data extraction attempt failed for several sources.

ORIGINAL TOPIC: {topic}

FAILED EXTRACTIONS:
{json.dumps(failures_summary, indent=2)}

DESIRED DATA SCHEMA:
{json.dumps(schema, indent=2)}

Analyze these failures and provide alternative strategies to get the same data.

Return a JSON object with:
{{
  "failure_analysis": "Brief analysis of why sources failed (e.g., bot protection, JS rendering, paywalls)",
  "alternative_strategies": [
    {{
      "strategy": "description of approach",
      "search_queries": ["query 1", "query 2"],
      "source_types": ["news articles", "comparison sites", "government data", "research reports", "social media", "forums", "cached/archive versions"],
      "expected_data_quality": "high|medium|low"
    }}
  ],
  "alternative_urls": [
    {{"url": "https://...", "title": "...", "type": "...", "rationale": "why this might work"}}
  ],
  "web_search_queries": ["specific search queries to find the data via search engines"]
}}

Focus on:
1. News articles that might contain the data
2. Comparison/review sites
3. Industry reports or aggregators
4. Government or regulatory databases
5. Forums/Reddit discussions with cited data
6. Archive.org cached versions
7. Data aggregation APIs

Return only the JSON object."""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text.strip()

        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        return json.loads(result_text)

    except Exception as e:
        return {"error": str(e)}


def run_recovery_search_worker(client, query: str, topic: str, schema: dict, worker_id: int, model: str = "claude-3-5-haiku-20241022") -> dict:
    """Run a recovery worker that searches and extracts data using web search."""

    prompt = f"""You are a research recovery worker. The direct website extraction failed, so you need to find the data through alternative means.

RESEARCH TOPIC: {topic}

SEARCH QUERY TO INVESTIGATE: {query}

DATA WE NEED (schema):
{json.dumps(schema, indent=2)}

YOUR TASK:
1. Based on your knowledge, provide what data you know about this query
2. Cite specific sources where this data can typically be found
3. If you have concrete data points, include them
4. Be honest about confidence levels

Return JSON:
{{
  "query": "{query}",
  "found_data": {{ ...data matching schema as best as possible... }},
  "sources_cited": ["source 1", "source 2"],
  "confidence": "high|medium|low",
  "notes": "any caveats or context",
  "suggested_manual_sources": ["URLs or source names to check manually"]
}}

Return only the JSON object."""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text.strip()

        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        result = json.loads(result_text)
        result['_worker_id'] = worker_id
        result['_recovery'] = True
        result['_success'] = result.get('confidence') in ['high', 'medium']
        result['_attempt'] = 2
        return result

    except Exception as e:
        return {
            '_worker_id': worker_id,
            '_recovery': True,
            '_success': False,
            '_attempt': 2,
            'error': str(e),
            'query': query
        }


def run_alternative_url_worker(client, url_info: dict, schema: dict, worker_id: int, model: str = "claude-3-5-haiku-20241022") -> dict:
    """Try to extract from an alternative URL suggested by recovery strategy."""

    url = url_info.get('url', '')
    rationale = url_info.get('rationale', '')

    prompt = f"""You are a data extraction worker trying an alternative source.

URL: {url}
WHY THIS SOURCE: {rationale}

EXTRACTION SCHEMA:
{json.dumps(schema, indent=2)}

INSTRUCTIONS:
1. This is a fallback attempt - the primary sources were blocked
2. Extract whatever data you can that matches the schema
3. This might be a news article, comparison site, or aggregator
4. Partial data is better than no data
5. Note the source type and any limitations

Return JSON:
{{
  "source_url": "{url}",
  "source_type": "news|comparison|aggregator|forum|archive|other",
  ...schema fields...,
  "data_freshness": "current|recent|dated|unknown",
  "confidence": "high|medium|low",
  "limitations": ["any caveats"]
}}

If you cannot access, return {{"error": "reason", "url": "{url}"}}

Return only the JSON object."""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text.strip()

        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        result = json.loads(result_text)
        result['_worker_id'] = worker_id
        result['_url'] = url
        result['_recovery'] = True
        result['_success'] = 'error' not in result
        result['_attempt'] = 2
        return result

    except Exception as e:
        return {
            '_worker_id': worker_id,
            '_url': url,
            '_recovery': True,
            '_success': False,
            '_attempt': 2,
            'error': str(e)
        }


def synthesize_results(client, topic: str, results: list, recovery_results: list = None, model: str = "claude-sonnet-4-20250514") -> dict:
    """Use Sonnet to synthesize results into a final report."""

    all_results = results.copy()
    if recovery_results:
        all_results.extend(recovery_results)

    # Separate successful and failed
    successful = [r for r in all_results if r.get('_success', False)]
    failed = [r for r in all_results if not r.get('_success', False)]

    prompt = f"""Synthesize these research results into a comprehensive summary.

RESEARCH TOPIC: {topic}

SUCCESSFUL EXTRACTIONS ({len(successful)}):
{json.dumps(successful, indent=2)}

FAILED EXTRACTIONS ({len(failed)}):
{json.dumps([{{'url': r.get('_url', r.get('query', 'unknown')), 'error': r.get('error', 'unknown')}} for r in failed], indent=2)}

Create a synthesis with:
1. Executive Summary (3-5 sentences) - focus on what WAS found
2. Key Findings (bullet points) - actual data discovered
3. Data Quality Assessment - based on sources and confidence
4. Gaps and Limitations - what couldn't be found and why
5. Recommendations - how to get missing data manually

Return as JSON:
{{
  "executive_summary": "...",
  "key_findings": ["...", "..."],
  "quality_assessment": {{"completeness": "X%", "confidence": "high|medium|low", "sources_used": N}},
  "gaps": ["...", "..."],
  "recommendations": ["...", "..."],
  "manual_followup_needed": ["specific things to check manually"]
}}"""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text.strip()

        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        return json.loads(result_text)

    except Exception as e:
        return {"error": str(e), "raw_results": all_results}


def main():
    init_session_state()

    # Header
    st.markdown('<p class="main-header">🔬 Web Research Orchestrator</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Multi-model research with automatic retry & recovery</p>', unsafe_allow_html=True)
    st.divider()

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")

        # API Key
        api_key_input = st.text_input(
            "Anthropic API Key",
            value=st.session_state.api_key,
            type="password",
            help="Your Anthropic API key. Set ANTHROPIC_API_KEY env var to skip this."
        )
        if api_key_input:
            st.session_state.api_key = api_key_input

        st.divider()

        # Model selection
        st.subheader("Models")
        orchestrator_model = st.selectbox(
            "Orchestrator",
            ["claude-sonnet-4-20250514", "claude-opus-4-5-20251101"],
            help="Model for planning and synthesis"
        )
        worker_model = st.selectbox(
            "Workers",
            ["claude-3-5-haiku-20241022", "claude-sonnet-4-20250514"],
            help="Model for data extraction"
        )

        st.divider()

        # Worker settings
        st.subheader("Workers")
        max_workers = st.slider("Max Parallel Workers", 1, 10, 5)

        st.divider()

        # Recovery settings
        st.subheader("🔄 Recovery Settings")
        enable_recovery = st.checkbox("Enable automatic retry", value=True, help="Try alternative sources if primary extraction fails")
        recovery_threshold = st.slider("Retry if success rate below", 0, 100, 50, format="%d%%", help="Trigger recovery if fewer than X% of sources succeed")

        st.divider()

        # History
        st.subheader("📜 Research History")
        if st.session_state.research_history:
            for i, item in enumerate(reversed(st.session_state.research_history[-5:])):
                with st.expander(f"{item['topic'][:30]}...", expanded=False):
                    st.caption(item['timestamp'])
                    if st.button("Load", key=f"load_{i}"):
                        st.session_state.current_results = item['results']
                        st.rerun()
        else:
            st.caption("No research history yet")

    # Main content
    tab1, tab2, tab3 = st.tabs(["🔍 New Research", "📊 Results", "📥 Export"])

    with tab1:
        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("Research Topic")
            topic = st.text_area(
                "What would you like to research?",
                placeholder="e.g., Compare pricing for top 5 project management tools (Asana, Monday, Notion, ClickUp, Linear)",
                height=100
            )

            research_type = st.radio(
                "Research Type",
                ["🎯 Custom URLs", "🔍 Auto-Discovery"],
                horizontal=True
            )

        with col2:
            st.subheader("Extraction Schema")
            default_schema = {
                "title": "Page title",
                "main_points": ["Key points"],
                "data": {},
                "confidence": "high|medium|low"
            }
            schema_json = st.text_area(
                "JSON Schema",
                value=json.dumps(default_schema, indent=2),
                height=200
            )

            try:
                schema = json.loads(schema_json)
                st.success("✓ Valid JSON")
            except:
                st.error("Invalid JSON")
                schema = default_schema

        st.divider()

        if research_type == "🎯 Custom URLs":
            st.subheader("URLs to Research")
            urls_input = st.text_area(
                "Enter URLs (one per line)",
                placeholder="https://asana.com/pricing\nhttps://monday.com/pricing\nhttps://notion.so/pricing",
                height=150
            )
            urls = [u.strip() for u in urls_input.strip().split('\n') if u.strip()]
        else:
            num_sources = st.slider("Number of sources to discover", 5, 20, 10)
            urls = []

        # Run button
        if st.button("🚀 Start Research", type="primary", use_container_width=True):
            client = get_client()

            if not client:
                st.error("Please enter your Anthropic API key in the sidebar")
            elif not topic:
                st.error("Please enter a research topic")
            else:
                results = {
                    'topic': topic,
                    'timestamp': datetime.now().isoformat(),
                    'schema': schema,
                    'sources': [],
                    'extraction_results': [],
                    'recovery_results': [],
                    'recovery_strategy': None,
                    'synthesis': None
                }

                # Phase 1: Discovery (if auto-discovery)
                if research_type == "🔍 Auto-Discovery":
                    with st.status("🔍 Discovering sources...", expanded=True) as status:
                        st.write(f"Using {orchestrator_model.split('-')[1].title()} to find relevant URLs...")
                        discovered = run_discovery_search(client, topic, num_sources, model=orchestrator_model)
                        urls = [d['url'] for d in discovered]
                        results['sources'] = discovered

                        if urls:
                            st.write(f"Found {len(urls)} sources:")
                            for d in discovered:
                                st.write(f"  • [{d.get('type', 'unknown')}] {d.get('title', d['url'][:50])}")
                        status.update(label=f"✓ Found {len(urls)} sources", state="complete")
                else:
                    results['sources'] = [{'url': u} for u in urls]

                if not urls:
                    st.error("No URLs to research. Please add URLs or try auto-discovery.")
                else:
                    # Phase 2: Initial extraction
                    with st.status(f"⚡ Extracting data from {len(urls)} sources...", expanded=True) as status:
                        progress_bar = st.progress(0)
                        progress_text = st.empty()

                        extraction_results = []

                        with ThreadPoolExecutor(max_workers=max_workers) as executor:
                            futures = {
                                executor.submit(run_haiku_worker, client, url, schema, i, model=worker_model): (i, url)
                                for i, url in enumerate(urls)
                            }

                            completed = 0
                            for future in as_completed(futures):
                                worker_id, url = futures[future]
                                result = future.result()
                                extraction_results.append(result)

                                completed += 1
                                progress_bar.progress(completed / len(urls))
                                status_icon = "✅" if result.get('_success') else "❌"
                                progress_text.write(f"{status_icon} {completed}/{len(urls)}: {url[:50]}...")

                        results['extraction_results'] = extraction_results
                        success_count = sum(1 for r in extraction_results if r.get('_success', False))
                        success_rate = (success_count / len(urls)) * 100 if urls else 0
                        status.update(
                            label=f"✓ Initial extraction: {success_count}/{len(urls)} sources ({success_rate:.0f}%)",
                            state="complete"
                        )

                    # Phase 3: Recovery (if enabled and needed)
                    failed_results = [r for r in extraction_results if not r.get('_success', False)]
                    recovery_results = []

                    if enable_recovery and success_rate < recovery_threshold and failed_results:
                        # Phase 3a: Analyze failures and get strategy
                        with st.status("🔄 Analyzing failures and planning recovery...", expanded=True) as status:
                            st.write(f"⚠️ Only {success_rate:.0f}% success rate - initiating recovery...")
                            st.write("Analyzing why extractions failed...")

                            recovery_strategy = analyze_failures_and_get_recovery_strategy(
                                client, topic, failed_results, schema, model=orchestrator_model
                            )
                            results['recovery_strategy'] = recovery_strategy

                            if 'error' not in recovery_strategy:
                                st.write(f"📋 Analysis: {recovery_strategy.get('failure_analysis', 'Unknown')}")
                                st.write(f"📍 Found {len(recovery_strategy.get('alternative_urls', []))} alternative URLs")
                                st.write(f"🔎 Generated {len(recovery_strategy.get('web_search_queries', []))} search queries")

                            status.update(label="✓ Recovery strategy ready", state="complete")

                        # Phase 3b: Execute recovery
                        if 'error' not in recovery_strategy:
                            with st.status("🔄 Executing recovery attempts...", expanded=True) as status:
                                progress_bar = st.progress(0)
                                progress_text = st.empty()

                                # Collect all recovery tasks
                                alt_urls = recovery_strategy.get('alternative_urls', [])[:5]  # Limit to 5
                                search_queries = recovery_strategy.get('web_search_queries', [])[:5]  # Limit to 5

                                total_recovery = len(alt_urls) + len(search_queries)

                                if total_recovery > 0:
                                    st.write(f"Trying {len(alt_urls)} alternative URLs and {len(search_queries)} search queries...")

                                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                                        futures = {}

                                        # Submit alternative URL workers
                                        for i, url_info in enumerate(alt_urls):
                                            futures[executor.submit(
                                                run_alternative_url_worker, client, url_info, schema, i, model=worker_model
                                            )] = ('url', i, url_info.get('url', 'unknown'))

                                        # Submit search query workers
                                        for i, query in enumerate(search_queries):
                                            futures[executor.submit(
                                                run_recovery_search_worker, client, query, topic, schema, len(alt_urls) + i, model=worker_model
                                            )] = ('search', i, query)

                                        completed = 0
                                        for future in as_completed(futures):
                                            task_type, idx, identifier = futures[future]
                                            result = future.result()
                                            recovery_results.append(result)

                                            completed += 1
                                            progress_bar.progress(completed / total_recovery)
                                            status_icon = "✅" if result.get('_success') else "❌"
                                            progress_text.write(f"{status_icon} Recovery {completed}/{total_recovery}: {identifier[:50]}...")

                                    results['recovery_results'] = recovery_results
                                    recovery_success = sum(1 for r in recovery_results if r.get('_success', False))
                                    status.update(
                                        label=f"✓ Recovery complete: {recovery_success}/{total_recovery} additional sources",
                                        state="complete"
                                    )
                                else:
                                    st.write("No recovery strategies available")
                                    status.update(label="✓ No recovery options", state="complete")

                    # Phase 4: Final synthesis
                    with st.status("🧠 Synthesizing all results...", expanded=True) as status:
                        total_success = sum(1 for r in extraction_results if r.get('_success', False))
                        total_success += sum(1 for r in recovery_results if r.get('_success', False))
                        st.write(f"Synthesizing {total_success} successful extractions...")

                        synthesis = synthesize_results(
                            client, topic, extraction_results, recovery_results, model=orchestrator_model
                        )
                        results['synthesis'] = synthesis
                        status.update(label="✓ Synthesis complete", state="complete")

                    # Save results
                    st.session_state.current_results = results
                    st.session_state.research_history.append({
                        'topic': topic,
                        'timestamp': results['timestamp'],
                        'results': results
                    })

                    # Final summary
                    total_attempted = len(extraction_results) + len(recovery_results)
                    total_success = sum(1 for r in extraction_results + recovery_results if r.get('_success', False))

                    if total_success > 0:
                        st.success(f"✅ Research complete! Found data from {total_success}/{total_attempted} sources. Check the Results tab.")
                        st.balloons()
                    else:
                        st.warning(f"⚠️ Research complete but no data could be extracted. Check Results tab for recommendations.")

    with tab2:
        if st.session_state.current_results:
            results = st.session_state.current_results

            st.subheader(f"📋 {results['topic']}")
            st.caption(f"Completed: {results['timestamp']}")

            # Synthesis
            if results.get('synthesis') and 'error' not in results['synthesis']:
                synthesis = results['synthesis']

                st.markdown("### Executive Summary")
                st.info(synthesis.get('executive_summary', 'No summary available'))

                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("### Key Findings")
                    for finding in synthesis.get('key_findings', []):
                        st.markdown(f"• {finding}")

                with col2:
                    st.markdown("### Quality Assessment")
                    qa = synthesis.get('quality_assessment', {})
                    st.metric("Completeness", qa.get('completeness', 'N/A'))
                    st.metric("Confidence", qa.get('confidence', 'N/A'))
                    st.metric("Sources Used", qa.get('sources_used', 'N/A'))

                if synthesis.get('gaps'):
                    st.markdown("### Gaps & Limitations")
                    for gap in synthesis['gaps']:
                        st.markdown(f"• {gap}")

                if synthesis.get('recommendations'):
                    st.markdown("### 💡 Recommendations")
                    for rec in synthesis['recommendations']:
                        st.markdown(f"• {rec}")

                if synthesis.get('manual_followup_needed'):
                    st.markdown("### 📝 Manual Follow-up Needed")
                    for item in synthesis['manual_followup_needed']:
                        st.markdown(f"• {item}")

            st.divider()

            # Recovery strategy (if used)
            if results.get('recovery_strategy') and 'error' not in results.get('recovery_strategy', {}):
                with st.expander("🔄 Recovery Strategy Used"):
                    strategy = results['recovery_strategy']
                    st.write(f"**Failure Analysis:** {strategy.get('failure_analysis', 'N/A')}")

                    if strategy.get('alternative_urls'):
                        st.write("**Alternative URLs Tried:**")
                        for url_info in strategy['alternative_urls']:
                            st.write(f"  • {url_info.get('url', 'N/A')} - {url_info.get('rationale', '')}")

                    if strategy.get('web_search_queries'):
                        st.write("**Search Queries Used:**")
                        for query in strategy['web_search_queries']:
                            st.write(f"  • {query}")

            # Raw results table
            st.markdown("### 📊 Extraction Results")

            all_results = results.get('extraction_results', []) + results.get('recovery_results', [])
            if all_results:
                # Create DataFrame for display
                df_data = []
                for r in all_results:
                    source = r.get('_url', r.get('query', 'N/A'))
                    row = {
                        'Source': source[:50] + '...' if len(source) > 50 else source,
                        'Type': 'Recovery' if r.get('_recovery') else 'Primary',
                        'Status': '✅' if r.get('_success') else '❌',
                        'Confidence': r.get('confidence', '-'),
                        'Error': r.get('error', '-') if not r.get('_success') else '-'
                    }
                    df_data.append(row)

                df = pd.DataFrame(df_data)
                st.dataframe(df, use_container_width=True)

                # Expandable raw JSON
                with st.expander("View Raw JSON"):
                    st.json(all_results)
        else:
            st.info("No results yet. Run a research query in the 'New Research' tab.")

    with tab3:
        if st.session_state.current_results:
            results = st.session_state.current_results

            st.subheader("📥 Export Results")

            col1, col2, col3 = st.columns(3)

            with col1:
                # JSON export
                json_str = json.dumps(results, indent=2, default=str)
                st.download_button(
                    "📄 Download JSON",
                    json_str,
                    file_name=f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    use_container_width=True
                )

            with col2:
                # CSV export (extraction results only)
                all_results = results.get('extraction_results', []) + results.get('recovery_results', [])
                if all_results:
                    df = pd.json_normalize(all_results)
                    csv = df.to_csv(index=False)
                    st.download_button(
                        "📊 Download CSV",
                        csv,
                        file_name=f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )

            with col3:
                # Markdown export
                md = f"""# Research Report: {results['topic']}

**Date:** {results['timestamp']}

## Executive Summary

{results.get('synthesis', {}).get('executive_summary', 'N/A')}

## Key Findings

"""
                for finding in results.get('synthesis', {}).get('key_findings', []):
                    md += f"- {finding}\n"

                md += f"""
## Quality Assessment

- **Completeness:** {results.get('synthesis', {}).get('quality_assessment', {}).get('completeness', 'N/A')}
- **Confidence:** {results.get('synthesis', {}).get('quality_assessment', {}).get('confidence', 'N/A')}

## Gaps & Limitations

"""
                for gap in results.get('synthesis', {}).get('gaps', []):
                    md += f"- {gap}\n"

                md += """
## Recommendations

"""
                for rec in results.get('synthesis', {}).get('recommendations', []):
                    md += f"- {rec}\n"

                md += """
## Sources

"""
                for source in results.get('sources', []):
                    md += f"- {source.get('url', 'N/A')}\n"

                st.download_button(
                    "📝 Download Markdown",
                    md,
                    file_name=f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown",
                    use_container_width=True
                )

            st.divider()

            # Preview
            st.markdown("### Preview")
            preview_format = st.radio("Format", ["JSON", "Markdown"], horizontal=True)

            if preview_format == "JSON":
                st.json(results)
            else:
                st.markdown(md)
        else:
            st.info("No results to export. Run a research query first.")


if __name__ == "__main__":
    main()

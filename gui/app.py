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


def run_haiku_worker(client, url: str, schema: dict, worker_id: int) -> dict:
    """Run a single Haiku worker to extract data from a URL."""
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
            model="claude-3-5-haiku-latest",
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
        return result

    except json.JSONDecodeError:
        return {
            '_worker_id': worker_id,
            '_url': url,
            '_success': False,
            'error': 'Failed to parse response as JSON',
            'raw_response': result_text[:500] if 'result_text' in locals() else 'No response'
        }
    except Exception as e:
        return {
            '_worker_id': worker_id,
            '_url': url,
            '_success': False,
            'error': str(e)
        }


def run_discovery_search(client, topic: str, num_results: int = 10) -> list:
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
            model="claude-3-5-sonnet-latest",
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


def synthesize_results(client, topic: str, results: list) -> dict:
    """Use Sonnet to synthesize results into a final report."""
    prompt = f"""Synthesize these research results into a comprehensive summary.

RESEARCH TOPIC: {topic}

RAW RESULTS:
{json.dumps(results, indent=2)}

Create a synthesis with:
1. Executive Summary (3-5 sentences)
2. Key Findings (bullet points)
3. Data Quality Assessment
4. Gaps and Limitations

Return as JSON:
{{
  "executive_summary": "...",
  "key_findings": ["...", "..."],
  "quality_assessment": {{"completeness": "X%", "confidence": "high|medium|low"}},
  "gaps": ["...", "..."],
  "recommendations": ["...", "..."]
}}"""

    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-latest",
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
        return {"error": str(e), "raw_results": results}


def main():
    init_session_state()

    # Header
    st.markdown('<p class="main-header">🔬 Web Research Orchestrator</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Multi-model research with Opus strategy + Haiku workers</p>', unsafe_allow_html=True)
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
            ["claude-3-5-sonnet-latest", "claude-3-opus-latest"],
            help="Model for planning and synthesis"
        )
        worker_model = st.selectbox(
            "Workers",
            ["claude-3-5-haiku-latest", "claude-3-5-sonnet-latest"],
            help="Model for data extraction"
        )

        st.divider()

        # Worker settings
        st.subheader("Workers")
        max_workers = st.slider("Max Parallel Workers", 1, 10, 5)

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
                    'synthesis': None
                }

                # Phase 1: Discovery (if auto-discovery)
                if research_type == "🔍 Auto-Discovery":
                    with st.status("🔍 Discovering sources...", expanded=True) as status:
                        st.write("Using Sonnet to find relevant URLs...")
                        discovered = run_discovery_search(client, topic, num_sources)
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
                    # Phase 2: Parallel extraction
                    with st.status(f"⚡ Extracting data from {len(urls)} sources...", expanded=True) as status:
                        progress_bar = st.progress(0)
                        progress_text = st.empty()

                        extraction_results = []

                        with ThreadPoolExecutor(max_workers=max_workers) as executor:
                            futures = {
                                executor.submit(run_haiku_worker, client, url, schema, i): (i, url)
                                for i, url in enumerate(urls)
                            }

                            completed = 0
                            for future in as_completed(futures):
                                worker_id, url = futures[future]
                                result = future.result()
                                extraction_results.append(result)

                                completed += 1
                                progress_bar.progress(completed / len(urls))
                                progress_text.write(f"Completed {completed}/{len(urls)}: {url[:50]}...")

                        results['extraction_results'] = extraction_results
                        success_count = sum(1 for r in extraction_results if r.get('_success', False))
                        status.update(
                            label=f"✓ Extracted data from {success_count}/{len(urls)} sources",
                            state="complete"
                        )

                    # Phase 3: Synthesis
                    with st.status("🧠 Synthesizing results...", expanded=True) as status:
                        st.write("Using Sonnet to analyze and synthesize findings...")
                        synthesis = synthesize_results(client, topic, extraction_results)
                        results['synthesis'] = synthesis
                        status.update(label="✓ Synthesis complete", state="complete")

                    # Save results
                    st.session_state.current_results = results
                    st.session_state.research_history.append({
                        'topic': topic,
                        'timestamp': results['timestamp'],
                        'results': results
                    })

                    st.success("✅ Research complete! Check the Results tab.")
                    st.balloons()

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

                if synthesis.get('gaps'):
                    st.markdown("### Gaps & Limitations")
                    for gap in synthesis['gaps']:
                        st.markdown(f"• {gap}")

            st.divider()

            # Raw results table
            st.markdown("### 📊 Extraction Results")

            extraction_results = results.get('extraction_results', [])
            if extraction_results:
                # Create DataFrame for display
                df_data = []
                for r in extraction_results:
                    row = {
                        'URL': r.get('_url', 'N/A')[:50] + '...' if len(r.get('_url', '')) > 50 else r.get('_url', 'N/A'),
                        'Status': '✅' if r.get('_success') else '❌',
                        'Error': r.get('error', '-') if not r.get('_success') else '-'
                    }
                    # Add schema fields
                    for key in results['schema'].keys():
                        if key in r:
                            val = r[key]
                            if isinstance(val, (list, dict)):
                                val = json.dumps(val)[:100]
                            row[key] = val
                    df_data.append(row)

                df = pd.DataFrame(df_data)
                st.dataframe(df, use_container_width=True)

                # Expandable raw JSON
                with st.expander("View Raw JSON"):
                    st.json(extraction_results)
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
                if results.get('extraction_results'):
                    df = pd.json_normalize(results['extraction_results'])
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

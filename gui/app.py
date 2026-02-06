"""
Web Research Orchestrator - Enhanced Edition
Features: Brave Search, Firecrawl, streaming, export, history, caching, cost tracking
"""

import streamlit as st
import json
import os
import hashlib
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Core imports
try:
    import anthropic
    import pandas as pd
    import httpx
except ImportError as e:
    st.error(f"Missing dependency: {e}")
    st.stop()

# Optional extraction module
EXTRACTION_AVAILABLE = False
try:
    from extraction import MultiStrategyExtractor, fetch_html_sync
    EXTRACTION_AVAILABLE = True
except:
    pass

# ============ Configuration ============

MODELS = {
    "planner": "claude-sonnet-4-20250514",
    "extractor": "claude-haiku-4-5-20251001",
    "synthesizer": "claude-sonnet-4-20250514"
}

# Cost per 1M tokens (approximate)
COSTS = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.25, "output": 1.25},
}

# ============ Page Config ============

st.set_page_config(
    page_title="Research Assistant",
    page_icon="🔬",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ============ Styles ============

st.markdown("""
<style>
    #MainMenu, footer, header, .stDeployButton {display: none !important;}

    .main .block-container {
        max-width: 52rem;
        padding: 1rem 1rem 8rem 1rem;
    }

    /* Header */
    .app-header {
        text-align: center;
        padding: 1.5rem 0;
        border-bottom: 1px solid #e5e5e5;
        margin-bottom: 1.5rem;
    }
    .app-header h1 {
        font-size: 1.75rem;
        font-weight: 600;
        margin: 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .app-header p {
        color: #666;
        margin: 0.5rem 0 0 0;
        font-size: 0.95rem;
    }

    /* Status badges */
    .status-bar {
        display: flex;
        gap: 0.5rem;
        justify-content: center;
        margin-top: 0.75rem;
        flex-wrap: wrap;
    }
    .badge {
        font-size: 0.7rem;
        padding: 0.2rem 0.6rem;
        border-radius: 1rem;
        background: #f0f0f0;
        color: #666;
    }
    .badge.active {
        background: #d1fae5;
        color: #065f46;
    }

    /* Messages */
    .user-msg {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.875rem 1.25rem;
        border-radius: 1.25rem 1.25rem 0.25rem 1.25rem;
        margin: 1rem 0 1rem auto;
        max-width: 80%;
        width: fit-content;
    }

    .assistant-msg {
        padding: 0.5rem 0;
    }

    /* Progress */
    .progress-container {
        background: #f8f9fa;
        border-radius: 0.75rem;
        padding: 1rem;
        margin: 1rem 0;
    }
    .progress-step {
        display: flex;
        align-items: center;
        padding: 0.4rem 0;
        color: #666;
        font-size: 0.9rem;
    }
    .progress-step.active {
        color: #1a1a1a;
        font-weight: 500;
    }
    .progress-step.done {
        color: #059669;
    }
    .progress-step .icon {
        width: 1.5rem;
        margin-right: 0.5rem;
    }

    /* Results card */
    .results-card {
        background: white;
        border: 1px solid #e5e5e5;
        border-radius: 0.75rem;
        padding: 1.25rem;
        margin: 1rem 0;
    }
    .results-card h3 {
        margin: 0 0 0.75rem 0;
        font-size: 1rem;
        color: #1a1a1a;
    }

    /* Cost tracker */
    .cost-badge {
        position: fixed;
        bottom: 5rem;
        right: 1rem;
        background: white;
        border: 1px solid #e5e5e5;
        border-radius: 0.5rem;
        padding: 0.4rem 0.75rem;
        font-size: 0.75rem;
        color: #666;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        z-index: 100;
    }

    /* Source pills */
    .source-pill {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 0.75rem;
        font-size: 0.75rem;
        margin: 0.2rem;
        text-decoration: none;
    }
    .source-pill.high { background: #d1fae5; color: #065f46; }
    .source-pill.medium { background: #fef3c7; color: #92400e; }
    .source-pill.low { background: #fee2e2; color: #991b1b; }

    /* Follow-up chips */
    .followup-chips {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 1rem;
    }

    /* Dataframe styling */
    .stDataFrame {
        border: 1px solid #e5e5e5;
        border-radius: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)


# ============ Helper Functions ============

def get_secret(key, default=""):
    """Get secret from Streamlit secrets or environment."""
    try:
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except:
        pass
    return os.environ.get(key, default)


def check_password():
    """Simple password protection."""
    passwords = {}
    try:
        if hasattr(st, 'secrets') and 'passwords' in st.secrets:
            passwords = dict(st.secrets["passwords"])
    except:
        pass

    if not passwords:
        return True

    if st.session_state.get('authenticated'):
        return True

    st.markdown('<div class="app-header"><h1>🔬 Research Assistant</h1><p>Sign in to continue</p></div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Continue", use_container_width=True, type="primary"):
                if username in passwords and passwords[username] == password:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Invalid credentials")
    return False


def init_state():
    """Initialize session state."""
    defaults = {
        'messages': [],
        'history': [],
        'cache': {},
        'total_cost': 0.0,
        'session_cost': 0.0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def get_client():
    """Get Anthropic client."""
    key = get_secret('ANTHROPIC_API_KEY')
    if not key:
        return None
    return anthropic.Anthropic(api_key=key)


def cache_key(url):
    """Generate cache key for URL."""
    return hashlib.md5(url.encode()).hexdigest()


def track_cost(model, input_tokens, output_tokens):
    """Track API costs."""
    if model in COSTS:
        cost = (input_tokens * COSTS[model]["input"] + output_tokens * COSTS[model]["output"]) / 1_000_000
        st.session_state.session_cost += cost
        st.session_state.total_cost += cost
        return cost
    return 0


def score_source_reliability(url, title=""):
    """Score source reliability (0-1)."""
    score = 0.5

    # Official domains boost
    official = ['.gov', '.edu', '.org', 'official', 'pricing', 'docs.']
    if any(x in url.lower() for x in official):
        score += 0.2

    # Known reliable sources
    reliable = ['github.com', 'stackoverflow.com', 'wikipedia.org', 'reuters.com', 'techcrunch.com']
    if any(x in url.lower() for x in reliable):
        score += 0.15

    # Comparison/review sites
    reviews = ['g2.com', 'capterra.com', 'trustpilot', 'review', 'compare', 'versus']
    if any(x in url.lower() for x in reviews):
        score += 0.1

    # Penalize suspicious patterns
    suspicious = ['spam', 'click', 'track', 'redirect', 'bit.ly', 'tinyurl']
    if any(x in url.lower() for x in suspicious):
        score -= 0.3

    return max(0, min(1, score))


# ============ API Integrations ============

def brave_search(query, count=10):
    """Search using Brave Search API."""
    api_key = get_secret('BRAVE_API_KEY')
    if not api_key:
        return []

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
                params={"q": query, "count": count}
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for item in data.get("web", {}).get("results", []):
                results.append({
                    "url": item.get("url"),
                    "title": item.get("title"),
                    "description": item.get("description", ""),
                    "type": "search"
                })
            return results
    except Exception as e:
        return []


def firecrawl_scrape(url):
    """Scrape URL using Firecrawl API."""
    api_key = get_secret('FIRECRAWL_API_KEY')
    if not api_key:
        return None, "No Firecrawl API key"

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                "https://api.firecrawl.dev/v0/scrape",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"url": url, "pageOptions": {"onlyMainContent": True}}
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("success"):
                content = data.get("data", {})
                markdown = content.get("markdown", "")
                metadata = content.get("metadata", {})
                return {"markdown": markdown, "title": metadata.get("title", ""), "metadata": metadata}, None
            return None, "Scrape failed"
    except Exception as e:
        return None, str(e)


# ============ Research Functions ============

def understand_query(client, query):
    """Analyze and plan the research."""
    response = client.messages.create(
        model=MODELS["planner"],
        max_tokens=1000,
        messages=[{"role": "user", "content": f"""Analyze this research request:

"{query}"

Return JSON only:
{{
    "clear": true,
    "type": "pricing|comparison|features|general|deep_dive",
    "subjects": ["specific items to research"],
    "search_queries": ["2-3 optimized search queries"],
    "data_needed": ["specific data points"],
    "schema": {{"field_name": "what to extract"}},
    "clarification": null
}}

If unclear, set clear=false and provide clarification question.
Design schema with 4-6 relevant fields for the topic."""}]
    )

    track_cost(MODELS["planner"], response.usage.input_tokens, response.usage.output_tokens)

    text = response.content[0].text.strip()
    if "```" in text:
        text = text.split("```")[1].replace("json", "").strip()
    if not text.startswith("{"):
        text = text[text.find("{"):]
    return json.loads(text)


def search_sources(client, query, search_queries):
    """Find sources using Brave Search + LLM fallback."""
    all_results = []

    # Try Brave Search first
    for sq in search_queries[:3]:
        results = brave_search(sq, count=5)
        all_results.extend(results)

    # Deduplicate by URL
    seen = set()
    unique = []
    for r in all_results:
        if r["url"] not in seen:
            seen.add(r["url"])
            r["reliability"] = score_source_reliability(r["url"], r.get("title", ""))
            unique.append(r)

    # If Brave didn't work, fall back to LLM
    if not unique:
        response = client.messages.create(
            model=MODELS["planner"],
            max_tokens=1500,
            messages=[{"role": "user", "content": f"""Find 6-8 real, working URLs for: {query}

Return JSON array only:
[{{"url": "https://...", "title": "...", "type": "official|review|comparison"}}]

Use real URLs that actually exist. Prioritize official sites and reputable sources."""}]
        )
        track_cost(MODELS["planner"], response.usage.input_tokens, response.usage.output_tokens)

        text = response.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        if not text.startswith("["):
            text = text[text.find("["):]

        try:
            sources = json.loads(text)
            for s in sources:
                s["reliability"] = score_source_reliability(s["url"], s.get("title", ""))
            unique = sources
        except:
            unique = []

    # Sort by reliability
    unique.sort(key=lambda x: x.get("reliability", 0.5), reverse=True)
    return unique[:8]


def extract_from_source(client, source, schema, topic, cache_dict):
    """Extract data from a single source. Thread-safe version."""
    url = source["url"]
    ck = cache_key(url)

    # Check cache (passed as parameter for thread safety)
    if ck in cache_dict:
        cached = cache_dict[ck]
        return {**cached, '_url': url, '_cached': True, '_ok': True, '_cache_key': ck}

    content = None
    method = "unknown"

    # Strategy 1: Firecrawl (best for JS-heavy sites)
    fc_result, fc_error = firecrawl_scrape(url)
    if fc_result:
        content = fc_result.get("markdown", "")[:4000]
        method = "firecrawl"

    # Strategy 2: Direct fetch + CSS/Regex extraction
    if not content and EXTRACTION_AVAILABLE:
        try:
            html, _ = fetch_html_sync(url, timeout=10)
            if html:
                extractor = MultiStrategyExtractor(html, url)
                result = extractor.extract_all(schema)
                if result.confidence >= 0.5:
                    return {**result.data, '_url': url, '_method': 'css/regex', '_confidence': result.confidence, '_ok': True, '_cache_key': ck, '_cache_data': result.data}
                content = html[:4000]
                method = "html"
        except:
            pass

    # Strategy 3: LLM extraction
    try:
        prompt = f"""Extract data from this source about: {topic}

URL: {url}
{f'CONTENT:\n{content}' if content else 'Note: Could not fetch content. Use your knowledge about this URL.'}

EXTRACT THESE FIELDS:
{json.dumps(schema, indent=2)}

Return ONLY a valid JSON object. Use null for fields you cannot find."""

        response = client.messages.create(
            model=MODELS["extractor"],
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )

        # Return cost info for tracking in main thread
        cost_info = {
            'model': MODELS["extractor"],
            'input_tokens': response.usage.input_tokens,
            'output_tokens': response.usage.output_tokens
        }

        text = response.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        if not text.startswith("{"):
            start = text.find("{")
            if start != -1:
                text = text[start:]

        data = json.loads(text)
        return {**data, '_url': url, '_method': method or 'llm', '_ok': True, '_cache_key': ck, '_cache_data': data, '_cost': cost_info}

    except Exception as e:
        return {'_url': url, '_error': str(e)[:100], '_ok': False}


def synthesize_results(client, query, results, research_type):
    """Synthesize findings with streaming."""
    good = [r for r in results if r.get('_ok')]

    prompt = f"""Synthesize this research on: {query}

Data from {len(good)} sources:
{json.dumps(good, indent=2)}

Return JSON:
{{
    "summary": "2-3 sentence executive summary",
    "findings": ["key finding 1", "key finding 2", "key finding 3"],
    "table": {{"headers": ["Name", "Key Info", ...], "rows": [["Item", "Details", ...], ...]}},
    "recommendation": "brief actionable recommendation",
    "follow_up_questions": ["suggested follow-up 1", "suggested follow-up 2", "suggested follow-up 3"],
    "confidence": 0.0-1.0
}}

Make the table comprehensive. Include all items with their key details."""

    response = client.messages.create(
        model=MODELS["synthesizer"],
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}]
    )
    track_cost(MODELS["synthesizer"], response.usage.input_tokens, response.usage.output_tokens)

    text = response.content[0].text
    if "```" in text:
        text = text.split("```")[1].replace("json", "").strip()
    if not text.startswith("{"):
        text = text[text.find("{"):]

    return json.loads(text)


def answer_followup(client, question, research):
    """Answer follow-up question about research."""
    response = client.messages.create(
        model=MODELS["planner"],
        max_tokens=1000,
        messages=[{"role": "user", "content": f"""Based on this research:

Topic: {research.get('query')}
Findings: {json.dumps(research.get('synthesis', {}))}
Raw Data: {json.dumps(research.get('results', [])[:5])}

Question: {question}

Give a concise, specific answer referencing the data. If the data doesn't contain the answer, say so."""}]
    )
    track_cost(MODELS["planner"], response.usage.input_tokens, response.usage.output_tokens)
    return response.content[0].text


# ============ UI Components ============

def render_header():
    """Render app header with status badges."""
    brave_ok = bool(get_secret('BRAVE_API_KEY'))
    firecrawl_ok = bool(get_secret('FIRECRAWL_API_KEY'))

    badges = []
    if brave_ok:
        badges.append('<span class="badge active">🔍 Brave Search</span>')
    if firecrawl_ok:
        badges.append('<span class="badge active">🔥 Firecrawl</span>')
    if EXTRACTION_AVAILABLE:
        badges.append('<span class="badge active">⚡ Fast Extract</span>')

    st.markdown(f'''
    <div class="app-header">
        <h1>🔬 Research Assistant</h1>
        <p>AI-powered research with real-time web search</p>
        <div class="status-bar">
            {' '.join(badges)}
        </div>
    </div>
    ''', unsafe_allow_html=True)


def render_message(msg, msg_idx=0):
    """Render a chat message."""
    if msg['role'] == 'user':
        st.markdown(f'<div class="user-msg">{msg["content"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="assistant-msg">{msg["content"]}</div>', unsafe_allow_html=True)

        # Render research results if present
        if msg.get('research'):
            render_research_results(msg['research'], msg_idx)


def render_research_results(research, msg_idx=0):
    """Render research results with unique keys."""
    synthesis = research.get('synthesis', {})
    # Create unique key prefix from timestamp or index
    key_prefix = research.get('timestamp', str(msg_idx))[:20].replace(':', '').replace('-', '')
    results = research.get('results', [])

    # Summary
    if synthesis.get('summary'):
        st.info(synthesis['summary'])

    # Table
    if synthesis.get('table'):
        table = synthesis['table']
        if table.get('headers') and table.get('rows'):
            df = pd.DataFrame(table['rows'], columns=table['headers'])
            st.dataframe(df, use_container_width=True, hide_index=True)

    # Findings
    if synthesis.get('findings'):
        with st.expander("🔍 Key Findings", expanded=False):
            for f in synthesis['findings']:
                st.markdown(f"• {f}")

    # Recommendation
    if synthesis.get('recommendation'):
        st.success(f"💡 **Recommendation:** {synthesis['recommendation']}")

    # Sources with reliability
    if results:
        successful = [r for r in results if r.get('_ok')]
        with st.expander(f"📚 Sources ({len(successful)}/{len(results)} successful)"):
            for r in results:
                url = r.get('_url', '')
                reliability = score_source_reliability(url)
                level = "high" if reliability > 0.6 else "medium" if reliability > 0.4 else "low"
                method = r.get('_method', 'unknown')
                cached = "📦" if r.get('_cached') else ""

                if r.get('_ok'):
                    st.markdown(f'<a href="{url}" target="_blank" class="source-pill {level}">{cached} {url[:40]}... ({method})</a>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<span class="source-pill low">❌ {url[:40]}...</span>', unsafe_allow_html=True)

    # Export buttons
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        json_data = export_to_json(research)
        st.download_button(
            "📥 JSON",
            json_data,
            file_name=f"research_{key_prefix}.json",
            mime="application/json",
            use_container_width=True,
            key=f"dl_json_{key_prefix}"
        )
    with col2:
        csv_data = export_to_csv(research)
        if csv_data:
            st.download_button(
                "📥 CSV",
                csv_data,
                file_name=f"research_{key_prefix}.csv",
                mime="text/csv",
                use_container_width=True,
                key=f"dl_csv_{key_prefix}"
            )

    # Follow-up suggestions
    if synthesis.get('follow_up_questions'):
        st.markdown("**Suggested follow-ups:**")
        cols = st.columns(min(3, len(synthesis['follow_up_questions'])))
        for i, q in enumerate(synthesis['follow_up_questions'][:3]):
            with cols[i]:
                if st.button(q[:40] + "...", key=f"followup_{key_prefix}_{i}", use_container_width=True):
                    st.session_state.pending_query = q
                    st.rerun()


def render_progress(steps, current_step):
    """Render progress indicator."""
    html = '<div class="progress-container">'
    for i, step in enumerate(steps):
        if i < current_step:
            html += f'<div class="progress-step done"><span class="icon">✓</span> {step}</div>'
        elif i == current_step:
            html += f'<div class="progress-step active"><span class="icon">●</span> {step}...</div>'
        else:
            html += f'<div class="progress-step"><span class="icon">○</span> {step}</div>'
    html += '</div>'
    return html


def render_cost_badge():
    """Render floating cost badge."""
    if st.session_state.session_cost > 0:
        st.markdown(f'''
        <div class="cost-badge">
            💰 Session: ${st.session_state.session_cost:.4f}
        </div>
        ''', unsafe_allow_html=True)


# ============ Export Functions ============

def export_to_json(research):
    """Export research to JSON."""
    return json.dumps(research, indent=2, default=str)


def export_to_csv(research):
    """Export research table to CSV."""
    synthesis = research.get('synthesis', {})
    table = synthesis.get('table', {})
    if table.get('headers') and table.get('rows'):
        df = pd.DataFrame(table['rows'], columns=table['headers'])
        return df.to_csv(index=False)
    return ""


# ============ Main App ============

def main():
    init_state()

    if not check_password():
        return

    render_header()

    # Sidebar for history and settings
    with st.sidebar:
        st.markdown("### History")
        if st.session_state.history:
            for i, h in enumerate(st.session_state.history[-10:]):
                if st.button(h['query'][:30] + "...", key=f"hist_{i}", use_container_width=True):
                    st.session_state.messages = h['messages']
                    st.rerun()
        else:
            st.caption("No research history yet")

        st.divider()

        st.markdown("### Session Stats")
        st.caption(f"Cost: ${st.session_state.session_cost:.4f}")
        st.caption(f"Cached URLs: {len(st.session_state.cache)}")

        if st.button("Clear Cache", use_container_width=True):
            st.session_state.cache = {}
            st.rerun()

    # Chat history
    for idx, msg in enumerate(st.session_state.messages):
        render_message(msg, idx)

    # Example prompts if empty
    if not st.session_state.messages:
        st.markdown("#### Try asking:")
        examples = [
            "Compare pricing for Notion vs Obsidian vs Roam",
            "Research top 5 CRM tools for startups",
            "What are the best project management tools in 2024?",
            "Compare cloud hosting: AWS vs GCP vs Azure pricing"
        ]
        cols = st.columns(2)
        for i, ex in enumerate(examples):
            with cols[i % 2]:
                if st.button(ex, key=f"ex_{i}", use_container_width=True):
                    st.session_state.pending_query = ex
                    st.rerun()

    # Cost badge
    render_cost_badge()

    # Chat input
    query = st.chat_input("Ask me to research anything...")

    # Check for pending query
    if hasattr(st.session_state, 'pending_query') and st.session_state.pending_query:
        query = st.session_state.pending_query
        st.session_state.pending_query = None

    if query:
        # Add user message
        st.session_state.messages.append({'role': 'user', 'content': query})
        st.markdown(f'<div class="user-msg">{query}</div>', unsafe_allow_html=True)

        client = get_client()
        if not client:
            st.session_state.messages.append({
                'role': 'assistant',
                'content': "Please configure your Anthropic API key to continue."
            })
            st.rerun()

        # Check if this is a follow-up
        current_research = None
        for msg in reversed(st.session_state.messages[:-1]):
            if msg.get('research'):
                current_research = msg['research']
                break

        if current_research and len(query.split()) < 20:
            with st.spinner("Thinking..."):
                answer = answer_followup(client, query, current_research)
            st.session_state.messages.append({'role': 'assistant', 'content': answer})
            st.rerun()

        # New research
        steps = ["Understanding request", "Searching sources", "Extracting data", "Synthesizing findings"]
        progress = st.empty()

        # Step 1: Understand
        progress.markdown(render_progress(steps, 0), unsafe_allow_html=True)
        try:
            parsed = understand_query(client, query)
        except Exception as e:
            parsed = {'clear': True, 'subjects': [query], 'search_queries': [query], 'schema': {'name': 'Name', 'details': 'Details'}}

        if not parsed.get('clear') and parsed.get('clarification'):
            st.session_state.messages.append({'role': 'assistant', 'content': parsed['clarification']})
            progress.empty()
            st.rerun()

        # Step 2: Search
        progress.markdown(render_progress(steps, 1), unsafe_allow_html=True)
        sources = search_sources(client, query, parsed.get('search_queries', [query]))

        if not sources:
            st.session_state.messages.append({
                'role': 'assistant',
                'content': "I couldn't find relevant sources. Could you try rephrasing your query?"
            })
            progress.empty()
            st.rerun()

        # Step 3: Extract
        progress.markdown(render_progress(steps, 2), unsafe_allow_html=True)
        schema = parsed.get('schema', {'name': 'Name', 'info': 'Key information'})

        # Get cache snapshot for thread-safe access
        cache_snapshot = dict(st.session_state.cache)

        results = []
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(extract_from_source, client, s, schema, query, cache_snapshot): s for s in sources}
            done_count = 0
            for future in as_completed(futures):
                result = future.result()
                results.append(result)

                # Update cache and costs in main thread
                if result.get('_cache_key') and result.get('_cache_data'):
                    st.session_state.cache[result['_cache_key']] = result['_cache_data']
                if result.get('_cost'):
                    cost = result['_cost']
                    track_cost(cost['model'], cost['input_tokens'], cost['output_tokens'])

                done_count += 1
                progress.markdown(
                    render_progress(steps, 2) + f'<p style="font-size:0.8rem;color:#666;margin-left:2rem;">({done_count}/{len(sources)} sources)</p>',
                    unsafe_allow_html=True
                )

        # Step 4: Synthesize
        progress.markdown(render_progress(steps, 3), unsafe_allow_html=True)
        try:
            synthesis = synthesize_results(client, query, results, parsed.get('type', 'general'))
        except Exception as e:
            synthesis = {
                'summary': f'Research completed with {sum(1 for r in results if r.get("_ok"))} sources.',
                'findings': [],
                'follow_up_questions': []
            }

        progress.empty()

        # Build research object
        research_data = {
            'query': query,
            'parsed': parsed,
            'sources': sources,
            'results': results,
            'synthesis': synthesis,
            'timestamp': datetime.now().isoformat(),
            'cost': st.session_state.session_cost
        }

        # Add to history
        st.session_state.history.append({
            'query': query,
            'messages': st.session_state.messages.copy(),
            'timestamp': datetime.now().isoformat()
        })

        # Add response
        successful = sum(1 for r in results if r.get('_ok'))
        cached = sum(1 for r in results if r.get('_cached'))

        response_text = f"Here's what I found ({successful} sources"
        if cached:
            response_text += f", {cached} cached"
        response_text += "):"

        st.session_state.messages.append({
            'role': 'assistant',
            'content': response_text,
            'research': research_data
        })

        st.rerun()


if __name__ == "__main__":
    main()

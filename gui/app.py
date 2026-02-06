"""
Web Research Orchestrator - Streamlit GUI
A conversational interface for multi-model web research with Claude.

Models used:
- Claude Sonnet 4 (claude-sonnet-4-20250514): Orchestration, synthesis, analysis
- Claude Haiku 3.5 (claude-3-5-haiku-20241022): Data extraction workers
"""

import streamlit as st
import anthropic
import json
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import os
import re

# Import multi-strategy extraction module
try:
    from extraction import (
        MultiStrategyExtractor,
        ExtractedData,
        ValidationResult,
        validate_extracted_data,
        fetch_html_sync,
    )
    EXTRACTION_MODULE_AVAILABLE = True
except ImportError:
    EXTRACTION_MODULE_AVAILABLE = False

# Page config
st.set_page_config(
    page_title="Web Research Orchestrator",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for clean, modern look
st.markdown("""
<style>
    /* Main container */
    .main-header {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #667eea, #764ba2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
        text-align: center;
    }
    .subtitle {
        color: #666;
        font-size: 1rem;
        text-align: center;
        margin-top: 0;
        margin-bottom: 2rem;
    }

    /* Chat messages */
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 1rem 1rem 0.25rem 1rem;
        margin: 0.5rem 0;
        max-width: 80%;
        margin-left: auto;
    }
    .assistant-message {
        background: #f7f7f8;
        color: #1a1a1a;
        padding: 1rem 1.5rem;
        border-radius: 1rem 1rem 1rem 0.25rem;
        margin: 0.5rem 0;
        max-width: 90%;
        border: 1px solid #e5e5e5;
    }

    /* Progress indicators */
    .thinking-box {
        background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%);
        border-left: 4px solid #667eea;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .step-indicator {
        display: flex;
        align-items: center;
        padding: 0.5rem 0;
        color: #555;
    }
    .step-indicator.active {
        color: #667eea;
        font-weight: 600;
    }
    .step-indicator.complete {
        color: #22c55e;
    }
    .step-indicator.error {
        color: #ef4444;
    }

    /* Results cards */
    .result-card {
        background: white;
        border: 1px solid #e5e5e5;
        border-radius: 0.75rem;
        padding: 1.25rem;
        margin: 0.75rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .result-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }

    /* Cost badge */
    .cost-badge {
        background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 2rem;
        font-size: 0.85rem;
        display: inline-block;
    }

    /* Hide default Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}

    /* Input styling */
    .stTextInput > div > div > input {
        border-radius: 1.5rem;
        padding: 0.75rem 1.25rem;
        border: 2px solid #e5e5e5;
    }
    .stTextInput > div > div > input:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2);
    }
</style>
""", unsafe_allow_html=True)


# ============ Utility Functions ============

def get_secret(key: str, default: str = "") -> str:
    """Get a secret from Streamlit secrets or environment variables."""
    try:
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, default)


def check_password() -> bool:
    """Check password protection for cloud demos."""
    passwords = {}
    try:
        if hasattr(st, 'secrets') and 'passwords' in st.secrets:
            passwords = dict(st.secrets["passwords"])
    except Exception:
        pass

    if not passwords:
        return True

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    # Login page
    st.markdown('<p class="main-header">🔬 Web Research Orchestrator</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">AI-powered research assistant</p>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("### 🔐 Login")
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login", type="primary", use_container_width=True):
                if username in passwords and passwords[username] == password:
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Invalid credentials")
    return False


def init_session_state():
    """Initialize session state."""
    defaults = {
        'messages': [],
        'current_research': None,
        'api_key': get_secret('ANTHROPIC_API_KEY', ''),
        'processing': False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_client():
    """Get Anthropic client."""
    if not st.session_state.api_key:
        return None
    return anthropic.Anthropic(api_key=st.session_state.api_key)


# ============ Research Functions ============

def clarify_query(client, query: str) -> dict:
    """Use Claude to understand the query and ask clarifying questions if needed."""
    prompt = f"""You are a research assistant. Analyze this research request and determine if you need clarification.

USER REQUEST: {query}

Respond with JSON:
{{
    "understood": true/false,
    "research_type": "pricing|comparison|data_extraction|competitive_intel|general",
    "entities": ["list of companies/products/topics to research"],
    "data_points": ["what specific data to extract"],
    "clarifying_questions": ["questions if unclear, empty if understood"],
    "suggested_schema": {{"field": "description"}},
    "search_strategy": "brief description of how you'll approach this"
}}

If the request is clear, set understood=true and provide your research plan.
If unclear, set understood=false and ask 1-2 specific clarifying questions.

Return only valid JSON."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        return {"understood": True, "error": str(e), "entities": [], "data_points": [], "clarifying_questions": []}


def discover_sources(client, topic: str, entities: list, num_sources: int = 8) -> list:
    """Find relevant URLs to research."""
    prompt = f"""Find {num_sources} specific, real URLs for researching this topic.

TOPIC: {topic}
ENTITIES TO RESEARCH: {', '.join(entities) if entities else topic}

Return JSON array:
[{{"url": "https://...", "title": "...", "type": "official|news|comparison|docs", "priority": "high|medium"}}]

Focus on official sources, reputable news, and comparison sites. Return only the JSON array."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception:
        return []


def extract_from_url(client, url: str, schema: dict, topic: str) -> dict:
    """Extract data from a single URL using multi-strategy approach."""
    html_content = None

    # Try to fetch HTML first (for CSS/regex extraction)
    if EXTRACTION_MODULE_AVAILABLE:
        try:
            html_content, _ = fetch_html_sync(url, timeout=10)
            if html_content:
                extractor = MultiStrategyExtractor(html_content, url)
                result = extractor.extract_all(schema)
                if result.confidence >= 0.6:
                    data = result.data.copy()
                    data['_url'] = url
                    data['_method'] = result.extraction_method
                    data['_confidence'] = result.confidence
                    data['_success'] = True
                    return data
        except Exception:
            pass

    # Fall back to LLM extraction
    prompt = f"""Extract data from this URL for research on: {topic}

URL: {url}
{f'CONTENT: {html_content[:3000]}' if html_content else ''}

SCHEMA: {json.dumps(schema)}

Return JSON matching the schema. Use null for missing fields.
If you cannot access the content, return {{"_error": "reason"}}"""

    try:
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        data['_url'] = url
        data['_method'] = 'llm'
        data['_success'] = '_error' not in data
        return data
    except Exception as e:
        return {'_url': url, '_error': str(e), '_success': False}


def synthesize_findings(client, topic: str, results: list) -> dict:
    """Create a synthesis of all findings."""
    successful = [r for r in results if r.get('_success')]

    prompt = f"""Synthesize these research findings into a clear summary.

TOPIC: {topic}

DATA COLLECTED ({len(successful)} sources):
{json.dumps(successful, indent=2)}

Create a synthesis with:
1. Key findings (the most important discoveries)
2. Comparison table if applicable
3. Recommendations or insights
4. Data gaps (what's missing)

Return JSON:
{{
    "summary": "2-3 sentence executive summary",
    "key_findings": ["finding 1", "finding 2"],
    "comparison_table": {{"headers": [...], "rows": [[...]]}},
    "insights": ["insight 1"],
    "gaps": ["what's missing"],
    "confidence": "high|medium|low"
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        return {"summary": f"Error: {e}", "key_findings": [], "confidence": "low"}


def answer_followup(client, question: str, research_data: dict) -> str:
    """Answer a follow-up question about the research."""
    prompt = f"""Answer this follow-up question about the research data.

RESEARCH TOPIC: {research_data.get('topic', 'Unknown')}

FINDINGS:
{json.dumps(research_data.get('synthesis', {}), indent=2)}

RAW DATA:
{json.dumps(research_data.get('results', [])[:5], indent=2)}

QUESTION: {question}

Provide a clear, concise answer based on the data. If the data doesn't contain the answer, say so."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        return f"Sorry, I encountered an error: {e}"


# ============ UI Components ============

def render_thinking(steps: list, current_step: int):
    """Render the thinking/progress indicator."""
    html = '<div class="thinking-box">'
    html += '<strong>🧠 Working on it...</strong><br><br>'

    for i, step in enumerate(steps):
        if i < current_step:
            status = "complete"
            icon = "✅"
        elif i == current_step:
            status = "active"
            icon = "⏳"
        else:
            status = ""
            icon = "⬜"
        html += f'<div class="step-indicator {status}">{icon} {step}</div>'

    html += '</div>'
    return html


def render_results_card(data: dict):
    """Render a result as a nice card."""
    url = data.get('_url', 'Unknown source')
    method = data.get('_method', 'unknown')
    success = data.get('_success', False)

    # Clean data for display (remove internal fields)
    display_data = {k: v for k, v in data.items() if not k.startswith('_') and v is not None}

    status_icon = "✅" if success else "❌"
    method_badge = f"{'🆓' if method in ['css', 'regex'] else '🤖'} {method}"

    with st.container():
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"**{status_icon} {url[:60]}{'...' if len(url) > 60 else ''}**")
        with col2:
            st.caption(method_badge)

        if display_data:
            with st.expander("View data", expanded=False):
                st.json(display_data)


def render_synthesis(synthesis: dict):
    """Render the synthesis in a nice format."""
    st.markdown("### 📊 Research Summary")

    # Summary
    if synthesis.get('summary'):
        st.info(synthesis['summary'])

    # Key findings
    if synthesis.get('key_findings'):
        st.markdown("**Key Findings:**")
        for finding in synthesis['key_findings']:
            st.markdown(f"• {finding}")

    # Comparison table
    if synthesis.get('comparison_table'):
        table = synthesis['comparison_table']
        if table.get('headers') and table.get('rows'):
            st.markdown("**Comparison:**")
            df = pd.DataFrame(table['rows'], columns=table['headers'])
            st.dataframe(df, use_container_width=True, hide_index=True)

    # Insights
    if synthesis.get('insights'):
        st.markdown("**💡 Insights:**")
        for insight in synthesis['insights']:
            st.markdown(f"• {insight}")

    # Confidence
    confidence = synthesis.get('confidence', 'medium')
    confidence_colors = {'high': '🟢', 'medium': '🟡', 'low': '🔴'}
    st.caption(f"Confidence: {confidence_colors.get(confidence, '⚪')} {confidence}")


# ============ Main Research Flow ============

def run_research(query: str, progress_container):
    """Execute the full research flow with live progress."""
    client = get_client()
    if not client:
        st.error("API key not configured")
        return None

    steps = [
        "Understanding your request",
        "Finding relevant sources",
        "Extracting data",
        "Analyzing findings",
        "Preparing summary"
    ]

    research_data = {
        'topic': query,
        'timestamp': datetime.now().isoformat(),
        'results': [],
        'synthesis': None,
    }

    # Step 1: Understand query
    with progress_container:
        st.markdown(render_thinking(steps, 0), unsafe_allow_html=True)

    clarification = clarify_query(client, query)

    # Check if we need clarification
    if not clarification.get('understood', True) and clarification.get('clarifying_questions'):
        return {'needs_clarification': True, 'questions': clarification['clarifying_questions'], 'partial': clarification}

    schema = clarification.get('suggested_schema', {"name": "Name", "details": "Key details"})
    entities = clarification.get('entities', [])

    # Step 2: Find sources
    with progress_container:
        st.markdown(render_thinking(steps, 1), unsafe_allow_html=True)
        st.caption(f"Strategy: {clarification.get('search_strategy', 'General search')}")

    sources = discover_sources(client, query, entities)
    research_data['sources'] = sources

    if not sources:
        return {'error': 'Could not find relevant sources'}

    # Step 3: Extract data
    with progress_container:
        st.markdown(render_thinking(steps, 2), unsafe_allow_html=True)
        extraction_status = st.empty()

    results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(extract_from_url, client, s['url'], schema, query): s for s in sources}
        completed = 0
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            completed += 1
            extraction_status.caption(f"Processed {completed}/{len(sources)} sources...")

    research_data['results'] = results
    successful = sum(1 for r in results if r.get('_success'))

    # Step 4: Analyze
    with progress_container:
        st.markdown(render_thinking(steps, 3), unsafe_allow_html=True)
        st.caption(f"Analyzing {successful} successful extractions...")

    # Step 5: Synthesize
    with progress_container:
        st.markdown(render_thinking(steps, 4), unsafe_allow_html=True)

    synthesis = synthesize_findings(client, query, results)
    research_data['synthesis'] = synthesis

    return research_data


# ============ Main App ============

def main():
    init_session_state()

    if not check_password():
        return

    # Header
    st.markdown('<p class="main-header">🔬 Web Research Orchestrator</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Ask me to research anything • Powered by Claude Sonnet & Haiku</p>', unsafe_allow_html=True)

    # Sidebar (collapsed by default)
    with st.sidebar:
        st.markdown("### ⚙️ Settings")

        if get_secret('ANTHROPIC_API_KEY'):
            st.success("✅ API configured")
        else:
            api_key = st.text_input("Anthropic API Key", type="password")
            if api_key:
                st.session_state.api_key = api_key

        st.divider()
        st.caption("**Models:**")
        st.caption("• Sonnet 4 - Planning & synthesis")
        st.caption("• Haiku 3.5 - Data extraction")

        st.divider()
        if st.button("🗑️ Clear conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.current_research = None
            st.rerun()

        if st.session_state.get('authenticated'):
            st.divider()
            st.caption(f"👤 {st.session_state.get('username', 'User')}")
            if st.button("Logout", use_container_width=True):
                st.session_state.authenticated = False
                st.rerun()

    # Main chat area
    chat_container = st.container()

    # Display message history
    with chat_container:
        for msg in st.session_state.messages:
            if msg['role'] == 'user':
                st.markdown(f'<div class="user-message">{msg["content"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="assistant-message">{msg["content"]}</div>', unsafe_allow_html=True)

                # If there's research data, show it
                if msg.get('research_data') and msg['research_data'].get('synthesis'):
                    render_synthesis(msg['research_data']['synthesis'])

                    with st.expander("📋 View all sources", expanded=False):
                        for result in msg['research_data'].get('results', []):
                            render_results_card(result)

    # Input area
    st.divider()

    col1, col2 = st.columns([6, 1])
    with col1:
        user_input = st.text_input(
            "Ask me to research something...",
            placeholder="e.g., Compare pricing for top 5 project management tools",
            label_visibility="collapsed",
            key="user_input"
        )
    with col2:
        send_clicked = st.button("🔍", type="primary", use_container_width=True)

    # Example prompts for new users
    if not st.session_state.messages:
        st.markdown("**Try asking:**")
        examples = [
            "Compare pricing for Notion, Obsidian, and Roam Research",
            "Research the top 5 CRM tools for small businesses",
            "Find pricing and features for popular email marketing platforms",
        ]
        cols = st.columns(len(examples))
        for i, example in enumerate(examples):
            with cols[i]:
                if st.button(example, key=f"example_{i}", use_container_width=True):
                    user_input = example
                    send_clicked = True

    # Process input
    if (send_clicked or user_input) and user_input and not st.session_state.processing:
        st.session_state.processing = True

        # Add user message
        st.session_state.messages.append({'role': 'user', 'content': user_input})

        # Check if this is a follow-up question
        if st.session_state.current_research and any(word in user_input.lower() for word in ['which', 'what', 'how', 'why', 'tell me', 'more about', 'compare']):
            # It's a follow-up
            with st.spinner("Thinking..."):
                answer = answer_followup(get_client(), user_input, st.session_state.current_research)
            st.session_state.messages.append({'role': 'assistant', 'content': answer})
        else:
            # New research query
            progress_container = st.empty()

            with progress_container.container():
                result = run_research(user_input, st)

            progress_container.empty()

            if result:
                if result.get('needs_clarification'):
                    # Ask clarifying questions
                    questions = result['questions']
                    response = "I want to make sure I understand your request. " + " ".join(questions)
                    st.session_state.messages.append({'role': 'assistant', 'content': response})
                elif result.get('error'):
                    st.session_state.messages.append({'role': 'assistant', 'content': f"Sorry, I ran into an issue: {result['error']}"})
                else:
                    # Success!
                    st.session_state.current_research = result
                    summary = result.get('synthesis', {}).get('summary', 'Research complete!')
                    successful = sum(1 for r in result.get('results', []) if r.get('_success'))
                    total = len(result.get('results', []))

                    response = f"✅ **Research complete!** Analyzed {successful}/{total} sources.\n\n{summary}"
                    st.session_state.messages.append({
                        'role': 'assistant',
                        'content': response,
                        'research_data': result
                    })

        st.session_state.processing = False
        st.rerun()


if __name__ == "__main__":
    main()

"""
Web Research Orchestrator - Claude-style Chat Interface
"""

import streamlit as st
import anthropic
import json
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

# Import extraction module
try:
    from extraction import MultiStrategyExtractor, fetch_html_sync
    EXTRACTION_AVAILABLE = True
except ImportError:
    EXTRACTION_AVAILABLE = False

# Page config - wide layout, no sidebar
st.set_page_config(
    page_title="Research Assistant",
    page_icon="🔬",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Claude-style CSS
st.markdown("""
<style>
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}
    header {visibility: hidden;}

    /* Main container - Claude-like centered layout */
    .main .block-container {
        max-width: 48rem;
        padding-top: 2rem;
        padding-bottom: 6rem;
    }

    /* Header */
    .header {
        text-align: center;
        padding: 1rem 0 2rem 0;
        border-bottom: 1px solid #e5e5e5;
        margin-bottom: 2rem;
    }
    .header h1 {
        font-size: 1.5rem;
        font-weight: 600;
        color: #1a1a1a;
        margin: 0;
    }
    .header p {
        color: #666;
        font-size: 0.9rem;
        margin: 0.5rem 0 0 0;
    }

    /* Chat messages */
    .message {
        padding: 1rem 0;
        line-height: 1.6;
    }
    .message.user {
        background: transparent;
    }
    .message.user .content {
        background: #f4f4f4;
        padding: 1rem 1.25rem;
        border-radius: 1.5rem;
        display: inline-block;
        max-width: 85%;
        float: right;
        clear: both;
    }
    .message.assistant {
        background: transparent;
    }
    .message.assistant .content {
        color: #1a1a1a;
    }
    .message.assistant .avatar {
        width: 28px;
        height: 28px;
        background: linear-gradient(135deg, #D4A574 0%, #C4956A 100%);
        border-radius: 50%;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        margin-right: 0.75rem;
        vertical-align: top;
    }

    /* Clear floats */
    .clearfix::after {
        content: "";
        clear: both;
        display: table;
    }

    /* Thinking/Progress */
    .thinking {
        color: #666;
        font-style: italic;
        padding: 0.5rem 0;
    }
    .thinking .dot {
        animation: blink 1.4s infinite;
    }
    .thinking .dot:nth-child(2) { animation-delay: 0.2s; }
    .thinking .dot:nth-child(3) { animation-delay: 0.4s; }
    @keyframes blink {
        0%, 100% { opacity: 0.2; }
        50% { opacity: 1; }
    }

    .step {
        padding: 0.25rem 0;
        color: #666;
        font-size: 0.9rem;
    }
    .step.done {
        color: #10a37f;
    }
    .step.active {
        color: #1a1a1a;
        font-weight: 500;
    }

    /* Results styling */
    .finding {
        padding: 0.75rem 0;
        border-bottom: 1px solid #f0f0f0;
    }
    .finding:last-child {
        border-bottom: none;
    }

    /* Input area - fixed at bottom */
    .input-area {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: white;
        border-top: 1px solid #e5e5e5;
        padding: 1rem;
        z-index: 100;
    }
    .input-container {
        max-width: 48rem;
        margin: 0 auto;
    }

    /* Style the text input to look like Claude's */
    .stTextInput > div > div > input {
        border: 1px solid #d9d9d9 !important;
        border-radius: 1.5rem !important;
        padding: 0.75rem 1.25rem !important;
        font-size: 1rem !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: #10a37f !important;
        box-shadow: 0 0 0 1px #10a37f !important;
    }

    /* Example chips */
    .examples {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        justify-content: center;
        padding: 1rem 0;
    }
    .example-chip {
        background: #f7f7f8;
        border: 1px solid #e5e5e5;
        border-radius: 1rem;
        padding: 0.5rem 1rem;
        font-size: 0.85rem;
        color: #666;
        cursor: pointer;
        transition: all 0.2s;
    }
    .example-chip:hover {
        background: #e5e5e5;
        color: #1a1a1a;
    }

    /* Data table */
    .dataframe {
        font-size: 0.9rem !important;
    }

    /* Source pills */
    .source-pill {
        display: inline-block;
        background: #f0f0f0;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.8rem;
        color: #666;
        margin: 0.25rem;
    }
    .source-pill.success {
        background: #d1fae5;
        color: #065f46;
    }
    .source-pill.failed {
        background: #fee2e2;
        color: #991b1b;
    }
</style>
""", unsafe_allow_html=True)


# ============ Helper Functions ============

def get_secret(key, default=""):
    try:
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except:
        pass
    return os.environ.get(key, default)


def check_password():
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

    # Login UI
    st.markdown("""
    <div class="header">
        <h1>🔬 Research Assistant</h1>
        <p>Sign in to continue</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Continue", use_container_width=True, type="primary"):
                if username in passwords and passwords[username] == password:
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Invalid credentials")
    return False


def init_state():
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'research' not in st.session_state:
        st.session_state.research = None
    if 'api_key' not in st.session_state:
        st.session_state.api_key = get_secret('ANTHROPIC_API_KEY')


def get_client():
    if not st.session_state.api_key:
        return None
    return anthropic.Anthropic(api_key=st.session_state.api_key)


# ============ Research Functions ============

def understand_query(client, query):
    """Parse and understand the research request."""
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
    "clarification": "question to ask if unclear, or null",
    "schema": {{"field": "what to extract"}}
}}

Be helpful - if reasonably clear, set clear=true and proceed."""}]
    )
    text = response.content[0].text
    if "```" in text:
        text = text.split("```")[1].replace("json", "").strip()
    return json.loads(text)


def find_sources(client, query, subjects):
    """Find URLs to research."""
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{"role": "user", "content": f"""Find 6-8 URLs for researching: {query}
Subjects: {', '.join(subjects)}

Return JSON array: [{{"url": "...", "title": "...", "type": "official|review|news"}}]
Focus on official sites and reputable sources."""}]
    )
    text = response.content[0].text
    if "```" in text:
        text = text.split("```")[1].replace("json", "").strip()
    return json.loads(text)


def extract_data(client, url, schema, topic):
    """Extract data from a URL."""
    html = None

    # Try fast extraction first
    if EXTRACTION_AVAILABLE:
        try:
            html, _ = fetch_html_sync(url, timeout=8)
            if html:
                extractor = MultiStrategyExtractor(html, url)
                result = extractor.extract_all(schema)
                if result.confidence >= 0.5:
                    return {**result.data, '_url': url, '_method': 'fast', '_ok': True}
        except:
            pass

    # LLM extraction
    try:
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1500,
            messages=[{"role": "user", "content": f"""Extract from {url} for: {topic}
{f'Content: {html[:2500]}' if html else ''}
Schema: {json.dumps(schema)}
Return JSON. Use null for missing."""}]
        )
        text = response.content[0].text
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        data = json.loads(text)
        return {**data, '_url': url, '_method': 'ai', '_ok': '_error' not in data}
    except Exception as e:
        return {'_url': url, '_error': str(e), '_ok': False}


def synthesize(client, query, results):
    """Create synthesis of findings."""
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
    "recommendation": "brief recommendation if applicable"
}}"""}]
    )
    text = response.content[0].text
    if "```" in text:
        text = text.split("```")[1].replace("json", "").strip()
    return json.loads(text)


def answer_question(client, question, research):
    """Answer follow-up question."""
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": f"""Based on this research:

Topic: {research.get('query')}
Findings: {json.dumps(research.get('synthesis', {}))}
Data: {json.dumps(research.get('results', [])[:3])}

Answer: {question}

Be concise and specific. Reference the data."""}]
    )
    return response.content[0].text


# ============ Main App ============

def main():
    init_state()

    if not check_password():
        return

    # Header
    st.markdown("""
    <div class="header">
        <h1>🔬 Research Assistant</h1>
        <p>Ask me to research anything</p>
    </div>
    """, unsafe_allow_html=True)

    # Settings in expander (not sidebar)
    if not get_secret('ANTHROPIC_API_KEY'):
        with st.expander("⚙️ Settings"):
            key = st.text_input("API Key", type="password")
            if key:
                st.session_state.api_key = key

    # Chat history
    for msg in st.session_state.messages:
        if msg['role'] == 'user':
            st.markdown(f"""
            <div class="message user clearfix">
                <div class="content">{msg['content']}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="message assistant">
                <span class="avatar">🔬</span>
                <span class="content">{msg['content']}</span>
            </div>
            """, unsafe_allow_html=True)

            # Show research results if present
            if msg.get('research'):
                research = msg['research']
                synthesis = research.get('synthesis', {})

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
                    for f in synthesis['findings']:
                        st.markdown(f"• {f}")

                # Recommendation
                if synthesis.get('recommendation'):
                    st.success(f"💡 {synthesis['recommendation']}")

                # Sources
                results = research.get('results', [])
                if results:
                    with st.expander(f"📚 Sources ({sum(1 for r in results if r.get('_ok'))}/{len(results)} successful)"):
                        for r in results:
                            status = "success" if r.get('_ok') else "failed"
                            url = r.get('_url', 'Unknown')[:50]
                            st.markdown(f'<span class="source-pill {status}">{url}</span>', unsafe_allow_html=True)

    # Show examples if no messages
    if not st.session_state.messages:
        st.markdown("#### Try asking:")
        cols = st.columns(2)
        examples = [
            "Compare pricing for Notion vs Obsidian vs Roam",
            "Research top 5 CRM tools for startups",
            "Find features of popular email marketing tools",
            "Compare project management software pricing"
        ]
        for i, ex in enumerate(examples):
            with cols[i % 2]:
                if st.button(ex, key=f"ex_{i}", use_container_width=True):
                    st.session_state.pending_query = ex
                    st.rerun()

    # Input
    st.markdown("<br>", unsafe_allow_html=True)
    query = st.chat_input("Ask me to research something...")

    # Check for pending query from examples
    if hasattr(st.session_state, 'pending_query'):
        query = st.session_state.pending_query
        del st.session_state.pending_query

    if query:
        # Add user message
        st.session_state.messages.append({'role': 'user', 'content': query})

        client = get_client()
        if not client:
            st.session_state.messages.append({
                'role': 'assistant',
                'content': "Please add your Anthropic API key in Settings to continue."
            })
            st.rerun()

        # Check if follow-up question
        if st.session_state.research and len(query.split()) < 15:
            with st.spinner("Thinking..."):
                answer = answer_question(client, query, st.session_state.research)
            st.session_state.messages.append({'role': 'assistant', 'content': answer})
            st.rerun()

        # New research
        progress = st.empty()

        # Step 1: Understand
        progress.markdown("*Understanding your request...*")
        try:
            parsed = understand_query(client, query)
        except:
            parsed = {'clear': True, 'subjects': [query], 'schema': {'name': 'Name', 'details': 'Details'}}

        if not parsed.get('clear') and parsed.get('clarification'):
            st.session_state.messages.append({
                'role': 'assistant',
                'content': parsed['clarification']
            })
            progress.empty()
            st.rerun()

        # Step 2: Find sources
        progress.markdown("*Finding sources...*")
        try:
            sources = find_sources(client, query, parsed.get('subjects', [query]))
        except:
            sources = []

        if not sources:
            st.session_state.messages.append({
                'role': 'assistant',
                'content': "I couldn't find relevant sources for that query. Could you try rephrasing?"
            })
            progress.empty()
            st.rerun()

        # Step 3: Extract
        progress.markdown(f"*Researching {len(sources)} sources...*")
        schema = parsed.get('schema', {'name': 'Name', 'info': 'Key information'})

        results = []
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(extract_data, client, s['url'], schema, query): s for s in sources}
            for future in as_completed(futures):
                results.append(future.result())
                progress.markdown(f"*Researching {len(sources)} sources... ({len(results)}/{len(sources)})*")

        # Step 4: Synthesize
        progress.markdown("*Analyzing findings...*")
        try:
            synthesis = synthesize(client, query, results)
        except Exception as e:
            synthesis = {'summary': f'Completed research with {sum(1 for r in results if r.get("_ok"))} sources.', 'findings': []}

        progress.empty()

        # Save research
        research_data = {
            'query': query,
            'results': results,
            'synthesis': synthesis,
            'timestamp': datetime.now().isoformat()
        }
        st.session_state.research = research_data

        # Add response
        successful = sum(1 for r in results if r.get('_ok'))
        st.session_state.messages.append({
            'role': 'assistant',
            'content': f"Here's what I found ({successful} sources analyzed):",
            'research': research_data
        })

        st.rerun()


if __name__ == "__main__":
    main()

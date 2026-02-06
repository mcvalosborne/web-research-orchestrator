"""
Web Research Orchestrator - Claude Web Search Edition
Primary: Claude's built-in web search for grounded, cited answers
Backup: Brave Search + Firecrawl for deep extraction
"""

import streamlit as st
import json
import os
import hashlib
from datetime import datetime

# Core imports
try:
    import anthropic
    import pandas as pd
    import httpx
except ImportError as e:
    st.error(f"Missing dependency: {e}")
    st.stop()

# ============ Configuration ============

MODEL = "claude-sonnet-4-20250514"
WEB_SEARCH_BETA = "web-search-2025-03-05"

# Cost per 1M tokens
COSTS = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
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
        line-height: 1.7;
    }

    .citation {
        display: inline-block;
        background: #e8f4f8;
        color: #0369a1;
        padding: 0.1rem 0.4rem;
        border-radius: 0.25rem;
        font-size: 0.75rem;
        text-decoration: none;
        margin: 0 0.1rem;
    }
    .citation:hover {
        background: #0369a1;
        color: white;
    }

    .sources-list {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
    .source-item {
        padding: 0.5rem 0;
        border-bottom: 1px solid #e2e8f0;
        font-size: 0.9rem;
    }
    .source-item:last-child {
        border-bottom: none;
    }
    .source-item a {
        color: #0369a1;
        text-decoration: none;
    }
    .source-item a:hover {
        text-decoration: underline;
    }
    .source-title {
        font-weight: 500;
    }
    .source-url {
        color: #64748b;
        font-size: 0.8rem;
    }

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

    .thinking {
        color: #666;
        font-style: italic;
        padding: 0.5rem 0;
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
    defaults = {
        'messages': [],
        'history': [],
        'total_cost': 0.0,
        'session_cost': 0.0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def get_client():
    key = get_secret('ANTHROPIC_API_KEY')
    if not key:
        return None
    return anthropic.Anthropic(api_key=key)


def track_cost(input_tokens, output_tokens):
    cost = (input_tokens * COSTS[MODEL]["input"] + output_tokens * COSTS[MODEL]["output"]) / 1_000_000
    st.session_state.session_cost += cost
    st.session_state.total_cost += cost
    return cost


# ============ Claude Web Search ============

def research_with_web_search(client, query, max_searches=5):
    """
    Use Claude's built-in web search for grounded research.
    Returns structured response with text and citations.
    """
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            betas=[WEB_SEARCH_BETA],
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": max_searches
            }],
            messages=[{
                "role": "user",
                "content": f"""Research the following topic and provide a comprehensive, well-organized response:

{query}

Requirements:
1. Search for current, accurate information
2. Compare options if the query involves comparison
3. Include specific data (prices, features, dates) when available
4. Organize with clear headings and bullet points
5. If comparing items, create a summary table at the end
6. Be specific and cite your sources"""
            }]
        )

        # Track cost
        track_cost(response.usage.input_tokens, response.usage.output_tokens)

        # Parse response
        text_content = ""
        sources = []
        search_queries_used = []

        for block in response.content:
            if block.type == "text":
                text_content += block.text
            elif block.type == "web_search_tool_result":
                for result in block.content:
                    if hasattr(result, 'url'):
                        sources.append({
                            'url': result.url,
                            'title': getattr(result, 'title', ''),
                            'snippet': getattr(result, 'snippet', getattr(result, 'encrypted_content', ''))[:200]
                        })

        # Dedupe sources by URL
        seen = set()
        unique_sources = []
        for s in sources:
            if s['url'] not in seen:
                seen.add(s['url'])
                unique_sources.append(s)

        return {
            'text': text_content,
            'sources': unique_sources[:10],  # Top 10 sources
            'search_count': response.usage.server_tool_use.get('web_search_requests', 0) if hasattr(response.usage, 'server_tool_use') else 0,
            'input_tokens': response.usage.input_tokens,
            'output_tokens': response.usage.output_tokens,
            'success': True
        }

    except Exception as e:
        return {
            'text': f"Error during research: {str(e)}",
            'sources': [],
            'success': False,
            'error': str(e)
        }


def answer_followup(client, question, context):
    """Answer follow-up question using previous research context."""
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            betas=[WEB_SEARCH_BETA],
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 3
            }],
            messages=[{
                "role": "user",
                "content": f"""Previous research topic: {context.get('query', 'Unknown')}

Previous findings summary:
{context.get('text', '')[:2000]}

Follow-up question: {question}

Answer the follow-up question. Search for additional information if needed."""
            }]
        )

        track_cost(response.usage.input_tokens, response.usage.output_tokens)

        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text

        return text

    except Exception as e:
        return f"Error: {str(e)}"


# ============ UI Components ============

def render_header():
    st.markdown('''
    <div class="app-header">
        <h1>🔬 Research Assistant</h1>
        <p>AI-powered research with real-time web search</p>
        <div class="status-bar">
            <span class="badge active">🌐 Claude Web Search</span>
            <span class="badge active">📊 Grounded Citations</span>
        </div>
    </div>
    ''', unsafe_allow_html=True)


def render_message(msg, msg_idx=0):
    if msg['role'] == 'user':
        st.markdown(f'<div class="user-msg">{msg["content"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="assistant-msg">', unsafe_allow_html=True)

        # Render the text content
        text = msg.get('content', '')
        st.markdown(text)

        st.markdown('</div>', unsafe_allow_html=True)

        # Render research results if present
        if msg.get('research'):
            render_research_results(msg['research'], msg_idx)


def render_research_results(research, msg_idx=0):
    key_prefix = str(msg_idx)
    sources = research.get('sources', [])

    # Sources section
    if sources:
        with st.expander(f"📚 Sources ({len(sources)} citations)", expanded=False):
            for i, s in enumerate(sources):
                st.markdown(f"""
                <div class="source-item">
                    <span class="source-title">[{i+1}] {s.get('title', 'Source')[:60]}</span><br>
                    <a href="{s.get('url', '#')}" target="_blank" class="source-url">{s.get('url', '')[:80]}...</a>
                </div>
                """, unsafe_allow_html=True)

    # Export buttons
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        json_data = json.dumps(research, indent=2, default=str)
        st.download_button(
            "📥 JSON",
            json_data,
            file_name=f"research_{key_prefix}.json",
            mime="application/json",
            use_container_width=True,
            key=f"dl_json_{key_prefix}"
        )

    # Stats
    with col3:
        searches = research.get('search_count', 0)
        st.caption(f"🔍 {searches} web searches")


def render_cost_badge():
    if st.session_state.session_cost > 0:
        st.markdown(f'''
        <div class="cost-badge">
            💰 ${st.session_state.session_cost:.4f}
        </div>
        ''', unsafe_allow_html=True)


# ============ Main App ============

def main():
    init_state()

    if not check_password():
        return

    render_header()

    # Sidebar
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
        st.markdown("### Stats")
        st.caption(f"Session cost: ${st.session_state.session_cost:.4f}")

    # Chat history
    for idx, msg in enumerate(st.session_state.messages):
        render_message(msg, idx)

    # Example prompts if empty
    if not st.session_state.messages:
        st.markdown("#### Try asking:")
        examples = [
            "Compare pricing for Notion vs Obsidian vs Roam",
            "What are the top 5 CRM tools for startups in 2025?",
            "Compare AWS vs GCP vs Azure pricing and features",
            "Best project management software for remote teams"
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

        # Check if follow-up question
        current_research = None
        for msg in reversed(st.session_state.messages[:-1]):
            if msg.get('research'):
                current_research = msg['research']
                break

        if current_research and len(query.split()) < 20:
            # Answer follow-up
            with st.spinner("Researching..."):
                answer = answer_followup(client, query, current_research)
            st.session_state.messages.append({
                'role': 'assistant',
                'content': answer
            })
            st.rerun()

        # New research
        with st.spinner("🔍 Searching the web and analyzing results..."):
            result = research_with_web_search(client, query)

        if result['success']:
            # Add to history
            st.session_state.history.append({
                'query': query,
                'messages': st.session_state.messages.copy(),
                'timestamp': datetime.now().isoformat()
            })

            # Add response
            st.session_state.messages.append({
                'role': 'assistant',
                'content': result['text'],
                'research': {
                    'query': query,
                    'text': result['text'],
                    'sources': result['sources'],
                    'search_count': result.get('search_count', 0),
                    'timestamp': datetime.now().isoformat()
                }
            })
        else:
            st.session_state.messages.append({
                'role': 'assistant',
                'content': f"I encountered an issue: {result.get('error', 'Unknown error')}. Please try again."
            })

        st.rerun()


if __name__ == "__main__":
    main()

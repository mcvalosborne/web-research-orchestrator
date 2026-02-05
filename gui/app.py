"""
Web Research Orchestrator - Streamlit GUI
A visual interface for running multi-model web research with Claude.

Features:
- Multi-strategy extraction (CSS/Regex → LLM fallback)
- Pydantic validation for data quality
- Cost tracking and comparison
- Parallel Haiku workers
"""

import streamlit as st
import anthropic
import json
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import os
import requests

# Import multi-strategy extraction module
try:
    from extraction import (
        MultiStrategyExtractor,
        ExtractedData,
        ValidationResult,
        validate_extracted_data,
        fetch_html_sync,
        extract_with_fallback,
        get_extraction_stats,
    )
    EXTRACTION_MODULE_AVAILABLE = True
except ImportError:
    EXTRACTION_MODULE_AVAILABLE = False

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
    .agent-flow {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
        color: white;
    }
    .agent-node {
        display: inline-block;
        background: rgba(233, 69, 96, 0.2);
        border: 2px solid #e94560;
        border-radius: 8px;
        padding: 8px 16px;
        margin: 4px;
        font-size: 0.9rem;
    }
    .agent-node.active {
        background: #e94560;
        animation: pulse 1s infinite;
    }
    .agent-node.complete {
        background: rgba(46, 204, 113, 0.3);
        border-color: #2ecc71;
    }
    .agent-node.failed {
        background: rgba(231, 76, 60, 0.3);
        border-color: #e74c3c;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
    }
    .flow-arrow {
        color: #e94560;
        font-size: 1.5rem;
        margin: 0 8px;
    }
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #e94560, #ff6b6b);
    }
    .chat-message {
        padding: 12px;
        border-radius: 8px;
        margin: 8px 0;
    }
    .chat-user {
        background: #e8f4f8;
        border-left: 4px solid #3498db;
    }
    .chat-assistant {
        background: #f8f8f8;
        border-left: 4px solid #e94560;
    }
</style>
""", unsafe_allow_html=True)


def get_secret(key: str, default: str = "") -> str:
    """Get a secret from Streamlit secrets or environment variables."""
    # Try Streamlit secrets first (for cloud deployment)
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    # Fall back to environment variables (for local development)
    return os.environ.get(key, default)


def check_password() -> bool:
    """Check if password protection is enabled and verify password."""
    # Check if password protection is configured
    try:
        passwords = st.secrets.get("passwords", {})
        if not passwords:
            return True  # No password protection configured
    except Exception:
        return True  # Secrets not available, skip password check

    # Initialize authentication state
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    # Show login form
    st.markdown("### 🔐 Login Required")
    st.markdown("This demo requires authentication.")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", type="primary")

        if submitted:
            if username in passwords and passwords[username] == password:
                st.session_state.authenticated = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("Invalid username or password")

    return False


def init_session_state():
    """Initialize session state variables."""
    if 'research_history' not in st.session_state:
        st.session_state.research_history = []
    if 'current_results' not in st.session_state:
        st.session_state.current_results = None
    if 'api_key' not in st.session_state:
        # Load from secrets first, then env vars
        st.session_state.api_key = get_secret('ANTHROPIC_API_KEY', '')
    if 'brave_api_key' not in st.session_state:
        st.session_state.brave_api_key = get_secret('BRAVE_API_KEY', '')
    if 'firecrawl_api_key' not in st.session_state:
        st.session_state.firecrawl_api_key = get_secret('FIRECRAWL_API_KEY', '')
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'agent_flow_log' not in st.session_state:
        st.session_state.agent_flow_log = []


# ============ Cost Tracking ============

# Pricing per 1M tokens (as of 2024)
MODEL_PRICING = {
    "claude-opus-4-5-20251101": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    # Fallbacks for any model string containing these
    "opus": {"input": 15.00, "output": 75.00},
    "sonnet": {"input": 3.00, "output": 15.00},
    "haiku": {"input": 0.80, "output": 4.00},
}

def get_model_pricing(model_name: str) -> dict:
    """Get pricing for a model."""
    if model_name in MODEL_PRICING:
        return MODEL_PRICING[model_name]
    # Fallback: check if model name contains known model type
    for key in ["opus", "sonnet", "haiku"]:
        if key in model_name.lower():
            return MODEL_PRICING[key]
    return MODEL_PRICING["sonnet"]  # Default to Sonnet pricing

def calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Calculate cost for a single API call."""
    pricing = get_model_pricing(model)
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost

def calculate_opus_equivalent_cost(input_tokens: int, output_tokens: int) -> float:
    """Calculate what it would cost if we used Opus for everything."""
    pricing = MODEL_PRICING["opus"]
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost

class CostTracker:
    """Track API costs across a research session."""

    def __init__(self):
        self.calls = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def add_call(self, model: str, input_tokens: int, output_tokens: int, agent_type: str = "worker"):
        """Record an API call."""
        cost = calculate_cost(input_tokens, output_tokens, model)
        self.calls.append({
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "agent_type": agent_type
        })
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    def get_total_cost(self) -> float:
        """Get total actual cost."""
        return sum(c["cost"] for c in self.calls)

    def get_opus_equivalent_cost(self) -> float:
        """Get what it would cost with Opus only."""
        return calculate_opus_equivalent_cost(self.total_input_tokens, self.total_output_tokens)

    def get_savings(self) -> tuple:
        """Get savings amount and percentage."""
        actual = self.get_total_cost()
        opus = self.get_opus_equivalent_cost()
        savings = opus - actual
        percentage = (savings / opus * 100) if opus > 0 else 0
        return savings, percentage

    def get_breakdown(self) -> dict:
        """Get cost breakdown by agent type."""
        breakdown = {"orchestrator": 0, "worker": 0, "analyst": 0, "qa": 0}
        for call in self.calls:
            agent_type = call.get("agent_type", "worker")
            if agent_type in breakdown:
                breakdown[agent_type] += call["cost"]
            else:
                breakdown["worker"] += call["cost"]
        return breakdown

    def get_summary(self) -> dict:
        """Get full cost summary."""
        actual_cost = self.get_total_cost()
        opus_cost = self.get_opus_equivalent_cost()
        savings, savings_pct = self.get_savings()

        return {
            "total_calls": len(self.calls),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "actual_cost": actual_cost,
            "opus_equivalent_cost": opus_cost,
            "savings": savings,
            "savings_percentage": savings_pct,
            "breakdown": self.get_breakdown(),
            "calls": self.calls
        }


def get_client():
    """Get Anthropic client."""
    api_key = st.session_state.api_key or os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)


def log_agent_activity(agent_name: str, status: str, message: str, thread_safe: bool = False):
    """Log agent activity for visualization."""
    # Skip logging if called from a thread (session_state not available)
    if thread_safe:
        return
    try:
        if 'agent_flow_log' in st.session_state:
            st.session_state.agent_flow_log.append({
                'timestamp': datetime.now().isoformat(),
                'agent': agent_name,
                'status': status,  # 'active', 'complete', 'failed'
                'message': message
            })
    except:
        pass  # Silently fail if called from thread


def render_agent_flow(container):
    """Render the agent flow visualization."""
    if not st.session_state.agent_flow_log:
        return

    html = '<div class="agent-flow">'
    html += '<h4 style="color: #e94560; margin-bottom: 15px;">🔄 Agent Activity Flow</h4>'

    # Group by agent
    agents = {}
    for log in st.session_state.agent_flow_log:
        agent = log['agent']
        if agent not in agents:
            agents[agent] = {'status': log['status'], 'messages': []}
        agents[agent]['status'] = log['status']
        agents[agent]['messages'].append(log['message'])

    # Render flow
    for i, (agent, data) in enumerate(agents.items()):
        status_class = data['status']
        html += f'<span class="agent-node {status_class}">{agent}</span>'
        if i < len(agents) - 1:
            html += '<span class="flow-arrow">→</span>'

    html += '<div style="margin-top: 15px; font-size: 0.85rem; color: #aaa;">'
    # Show last 5 activities
    for log in st.session_state.agent_flow_log[-5:]:
        icon = "🟢" if log['status'] == 'complete' else "🔴" if log['status'] == 'failed' else "🟡"
        html += f'<div>{icon} [{log["agent"]}] {log["message"]}</div>'
    html += '</div></div>'

    container.markdown(html, unsafe_allow_html=True)


# ============ API Integration Functions ============

def brave_search(query: str, num_results: int = 10) -> list:
    """Search using Brave Search API."""
    if not st.session_state.brave_api_key:
        return []

    try:
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": st.session_state.brave_api_key
        }
        params = {
            "q": query,
            "count": num_results
        }
        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers,
            params=params,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get('web', {}).get('results', []):
            results.append({
                'url': item.get('url'),
                'title': item.get('title'),
                'description': item.get('description', ''),
                'type': 'search_result',
                'relevance': 'high'
            })
        return results

    except Exception as e:
        st.warning(f"Brave Search failed: {e}")
        return []


def firecrawl_scrape_direct(url: str, api_key: str) -> dict:
    """Scrape a URL using Firecrawl API (thread-safe version)."""
    if not api_key:
        return {'error': 'Firecrawl API key not set'}

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "url": url,
            "formats": ["markdown"]
        }
        response = requests.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        if data.get('success'):
            return {
                'success': True,
                'content': data.get('data', {}).get('markdown', ''),
                'metadata': data.get('data', {}).get('metadata', {})
            }
        else:
            return {'error': data.get('error', 'Unknown error')}

    except Exception as e:
        return {'error': str(e)}


def firecrawl_scrape(url: str) -> dict:
    """Scrape a URL using Firecrawl API."""
    if not st.session_state.firecrawl_api_key:
        return {'error': 'Firecrawl API key not set'}

    try:
        headers = {
            "Authorization": f"Bearer {st.session_state.firecrawl_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "url": url,
            "formats": ["markdown"]
        }
        response = requests.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        if data.get('success'):
            return {
                'success': True,
                'content': data.get('data', {}).get('markdown', ''),
                'metadata': data.get('data', {}).get('metadata', {})
            }
        else:
            return {'error': data.get('error', 'Unknown error')}

    except Exception as e:
        return {'error': str(e)}


# ============ Worker Functions ============

def run_haiku_worker(client, url: str, schema: dict, worker_id: int, model: str = "claude-3-5-haiku-20241022", use_firecrawl: bool = False, firecrawl_key: str = "", use_multi_strategy: bool = True) -> dict:
    """
    Run a worker to extract data from a URL.

    Uses multi-strategy extraction:
    1. CSS/XPath selectors (free, fast)
    2. Regex patterns (free, fast)
    3. LLM extraction (costly, slow) - only if needed

    This reduces costs by ~60% by avoiding LLM calls when simpler methods work.
    """

    # Note: Can't log from threads, will log from main thread after completion

    content_source = "direct"
    extra_content = ""
    html_content = None
    input_tokens = 0
    output_tokens = 0

    # Try Firecrawl first if enabled (key passed from main thread)
    if use_firecrawl and firecrawl_key:
        firecrawl_result = firecrawl_scrape_direct(url, firecrawl_key)
        if firecrawl_result.get('success'):
            extra_content = firecrawl_result.get('content', '')[:8000]
            html_content = extra_content
            content_source = "firecrawl"

    # ============ Multi-Strategy Extraction (CSS/Regex first) ============
    if use_multi_strategy and EXTRACTION_MODULE_AVAILABLE:
        try:
            # Fetch HTML if not already fetched via Firecrawl
            if html_content is None:
                html_content, fetch_error = fetch_html_sync(url, timeout=15)

            if html_content:
                # Try CSS/Regex extraction first (FREE)
                extractor = MultiStrategyExtractor(html_content, url)
                css_result = extractor.extract_all(schema)

                # If we got good results without LLM, return early (cost savings!)
                if css_result.confidence >= 0.6 and len(css_result.fields_missing) <= len(schema) * 0.3:
                    # Validate the data
                    validation = validate_extracted_data(css_result.data, schema)

                    result = css_result.data.copy()
                    result['_worker_id'] = worker_id
                    result['_url'] = url
                    result['_success'] = validation.is_valid or css_result.confidence >= 0.5
                    result['_attempt'] = 1
                    result['_source'] = content_source
                    result['_extraction_method'] = css_result.extraction_method
                    result['_confidence'] = css_result.confidence
                    result['_model'] = 'none'  # No LLM used!
                    result['_input_tokens'] = 0  # Free extraction
                    result['_output_tokens'] = 0
                    result['_fields_extracted'] = css_result.fields_extracted
                    result['_fields_missing'] = css_result.fields_missing
                    result['_validation_errors'] = css_result.validation_errors + validation.errors

                    return result

                # CSS/Regex got partial results - use LLM only for missing fields
                if css_result.fields_extracted and css_result.fields_missing:
                    # Only ask LLM about missing fields (cost optimization)
                    missing_schema = {k: schema[k] for k in css_result.fields_missing}
                    content_source = "hybrid"

                    prompt = f"""You are a data extraction worker. I already extracted some data using HTML parsing.
Extract ONLY the missing fields from this URL.

URL: {url}

CONTENT (first 5000 chars):
{html_content[:5000]}

ALREADY EXTRACTED (do not re-extract):
{json.dumps(css_result.data, indent=2)}

MISSING FIELDS TO EXTRACT:
{json.dumps(missing_schema, indent=2)}

Return ONLY valid JSON with the missing fields. Use null if not found."""

                    response = client.messages.create(
                        model=model,
                        max_tokens=1500,
                        messages=[{"role": "user", "content": prompt}]
                    )

                    input_tokens = response.usage.input_tokens
                    output_tokens = response.usage.output_tokens

                    result_text = response.content[0].text.strip()
                    if result_text.startswith("```"):
                        result_text = result_text.split("```")[1]
                        if result_text.startswith("json"):
                            result_text = result_text[4:]

                    llm_result = json.loads(result_text)

                    # Merge CSS results with LLM results
                    merged = css_result.data.copy()
                    for k, v in llm_result.items():
                        if v is not None and k not in merged:
                            merged[k] = v

                    # Validate merged data
                    validation = validate_extracted_data(merged, schema)

                    result = merged.copy()
                    result['_worker_id'] = worker_id
                    result['_url'] = url
                    result['_success'] = 'error' not in result
                    result['_attempt'] = 1
                    result['_source'] = content_source
                    result['_extraction_method'] = 'hybrid'
                    result['_confidence'] = (css_result.confidence + 0.7) / 2
                    result['_model'] = model
                    result['_input_tokens'] = input_tokens
                    result['_output_tokens'] = output_tokens
                    result['_css_extracted'] = css_result.fields_extracted
                    result['_llm_extracted'] = list(llm_result.keys())

                    return result

        except Exception as e:
            # Multi-strategy failed, fall back to full LLM extraction
            pass

    # ============ Full LLM Extraction (fallback) ============
    if html_content and len(html_content) > 100:
        extra_content = f"\n\nPAGE CONTENT:\n{html_content[:5000]}"

    prompt = f"""You are a data extraction worker. Extract structured data from this URL.

URL: {url}
{extra_content if extra_content else ''}

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

        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        result = json.loads(result_text)

        # Validate with Pydantic if available
        if EXTRACTION_MODULE_AVAILABLE:
            validation = validate_extracted_data(result, schema)
            if validation.cleaned_data:
                result.update(validation.cleaned_data)

        result['_worker_id'] = worker_id
        result['_url'] = url
        result['_success'] = 'error' not in result
        result['_attempt'] = 1
        result['_source'] = content_source
        result['_extraction_method'] = 'llm'
        result['_model'] = model
        result['_input_tokens'] = response.usage.input_tokens
        result['_output_tokens'] = response.usage.output_tokens

        return result

    except json.JSONDecodeError:
        return {
            '_worker_id': worker_id,
            '_url': url,
            '_success': False,
            '_attempt': 1,
            '_extraction_method': 'llm',
            '_model': model,
            '_input_tokens': response.usage.input_tokens if 'response' in locals() else 0,
            '_output_tokens': response.usage.output_tokens if 'response' in locals() else 0,
            'error': 'Failed to parse response as JSON',
            'raw_response': result_text[:500] if 'result_text' in locals() else 'No response'
        }
    except Exception as e:
        return {
            '_worker_id': worker_id,
            '_url': url,
            '_success': False,
            '_attempt': 1,
            '_extraction_method': 'llm',
            '_model': model,
            '_input_tokens': 0,
            '_output_tokens': 0,
            'error': str(e)
        }


def run_discovery_search(client, topic: str, num_results: int = 10, model: str = "claude-sonnet-4-20250514", use_brave: bool = False) -> tuple:
    """Use Claude to generate relevant search queries and find URLs. Returns (results, token_info)."""

    log_agent_activity("Discovery", "active", f"Finding sources for: {topic[:50]}...")

    # Try Brave Search first if enabled
    if use_brave and st.session_state.brave_api_key:
        log_agent_activity("Brave Search", "active", "Searching web...")
        brave_results = brave_search(topic, num_results)
        if brave_results:
            log_agent_activity("Brave Search", "complete", f"Found {len(brave_results)} results")
            return brave_results, {"input_tokens": 0, "output_tokens": 0, "model": model}

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

        results = json.loads(result_text)
        log_agent_activity("Discovery", "complete", f"Found {len(results)} sources")
        token_info = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens, "model": model}
        return results, token_info

    except Exception as e:
        log_agent_activity("Discovery", "failed", f"Error: {str(e)[:50]}")
        st.error(f"Discovery search failed: {e}")
        return [], {"input_tokens": 0, "output_tokens": 0, "model": model}


def analyze_failures_and_get_recovery_strategy(client, topic: str, failed_results: list, schema: dict, model: str = "claude-sonnet-4-20250514") -> tuple:
    """Analyze why extractions failed and generate recovery strategies. Returns (result, token_info)."""

    log_agent_activity("Recovery Planner", "active", "Analyzing failures...")

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

        result = json.loads(result_text)
        log_agent_activity("Recovery Planner", "complete", f"Generated {len(result.get('alternative_urls', []))} alternatives")
        token_info = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens, "model": model}
        return result, token_info

    except Exception as e:
        log_agent_activity("Recovery Planner", "failed", f"Error: {str(e)[:50]}")
        return {"error": str(e)}, {"input_tokens": 0, "output_tokens": 0, "model": model}


def run_recovery_search_worker(client, query: str, topic: str, schema: dict, worker_id: int, model: str = "claude-3-5-haiku-20241022") -> dict:
    """Run a recovery worker that searches and extracts data using web search."""

    # Note: Can't log from threads

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
        result['_model'] = model
        result['_input_tokens'] = response.usage.input_tokens
        result['_output_tokens'] = response.usage.output_tokens

        return result

    except Exception as e:
        return {
            '_worker_id': worker_id,
            '_recovery': True,
            '_success': False,
            '_attempt': 2,
            '_model': model,
            '_input_tokens': 0,
            '_output_tokens': 0,
            'error': str(e),
            'query': query
        }


def run_alternative_url_worker(client, url_info: dict, schema: dict, worker_id: int, model: str = "claude-3-5-haiku-20241022", use_firecrawl: bool = False, firecrawl_key: str = "") -> dict:
    """Try to extract from an alternative URL suggested by recovery strategy."""

    url = url_info.get('url', '')
    rationale = url_info.get('rationale', '')

    # Note: Can't log from threads

    # Try Firecrawl if enabled (key passed from main thread)
    extra_content = ""
    if use_firecrawl and firecrawl_key:
        firecrawl_result = firecrawl_scrape_direct(url, firecrawl_key)
        if firecrawl_result.get('success'):
            extra_content = f"\n\nSCRAPED CONTENT:\n{firecrawl_result.get('content', '')[:5000]}"

    prompt = f"""You are a data extraction worker trying an alternative source.

URL: {url}
WHY THIS SOURCE: {rationale}
{extra_content}

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
        result['_model'] = model
        result['_input_tokens'] = response.usage.input_tokens
        result['_output_tokens'] = response.usage.output_tokens

        return result

    except Exception as e:
        return {
            '_worker_id': worker_id,
            '_url': url,
            '_recovery': True,
            '_success': False,
            '_attempt': 2,
            '_model': model,
            '_input_tokens': 0,
            '_output_tokens': 0,
            'error': str(e)
        }


def synthesize_results(client, topic: str, results: list, recovery_results: list = None, model: str = "claude-sonnet-4-20250514") -> tuple:
    """Use Sonnet to synthesize results into a final report. Returns (result, token_info)."""

    log_agent_activity("Synthesizer", "active", "Analyzing all results...")

    all_results = results.copy()
    if recovery_results:
        all_results.extend(recovery_results)

    successful = [r for r in all_results if r.get('_success', False)]
    failed = [r for r in all_results if not r.get('_success', False)]

    failed_summary = [{'url': r.get('_url', r.get('query', 'unknown')), 'error': r.get('error', 'unknown')} for r in failed]

    prompt = f"""Synthesize these research results into a comprehensive summary.

RESEARCH TOPIC: {topic}

SUCCESSFUL EXTRACTIONS ({len(successful)}):
{json.dumps(successful, indent=2)}

FAILED EXTRACTIONS ({len(failed)}):
{json.dumps(failed_summary, indent=2)}

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

        result = json.loads(result_text)
        log_agent_activity("Synthesizer", "complete", "Synthesis complete")
        token_info = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens, "model": model}
        return result, token_info

    except Exception as e:
        log_agent_activity("Synthesizer", "failed", f"Error: {str(e)[:50]}")
        return {"error": str(e), "raw_results": all_results}, {"input_tokens": 0, "output_tokens": 0, "model": model}


def run_analyst_agent(client, topic: str, results: dict, model: str = "claude-sonnet-4-20250514") -> tuple:
    """Analyst agent that creates visualizations and insights from the data. Returns (result, token_info)."""

    log_agent_activity("Analyst", "active", "Creating visualizations...")

    all_results = results.get('extraction_results', []) + results.get('recovery_results', [])
    successful = [r for r in all_results if r.get('_success', False)]

    prompt = f"""You are a data analyst. Create visualizations and structured analysis from this research data.

RESEARCH TOPIC: {topic}

DATA COLLECTED:
{json.dumps(successful, indent=2)}

SYNTHESIS:
{json.dumps(results.get('synthesis', {}), indent=2)}

Create an analysis with:
1. A summary table of the key data points (as markdown table)
2. Comparison insights if multiple items were researched
3. Trends or patterns you notice
4. Recommended chart types for this data (with the data formatted for each)

Return as JSON:
{{
  "summary_table_markdown": "| Column 1 | Column 2 |\\n|---|---|\\n| data | data |",
  "comparison_insights": ["insight 1", "insight 2"],
  "trends_patterns": ["pattern 1", "pattern 2"],
  "charts": [
    {{
      "type": "bar|line|pie|scatter",
      "title": "Chart title",
      "description": "What this shows",
      "data": {{"labels": [...], "values": [...], "series_name": "..."}}
    }}
  ],
  "key_metrics": [
    {{"metric": "name", "value": "X", "context": "explanation"}}
  ]
}}"""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text.strip()

        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        result = json.loads(result_text)
        log_agent_activity("Analyst", "complete", f"Created {len(result.get('charts', []))} charts")
        token_info = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens, "model": model}
        return result, token_info

    except Exception as e:
        log_agent_activity("Analyst", "failed", f"Error: {str(e)[:50]}")
        return {"error": str(e)}, {"input_tokens": 0, "output_tokens": 0, "model": model}


def run_followup_qa(client, question: str, results: dict, chat_history: list, model: str = "claude-sonnet-4-20250514") -> tuple:
    """Answer follow-up questions about the research data. Returns (answer, token_info)."""

    log_agent_activity("Q&A Agent", "active", f"Answering: {question[:40]}...")

    # Build context from results
    context = {
        'topic': results.get('topic'),
        'synthesis': results.get('synthesis'),
        'successful_extractions': [r for r in results.get('extraction_results', []) + results.get('recovery_results', []) if r.get('_success')],
        'sources': results.get('sources', [])
    }

    # Build chat messages
    messages = []

    # System context
    messages.append({
        "role": "user",
        "content": f"""You are a research assistant helping analyze research data. Here is the context:

RESEARCH TOPIC: {context['topic']}

SYNTHESIS:
{json.dumps(context['synthesis'], indent=2)}

EXTRACTED DATA:
{json.dumps(context['successful_extractions'], indent=2)}

SOURCES:
{json.dumps(context['sources'], indent=2)}

Answer questions about this research data. Be specific and cite the data when relevant."""
    })

    messages.append({
        "role": "assistant",
        "content": "I understand the research data. I'm ready to answer your questions about the findings."
    })

    # Add chat history
    for msg in chat_history[-10:]:  # Last 10 messages
        messages.append({"role": msg['role'], "content": msg['content']})

    # Add current question
    messages.append({"role": "user", "content": question})

    try:
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=messages
        )

        answer = response.content[0].text.strip()
        log_agent_activity("Q&A Agent", "complete", "Answered question")
        token_info = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens, "model": model}
        return answer, token_info

    except Exception as e:
        log_agent_activity("Q&A Agent", "failed", f"Error: {str(e)[:50]}")
        return f"Error answering question: {str(e)}", {"input_tokens": 0, "output_tokens": 0, "model": model}


def main():
    init_session_state()

    # Check password protection (for cloud demos)
    if not check_password():
        return  # Stop here if not authenticated

    # Header
    st.markdown('<p class="main-header">🔬 Web Research Orchestrator</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Multi-model research with automatic retry, analysis & visualization</p>', unsafe_allow_html=True)
    st.divider()

    # Check if API key is pre-configured via secrets
    api_key_from_secrets = bool(get_secret('ANTHROPIC_API_KEY', ''))

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Show logged in user if authenticated
        if st.session_state.get('authenticated') and st.session_state.get('username'):
            st.caption(f"👤 Logged in as: {st.session_state.username}")
            if st.button("Logout", type="secondary", use_container_width=True):
                st.session_state.authenticated = False
                st.session_state.username = None
                st.rerun()
            st.divider()

        # API Keys Section - collapsed if pre-configured
        with st.expander("🔑 API Keys", expanded=not api_key_from_secrets):
            if api_key_from_secrets:
                st.success("✓ API keys loaded from secrets")

            api_key_input = st.text_input(
                "Anthropic API Key *",
                value=st.session_state.api_key,
                type="password",
                help="Required. Pre-configured via secrets." if api_key_from_secrets else "Required. Set ANTHROPIC_API_KEY env var to skip.",
                disabled=api_key_from_secrets
            )
            if api_key_input:
                st.session_state.api_key = api_key_input

            st.divider()

            brave_key_input = st.text_input(
                "Brave Search API Key",
                value=st.session_state.brave_api_key,
                type="password",
                help="Optional. Enables real web search. Get free key at brave.com/search/api/"
            )
            if brave_key_input:
                st.session_state.brave_api_key = brave_key_input

            firecrawl_key_input = st.text_input(
                "Firecrawl API Key",
                value=st.session_state.firecrawl_api_key,
                type="password",
                help="Optional. Enables JS rendering & anti-bot bypass. Get free key at firecrawl.dev"
            )
            if firecrawl_key_input:
                st.session_state.firecrawl_api_key = firecrawl_key_input

            # Show API status
            st.caption("API Status:")
            st.caption(f"{'✅' if st.session_state.api_key else '❌'} Anthropic (required)")
            st.caption(f"{'✅' if st.session_state.brave_api_key else '⬜'} Brave Search (optional)")
            st.caption(f"{'✅' if st.session_state.firecrawl_api_key else '⬜'} Firecrawl (optional)")

        st.divider()

        # Model selection
        st.subheader("🤖 Models")
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
        st.subheader("⚙️ Settings")
        max_workers = st.slider("Max Parallel Workers", 1, 10, 5)

        enable_recovery = st.checkbox("Enable automatic retry", value=True)
        recovery_threshold = st.slider("Retry if success below", 0, 100, 50, format="%d%%")

        use_brave = st.checkbox("Use Brave Search", value=bool(st.session_state.brave_api_key), disabled=not st.session_state.brave_api_key)
        use_firecrawl = st.checkbox("Use Firecrawl", value=bool(st.session_state.firecrawl_api_key), disabled=not st.session_state.firecrawl_api_key)

        st.divider()

        # History
        st.subheader("📜 History")
        if st.session_state.research_history:
            for i, item in enumerate(reversed(st.session_state.research_history[-5:])):
                if st.button(f"📄 {item['topic'][:25]}...", key=f"hist_{i}", use_container_width=True):
                    st.session_state.current_results = item['results']
                    st.session_state.chat_history = []
                    st.rerun()
        else:
            st.caption("No history yet")

    # Main content
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔍 Research", "📊 Results", "📈 Analysis", "💬 Q&A", "📥 Export"])

    with tab1:
        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("Research Topic")
            topic = st.text_area(
                "What would you like to research?",
                placeholder="e.g., Compare pricing for top 5 project management tools",
                height=100
            )

            research_type = st.radio(
                "Research Type",
                ["🔍 Auto-Discovery", "🎯 Custom URLs"],
                horizontal=True
            )

        with col2:
            st.subheader("Extraction Schema")
            default_schema = {
                "title": "Page/item title",
                "price": "Price if applicable",
                "features": ["Key features"],
                "data_points": {},
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
            urls_input = st.text_area(
                "Enter URLs (one per line)",
                placeholder="https://example.com/pricing",
                height=100
            )
            urls = [u.strip() for u in urls_input.strip().split('\n') if u.strip()]
            num_sources = len(urls)
        else:
            num_sources = st.slider("Number of sources", 5, 20, 10)
            urls = []

        # Agent flow visualization placeholder
        flow_container = st.empty()

        # Run button
        if st.button("🚀 Start Research", type="primary", use_container_width=True):
            client = get_client()

            if not client:
                st.error("Please enter your Anthropic API key")
            elif not topic:
                st.error("Please enter a research topic")
            else:
                # Clear previous flow log
                st.session_state.agent_flow_log = []

                # Initialize cost tracker
                cost_tracker = CostTracker()

                results = {
                    'topic': topic,
                    'timestamp': datetime.now().isoformat(),
                    'schema': schema,
                    'sources': [],
                    'extraction_results': [],
                    'recovery_results': [],
                    'recovery_strategy': None,
                    'synthesis': None,
                    'analysis': None,
                    'cost_summary': None
                }

                log_agent_activity("Orchestrator", "active", "Starting research...")

                # Phase 1: Discovery
                if research_type == "🔍 Auto-Discovery":
                    with st.status("🔍 Discovering sources...", expanded=True) as status:
                        render_agent_flow(flow_container)
                        discovered, discovery_tokens = run_discovery_search(client, topic, num_sources, model=orchestrator_model, use_brave=use_brave)

                        # Track discovery cost
                        if discovery_tokens.get('input_tokens', 0) > 0:
                            cost_tracker.add_call(discovery_tokens['model'], discovery_tokens['input_tokens'], discovery_tokens['output_tokens'], "orchestrator")

                        urls = [d['url'] for d in discovered]
                        results['sources'] = discovered

                        if urls:
                            st.write(f"Found {len(urls)} sources")
                        status.update(label=f"✓ Found {len(urls)} sources", state="complete")
                else:
                    results['sources'] = [{'url': u} for u in urls]

                if not urls:
                    st.error("No URLs to research")
                else:
                    # Phase 2: Extraction
                    with st.status(f"⚡ Extracting from {len(urls)} sources...", expanded=True) as status:
                        progress_bar = st.progress(0)
                        extraction_results = []

                        # Capture API key before entering thread pool (session_state not available in threads)
                        firecrawl_key = st.session_state.firecrawl_api_key if use_firecrawl else ""

                        with ThreadPoolExecutor(max_workers=max_workers) as executor:
                            futures = {
                                executor.submit(run_haiku_worker, client, url, schema, i, worker_model, use_firecrawl, firecrawl_key): (i, url)
                                for i, url in enumerate(urls)
                            }

                            completed = 0
                            for future in as_completed(futures):
                                result = future.result()
                                extraction_results.append(result)

                                # Track worker cost
                                if result.get('_input_tokens', 0) > 0:
                                    cost_tracker.add_call(result.get('_model', worker_model), result.get('_input_tokens', 0), result.get('_output_tokens', 0), "worker")

                                completed += 1
                                progress_bar.progress(completed / len(urls))
                                render_agent_flow(flow_container)

                        results['extraction_results'] = extraction_results
                        success_count = sum(1 for r in extraction_results if r.get('_success'))
                        success_rate = (success_count / len(urls)) * 100
                        status.update(label=f"✓ {success_count}/{len(urls)} succeeded ({success_rate:.0f}%)", state="complete")

                    # Phase 3: Recovery
                    failed_results = [r for r in extraction_results if not r.get('_success')]
                    recovery_results = []

                    if enable_recovery and success_rate < recovery_threshold and failed_results:
                        with st.status("🔄 Recovery phase...", expanded=True) as status:
                            render_agent_flow(flow_container)
                            recovery_strategy, recovery_tokens = analyze_failures_and_get_recovery_strategy(client, topic, failed_results, schema, orchestrator_model)

                            # Track recovery planning cost
                            if recovery_tokens.get('input_tokens', 0) > 0:
                                cost_tracker.add_call(recovery_tokens['model'], recovery_tokens['input_tokens'], recovery_tokens['output_tokens'], "orchestrator")

                            results['recovery_strategy'] = recovery_strategy

                            if 'error' not in recovery_strategy:
                                alt_urls = recovery_strategy.get('alternative_urls', [])[:5]
                                queries = recovery_strategy.get('web_search_queries', [])[:5]

                                # Capture API key before entering thread pool
                                firecrawl_key = st.session_state.firecrawl_api_key if use_firecrawl else ""

                                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                                    futures = {}
                                    for i, url_info in enumerate(alt_urls):
                                        futures[executor.submit(run_alternative_url_worker, client, url_info, schema, i, worker_model, use_firecrawl, firecrawl_key)] = i
                                    for i, query in enumerate(queries):
                                        futures[executor.submit(run_recovery_search_worker, client, query, topic, schema, len(alt_urls) + i, worker_model)] = i

                                    for future in as_completed(futures):
                                        result = future.result()
                                        recovery_results.append(result)

                                        # Track recovery worker cost
                                        if result.get('_input_tokens', 0) > 0:
                                            cost_tracker.add_call(result.get('_model', worker_model), result.get('_input_tokens', 0), result.get('_output_tokens', 0), "worker")

                                        render_agent_flow(flow_container)

                                results['recovery_results'] = recovery_results
                            status.update(label=f"✓ Recovery: {sum(1 for r in recovery_results if r.get('_success'))} additional", state="complete")

                    # Phase 4: Synthesis
                    with st.status("🧠 Synthesizing...", expanded=True) as status:
                        render_agent_flow(flow_container)
                        synthesis, synthesis_tokens = synthesize_results(client, topic, extraction_results, recovery_results, orchestrator_model)

                        # Track synthesis cost
                        if synthesis_tokens.get('input_tokens', 0) > 0:
                            cost_tracker.add_call(synthesis_tokens['model'], synthesis_tokens['input_tokens'], synthesis_tokens['output_tokens'], "orchestrator")

                        results['synthesis'] = synthesis
                        status.update(label="✓ Synthesis complete", state="complete")

                    # Phase 5: Analysis
                    with st.status("📊 Creating analysis...", expanded=True) as status:
                        render_agent_flow(flow_container)
                        analysis, analysis_tokens = run_analyst_agent(client, topic, results, orchestrator_model)

                        # Track analyst cost
                        if analysis_tokens.get('input_tokens', 0) > 0:
                            cost_tracker.add_call(analysis_tokens['model'], analysis_tokens['input_tokens'], analysis_tokens['output_tokens'], "analyst")

                        results['analysis'] = analysis
                        status.update(label="✓ Analysis complete", state="complete")

                    log_agent_activity("Orchestrator", "complete", "Research complete!")
                    render_agent_flow(flow_container)

                    # Store cost summary
                    results['cost_summary'] = cost_tracker.get_summary()

                    # Save
                    st.session_state.current_results = results
                    st.session_state.chat_history = []
                    st.session_state.research_history.append({
                        'topic': topic,
                        'timestamp': results['timestamp'],
                        'results': results
                    })

                    total = len(extraction_results) + len(recovery_results)
                    success = sum(1 for r in extraction_results + recovery_results if r.get('_success'))

                    # Display cost info
                    cost_summary = results['cost_summary']
                    st.success(f"✅ Complete! {success}/{total} sources. Check Results & Analysis tabs.")
                    st.info(f"💰 Cost: ${cost_summary['actual_cost']:.4f} (saved {cost_summary['savings_percentage']:.0f}% vs Opus-only: ${cost_summary['opus_equivalent_cost']:.4f})")

    with tab2:
        if st.session_state.current_results:
            results = st.session_state.current_results

            st.subheader(f"📋 {results['topic']}")

            if results.get('synthesis') and 'error' not in results['synthesis']:
                synthesis = results['synthesis']

                st.markdown("### Executive Summary")
                st.info(synthesis.get('executive_summary', 'N/A'))

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### Key Findings")
                    for f in synthesis.get('key_findings', []):
                        st.markdown(f"• {f}")

                with col2:
                    st.markdown("### Quality")
                    qa = synthesis.get('quality_assessment', {})
                    st.metric("Completeness", qa.get('completeness', 'N/A'))
                    st.metric("Confidence", qa.get('confidence', 'N/A'))

                if synthesis.get('gaps'):
                    with st.expander("Gaps & Limitations"):
                        for g in synthesis['gaps']:
                            st.markdown(f"• {g}")

                if synthesis.get('recommendations'):
                    with st.expander("💡 Recommendations"):
                        for r in synthesis['recommendations']:
                            st.markdown(f"• {r}")

            st.divider()
            st.markdown("### Raw Results")
            all_res = results.get('extraction_results', []) + results.get('recovery_results', [])
            if all_res:
                df_data = [{
                    'Source': r.get('_url', r.get('query', 'N/A'))[:50],
                    'Type': 'Recovery' if r.get('_recovery') else 'Primary',
                    'Status': '✅' if r.get('_success') else '❌',
                    'Confidence': r.get('confidence', '-')
                } for r in all_res]
                st.dataframe(pd.DataFrame(df_data), use_container_width=True)

                with st.expander("View JSON"):
                    st.json(all_res)

            # Cost Summary
            if results.get('cost_summary'):
                st.divider()
                st.markdown("### 💰 Cost Summary")
                cost = results['cost_summary']

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Actual Cost", f"${cost['actual_cost']:.4f}")
                with col2:
                    st.metric("Opus Equivalent", f"${cost['opus_equivalent_cost']:.4f}")
                with col3:
                    st.metric("Savings", f"${cost['savings']:.4f}", f"{cost['savings_percentage']:.1f}%")
                with col4:
                    st.metric("Total Tokens", f"{cost['total_tokens']:,}")

                with st.expander("📊 Cost Breakdown"):
                    breakdown = cost.get('breakdown', {})
                    breakdown_data = []
                    for agent_type, agent_cost in breakdown.items():
                        if agent_cost > 0:
                            breakdown_data.append({
                                'Agent Type': agent_type.title(),
                                'Cost': f"${agent_cost:.4f}"
                            })
                    if breakdown_data:
                        st.dataframe(pd.DataFrame(breakdown_data), use_container_width=True)

                    st.caption(f"Total API calls: {cost['total_calls']}")
                    st.caption(f"Input tokens: {cost['total_input_tokens']:,} | Output tokens: {cost['total_output_tokens']:,}")
        else:
            st.info("Run a research query first.")

    with tab3:
        if st.session_state.current_results and st.session_state.current_results.get('analysis'):
            analysis = st.session_state.current_results['analysis']

            if 'error' not in analysis:
                st.markdown("### 📊 Data Analysis")

                # Summary table
                if analysis.get('summary_table_markdown'):
                    st.markdown("#### Summary Table")
                    st.markdown(analysis['summary_table_markdown'])

                # Key metrics
                if analysis.get('key_metrics'):
                    st.markdown("#### Key Metrics")
                    cols = st.columns(min(len(analysis['key_metrics']), 4))
                    for i, metric in enumerate(analysis['key_metrics']):
                        with cols[i % len(cols)]:
                            st.metric(metric.get('metric', 'N/A'), metric.get('value', 'N/A'))
                            st.caption(metric.get('context', ''))

                # Charts
                if analysis.get('charts'):
                    st.markdown("#### Visualizations")
                    for chart in analysis['charts']:
                        st.markdown(f"**{chart.get('title', 'Chart')}**")
                        st.caption(chart.get('description', ''))

                        data = chart.get('data', {})
                        chart_type = chart.get('type', 'bar')

                        if data.get('labels') and data.get('values'):
                            df = pd.DataFrame({
                                'Category': data['labels'],
                                'Value': data['values']
                            })

                            if chart_type == 'bar':
                                st.bar_chart(df.set_index('Category'))
                            elif chart_type == 'line':
                                st.line_chart(df.set_index('Category'))
                            else:
                                st.dataframe(df)

                # Insights
                if analysis.get('comparison_insights'):
                    st.markdown("#### Insights")
                    for insight in analysis['comparison_insights']:
                        st.markdown(f"• {insight}")

                if analysis.get('trends_patterns'):
                    st.markdown("#### Trends & Patterns")
                    for trend in analysis['trends_patterns']:
                        st.markdown(f"• {trend}")
            else:
                st.error(f"Analysis error: {analysis.get('error')}")
        else:
            st.info("Run a research query to see analysis.")

    with tab4:
        if st.session_state.current_results:
            st.markdown("### 💬 Ask Questions About Your Research")
            st.caption(f"Topic: {st.session_state.current_results.get('topic', 'N/A')}")

            # Display chat history
            for msg in st.session_state.chat_history:
                css_class = "chat-user" if msg['role'] == 'user' else "chat-assistant"
                icon = "🧑" if msg['role'] == 'user' else "🤖"
                st.markdown(f'<div class="chat-message {css_class}">{icon} {msg["content"]}</div>', unsafe_allow_html=True)

            # Input
            question = st.text_input("Ask a question about the research data", key="qa_input", placeholder="e.g., What's the cheapest option? Which has the most features?")

            if st.button("Ask", type="primary") and question:
                client = get_client()
                if client:
                    st.session_state.chat_history.append({'role': 'user', 'content': question})

                    with st.spinner("Thinking..."):
                        answer, qa_tokens = run_followup_qa(client, question, st.session_state.current_results, st.session_state.chat_history, orchestrator_model)

                    st.session_state.chat_history.append({'role': 'assistant', 'content': answer})
                    st.rerun()

            if st.button("Clear Chat"):
                st.session_state.chat_history = []
                st.rerun()
        else:
            st.info("Run a research query first to ask questions.")

    with tab5:
        if st.session_state.current_results:
            results = st.session_state.current_results

            st.subheader("📥 Export")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.download_button(
                    "📄 JSON",
                    json.dumps(results, indent=2, default=str),
                    f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    "application/json",
                    use_container_width=True
                )

            with col2:
                all_res = results.get('extraction_results', []) + results.get('recovery_results', [])
                if all_res:
                    df = pd.json_normalize(all_res)
                    st.download_button(
                        "📊 CSV",
                        df.to_csv(index=False),
                        f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        "text/csv",
                        use_container_width=True
                    )

            with col3:
                md = f"# {results['topic']}\n\n"
                md += f"**Date:** {results['timestamp']}\n\n"
                md += f"## Summary\n{results.get('synthesis', {}).get('executive_summary', 'N/A')}\n\n"
                md += "## Findings\n"
                for f in results.get('synthesis', {}).get('key_findings', []):
                    md += f"- {f}\n"

                st.download_button(
                    "📝 Markdown",
                    md,
                    f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    "text/markdown",
                    use_container_width=True
                )
        else:
            st.info("Run a research query first.")


if __name__ == "__main__":
    main()

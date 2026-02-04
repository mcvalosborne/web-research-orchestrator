#!/usr/bin/env python3
"""
Test script to verify cost tracking functionality.
Run this to see the cost tracking in action without the GUI.
"""

import os
import json
import anthropic
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import from app.py
import sys
sys.path.insert(0, '.')

from app import (
    CostTracker,
    run_haiku_worker,
    run_discovery_search,
    synthesize_results,
    MODEL_PRICING
)

def test_cost_tracking():
    """Run a simple test to demonstrate cost tracking."""

    # Check for API key
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set. Please set it first:")
        print("   export ANTHROPIC_API_KEY=your-key-here")
        return

    client = anthropic.Anthropic(api_key=api_key)
    cost_tracker = CostTracker()

    print("🔬 Web Research Orchestrator - Cost Tracking Test")
    print("=" * 50)

    # Test topic
    topic = "Compare pricing for top 3 note-taking apps"
    schema = {
        "name": "App name",
        "price": "Monthly price",
        "features": ["Key features"]
    }

    print(f"\n📋 Topic: {topic}")
    print(f"📊 Schema: {json.dumps(schema)}")

    # Phase 1: Discovery
    print("\n🔍 Phase 1: Discovery...")

    # Mock session state for the function (it checks for brave_api_key)
    class MockSessionState:
        brave_api_key = ""
        firecrawl_api_key = ""
        agent_flow_log = []

    # Monkey-patch st.session_state for testing
    import app
    class MockSt:
        session_state = MockSessionState()
        @staticmethod
        def error(msg): print(f"❌ Error: {msg}")
        @staticmethod
        def warning(msg): print(f"⚠️ Warning: {msg}")
    app.st = MockSt()

    discovered, discovery_tokens = run_discovery_search(
        client, topic, num_results=3,
        model="claude-sonnet-4-20250514",
        use_brave=False
    )

    if discovery_tokens.get('input_tokens', 0) > 0:
        cost_tracker.add_call(
            discovery_tokens['model'],
            discovery_tokens['input_tokens'],
            discovery_tokens['output_tokens'],
            "orchestrator"
        )

    urls = [d['url'] for d in discovered]
    print(f"   Found {len(urls)} sources")
    for d in discovered:
        print(f"   - {d.get('title', d.get('url', 'Unknown'))[:50]}")

    # Phase 2: Extraction with Haiku workers
    print("\n⚡ Phase 2: Extraction with Haiku workers...")
    extraction_results = []

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(
                run_haiku_worker, client, url, schema, i,
                "claude-3-5-haiku-20241022", False, ""
            ): (i, url)
            for i, url in enumerate(urls)
        }

        for future in as_completed(futures):
            result = future.result()
            extraction_results.append(result)

            # Track worker cost
            if result.get('_input_tokens', 0) > 0:
                cost_tracker.add_call(
                    result.get('_model', 'haiku'),
                    result.get('_input_tokens', 0),
                    result.get('_output_tokens', 0),
                    "worker"
                )

            status = "✅" if result.get('_success') else "❌"
            print(f"   {status} Worker {result.get('_worker_id')}: {result.get('_url', 'N/A')[:40]}...")

    # Phase 3: Synthesis
    print("\n🧠 Phase 3: Synthesis...")
    synthesis, synthesis_tokens = synthesize_results(
        client, topic, extraction_results, None,
        "claude-sonnet-4-20250514"
    )

    if synthesis_tokens.get('input_tokens', 0) > 0:
        cost_tracker.add_call(
            synthesis_tokens['model'],
            synthesis_tokens['input_tokens'],
            synthesis_tokens['output_tokens'],
            "orchestrator"
        )

    print("   ✅ Synthesis complete")

    # Display cost summary
    print("\n" + "=" * 50)
    print("💰 COST SUMMARY")
    print("=" * 50)

    summary = cost_tracker.get_summary()

    print(f"\n📊 API Calls: {summary['total_calls']}")
    print(f"📝 Total Tokens: {summary['total_tokens']:,}")
    print(f"   - Input: {summary['total_input_tokens']:,}")
    print(f"   - Output: {summary['total_output_tokens']:,}")

    print(f"\n💵 Actual Cost: ${summary['actual_cost']:.4f}")
    print(f"💎 Opus Equivalent: ${summary['opus_equivalent_cost']:.4f}")
    print(f"💰 Savings: ${summary['savings']:.4f} ({summary['savings_percentage']:.1f}%)")

    print("\n📈 Cost Breakdown by Agent Type:")
    for agent_type, cost in summary['breakdown'].items():
        if cost > 0:
            print(f"   - {agent_type.title()}: ${cost:.4f}")

    print("\n📋 Individual Calls:")
    for i, call in enumerate(summary['calls']):
        model_short = "Haiku" if "haiku" in call['model'].lower() else "Sonnet" if "sonnet" in call['model'].lower() else "Opus"
        print(f"   {i+1}. [{call['agent_type'].title()}] {model_short}: {call['input_tokens']} in / {call['output_tokens']} out = ${call['cost']:.4f}")

    # Show synthesis highlights
    if synthesis and 'error' not in synthesis:
        print("\n" + "=" * 50)
        print("📝 RESEARCH SUMMARY")
        print("=" * 50)
        print(f"\n{synthesis.get('executive_summary', 'N/A')}")

    print("\n✅ Test complete!")


if __name__ == "__main__":
    test_cost_tracking()

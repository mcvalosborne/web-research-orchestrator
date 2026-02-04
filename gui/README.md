# Web Research Orchestrator GUI

A Streamlit-based visual interface for running multi-model web research with Claude.

![Screenshot](screenshot.png)

## Features

- **🔍 Auto-Discovery**: Automatically find relevant sources using Sonnet
- **🎯 Custom URLs**: Research specific URLs you provide
- **⚡ Parallel Workers**: Run multiple Haiku workers simultaneously
- **📊 Results Table**: View extracted data in a clean table format
- **🧠 AI Synthesis**: Get an executive summary and key findings
- **📥 Multi-format Export**: Download as JSON, CSV, or Markdown
- **📜 History**: Access previous research sessions

## Quick Start

### 1. Install dependencies

```bash
cd gui
pip install -r requirements.txt
```

### 2. Set your API key

Either set the environment variable:
```bash
export ANTHROPIC_API_KEY=your-key-here
```

Or enter it in the sidebar when you run the app.

### 3. Run the app

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`

## Usage

### Auto-Discovery Mode

1. Enter a research topic (e.g., "Compare pricing for top CRM tools")
2. Select "Auto-Discovery"
3. Set the number of sources to find
4. Configure your extraction schema
5. Click "Start Research"

### Custom URLs Mode

1. Enter your research topic
2. Select "Custom URLs"
3. Paste URLs (one per line)
4. Configure your extraction schema
5. Click "Start Research"

## Extraction Schema

Define what data to extract using a JSON schema:

```json
{
  "title": "Page title",
  "price": "Product price",
  "features": ["List of features"],
  "pros": ["Advantages"],
  "cons": ["Disadvantages"]
}
```

Workers will attempt to fill each field from the source content.

## Architecture

```
┌─────────────────────────────────────┐
│         Streamlit GUI               │
└─────────────────┬───────────────────┘
                  │
    ┌─────────────┴─────────────┐
    │                           │
    ▼                           ▼
┌───────────┐           ┌───────────────┐
│  Sonnet   │           │ Haiku Workers │
│ Discovery │           │  (Parallel)   │
│ Synthesis │           │  Extraction   │
└───────────┘           └───────────────┘
```

## Cost Optimization

The app uses:
- **Sonnet** for planning, discovery, and synthesis (smart tasks)
- **Haiku** for bulk data extraction (grunt work)

This can save **~97%** compared to using a more expensive model for everything.

Example: Researching 20 URLs
- All Opus: ~$0.30
- Sonnet + Haiku workers: ~$0.01

## Configuration Options

| Setting | Description | Default |
|---------|-------------|---------|
| Orchestrator Model | Model for planning/synthesis | Sonnet |
| Worker Model | Model for extraction | Haiku |
| Max Parallel Workers | Concurrent workers | 5 |

## Export Formats

- **JSON**: Complete results with all metadata
- **CSV**: Extraction results in tabular format
- **Markdown**: Human-readable report with synthesis

## Troubleshooting

### "Please enter your Anthropic API key"
Set `ANTHROPIC_API_KEY` environment variable or enter it in the sidebar.

### Workers failing
- Check if URLs are accessible
- Some sites block automated access
- Try reducing parallel workers

### Slow performance
- Reduce number of sources
- Reduce parallel workers
- Check your internet connection

## License

MIT

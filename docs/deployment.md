# Deployment Guide

Deploy the Web Research Orchestrator to Streamlit Community Cloud for free hosting.

## Prerequisites

- GitHub account (repo can be private)
- Anthropic API key
- (Optional) Brave Search API key
- (Optional) Firecrawl API key

## Deploy to Streamlit Community Cloud

### Step 1: Push to GitHub

Your repo should already be on GitHub. Make sure these files exist:
- `gui/app.py` - Main application
- `gui/requirements.txt` - Dependencies

### Step 2: Go to Streamlit Community Cloud

1. Visit [share.streamlit.io](https://share.streamlit.io)
2. Sign in with GitHub
3. Click **"New app"**

### Step 3: Configure the App

| Field | Value |
|-------|-------|
| Repository | `mcvalosborne/web-research-orchestrator` |
| Branch | `main` |
| Main file path | `gui/app.py` |

Click **"Deploy!"**

### Step 4: Add Secrets

Once deployed:

1. Click the **⋮** menu on your app
2. Select **"Settings"**
3. Go to **"Secrets"** section
4. Add your secrets in TOML format:

```toml
# Required
ANTHROPIC_API_KEY = "sk-ant-your-key-here"

# Optional
BRAVE_API_KEY = "your-brave-key"
FIRECRAWL_API_KEY = "your-firecrawl-key"

# Password protection (recommended for public demos)
[passwords]
demo = "your-demo-password"
admin = "your-admin-password"
```

5. Click **"Save"**
6. Reboot the app

## Password Protection

The app supports simple password protection for demos:

1. Add passwords in the secrets:
```toml
[passwords]
demo = "research2025"
client1 = "client-password"
```

2. Share the username/password with people you want to access the demo

3. Users will see a login screen before accessing the app

## Local Development

For local development, create `.streamlit/secrets.toml`:

```bash
cd gui
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit secrets.toml with your API keys
```

The `secrets.toml` file is gitignored and won't be committed.

## Environment Variables (Alternative)

You can also use environment variables:

```bash
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
export BRAVE_API_KEY="xxxxx"
export FIRECRAWL_API_KEY="xxxxx"
streamlit run gui/app.py
```

## Custom Domain (Optional)

Streamlit Community Cloud apps get a URL like:
`https://your-app-name.streamlit.app`

For a custom domain, upgrade to Streamlit Teams or use a reverse proxy.

## Troubleshooting

### "No module named 'extraction'"
Make sure `gui/extraction.py` exists and is committed to the repo.

### "API key not found"
1. Check that secrets are saved correctly
2. Reboot the app after saving secrets
3. Verify the key name matches exactly: `ANTHROPIC_API_KEY`

### App crashes on startup
1. Check the logs in Streamlit Cloud dashboard
2. Verify all dependencies are in `requirements.txt`
3. Test locally first: `streamlit run gui/app.py`

### Password protection not working
1. Make sure `[passwords]` section is in secrets
2. Format must be: `username = "password"`
3. Reboot after saving secrets

## Security Notes

1. **Never commit `secrets.toml`** - It's gitignored by default
2. **Use strong passwords** for demo access
3. **Rotate API keys** if you suspect they're compromised
4. **Private repo recommended** for sensitive projects

## Cost Considerations

Streamlit Community Cloud is free with limits:
- 1 GB RAM per app
- Apps sleep after inactivity
- 3 private apps per account

For the Web Research Orchestrator, the main costs are:
- **Anthropic API**: ~$0.01-0.05 per research query
- **Brave Search**: 2,000 free queries/month
- **Firecrawl**: 500 free credits

## Quick Reference

| Task | Command/Action |
|------|----------------|
| Deploy | share.streamlit.io → New app |
| Add secrets | Settings → Secrets → Save |
| View logs | Click app → ⋮ → Logs |
| Reboot | Settings → Reboot app |
| Delete | Settings → Delete app |

## Support

- [Streamlit Community Cloud Docs](https://docs.streamlit.io/streamlit-community-cloud)
- [Streamlit Forums](https://discuss.streamlit.io/)

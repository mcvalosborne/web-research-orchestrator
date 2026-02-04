#!/bin/bash

# Web Research Orchestrator - Quick Start Script

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔬 Web Research Orchestrator${NC}"
echo "================================"

# Check if pip is available
if ! command -v pip &> /dev/null; then
    echo -e "${RED}Error: pip is not installed${NC}"
    exit 1
fi

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -r requirements.txt
fi

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  ANTHROPIC_API_KEY not set${NC}"
    echo "You can enter it in the sidebar when the app opens."
    echo ""
fi

# Run the app
echo -e "${GREEN}Starting Streamlit app...${NC}"
echo ""
streamlit run app.py

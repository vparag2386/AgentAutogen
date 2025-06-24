#!/bin/bash
set -e

echo "🔧 Setting up Python virtual environment..."
python3 -m venv .venv

echo "📦 Activating virtual environment..."
source .venv/bin/activate

echo "⬇️ Installing dependencies..."
pip install --upgrade pip
pip install ag2[openai] ollama requests

echo ""
read -p "📝 Enter the feature to implement (e.g., 'Add JWT login'): " FEATURE

echo ""
echo "🚀 [Phase 1] Running multi-agent pipeline..."
python3 toolkit.py run "$FEATURE"

LOG_FILE=$(ls -t run_*.log | head -n 1)
MD_FILE="demo_output.md"

echo ""
echo "📄 [Phase 2] Converting log → markdown..."
python3 toolkit.py log2md "$LOG_FILE" "$MD_FILE"

echo ""
echo "📁 [Phase 3] Extracting Java files from markdown..."
python3 toolkit.py md2java "$MD_FILE"

echo ""
echo "✅ Done!"
echo "📦 Java files extracted to → extracted_src/"

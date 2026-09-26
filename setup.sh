#!/bin/bash
set -e
echo "🤖 AutoApply AI — Setup"
echo "========================"

if ! command -v python3 &> /dev/null; then
   echo "❌ Python 3 not found. Install Python 3.11+ first."
   exit 1
fi

python3 -m venv venv
echo "✅ Virtual environment created"

source venv/bin/activate
pip install -r requirements.txt --quiet
echo "✅ Python packages installed"

python -m playwright install chromium
echo "✅ Playwright Chromium installed"

mkdir -p uploads screenshots browser_profiles/linkedin browser_profiles/naukri logs

if [ ! -f .env ]; then
   cp .env.example .env
   echo "✅ .env file created — EDIT IT with your API keys before running!"
else
   echo "✅ .env already exists"
fi

echo ""
echo "🚀 Setup complete!"
echo "Next steps:"
echo "  1. Edit .env with your Gemini API keys and LinkedIn/Naukri credentials"
echo "  2. Run: source venv/bin/activate && python main.py"
echo "  3. Open: http://localhost:8000"
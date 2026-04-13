#!/bin/bash
# Chain Monitor — Setup Script
# Run this once to set up the project

set -e

echo "🔧 Chain Monitor Setup"
echo "====================="

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Create virtual environment
echo ""
echo "📦 Creating virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create .env from template if not exists
if [ ! -f .env ]; then
    echo ""
    echo "🔑 Creating .env from template..."
    cp .env.example .env
    echo "⚠️  Edit .env and add your API keys!"
else
    echo "✓ .env already exists"
fi

# Create storage directories
echo ""
echo "📁 Creating storage directories..."
mkdir -p storage/events
mkdir -p storage/health
mkdir -p storage/narratives

# Verify config files
echo ""
echo "📋 Verifying config files..."
for f in config/chains.yaml config/baselines.yaml config/narratives.yaml config/sources.yaml; do
    if [ -f "$f" ]; then
        echo "  ✓ $f"
    else
        echo "  ✗ $f MISSING"
        exit 1
    fi
done

# Verify DefiLlama chain slugs
echo ""
echo "🔗 Verifying DefiLlama chain slugs..."
python3 scripts/verify_sources.py

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your API keys"
echo "  2. Run: python3 main.py"
echo "  3. Check Telegram for first digest"

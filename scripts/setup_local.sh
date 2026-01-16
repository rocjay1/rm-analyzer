#!/bin/bash
set -e

echo "Starting local environment setup..."

# 1. Check/Install Homebrew
if ! command -v brew &> /dev/null; then
    echo "Homebrew not found. Please install Homebrew first."
    exit 1
fi

# 2. Check/Install Azure Functions Core Tools
if ! command -v func &> /dev/null; then
    echo "Installing Azure Functions Core Tools..."
    brew tap azure/functions
    brew install azure-functions-core-tools@4
else
    echo "Azure Functions Core Tools already installed."
fi

# 3. Check/Install Azurite
if ! command -v azurite &> /dev/null; then
    echo "Installing Azurite..."
    npm install -g azurite
else
    echo "Azurite already installed."
fi

# 4. Check/Install SWA CLI
if ! command -v swa &> /dev/null; then
    echo "Installing Azure Static Web Apps CLI..."
    npm install -g @azure/static-web-apps-cli
else
    echo "SWA CLI already installed."
fi

# 5. Python Setup
echo "Setting up Python environment..."
cd src/backend
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt

echo "Setup complete! You can now run ./run_local.sh"

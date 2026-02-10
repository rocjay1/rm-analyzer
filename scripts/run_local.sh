#!/bin/bash


# Enable job control so background processes are in their own process groups
# This prevents them from receiving Ctrl+C (SIGINT) directly from the terminal,
# ensuring they ONLY get the signal when we explicitly kill them in cleanup().
set -m

# Activate virtual environment if it exists
# Check if Go is installed
if ! command -v go &> /dev/null; then
    echo "Go is not installed. Please install Go to proceed."
    exit 1
fi

# Helper to kill processes on specific ports
kill_port() {
  local port=$1
  local pids=$(lsof -ti :$port)
  if [ -n "$pids" ]; then
    echo "Killing process on port $port (PIDs: $pids)..."
    kill -9 $pids 2>/dev/null
  fi
}

# Pre-cleanup: Check if ports are already in use and kill them
echo "Checking for stale processes..."
kill_port 7071  # Azure Functions
kill_port 10000 # Azurite Blob
kill_port 10001 # Azurite Queue
kill_port 10002 # Azurite Table
kill_port 4280  # SWA Emulator


# Function to kill background processes on exit
cleanup() {
    echo "Stopping services..."
    kill $(jobs -p) 2>/dev/null
}
trap cleanup EXIT

echo "Starting Azurite..."
# Start Azurite in background with specific ports
azurite --silent --location .azurite --debug .azurite/debug.log --skipApiVersionCheck &

echo "Starting Azure Functions Backend..."
echo "Building Go backend..."
cd src-go

# Use local paths for Go build to avoid permission issues
mkdir -p ../.gotmp/cache
export GOTMPDIR=$(pwd)/../.gotmp
export GOCACHE=$(pwd)/../.gotmp/cache
export GOPATH=$(pwd)/../.gotmp

go build -o handler cmd/handler/main.go
if [ $? -ne 0 ]; then
    echo "Go build failed."
    exit 1
fi

# Manually export critical values for local dev to ensure Go handler sees them
export TABLE_SERVICE_URL="http://127.0.0.1:10002/devstoreaccount1"
export BLOB_SERVICE_URL="http://127.0.0.1:10000/devstoreaccount1"
export QUEUE_SERVICE_URL="http://127.0.0.1:10001/devstoreaccount1"
export SAVINGS_TABLE="savings"
export CREDIT_CARDS_TABLE="creditcards"
export TRANSACTIONS_TABLE="transactions"
export PEOPLE_TABLE="people"
export ACCOUNTS_TABLE="accounts"

echo "Starting Azure Functions Backend..."
# Start Func in background
export FUNCTIONS_WORKER_RUNTIME=custom
func start --port 7071 &
FUNC_PID=$!

# Wait for Func to start (simple sleep for now, could be more robust)
sleep 5

echo "Starting Frontend Proxy..."
cd ../src/frontend
# Unset potentially conflicting variables from the current environment
unset AZURE_CLIENT_ID
unset AZURE_CLIENT_SECRET
unset AZURE_TENANT_ID
unset AZURE_SUBSCRIPTION_ID

# Explicitly load .env to override any existing session variables
if [ -f .env ]; then
  echo "Found .env file in $(pwd). Loading..."
  set -a
  source .env
  set +a
fi

echo "Environment Check (Masked):"
echo "AZURE_CLIENT_ID=$(echo $AZURE_CLIENT_ID | cut -c1-5)****************"
echo "AZURE_TENANT_ID=$(echo $AZURE_TENANT_ID | cut -c1-5)****************"
echo "API Route: http://localhost:7071"

# Serve static content from current dir (.), proxy API calls to func running on 7071
swa start . --api-location http://localhost:7071

# Wait for func to exit (if swa exits, trap will kill func)

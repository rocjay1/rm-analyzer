#!/bin/bash


# Enable job control so background processes are in their own process groups
# This prevents them from receiving Ctrl+C (SIGINT) directly from the terminal,
# ensuring they ONLY get the signal when we explicitly kill them in cleanup().
set -m

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
azurite --silent --location .azurite --debug .azurite/debug.log &

echo "Starting Azure Functions Backend..."
cd src/backend
# Start Func in background
func start --port 7071 &
FUNC_PID=$!

# Wait for Func to start (simple sleep for now, could be more robust)
sleep 5

echo "Starting Frontend Proxy..."
cd ../frontend
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

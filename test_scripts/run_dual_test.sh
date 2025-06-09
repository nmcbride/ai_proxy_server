#!/bin/bash
# Simple runner for dual server test.
# This ensures no other servers are running and handles cleanup.

# Function to cleanup any existing servers
cleanup() {
    echo "🧹 Cleaning up any existing servers..."
    pkill -f "uvicorn.*app.main:app" 2>/dev/null || true
    sleep 2
}

# Function to handle interruption
interrupt_handler() {
    echo -e "\n⚠️  Test interrupted, cleaning up..."
    cleanup
    exit 1
}

# Set interrupt handler
trap interrupt_handler SIGINT

echo "🚀 Starting Dual Server AI Proxy Test"
echo "This will test both direct streaming and hybrid streaming modes simultaneously"
echo ""

# Cleanup any existing servers first
cleanup

# Run the test
echo "▶️  Starting test..."
python test_scripts/test_dual_server.py

# Cleanup after test
cleanup

echo "✅ Test complete!" 
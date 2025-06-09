#!/usr/bin/env python3
"""
Mode Comparison Test Script
Helps test both ENABLE_HYBRID_STREAMING=true and false modes
"""

import asyncio
import os
import subprocess
import sys

async def main():
    """Guide user through testing both modes"""
    print("🎯 AI Proxy Server Mode Comparison Testing")
    print("=" * 60)
    print()
    
    current_hybrid = os.getenv('ENABLE_HYBRID_STREAMING', 'false').lower()
    print(f"Current ENABLE_HYBRID_STREAMING: {current_hybrid}")
    print()
    
    print("📋 Testing Instructions:")
    print()
    print("This script will help you test both streaming modes:")
    print("1. Direct Streaming (ENABLE_HYBRID_STREAMING=false)")
    print("2. Hybrid Streaming (ENABLE_HYBRID_STREAMING=true)")
    print()
    print("Since the server reads environment variables at startup,")
    print("you need to restart the server between tests.")
    print()
    
    print("🔄 Testing Process:")
    print()
    print("1. First, test current configuration:")
    print("   uv run python test_scripts/test_comprehensive.py")
    print()
    
    if current_hybrid == 'true':
        print("2. To test direct streaming mode:")
        print("   • Stop the server (Ctrl+C)")
        print("   • Start with: ENABLE_HYBRID_STREAMING=false uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001")
        print("   • Run: uv run python test_scripts/test_comprehensive.py")
        print()
        print("3. To return to hybrid streaming:")
        print("   • Stop the server (Ctrl+C)")
        print("   • Start with: ENABLE_HYBRID_STREAMING=true uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001")
    else:
        print("2. To test hybrid streaming mode:")
        print("   • Stop the server (Ctrl+C)")
        print("   • Start with: ENABLE_HYBRID_STREAMING=true uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001")
        print("   • Run: uv run python test_scripts/test_comprehensive.py")
        print()
        print("3. To return to direct streaming:")
        print("   • Stop the server (Ctrl+C)")
        print("   • Start with: ENABLE_HYBRID_STREAMING=false uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001")
    
    print()
    print("🔍 What to Look For:")
    print()
    print("Direct Streaming Mode (ENABLE_HYBRID_STREAMING=false):")
    print("  • Non-streaming with tools: ~3-5s (tools execute)")
    print("  • Streaming with tool request: ~1-2s (tools skipped)")
    print("  • 'No tool results detected' in streaming requests")
    print()
    print("Hybrid Streaming Mode (ENABLE_HYBRID_STREAMING=true):")
    print("  • Non-streaming with tools: ~3-5s (tools execute)")
    print("  • Streaming with tool request: ~3-5s (tools execute, then stream)")
    print("  • '✅ Tools executed' in streaming requests")
    print("  • Longer 'time to first chunk' in streaming (due to tool execution)")
    print()
    
    print("▶️  Run the comprehensive test now:")
    print("   uv run python test_scripts/test_comprehensive.py")
    print()


if __name__ == "__main__":
    asyncio.run(main()) 
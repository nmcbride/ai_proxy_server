#!/usr/bin/env python3
"""
Test All Modes Script
Runs comprehensive tests for both direct streaming and hybrid streaming modes
"""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx


class ModeTestRunner:
    def __init__(self):
        self.base_url = "http://localhost:8001"
        self.test_script_path = Path(__file__).parent / "test_comprehensive.py"
        
    async def run_all_mode_tests(self):
        """Run tests for both streaming modes"""
        print("🎯 AI Proxy Server - Complete Mode Testing")
        print("=" * 60)
        print()
        
        # Check if server is available
        if not await self.check_server_available():
            print("❌ Server is not running. Please start the server first.")
            print("   Example: uvicorn app.main:app --reload --host 0.0.0.0 --port 8001")
            return
            
        print("📋 Testing Plan:")
        print("  1. Test with ENABLE_HYBRID_STREAMING=false (Direct Streaming)")
        print("  2. Test with ENABLE_HYBRID_STREAMING=true (Hybrid Streaming)")
        print("  3. Compare results")
        print()
        
        # Test direct streaming mode
        await self.test_mode("false", "Direct Streaming Mode")
        
        print("\n" + "⏳" * 20)
        print("Waiting 2 seconds between test runs...")
        await asyncio.sleep(2)
        
        # Test hybrid streaming mode  
        await self.test_mode("true", "Hybrid Streaming Mode")
        
        print("\n" + "=" * 60)
        print("🎉 All mode testing completed!")
        print("=" * 60)
        
    async def check_server_available(self) -> bool:
        """Check if the server is running"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/mcp/status")
                return response.status_code == 200
        except Exception:
            return False
            
    async def test_mode(self, hybrid_enabled: str, mode_name: str):
        """Test a specific mode by setting environment and running comprehensive test"""
        print(f"\n🧪 Testing {mode_name}")
        print("=" * 50)
        print(f"Setting ENABLE_HYBRID_STREAMING={hybrid_enabled}")
        print()
        
        # Set environment variable for this test
        env = os.environ.copy()
        env["ENABLE_HYBRID_STREAMING"] = hybrid_enabled
        
        try:
            # Run the comprehensive test script with the environment setting
            result = subprocess.run(
                [sys.executable, str(self.test_script_path)],
                env=env,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )
            
            if result.returncode == 0:
                print(result.stdout)
                if result.stderr:
                    print("⚠️  Warnings/Errors:")
                    print(result.stderr)
            else:
                print(f"❌ Test failed with return code {result.returncode}")
                print("STDOUT:", result.stdout)
                print("STDERR:", result.stderr)
                
        except subprocess.TimeoutExpired:
            print("❌ Test timed out after 2 minutes")
        except Exception as e:
            print(f"❌ Error running test: {e}")


async def main():
    """Main function"""
    print("🚀 Starting comprehensive mode testing...")
    print()
    
    runner = ModeTestRunner()
    await runner.run_all_mode_tests()


if __name__ == "__main__":
    asyncio.run(main()) 
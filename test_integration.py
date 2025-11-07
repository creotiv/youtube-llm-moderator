#!/usr/bin/env python3
"""
Test script to verify the integration between youtube_moderator.py and animation-server.py
"""

import json
import time
import requests
import subprocess
import sys
import os

API_BASE = "http://localhost:5000"
STATS_FILE = "stats.json"


def test_stats_file():
    """Test if stats.json exists and has the right format."""
    print("📄 Testing stats.json file...")

    if not os.path.exists(STATS_FILE):
        print("❌ stats.json not found")
        return False

    try:
        with open(STATS_FILE, "r") as f:
            stats = json.load(f)

        required_fields = ["online_viewers", "total_views", "last_updated"]
        for field in required_fields:
            if field not in stats:
                print(f"❌ Missing field: {field}")
                return False

        print(f"✅ stats.json is valid")
        print(f"   - Online viewers: {stats['online_viewers']}")
        print(f"   - Total views: {stats['total_views']}")
        print(f"   - Last updated: {stats['last_updated']}")
        return True

    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in stats.json: {e}")
        return False
    except Exception as e:
        print(f"❌ Error reading stats.json: {e}")
        return False


def test_animation_server():
    """Test if the animation server is running and responding."""
    print("\n🌐 Testing animation server...")

    try:
        # Test health endpoint
        response = requests.get(f"{API_BASE}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Animation server is running")
        else:
            print(f"❌ Animation server health check failed: {response.status_code}")
            return False

        # Test stats endpoint
        response = requests.get(f"{API_BASE}/api/stats", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("✅ Stats API is working")
                print(f"   - Online viewers: {data['online_viewers']}")
                print(f"   - Total views: {data['total_views']}")
                return True
            else:
                print(f"❌ Stats API returned error: {data.get('error')}")
                return False
        else:
            print(f"❌ Stats API failed: {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to animation server. Is it running?")
        print("   Start it with: python animation-server.py")
        return False
    except Exception as e:
        print(f"❌ Error testing animation server: {e}")
        return False


def test_animation_page():
    """Test if the animation page loads correctly."""
    print("\n🎨 Testing animation page...")

    try:
        response = requests.get(f"{API_BASE}/", timeout=5)
        if response.status_code == 200:
            content = response.text
            if "vertical-bar" in content.lower() and "updateBar" in content:
                print("✅ Animation page loads correctly")
                return True
            else:
                print("❌ Animation page content seems incorrect")
                return False
        else:
            print(f"❌ Animation page failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing animation page: {e}")
        return False


def simulate_stats_update():
    """Simulate updating stats to test the integration."""
    print("\n🔄 Testing stats update...")

    try:
        # Generate some test data
        import random

        test_stats = {
            "online_viewers": random.randint(50, 200),
            "total_views": random.randint(1000, 5000),
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        # Update via API
        response = requests.post(
            f"{API_BASE}/api/update-stats", json=test_stats, timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("✅ Stats update via API successful")

                # Verify the update
                response = requests.get(f"{API_BASE}/api/stats", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if (
                        data["online_viewers"] == test_stats["online_viewers"]
                        and data["total_views"] == test_stats["total_views"]
                    ):
                        print("✅ Stats update verified")
                        return True
                    else:
                        print("❌ Stats update verification failed")
                        return False
                else:
                    print("❌ Failed to verify stats update")
                    return False
            else:
                print(f"❌ Stats update failed: {data.get('error')}")
                return False
        else:
            print(f"❌ Stats update API failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error testing stats update: {e}")
        return False


def main():
    """Run all tests."""
    print("🧪 Testing YouTube Moderator + Animation Integration")
    print("=" * 60)

    tests = [
        ("Stats File", test_stats_file),
        ("Animation Server", test_animation_server),
        ("Animation Page", test_animation_page),
        ("Stats Update", simulate_stats_update),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n🔍 Running {test_name} test...")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} test failed")

    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Integration is working correctly.")
        print("\n📝 Next steps:")
        print("1. Start youtube_moderator.py to get real-time stats")
        print("2. Start animation-server.py to serve the animation")
        print("3. Open http://localhost:5000 to view the animation")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

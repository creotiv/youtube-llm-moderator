#!/usr/bin/env python3
"""
Test script for the new in-memory stats system.
"""

import requests
import json
import time

API_BASE = "http://localhost:5555"


def test_server_health():
    """Test if the animation server is running."""
    print("🏥 Testing server health...")
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Server is healthy: {data['message']}")
            return True
        else:
            print(f"❌ Server health check failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Is it running?")
        print("   Start it with: python animation-server.py")
        return False
    except Exception as e:
        print(f"❌ Error testing server health: {e}")
        return False


def test_initial_stats():
    """Test getting initial stats from memory."""
    print("\n📊 Testing initial stats...")
    try:
        response = requests.get(f"{API_BASE}/api/stats", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("✅ Initial stats retrieved successfully")
                print(f"   - Online viewers: {data['online_viewers']}")
                print(f"   - Total views: {data['total_views']}")
                print(f"   - Video ID: {data['video_id']}")
                print(f"   - Title: {data['title']}")
                print(f"   - Channel: {data['channel_title']}")
                print(f"   - Is live: {data['is_live']}")
                return True
            else:
                print(f"❌ Stats API returned error: {data.get('error')}")
                return False
        else:
            print(f"❌ Stats API failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing initial stats: {e}")
        return False


def test_update_stats():
    """Test updating stats in memory."""
    print("\n🔄 Testing stats update...")
    try:
        # Create test data with all fields
        test_stats = {
            "online_viewers": 150,
            "total_views": 2500,
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "video_id": "test_video_123",
            "title": "Test Live Stream",
            "channel_title": "Test Channel",
            "actual_start_time": "2024-01-15T10:00:00Z",
            "scheduled_start_time": "2024-01-15T09:30:00Z",
            "is_live": True,
            "likes": 42,
            "comments": 15,
        }

        response = requests.post(
            f"{API_BASE}/api/update-stats", json=test_stats, timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("✅ Stats updated successfully")
                print(f"   - Online viewers: {data['online_viewers']}")
                print(f"   - Total views: {data['total_views']}")
                print(f"   - Video ID: {data['video_id']}")
                print(f"   - Title: {data['title']}")
                print(f"   - Channel: {data['channel_title']}")
                print(f"   - Is live: {data['is_live']}")
                print(f"   - Likes: {data['likes']}")
                print(f"   - Comments: {data['comments']}")
                return True
            else:
                print(f"❌ Update returned error: {data.get('error')}")
                return False
        else:
            print(f"❌ Update API failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing stats update: {e}")
        return False


def test_partial_update():
    """Test updating only some stats fields."""
    print("\n🔧 Testing partial stats update...")
    try:
        # Update only some fields
        partial_stats = {
            "online_viewers": 200,
            "total_views": 3000,
            "likes": 50,
        }

        response = requests.post(
            f"{API_BASE}/api/update-stats", json=partial_stats, timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("✅ Partial update successful")
                print(f"   - Online viewers: {data['online_viewers']} (should be 200)")
                print(f"   - Total views: {data['total_views']} (should be 3000)")
                print(f"   - Likes: {data['likes']} (should be 50)")
                print(
                    f"   - Video ID: {data['video_id']} (should remain 'test_video_123')"
                )
                print(f"   - Title: {data['title']} (should remain 'Test Live Stream')")
                return True
            else:
                print(f"❌ Partial update returned error: {data.get('error')}")
                return False
        else:
            print(f"❌ Partial update API failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing partial update: {e}")
        return False


def test_animation_page():
    """Test if the animation page loads with new stats."""
    print("\n🎨 Testing animation page...")
    try:
        response = requests.get(f"{API_BASE}/anim/potuzhnist", timeout=5)
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


def main():
    """Run all tests."""
    print("🧪 Testing In-Memory Stats System")
    print("=" * 50)

    tests = [
        ("Server Health", test_server_health),
        ("Initial Stats", test_initial_stats),
        ("Update Stats", test_update_stats),
        ("Partial Update", test_partial_update),
        ("Animation Page", test_animation_page),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n🔍 Running {test_name} test...")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} test failed")

    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! In-memory stats system is working correctly.")
        print("\n📝 Next steps:")
        print("1. Start animation-server.py")
        print("2. Start youtube_moderator.py to get real-time stats")
        print("3. Open http://localhost:5555/anim/potuzhnist to view the animation")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())


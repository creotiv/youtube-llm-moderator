#!/usr/bin/env python3
"""
Test script for the API server.
"""

import requests
import json
import time
import random

API_BASE = "http://localhost:5000"


def test_health():
    """Test the health endpoint."""
    try:
        response = requests.get(f"{API_BASE}/health")
        print(f"Health check: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False


def test_get_stats():
    """Test getting stats from the API."""
    try:
        response = requests.get(f"{API_BASE}/api/stats")
        data = response.json()
        print(f"Get stats: {response.status_code} - {data}")
        return data.get("success", False)
    except Exception as e:
        print(f"Get stats failed: {e}")
        return False


def test_update_stats(value):
    """Test updating stats via the API."""
    try:
        payload = {"online_viewers": value}
        response = requests.post(f"{API_BASE}/api/update-stats", json=payload)
        data = response.json()
        print(f"Update stats: {response.status_code} - {data}")
        return data.get("success", False)
    except Exception as e:
        print(f"Update stats failed: {e}")
        return False


def simulate_live_updates():
    """Simulate live updates to the stats."""
    print("\nSimulating live updates (press Ctrl+C to stop)...")
    try:
        while True:
            # Generate random value between 0 and 100
            value = random.randint(0, 100)
            print(f"Updating online viewers to: {value}")
            test_update_stats(value)
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nStopped simulation")


if __name__ == "__main__":
    print("Testing API server...")

    # Test health endpoint
    if not test_health():
        print("Server is not running. Please start it with: python api_server.py")
        exit(1)

    # Test get stats
    test_get_stats()

    # Test update stats
    test_update_stats(42)

    # Test get stats again
    test_get_stats()

    # Ask if user wants to simulate live updates
    try:
        simulate = (
            input("\nDo you want to simulate live updates? (y/n): ").lower().strip()
        )
        if simulate == "y":
            simulate_live_updates()
    except KeyboardInterrupt:
        print("\nExiting...")

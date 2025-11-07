#!/usr/bin/env python3
"""
Simple Flask server to serve the vertical bar animation and provide stats API.
This server works alongside the youtube_moderator.py to serve the animation.
"""

import json
import os
from flask import Flask, send_file, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ANIMATION_FILE = os.path.join(BASE_DIR, "animations", "vertical-bar.html")

# In-memory storage for stats
stats_memory = {
    "online_viewers": 0,
    "total_views": 0,
    "last_updated": "Unknown",
    "video_id": "",
    "title": "N/A",
    "channel_title": "N/A",
    "actual_start_time": "",
    "scheduled_start_time": "",
    "is_live": False,
    "likes": 0,
    "comments": 0,
}


@app.route("/anim/potuzhnist")
def index():
    """Serve the vertical bar animation page."""
    try:
        return send_file(ANIMATION_FILE)
    except FileNotFoundError:
        return "Animation file not found", 404


@app.route("/api/stats")
def get_stats():
    """Get the current stats from memory."""
    try:
        return jsonify(
            {
                **stats_memory,
                "success": True,
            }
        )
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}", "success": False}), 500


@app.route("/api/update-stats", methods=["POST"])
def update_stats():
    """Update the stats in memory."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided", "success": False}), 400

        # Update all stats fields in memory
        global stats_memory
        stats_memory.update(
            {
                "online_viewers": data.get(
                    "online_viewers", stats_memory["online_viewers"]
                ),
                "total_views": data.get("total_views", stats_memory["total_views"]),
                "last_updated": data.get("last_updated", stats_memory["last_updated"]),
                "video_id": data.get("video_id", stats_memory["video_id"]),
                "title": data.get("title", stats_memory["title"]),
                "channel_title": data.get(
                    "channel_title", stats_memory["channel_title"]
                ),
                "actual_start_time": data.get(
                    "actual_start_time", stats_memory["actual_start_time"]
                ),
                "scheduled_start_time": data.get(
                    "scheduled_start_time", stats_memory["scheduled_start_time"]
                ),
                "is_live": data.get("is_live", stats_memory["is_live"]),
                "likes": data.get("likes", stats_memory["likes"]),
                "comments": data.get("comments", stats_memory["comments"]),
            }
        )

        return jsonify(
            {
                "message": "Stats updated successfully",
                **stats_memory,
                "success": True,
            }
        )
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}", "success": False}), 500


@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "message": "Animation server is running"})


if __name__ == "__main__":
    print("Starting Animation Server...")
    print(f"Animation file: {ANIMATION_FILE}")
    print("Storage: In-memory (no file persistence)")
    print("Available endpoints:")
    print("  GET  /anim/potuzhnist - Serve vertical bar animation")
    print("  GET  /api/stats       - Get all stream statistics")
    print("  POST /api/update-stats - Update stats in memory")
    print("  GET  /health          - Health check")
    print("\nStarting server on http://localhost:5555")
    print("Make sure youtube_moderator.py is running to get real-time stats!")
    print("Stats will be stored in memory and reset when server restarts.")

    app.run(debug=True, host="0.0.0.0", port=5555)

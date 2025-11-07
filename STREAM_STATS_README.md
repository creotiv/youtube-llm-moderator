# YouTube Stream Statistics Integration

This enhancement adds real-time stream statistics fetching to your YouTube moderator bot, which automatically updates the vertical bar animation with live viewer counts and total views.

## 🚀 New Features

### Real-time Stream Statistics
- **Concurrent Viewers**: Estimated based on chat activity and stream data
- **Total Views**: Fetched from YouTube API video statistics
- **Auto-update**: Statistics refresh every 30 seconds
- **Live Animation**: Vertical bar updates automatically with real data

### Enhanced Animation Server
- **Dedicated Server**: `animation-server.py` serves the vertical bar animation
- **RESTful API**: Clean endpoints for stats data
- **Real-time Updates**: Animation refreshes every second with latest data
- **Error Handling**: Graceful fallbacks if data is unavailable

## 📁 Files Added/Modified

### New Files
- `animation-server.py` - Flask server for the animation
- `test_integration.py` - Integration testing script
- `STREAM_STATS_README.md` - This documentation

### Modified Files
- `youtube_moderator.py` - Added stats fetching functionality
- `animations/vertical-bar.html` - Updated to fetch from API
- `stats.json` - Now updated with real-time data

## 🔧 Configuration

### YouTube Moderator Settings
```python
# Stream statistics configuration
STATS_UPDATE_INTERVAL_SECONDS = 30  # Update stats every 30 seconds
FEATURE_STATS_ACTIVE = True  # Enable/disable stats fetching functionality
```

### Animation Settings
- **Update Frequency**: Every 1 second (configurable in HTML)
- **Data Source**: `/api/stats` endpoint
- **Fallback**: Default value if API is unavailable

## 🚀 How to Use

### 1. Start the YouTube Moderator
```bash
python youtube_moderator.py
```
This will:
- Authenticate with YouTube API
- Find your active live stream
- Start fetching statistics every 30 seconds
- Update `stats.json` with real-time data

### 2. Start the Animation Server
```bash
python animation-server.py
```
This will:
- Start Flask server on `http://localhost:5000`
- Serve the vertical bar animation
- Provide API endpoints for stats data

### 3. View the Animation
Open `http://localhost:5000` in your browser to see:
- Real-time vertical bar showing concurrent viewers
- Automatic updates every second
- Beautiful color transitions (green to red)
- Pulsing and glow effects

## 📊 API Endpoints

### GET `/api/stats`
Returns current stream statistics:
```json
{
    "online_viewers": 150,
    "total_views": 2500,
    "last_updated": "2024-01-15T10:30:00Z",
    "success": true
}
```

### POST `/api/update-stats`
Update statistics manually:
```bash
curl -X POST http://localhost:5000/api/update-stats \
  -H "Content-Type: application/json" \
  -d '{"online_viewers": 200, "total_views": 3000}'
```

### GET `/health`
Health check endpoint:
```json
{
    "status": "healthy",
    "message": "Animation server is running"
}
```

## 🧪 Testing

Run the integration test to verify everything works:
```bash
python test_integration.py
```

This will test:
- ✅ Stats file format and content
- ✅ Animation server connectivity
- ✅ Animation page loading
- ✅ Stats update functionality

## 📈 How Statistics Work

### Concurrent Viewers Estimation
Since YouTube doesn't provide exact concurrent viewer counts through public APIs, the system estimates based on:
1. **Chat Activity**: Number of recent messages (assumes 1-5% of viewers chat)
2. **Stream Data**: Available broadcast information
3. **Fallback Simulation**: Random values if real data unavailable

### Total Views
- Fetched directly from YouTube API video statistics
- Updated every 30 seconds
- More accurate than concurrent viewer estimation

## ⚙️ Customization

### Change Update Intervals
```python
# In youtube_moderator.py
STATS_UPDATE_INTERVAL_SECONDS = 60  # Update every minute

# In animations/vertical-bar.html
setInterval(fetchAndUpdateBar, 2000);  # Update animation every 2 seconds
```

### Modify Animation Appearance
Edit `animations/vertical-bar.html` to customize:
- Colors and gradients
- Animation effects
- Update frequency
- Bar dimensions

### Adjust Viewer Estimation
In `youtube_moderator.py`, modify the estimation logic:
```python
# Current estimation: recent_messages * 20
concurrent_viewers = max(10, recent_messages * 20)

# Customize multiplier or minimum value
concurrent_viewers = max(5, recent_messages * 50)  # More aggressive estimation
```

## 🔍 Troubleshooting

### Animation Not Updating
1. Check if `youtube_moderator.py` is running
2. Verify `stats.json` is being updated
3. Check browser console for JavaScript errors
4. Ensure animation server is running on port 5000

### No Real-time Data
1. Verify YouTube API authentication
2. Check if live stream is active
3. Review console output for API errors
4. Ensure `FEATURE_STATS_ACTIVE = True`

### Server Connection Issues
1. Check if port 5000 is available
2. Verify Flask dependencies are installed
3. Check firewall settings
4. Try different port in `animation-server.py`

## 🎯 Benefits

- **Real-time Visualization**: See live viewer count in beautiful animation
- **Automatic Updates**: No manual intervention required
- **YouTube Integration**: Uses your existing YouTube API setup
- **Customizable**: Easy to modify appearance and behavior
- **Reliable**: Graceful error handling and fallbacks
- **Lightweight**: Minimal additional resource usage

## 🔮 Future Enhancements

- **Multiple Metrics**: Add more statistics (likes, comments, etc.)
- **Historical Data**: Store and display trends over time
- **Multiple Streams**: Support for multiple concurrent streams
- **Advanced Analytics**: More sophisticated viewer estimation algorithms
- **Mobile Responsive**: Better mobile device support

---

**Note**: The concurrent viewer count is an estimation based on available data. For exact numbers, you would need access to YouTube's internal analytics, which requires special permissions.

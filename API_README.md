# Vertical Bar Animation API Server

This Python Flask API server provides endpoints to serve the vertical bar animation and manage online viewer statistics.

## Features

- **Animated Vertical Bar**: A beautiful animated vertical bar that displays online viewer count
- **Real-time Updates**: The bar automatically updates every 5 seconds with data from the API
- **RESTful API**: Clean API endpoints for getting and updating statistics
- **CORS Support**: Cross-origin requests are enabled for web integration

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Start the Server

```bash
python api_server.py
```

The server will start on `http://localhost:5000`

### Available Endpoints

- **GET /** - Serves the vertical bar animation page
- **GET /api/stats** - Returns the current online viewers count
- **POST /api/update-stats** - Updates the online viewers count
- **GET /health** - Health check endpoint

### API Examples

#### Get Current Stats
```bash
curl http://localhost:5000/api/stats
```

Response:
```json
{
    "online_viewers": 75,
    "success": true
}
```

#### Update Stats
```bash
curl -X POST http://localhost:5000/api/update-stats \
  -H "Content-Type: application/json" \
  -d '{"online_viewers": 85}'
```

Response:
```json
{
    "message": "Stats updated successfully",
    "online_viewers": 85,
    "success": true
}
```

### Testing

Run the test script to verify the API functionality:

```bash
python test_api.py
```

This will:
- Test all API endpoints
- Optionally simulate live updates to see the animation in action

## Data Storage

The online viewer count is stored in `stats.json`:

```json
{
    "online_viewers": 75,
    "total_views": 1250,
    "last_updated": "2024-01-15T10:30:00Z"
}
```

## Animation Features

The vertical bar animation includes:
- **Color Transition**: Green (0) to Red (100) based on value
- **Pulsing Effect**: Subtle animation for visual appeal
- **Glow Effect**: Dynamic glow that follows the bar
- **Scale Markers**: Visual scale from 0-100
- **Auto-refresh**: Updates every 5 seconds automatically

## Integration

To integrate with your existing systems, simply update the `online_viewers` value in `stats.json` or use the `/api/update-stats` endpoint. The animation will automatically reflect the changes.

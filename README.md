# PiBoat Server

A lightweight Python-based WebSocket relay server that facilitates real-time communication between an autonomous boat and a control client application. The server relays video data using WebRTC and telemetry data using JSON, optimizing for low latency over potentially unstable 4G cellular connections.

## Features

- Establish and maintain WebSocket connections between the autonomous boat and a control client
- Relay WebRTC video stream (1080p/30fps) from the boat to the control client
- Relay JSON-formatted telemetry data from the boat to the control client, including:
  - GPS position and heading
  - Speed and battery status
  - Water and environmental sensor data
- Transmit navigation commands from the control client to the autonomous boat
- Handle connection interruptions with automatic reconnection (crucial for maritime operations)
- Connection state tracking and monitoring
- Sequence numbering for telemetry to detect data loss
- Timestamp synchronization for accurate data representation

## Technology Stack

- **Language:** Python 3.9+
- **WebSocket Framework:** FastAPI with WebSocket support
- **WebRTC:** aiortc for Python WebRTC implementation
- **JSON Processing:** ujson for high-performance JSON handling
- **Async Framework:** asyncio for asynchronous operations
- **Containerization:** Docker

## Installation and Setup

### Prerequisites

- Docker and Docker Compose (recommended)
- Python 3.9+ (if running without Docker)

### Using Docker (Recommended)

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd websocket-relay-server
   ```

2. Configure environment variables (optional):
   Create a `.env` file with custom settings or use the defaults.

3. Build and run with Docker Compose:
   ```bash
   docker-compose up -d
   ```

The server will be available at `http://localhost:8000` with WebSocket endpoints at:
- `/ws/device/{device_id}` - For device connections
- `/ws/client/{client_id}` - For client connections

### Manual Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd websocket-relay-server
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the server:
   ```bash
   python -m server.main
   ```

## Configuration

The server can be configured with the following environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| PORT | HTTP and WebSocket port | 8000 |
| DEBUG_MODE | Enable debug mode | false |
| LOG_LEVEL | Logging level (INFO, DEBUG, etc.) | INFO |
| MAX_RECONNECT_ATTEMPTS | Maximum reconnection attempts | 5 |
| RECONNECT_INTERVAL | Seconds between reconnect attempts | 2 |
| CONNECTION_TIMEOUT | Connection timeout in seconds | 30 |
| PING_INTERVAL | WebSocket ping interval in seconds | 20 |
| TELEMETRY_BUFFER_SIZE | Number of telemetry messages to buffer | 100 |

## Message Protocol

### Boat to Server

The autonomous boat should send messages in the following formats:

#### 1. Telemetry Data
```json
{
  "type": "telemetry",
  "subtype": "sensor_data",
  "sequence": 1234,
  "timestamp": 1625049600000,
  "system_time": 1625049600000,
  "data": {
    "gps": {
      "latitude": 37.7749,
      "longitude": -122.4194,
      "heading": 225.5,
      "speed": 2.3
    },
    "status": "autonomous_navigation"
  }
}
```

#### 2. WebRTC Signaling (Offer)
```json
{
  "type": "webrtc",
  "subtype": "offer",
  "boatId": "boat-123",
  "sdp": "SDP_OFFER_DATA_HERE"
}
```

#### 3. WebRTC ICE Candidates
```json
{
  "type": "webrtc",
  "subtype": "ice_candidate",
  "boatId": "boat-123",
  "candidate": "ICE_CANDIDATE_DATA_HERE"
}
```

### Client to Server

Control clients should send messages in the following formats:

#### 1. Navigation Commands
```json
{
  "type": "command",
  "command": "set_waypoints",
  "boatId": "boat-123",
  "data": {
    "waypoints": [
      {
        "latitude": 37.7749,
        "longitude": -122.4194
      },
      {
        "latitude": 37.7750,
        "longitude": -122.4180
      },
      {
        "latitude": 37.7765,
        "longitude": -122.4175
      }
    ],
    "mode": "autonomous"
  }
}
```

You can also send a single waypoint:
```json
{
  "type": "command",
  "command": "set_waypoint",
  "boatId": "boat-123",
  "data": {
    "latitude": 37.7749,
    "longitude": -122.4194,
    "mode": "autonomous"
  }
}
```

#### 2. WebRTC Signaling (Answer)
```json
{
  "type": "webrtc",
  "subtype": "answer",
  "boatId": "boat-123",
  "sdp": "SDP_ANSWER_DATA_HERE"
}
```

#### 3. WebRTC ICE Candidates
```json
{
  "type": "webrtc",
  "subtype": "ice_candidate",
  "boatId": "boat-123",
  "candidate": "ICE_CANDIDATE_DATA_HERE"
}
```

## WebRTC Signaling Flow

The WebRTC connection is established through the following signaling flow:

1. The boat captures video and initiates the WebRTC connection by sending an "offer" to the server
2. The server relays the offer to the connected client
3. The client receives the offer and generates an "answer"
4. The server relays the answer back to the boat
5. Both the boat and client exchange ICE candidates through the server
6. Once the connection is established, video streams directly via WebRTC

## Health Check

The server provides a health check endpoint at `/health`, which returns status information about the server and its connections with the autonomous boat and control clients.

## Examples

Example boat and client implementations can be found in the `examples/` directory:

- `examples/device.py` - Example autonomous boat implementation
- `examples/client.py` - Example command-line control client implementation
- `examples/web_client/` - Web-based GUI client implementation

### Web Client

The web client provides a user-friendly graphical interface for controlling and monitoring the boat:

- Connect to the relay server with a simple UI
- View and select available devices
- Send commands with a form-based interface
- View live video feed via WebRTC
- Monitor telemetry data with real-time updates
- View system logs and command status in a console

To run the web client:

```bash
cd examples/web_client
python run_web_client.py
```

Then open a web browser to http://localhost:8080

For more information, see the [Web Client README](examples/web_client/README.md).

## Troubleshooting

Common issues and their solutions:

- **Connection Errors**: Check network connectivity and firewall settings. Maritime environments may require specialized antennas or signal boosters.
- **WebRTC Streaming Issues**: Ensure proper ICE server configuration and network ports.
- **High Latency**: Consider adjusting buffer sizes and reviewing network conditions. Be prepared for intermittent connectivity in open water.
- **GPS Accuracy**: Check GPS signal quality and ensure proper calibration of navigation sensors.

## License

[MIT License](LICENSE)
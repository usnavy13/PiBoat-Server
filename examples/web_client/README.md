# PiBoat Web Client

A web-based client application for the PiBoat WebSocket Relay Server, providing a graphical user interface to control and monitor a remote autonomous boat.

## Features

- Connect to the PiBoat relay server via WebSockets
- View and select available devices
- Send commands to the boat
- View live video feed via WebRTC
- Monitor telemetry data (GPS, system status, environment)
- Command console for viewing system messages

## Technology Stack

- **Frontend**: HTML, CSS, JavaScript
- **Backend**: Python (FastAPI)
- **WebSockets**: Native browser WebSocket API
- **WebRTC**: Native browser WebRTC API
- **Styling**: Custom CSS with responsive design

## Installation

### Prerequisites

- Python 3.9+
- Pip package manager

### Setup

1. Install the required dependencies:

```bash
pip install fastapi uvicorn jinja2 websockets aiortc
```

2. Navigate to the web client directory:

```bash
cd examples/web_client
```

## Usage

### Running the Web Client

Start the web client server:

```bash
python app.py
```

This will start the web client server on http://localhost:8080 by default.

### Command Line Options

- `--host`: Host to bind to (default: 0.0.0.0)
- `--port`: Port to bind to (default: 8080)
- `--relay-server`: WebSocket relay server URL (default: ws://localhost:8000)

Example:

```bash
python app.py --port 9000 --relay-server ws://relay.example.com:8000
```

### Using the Web Interface

1. **Connection**
   - Enter the relay server URL (e.g., ws://localhost:8000)
   - Click "Connect" to establish a connection

2. **Device Selection**
   - Once connected, available devices will appear in the list
   - Click on a device to select it
   - Click "Refresh Devices" to update the list

3. **Sending Commands**
   - Select a command from the dropdown
   - Modify the command data JSON as needed
   - Click "Send Command" to send the command to the selected device

4. **Viewing Video**
   - After selecting a device, click "Start Video" to begin streaming
   - Click "Stop Video" to end streaming

5. **Monitoring Telemetry**
   - Telemetry data will automatically update in the panels
   - GPS data includes latitude, longitude, heading, and speed
   - System data includes battery level, CPU temperature, and signal strength
   - Environment data includes water and air temperature, pressure, and humidity

6. **Console**
   - The console displays system messages, command statuses, and errors
   - Click "Clear" to clear the console

## Troubleshooting

- **Connection Issues**: Verify the relay server URL and ensure the server is running
- **Video Streaming Issues**: Ensure WebRTC is properly enabled in your browser
- **No Devices Listed**: Check if any devices are connected to the relay server
- **Command Failures**: Check the console for error messages

## Browser Compatibility

The web client is compatible with modern browsers that support WebSockets and WebRTC:

- Google Chrome 60+
- Firefox 55+
- Safari 11+
- Edge 79+

## Logging

The PiBoat Web Client includes comprehensive logging functionality that captures both server-side and client-side logs in a single file. These logs are useful for debugging, auditing, and troubleshooting issues with the PiBoat system.

### Log Features

- Server logs and client-side console logs are captured in the same file
- Log files are timestamped and stored in a dedicated directory
- Logs can be downloaded directly from the web interface
- Console logs are displayed in real-time in the UI

### Log Directory

By default, logs are stored in the `logs` directory. You can specify a custom log directory using the `--log-dir` parameter:

```
python run_web_client.py --log-dir /path/to/custom/logs
```

### Log Format

Each log entry includes:
- Timestamp
- Log level (INFO, WARNING, ERROR)
- Source (server or client)
- Message

### Downloading Logs

You can download the current log file by clicking the "Download Logs" button in the console section of the web interface.

## License

MIT License 
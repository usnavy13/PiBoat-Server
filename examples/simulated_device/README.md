# Simulated Device for PiBoat Server

This simulated device emulates an autonomous boat connecting to the PiBoat WebSocket relay server. It provides telemetry data and streams video from a looped video file.

## Features

- Connects to the PiBoat WebSocket relay server
- Streams video via WebRTC from the provided `simulated_video.mp4` file
- Generates realistic telemetry data (GPS, heading, speed, battery, environmental data)
- Logs commands received from clients for review
- Handles and acknowledges navigation commands
- Simulates boat movement based on commands received

## Prerequisites

- Python 3.9+
- PiBoat Server running (typically on localhost:8000)
- Required Python packages (see `requirements.txt` in the project root)
- The `simulated_video.mp4` file in the same directory

## Installation

1. Ensure you have the required Python packages installed:
   ```bash
   pip install -r ../../requirements.txt
   ```

2. Make sure you have a video file named `simulated_video.mp4` in this directory
   - The included file is a looped video that simulates a boat's camera

## Usage

1. Start the PiBoat Server first (if not already running):
   ```bash
   # From the project root
   python -m server.main
   ```

2. Run the simulated device:
   ```bash
   # From the examples/simulated_device directory
   python simulated_device.py
   ```

3. The device will:
   - Connect to the WebSocket server
   - Start sending telemetry data
   - Wait for WebRTC connection requests and commands from clients

## Logs and Command Review

- Normal operation logs are written to `simulated_device.log`
- All commands received from clients are:
  - Logged to the console
  - Saved to `command_log.json` for review
  - Stored in memory (accessible via the device object if needed)

## Telemetry Data

The simulated device generates the following telemetry:

- GPS position (latitude/longitude) - starts in San Francisco Bay and moves based on heading/speed
- Heading (0-360 degrees)
- Speed (0-10 knots)
- Battery status (percentage, voltage, current)
- Environmental data (water temperature, air temperature, water depth, wind speed/direction)

## Supported Commands

The device responds to these commands from clients:

- `set_waypoint` - Sets a single waypoint to navigate towards
- `set_waypoints` - Sets multiple waypoints as a route
- `emergency_stop` - Immediately stops the boat
- `set_speed` - Changes the boat's speed

## Configuration

You can modify these variables at the top of `simulated_device.py`:

- `WS_SERVER_URL` - WebSocket server URL (default: ws://localhost:8000/ws/device/{device_id})
- `DEVICE_ID` - Unique identifier for the device (default: auto-generated)
- `VIDEO_FILE` - Path to the video file (default: simulated_video.mp4 in the same directory)
- `TELEMETRY_INTERVAL` - Seconds between telemetry updates (default: 1 second)

## Customization

You can customize the simulation by modifying:

- Initial position in the `__init__` method of the `SimulatedDevice` class
- Telemetry data generation in the `telemetry_loop` method
- Command handling in the `handle_command` method 
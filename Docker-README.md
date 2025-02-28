# PiBoat Server Docker Setup

This repository includes a Docker setup for running both the PiBoat Server and the associated Web Client.

## Components

- **PiBoat Relay Server**: The main WebSocket relay server for connecting devices and clients
- **Web Client**: A browser-based client interface for connecting to and controlling devices

## Prerequisites

- Docker and Docker Compose installed on your system
- Git (to clone the repository)

## How to Run

1. Clone the repository (if you haven't already):
   ```bash
   git clone <repository-url>
   cd PiBoat-Server
   ```

2. Build and start the containers:
   ```bash
   docker compose up
   ```

   To run in detached mode (background):
   ```bash
   docker compose up -d
   ```

3. Access the web client in your browser:
   ```
   http://localhost:8080
   ```

4. To stop the services:
   ```bash
   docker compose down
   ```

## Services and Ports

- **Relay Server**: Runs on port 8000
- **Web Client**: Runs on port 8080

## Environment Variables

### Relay Server
- `PORT`: The port the server will listen on (default: 8000)
- `MAX_RECONNECT_ATTEMPTS`: Maximum number of reconnection attempts (default: 5)
- `RECONNECT_INTERVAL`: Interval between reconnection attempts in seconds (default: 2)
- `LOG_LEVEL`: Logging level (default: INFO)

### Web Client
- `PORT`: The port the web client will listen on (default: 8080)
- `RELAY_SERVER`: WebSocket URL of the relay server (default: ws://relay-server:8000)
- `LOG_LEVEL`: Logging level (default: INFO)

## Logs

Logs are stored in the following locations:
- Relay Server: `./logs`
- Web Client: `./logs/web_client`

## Building Individual Images

If you want to build and run the images separately:

### Relay Server
```bash
docker build -t piboat-server -f server.Dockerfile .
docker run -p 8000:8000 piboat-server
```

### Web Client
```bash
docker build -t piboat-web-client -f web-client.Dockerfile .
docker run -p 8080:8080 -e RELAY_SERVER=ws://<server-host>:8000 piboat-web-client
```

## Troubleshooting

### Missing Dependencies
If you encounter errors about missing Python modules:

1. For `ModuleNotFoundError: No module named 'pydantic_settings'`:
   - Make sure `pydantic-settings` is in your requirements.txt file
   - Rebuild the images: `docker compose build --no-cache`

2. For environment variable issues in the web client:
   - The CMD in the web-client.Dockerfile should use the shell form (no square brackets) to properly expand environment variables
   - Example: `CMD python app.py --host 0.0.0.0 --port 8080 --relay-server $RELAY_SERVER`

### Connection Issues
- If the web client can't connect to the relay server:
  - Check that both containers are running: `docker compose ps`
  - Make sure the relay server is healthy: `docker compose logs relay-server`
  - Verify the web client is using the correct relay server URL: `docker compose logs web-client`

### General Debugging
```bash
# View logs from all services
docker compose logs

# Follow logs in real-time
docker compose logs -f

# View logs from a specific service
docker compose logs relay-server
docker compose logs web-client

# Rebuild all services from scratch
docker compose down
docker compose build --no-cache
docker compose up
```

## Additional Notes

- The relay server needs to start successfully before the web client can connect to it. This is handled through the `depends_on` configuration in docker-compose.yml.
- If you're running the containers on a remote machine, replace `localhost` with the appropriate IP address or hostname when accessing the web client. 
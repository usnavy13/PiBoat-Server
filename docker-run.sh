#!/bin/bash

# PiBoat Docker Setup Script

# Stop all running containers
echo "Stopping any running containers..."
docker compose down

# Check if a rebuild is needed
if [ "$1" == "--rebuild" ]; then
  echo "Rebuilding containers from scratch..."
  docker compose build --no-cache
else
  echo "Building containers if needed..."
  docker compose build
fi

# Start the containers
echo "Starting containers..."
docker compose up $2

echo ""
echo "PiBoat Server should be running at: http://localhost:8000"
echo "PiBoat Web Client should be running at: http://localhost:8080"
echo ""
echo "To view logs, use: docker compose logs"
echo "To stop all containers, use: docker compose down" 
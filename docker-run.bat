@echo off
REM PiBoat Docker Setup Script for Windows

echo Stopping any running containers...
docker compose down

if "%1"=="--rebuild" (
  echo Rebuilding containers from scratch...
  docker compose build --no-cache
) else (
  echo Building containers if needed...
  docker compose build
)

echo Starting containers...
docker compose up %2

echo.
echo PiBoat Server should be running at: http://localhost:8000
echo PiBoat Web Client should be running at: http://localhost:8080
echo.
echo To view logs, use: docker compose logs
echo To stop all containers, use: docker compose down 
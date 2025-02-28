"""
Web-based client for PiBoat WebSocket Relay Server.

This script runs a small web server that serves the HTML/JS interface
and acts as a proxy for WebSocket connections to the relay server.
"""

import os
import logging
import uuid
import argparse
import json
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, Body
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Define default settings
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080
DEFAULT_RELAY_SERVER = "ws://localhost:8000"
DEFAULT_LOG_DIR = "logs"

# Create logs directory if it doesn't exist
def setup_logging(log_dir):
    """Set up logging configuration with file output."""
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Create a timestamped log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_path / f"piboat_webclient_{timestamp}.log"
    
    # Configure logging to both console and file
    handlers = [
        logging.StreamHandler(),  # Console handler
        logging.FileHandler(log_file)  # File handler
    ]
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    
    logger = logging.getLogger("web_client")
    logger.info(f"Logging to file: {log_file}")
    return log_file

# Create FastAPI app
app = FastAPI(title="PiBoat Web Client")

# Get the directory of the current file
base_dir = Path(__file__).resolve().parent

# Set up static files and templates
app.mount("/static", StaticFiles(directory=os.path.join(base_dir, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(base_dir, "templates"))

# Store path to the log file
current_log_file = None

@app.get("/", response_class=HTMLResponse)
async def get_home(request: Request):
    """Serve the main web interface."""
    # Generate a unique client ID for this session
    client_id = f"web-client-{uuid.uuid4().hex[:8]}"
    
    return templates.TemplateResponse(
        "index.html", 
        {
            "request": request, 
            "client_id": client_id,
            "relay_server": os.environ.get("RELAY_SERVER", DEFAULT_RELAY_SERVER),
            "log_file": str(current_log_file) if current_log_file else "None"
        }
    )

@app.post("/api/log")
async def client_log(request: Request, log_data: dict = Body(...)):
    """Endpoint to receive logs from the JavaScript client."""
    logger = logging.getLogger("client")
    message = log_data.get("message", "")
    log_type = log_data.get("type", "info")
    
    # Map JavaScript log types to Python logging levels
    level_map = {
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "success": logging.INFO,
        "telemetry": logging.INFO
    }
    
    level = level_map.get(log_type, logging.INFO)
    logger.log(level, f"[CLIENT] {message}")
    
    return JSONResponse({"status": "ok"})

@app.get("/api/log_file")
async def get_log_file():
    """Return the path to the current log file."""
    return {"log_file": str(current_log_file) if current_log_file else None}

@app.get("/api/download_log")
async def download_log():
    """Download the current log file."""
    if current_log_file and current_log_file.exists():
        return FileResponse(
            path=current_log_file,
            filename=current_log_file.name,
            media_type="text/plain"
        )
    return JSONResponse({"error": "Log file not found"}, status_code=404)

def main():
    """Main entry point for the web client."""
    parser = argparse.ArgumentParser(description="PiBoat Web Client")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host to bind to")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind to")
    parser.add_argument("--relay-server", default=DEFAULT_RELAY_SERVER, 
                        help="WebSocket relay server URL")
    parser.add_argument("--log-dir", default=DEFAULT_LOG_DIR,
                        help="Directory for log files")
    
    args = parser.parse_args()
    
    # Set up logging with file output
    global current_log_file
    current_log_file = setup_logging(args.log_dir)
    
    # Set environment variables for the templates
    os.environ["RELAY_SERVER"] = args.relay_server
    
    logger = logging.getLogger("web_client")
    logger.info(f"Starting web client on http://{args.host}:{args.port}")
    logger.info(f"Connecting to relay server at {args.relay_server}")
    
    # Start the Uvicorn server
    uvicorn.run(
        "app:app",
        host=args.host,
        port=args.port,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main() 
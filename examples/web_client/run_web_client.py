#!/usr/bin/env python3

"""
Run script for the PiBoat Web Client.

This script provides a convenient way to start the web client with default settings.
"""

import os
import sys
import subprocess
import argparse

# Add parent directory to path so we can import from examples.web_client
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Default settings
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080
DEFAULT_RELAY_SERVER = "ws://localhost:8000"
DEFAULT_LOG_DIR = "logs"


def main():
    """Run the PiBoat Web Client."""
    parser = argparse.ArgumentParser(description="PiBoat Web Client")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host to bind to (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to bind to (default: {DEFAULT_PORT})")
    parser.add_argument("--relay-server", default=DEFAULT_RELAY_SERVER, 
                        help=f"WebSocket relay server URL (default: {DEFAULT_RELAY_SERVER})")
    parser.add_argument("--log-dir", default=DEFAULT_LOG_DIR,
                        help=f"Directory for log files (default: {DEFAULT_LOG_DIR})")
    
    args = parser.parse_args()
    
    print(f"Starting PiBoat Web Client on http://{args.host}:{args.port}")
    print(f"Connecting to relay server: {args.relay_server}")
    print(f"Logs will be written to: {args.log_dir}")
    print("Press Ctrl+C to stop")
    
    # Change to the web_client directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Start the web client using the app.py module
    cmd = [
        sys.executable,
        "app.py",
        "--host", args.host,
        "--port", str(args.port),
        "--relay-server", args.relay_server,
        "--log-dir", args.log_dir
    ]
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nStopping PiBoat Web Client")
    

if __name__ == "__main__":
    main() 
import asyncio
import logging
import os
import signal
import sys
import time
from typing import Dict, Set
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from server.config import settings
from server.connection_manager import ConnectionManager
from server.webrtc_handler import WebRTCHandler
from server.telemetry_handler import TelemetryHandler
from server.command_handler import CommandHandler
from server.debug_tools import message_debugger

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(settings.log_dir, 'relay_server.log'))
    ]
)
logger = logging.getLogger(__name__)

# Initialize connection manager
connection_manager = ConnectionManager()
webrtc_handler = WebRTCHandler()
telemetry_handler = TelemetryHandler()
command_handler = CommandHandler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI application."""
    # Startup logic
    logger.info("Starting WebSocket Relay Server")
    os.makedirs(settings.log_dir, exist_ok=True)
    
    # Start ConnectionManager background tasks
    await connection_manager.start()
    
    # Setup graceful shutdown - Windows compatible
    yield
    
    # Shutdown logic
    logger.info("Shutting down WebSocket Relay Server")
    await connection_manager.close_all_connections()


app = FastAPI(title="WebSocket Relay Server", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "connections": {
            "devices": len(connection_manager.device_connections),
            "clients": len(connection_manager.client_connections)
        }
    }


@app.get("/debug/device-messages/{device_id}")
async def analyze_device_messages(device_id: str):
    """Analyze captured device messages for debugging."""
    results = message_debugger.analyze_device_messages(device_id)
    return results


@app.websocket("/ws/device/{device_id}")
async def device_websocket_endpoint(websocket: WebSocket, device_id: str):
    """WebSocket endpoint for device connections."""
    await connection_manager.connect_device(websocket, device_id)
    try:
        while True:
            data = await websocket.receive_json()
            # Log the raw message for debugging
            logger.debug(f"Received raw message from device {device_id}: {data}")
            
            # Capture message for debugging
            message_debugger.capture_device_message(device_id, data)
            
            message_type = data.get("type")
            
            # Transform GPS data format for compatibility
            if message_type is None:
                # Check if it looks like telemetry data with GPS position
                has_position = "position" in data and isinstance(data.get("position"), dict)
                has_gps_fields = has_position and "latitude" in data["position"] and "longitude" in data["position"]
                
                if has_gps_fields:
                    logger.info(f"Detected GPS data in non-standard format from device {device_id}, transforming to standard format")
                    
                    # Create a new properly formatted telemetry message
                    transformed_data = {
                        "type": "telemetry",
                        "subtype": "sensor_data",
                        "sequence": data.get("sequence", 0),
                        "timestamp": data.get("timestamp", time.time() * 1000),
                        "data": {
                            "gps": {
                                "latitude": data["position"]["latitude"],
                                "longitude": data["position"]["longitude"]
                            }
                        }
                    }
                    
                    # Add additional navigation data if available
                    if "navigation" in data and isinstance(data["navigation"], dict):
                        if "heading" in data["navigation"]:
                            transformed_data["data"]["heading"] = data["navigation"]["heading"]
                        if "speed" in data["navigation"]:
                            transformed_data["data"]["speed"] = data["navigation"]["speed"]
                    
                    # Add battery status if available
                    if "status" in data and isinstance(data["status"], dict) and "battery" in data["status"]:
                        transformed_data["data"]["battery"] = data["status"]["battery"]
                    
                    logger.debug(f"Transformed data: {transformed_data}")
                    data = transformed_data
                    message_type = "telemetry"
                else:
                    # Check for missing or null type for other message formats
                    logger.warning(f"Device {device_id} sent message without valid type field: {data}")
                    if any(key in data for key in ["gps", "location", "coordinates", "latitude", "longitude"]):
                        logger.info(f"Message appears to be telemetry data, processing as telemetry: {data}")
                        # Add type field and process as telemetry
                        data["type"] = "telemetry"
                        data["subtype"] = "sensor_data"  # Add required subtype field
                        message_type = "telemetry"
            
            if message_type == "webrtc":
                await webrtc_handler.handle_device_message(device_id, data, connection_manager)
            elif message_type == "telemetry":
                logger.debug(f"Processing telemetry data from device {device_id}: {data}")
                await telemetry_handler.process_telemetry(device_id, data, connection_manager)
            elif message_type == "pong":
                # Update last activity time to prevent timeout
                if device_id in connection_manager.device_connections:
                    connection_manager.device_connections[device_id].last_activity = time.time()
            elif message_type == "command_ack":
                # Handle command acknowledgement from device
                await command_handler.handle_command_acknowledgement(device_id, data, connection_manager)
            elif message_type == "status_response":
                # Handle status response from device - forward to paired client
                client_id = connection_manager.device_to_client_mapping.get(device_id)
                if client_id:
                    # Add deviceId field if not present
                    if "deviceId" not in data:
                        data["deviceId"] = device_id
                    await connection_manager.send_to_client(client_id, data)
                else:
                    logger.warning(f"Received status response from device {device_id} but no paired client")
            else:
                logger.warning(f"Unknown message type from device {device_id}: {message_type}")
                
    except WebSocketDisconnect:
        logger.info(f"Device {device_id} disconnected")
        await connection_manager.disconnect_device(device_id)
    except Exception as e:
        logger.error(f"Error in device websocket: {str(e)}", exc_info=True)
        await connection_manager.disconnect_device(device_id)


@app.websocket("/ws/client/{client_id}")
async def client_websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for client connections."""
    await connection_manager.connect_client(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "devices_list":
                await connection_manager.send_devices_list(client_id)
                continue
                
            if message_type == "pong":
                # Update last activity time to prevent timeout
                if client_id in connection_manager.client_connections:
                    connection_manager.client_connections[client_id].last_activity = time.time()
                continue
                
            target_device_id = data.get("deviceId")
            
            if not target_device_id and message_type != "devices_list":
                logger.warning(f"Client {client_id} sent message without deviceId for message type: {message_type}")
                await connection_manager.send_to_client(
                    client_id,
                    {"type": "error", "message": f"Missing deviceId for message type: {message_type}"}
                )
                continue
                
            if message_type == "webrtc":
                await webrtc_handler.handle_client_message(client_id, target_device_id, data, connection_manager)
            elif message_type == "command":
                await command_handler.process_command(client_id, target_device_id, data, connection_manager)
            elif message_type == "connect_device":
                # Pair the client with the device to start receiving telemetry
                success = await connection_manager.pair_device_with_client(target_device_id, client_id)
                if success:
                    logger.info(f"Client {client_id} connected to device {target_device_id} for telemetry")
                    await connection_manager.send_to_client(
                        client_id, 
                        {"type": "device_connected", "deviceId": target_device_id, "status": "connected"}
                    )
                else:
                    logger.warning(f"Failed to connect client {client_id} to device {target_device_id}")
                    await connection_manager.send_to_client(
                        client_id, 
                        {"type": "error", "message": f"Failed to connect to device {target_device_id}"}
                    )
            else:
                logger.warning(f"Unknown message type from client {client_id}: {message_type}")
                
    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
        await connection_manager.disconnect_client(client_id)
    except Exception as e:
        logger.error(f"Error in client websocket: {str(e)}", exc_info=True)
        await connection_manager.disconnect_client(client_id)


if __name__ == "__main__":
    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug_mode
    ) 
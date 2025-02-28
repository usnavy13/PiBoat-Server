import asyncio
import logging
import os
import signal
import sys
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


@app.websocket("/ws/device/{device_id}")
async def device_websocket_endpoint(websocket: WebSocket, device_id: str):
    """WebSocket endpoint for device connections."""
    await connection_manager.connect_device(websocket, device_id)
    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "webrtc":
                await webrtc_handler.handle_device_message(device_id, data, connection_manager)
            elif message_type == "telemetry":
                await telemetry_handler.process_telemetry(device_id, data, connection_manager)
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
                
            target_device_id = data.get("deviceId")
            
            if not target_device_id and message_type != "devices_list":
                logger.warning(f"Client {client_id} sent message without deviceId")
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
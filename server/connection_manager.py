import asyncio
import logging
import time
import ujson
from typing import Dict, Set, Optional

from fastapi import WebSocket

from server.config import settings

logger = logging.getLogger(__name__)


class ConnectionState:
    """Tracks the state of a connection."""
    
    def __init__(self, websocket: WebSocket, connection_id: str):
        self.websocket = websocket
        self.connection_id = connection_id
        self.connected = True
        self.last_activity = time.time()
        self.reconnect_attempts = 0
        self.paired_id: Optional[str] = None


class ConnectionManager:
    """Manages WebSocket connections for both devices and clients."""
    
    def __init__(self):
        self.device_connections: Dict[str, ConnectionState] = {}
        self.client_connections: Dict[str, ConnectionState] = {}
        self.device_to_client_mapping: Dict[str, str] = {}
        self.client_to_device_mapping: Dict[str, str] = {}
        self._background_tasks = []
    
    async def start(self):
        """Start background tasks."""
        self._background_tasks.append(asyncio.create_task(self._ping_connections()))
        self._background_tasks.append(asyncio.create_task(self._monitor_connections()))
    
    async def connect_device(self, websocket: WebSocket, device_id: str) -> None:
        """Accept and track a device connection."""
        await websocket.accept()
        
        # Check if device is reconnecting
        existing_device = self.device_connections.get(device_id)
        if existing_device and existing_device.connected:
            # Disconnect existing connection
            try:
                await existing_device.websocket.close()
            except Exception:
                pass  # Ignore errors during close
            logger.info(f"Device {device_id} reconnected, closed old connection")
            
        # Store new connection
        self.device_connections[device_id] = ConnectionState(websocket, device_id)
        logger.info(f"Device connected: {device_id}")
        
        # Restore pairing if client is still connected
        paired_client_id = self.device_to_client_mapping.get(device_id)
        if paired_client_id and paired_client_id in self.client_connections:
            self.device_connections[device_id].paired_id = paired_client_id
            await self.send_to_client(
                paired_client_id, 
                {"type": "connection_status", "deviceId": device_id, "status": "connected"}
            )
            logger.info(f"Restored pairing between device {device_id} and client {paired_client_id}")
    
    async def connect_client(self, websocket: WebSocket, client_id: str) -> None:
        """Accept and track a client connection."""
        await websocket.accept()
        
        # Check if client is reconnecting
        existing_client = self.client_connections.get(client_id)
        if existing_client and existing_client.connected:
            # Disconnect existing connection
            try:
                await existing_client.websocket.close()
            except Exception:
                pass  # Ignore errors during close
            logger.info(f"Client {client_id} reconnected, closed old connection")
            
        # Store new connection
        self.client_connections[client_id] = ConnectionState(websocket, client_id)
        logger.info(f"Client connected: {client_id}")
        
        # Restore pairing if device is still connected
        paired_device_id = self.client_to_device_mapping.get(client_id)
        if paired_device_id and paired_device_id in self.device_connections:
            self.client_connections[client_id].paired_id = paired_device_id
            
            # Notify client about device status
            await self.send_to_client(
                client_id, 
                {"type": "connection_status", "deviceId": paired_device_id, "status": "connected"}
            )
            logger.info(f"Restored pairing between client {client_id} and device {paired_device_id}")
        
        # Send list of available devices to the client
        await self.send_devices_list(client_id)
    
    async def disconnect_device(self, device_id: str) -> None:
        """Handle device disconnection."""
        if device_id in self.device_connections:
            self.device_connections[device_id].connected = False
            logger.info(f"Device disconnected: {device_id}")
            
            # Notify paired client if it exists
            paired_client_id = self.device_to_client_mapping.get(device_id)
            if paired_client_id and paired_client_id in self.client_connections:
                await self.send_to_client(
                    paired_client_id,
                    {"type": "connection_status", "deviceId": device_id, "status": "disconnected"}
                )
    
    async def disconnect_client(self, client_id: str) -> None:
        """Handle client disconnection."""
        if client_id in self.client_connections:
            self.client_connections[client_id].connected = False
            logger.info(f"Client disconnected: {client_id}")
    
    async def pair_device_with_client(self, device_id: str, client_id: str) -> bool:
        """Pair a device with a client for direct communication."""
        if (device_id in self.device_connections and 
            self.device_connections[device_id].connected and
            client_id in self.client_connections and 
            self.client_connections[client_id].connected):
            
            # Update mapping
            self.device_to_client_mapping[device_id] = client_id
            self.client_to_device_mapping[client_id] = device_id
            
            # Update connection states
            self.device_connections[device_id].paired_id = client_id
            self.client_connections[client_id].paired_id = device_id
            
            logger.info(f"Paired device {device_id} with client {client_id}")
            return True
        return False
    
    async def unpair_device_and_client(self, device_id: str, client_id: str) -> None:
        """Remove pairing between a device and client."""
        if self.device_to_client_mapping.get(device_id) == client_id:
            self.device_to_client_mapping.pop(device_id, None)
            self.client_to_device_mapping.pop(client_id, None)
            
            if device_id in self.device_connections:
                self.device_connections[device_id].paired_id = None
            
            if client_id in self.client_connections:
                self.client_connections[client_id].paired_id = None
                
            logger.info(f"Unpaired device {device_id} from client {client_id}")
    
    async def send_to_device(self, device_id: str, data: dict) -> bool:
        """Send data to a specific device."""
        if (device_id in self.device_connections and 
            self.device_connections[device_id].connected):
            try:
                device_conn = self.device_connections[device_id]
                await device_conn.websocket.send_json(data, mode="text")
                device_conn.last_activity = time.time()
                return True
            except Exception as e:
                logger.error(f"Error sending to device {device_id}: {str(e)}")
                await self.disconnect_device(device_id)
        return False
    
    async def send_to_client(self, client_id: str, data: dict) -> bool:
        """Send data to a specific client."""
        if (client_id in self.client_connections and 
            self.client_connections[client_id].connected):
            try:
                client_conn = self.client_connections[client_id]
                await client_conn.websocket.send_json(data, mode="text")
                client_conn.last_activity = time.time()
                return True
            except Exception as e:
                logger.error(f"Error sending to client {client_id}: {str(e)}")
                await self.disconnect_client(client_id)
        return False
    
    async def send_devices_list(self, client_id: str) -> None:
        """Send list of available devices to a client."""
        if client_id in self.client_connections:
            devices = [
                {
                    "id": device_id, 
                    "connected": device.connected,
                    "paired": device.paired_id == client_id
                }
                for device_id, device in self.device_connections.items()
            ]
            await self.send_to_client(client_id, {
                "type": "devices_list",
                "devices": devices
            })
    
    async def close_all_connections(self) -> None:
        """Close all WebSocket connections."""
        logger.info("Closing all connections")
        
        # Cancel background tasks
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        
        # Close device connections
        for device_id, conn in list(self.device_connections.items()):
            try:
                await conn.websocket.close()
                logger.info(f"Closed connection for device {device_id}")
            except Exception as e:
                logger.error(f"Error closing device connection {device_id}: {str(e)}")
        
        # Close client connections
        for client_id, conn in list(self.client_connections.items()):
            try:
                await conn.websocket.close()
                logger.info(f"Closed connection for client {client_id}")
            except Exception as e:
                logger.error(f"Error closing client connection {client_id}: {str(e)}")
                
        # Clear all mappings
        self.device_connections.clear()
        self.client_connections.clear()
        self.device_to_client_mapping.clear()
        self.client_to_device_mapping.clear()
        
        logger.info("All connections closed")
    
    async def _ping_connections(self) -> None:
        """Send periodic ping to all connections to keep them alive."""
        while True:
            try:
                # Ping devices
                for device_id, conn in list(self.device_connections.items()):
                    if conn.connected:
                        try:
                            await conn.websocket.send_json({"type": "ping"})
                        except Exception:
                            await self.disconnect_device(device_id)
                
                # Ping clients
                for client_id, conn in list(self.client_connections.items()):
                    if conn.connected:
                        try:
                            await conn.websocket.send_json({"type": "ping"})
                        except Exception:
                            await self.disconnect_client(client_id)
                            
            except Exception as e:
                logger.error(f"Error in ping task: {str(e)}")
                
            await asyncio.sleep(settings.ping_interval)
    
    async def _monitor_connections(self) -> None:
        """Monitor connections for timeouts."""
        while True:
            try:
                current_time = time.time()
                timeout = settings.connection_timeout
                
                # Check device connections
                for device_id, conn in list(self.device_connections.items()):
                    if conn.connected and (current_time - conn.last_activity) > timeout:
                        logger.warning(f"Device {device_id} connection timed out")
                        await self.disconnect_device(device_id)
                
                # Check client connections
                for client_id, conn in list(self.client_connections.items()):
                    if conn.connected and (current_time - conn.last_activity) > timeout:
                        logger.warning(f"Client {client_id} connection timed out")
                        await self.disconnect_client(client_id)
                        
            except Exception as e:
                logger.error(f"Error in connection monitor: {str(e)}")
                
            await asyncio.sleep(10)  # Check every 10 seconds 
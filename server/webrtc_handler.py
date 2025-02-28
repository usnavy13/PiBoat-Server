import logging
import asyncio
import ujson
from typing import Dict, Any, Optional

from server.config import settings

logger = logging.getLogger(__name__)


class WebRTCHandler:
    """Handles WebRTC signaling and session management."""
    
    def __init__(self):
        """Initialize WebRTC handler."""
        self.active_sessions = {}
    
    async def handle_device_message(self, device_id: str, message: Dict[str, Any], connection_manager) -> None:
        """Handle WebRTC messages from the device."""
        message_subtype = message.get("subtype")
        
        # Validate message format
        if not self._validate_webrtc_message(message, is_device=True):
            logger.warning(f"Invalid WebRTC message format from device {device_id}: {message}")
            return
        
        # Get paired client ID if it exists
        paired_client_id = connection_manager.device_to_client_mapping.get(device_id)
        if not paired_client_id:
            logger.warning(f"Device {device_id} sent WebRTC message but has no paired client")
            return
        
        # Log message type with limited content
        logger.debug(f"WebRTC message from device {device_id} to client {paired_client_id}: {message_subtype}")
        
        # Add sequence number for message ordering
        if "sequence" not in message:
            message["sequence"] = int(asyncio.get_event_loop().time() * 1000)
        
        # Ensure message uses boatId as specified in protocol
        if "device_id" in message:
            del message["device_id"]
        message["boatId"] = device_id
        
        # Just relay the message to the client, the relay server doesn't need to understand WebRTC
        await connection_manager.send_to_client(paired_client_id, message)
    
    async def handle_client_message(self, client_id: str, target_device_id: str, 
                                    message: Dict[str, Any], connection_manager) -> None:
        """Handle WebRTC messages from the client."""
        message_subtype = message.get("subtype")
        
        # Validate message format
        if not self._validate_webrtc_message(message, is_device=False):
            logger.warning(f"Invalid WebRTC message format from client {client_id}: {message}")
            await connection_manager.send_to_client(
                client_id, 
                {"type": "error", "message": "Invalid WebRTC message format"}
            )
            return
        
        # Ensure message uses boatId as specified in protocol
        if "boatId" in message and message["boatId"] != target_device_id:
            target_device_id = message["boatId"]
        else:
            message["boatId"] = target_device_id
        
        # Ensure client is paired with the target device
        if connection_manager.client_to_device_mapping.get(client_id) != target_device_id:
            logger.warning(f"Client {client_id} tried to send WebRTC message to unpaired device {target_device_id}")
            
            # Auto-pair if both are connected
            if target_device_id in connection_manager.device_connections and connection_manager.device_connections[target_device_id].connected:
                paired = await connection_manager.pair_device_with_client(target_device_id, client_id)
                if not paired:
                    await connection_manager.send_to_client(
                        client_id, 
                        {"type": "error", "message": f"Cannot connect to device {target_device_id}"}
                    )
                    return
            else:
                await connection_manager.send_to_client(
                    client_id, 
                    {"type": "error", "message": f"Device {target_device_id} is not available"}
                )
                return
        
        # Log message type
        logger.debug(f"WebRTC message from client {client_id} to device {target_device_id}: {message_subtype}")
        
        # Add sequence number for message ordering
        if "sequence" not in message:
            message["sequence"] = int(asyncio.get_event_loop().time() * 1000)
        
        # Handle connection initiation
        if message_subtype == "offer":
            session_id = f"{client_id}-{target_device_id}-{int(asyncio.get_event_loop().time() * 1000)}"
            self.active_sessions[session_id] = {
                "client_id": client_id,
                "device_id": target_device_id,
                "created_at": asyncio.get_event_loop().time(),
                "state": "offering"
            }
            message["sessionId"] = session_id
            
            # Update ice servers configuration if needed
            if "iceServers" not in message:
                message["iceServers"] = settings.webrtc_ice_servers
        
        # Just relay the message to the device, the relay server doesn't need to understand WebRTC details
        await connection_manager.send_to_device(target_device_id, message)
    
    def _validate_webrtc_message(self, message: Dict[str, Any], is_device: bool) -> bool:
        """Validate that a WebRTC message follows the expected format."""
        # Check required base fields
        if not isinstance(message, dict):
            return False
            
        if message.get("type") != "webrtc":
            return False
            
        subtype = message.get("subtype")
        if not subtype:
            return False
            
        # Validate specific subtypes
        if subtype == "offer":
            return "sdp" in message
            
        elif subtype == "answer":
            return "sdp" in message
            
        elif subtype == "ice_candidate":
            return "candidate" in message
            
        return True
        
    async def close_session(self, session_id: str, connection_manager) -> None:
        """Close a WebRTC session."""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            client_id = session["client_id"]
            device_id = session["device_id"]
            
            # Send close message to both parties
            message = {
                "type": "webrtc",
                "subtype": "close",
                "sessionId": session_id,
                "boatId": device_id
            }
            
            await connection_manager.send_to_client(client_id, message)
            await connection_manager.send_to_device(device_id, message)
            
            # Remove session
            del self.active_sessions[session_id]
            logger.info(f"Closed WebRTC session {session_id} between client {client_id} and device {device_id}")
            
    async def cleanup_old_sessions(self) -> None:
        """Periodically cleanup old or stale WebRTC sessions."""
        # This could be expanded in a production environment to clean up stale sessions
        pass 
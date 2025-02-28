import logging
import time
import asyncio
from typing import Dict, List, Any, Optional

from server.config import settings

logger = logging.getLogger(__name__)


class CommandHandler:
    """Processes and relays control commands from clients to devices."""
    
    def __init__(self):
        """Initialize command handler."""
        # Store command history for tracking and debugging
        self.command_history: Dict[str, List[Dict[str, Any]]] = {}
        # Track command sequence numbers
        self.command_sequences: Dict[str, int] = {}
        # Pending command acknowledgements
        self.pending_commands: Dict[str, Dict[str, Any]] = {}
    
    async def process_command(self, client_id: str, device_id: str, command_data: Dict[str, Any], connection_manager) -> None:
        """Process and relay a command from a client to a device."""
        # Check if client is paired with device
        if connection_manager.client_to_device_mapping.get(client_id) != device_id:
            logger.warning(f"Client {client_id} tried to send command to unpaired device {device_id}")
            await connection_manager.send_to_client(
                client_id,
                {
                    "type": "error",
                    "message": f"Not paired with device {device_id}",
                    "command_id": command_data.get("command_id")
                }
            )
            return
        
        # Process command
        processed_command = self._process_command(client_id, device_id, command_data)
        
        # Store in history
        self._add_to_command_history(device_id, processed_command)
        
        # Relay to device
        success = await connection_manager.send_to_device(device_id, processed_command)
        
        if not success:
            # Notify client that command couldn't be sent
            await connection_manager.send_to_client(
                client_id,
                {
                    "type": "command_status",
                    "status": "failed",
                    "message": "Device unavailable",
                    "command_id": processed_command.get("command_id")
                }
            )
            return
        
        # Register pending command for acknowledgement tracking
        command_id = processed_command.get("command_id")
        if command_id:
            self.pending_commands[command_id] = {
                "client_id": client_id,
                "device_id": device_id,
                "timestamp": time.time(),
                "command": processed_command,
                "status": "pending"
            }
            
            # Set up timeout for acknowledgement
            asyncio.create_task(self._command_timeout(command_id, connection_manager))
    
    def _process_command(self, client_id: str, device_id: str, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a command, adding metadata and validation."""
        # Increment sequence for this device
        if device_id not in self.command_sequences:
            self.command_sequences[device_id] = 0
        
        sequence = self.command_sequences[device_id] + 1
        self.command_sequences[device_id] = sequence
        
        # Generate unique command ID if not provided
        if "command_id" not in command_data:
            command_data["command_id"] = f"{device_id}-{sequence}-{int(time.time())}"
        
        # Add timestamp and sequence
        command_data["server_timestamp"] = int(time.time() * 1000)
        command_data["sequence"] = sequence
        
        # Add client identifier
        command_data["client_id"] = client_id
        
        return command_data
    
    def _add_to_command_history(self, device_id: str, command: Dict[str, Any]) -> None:
        """Add a command to the history for the device."""
        if device_id not in self.command_history:
            self.command_history[device_id] = []
        
        # Add to history, limiting to 100 most recent commands
        self.command_history[device_id].append(command)
        if len(self.command_history[device_id]) > 100:
            self.command_history[device_id] = self.command_history[device_id][-100:]
    
    async def handle_command_acknowledgement(self, device_id: str, ack_data: Dict[str, Any], connection_manager) -> None:
        """Handle acknowledgement from device for a command."""
        command_id = ack_data.get("command_id")
        status = ack_data.get("status", "unknown")
        
        if not command_id or command_id not in self.pending_commands:
            logger.warning(f"Received acknowledgement for unknown command: {command_id}")
            return
        
        # Get pending command info
        pending = self.pending_commands[command_id]
        client_id = pending["client_id"]
        
        # Update status
        pending["status"] = status
        
        # Relay acknowledgement to client
        await connection_manager.send_to_client(
            client_id,
            {
                "type": "command_status",
                "command_id": command_id,
                "status": status,
                "message": ack_data.get("message", ""),
                "timestamp": int(time.time() * 1000)
            }
        )
        
        # Remove from pending after successful acknowledgement
        if status in ["success", "completed", "failed", "rejected"]:
            self.pending_commands.pop(command_id, None)
    
    async def _command_timeout(self, command_id: str, connection_manager, timeout: int = 10) -> None:
        """Handle command timeout if no acknowledgement is received."""
        await asyncio.sleep(timeout)
        
        if command_id in self.pending_commands:
            pending = self.pending_commands[command_id]
            
            if pending["status"] == "pending":
                client_id = pending["client_id"]
                
                # Notify client about timeout
                await connection_manager.send_to_client(
                    client_id,
                    {
                        "type": "command_status",
                        "command_id": command_id,
                        "status": "timeout",
                        "message": "Device did not acknowledge command",
                        "timestamp": int(time.time() * 1000)
                    }
                )
                
                # Remove from pending
                self.pending_commands.pop(command_id, None)
    
    def get_command_history(self, device_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get command history for a device."""
        if device_id not in self.command_history:
            return []
        
        # Get the most recent commands up to the limit
        return self.command_history[device_id][-limit:] 
import logging
import time
import asyncio
import ujson
from typing import Dict, List, Any, Optional
from collections import deque

from server.config import settings

logger = logging.getLogger(__name__)


class TelemetryHandler:
    """Processes and relays telemetry data from devices to clients."""
    
    def __init__(self):
        """Initialize telemetry handler."""
        # Store recent telemetry for each device
        self.telemetry_buffers: Dict[str, deque] = {}
        # Track sequence numbers for detecting data loss
        self.sequence_trackers: Dict[str, Dict[str, int]] = {}
        # Timestamp offset tracking for synchronization
        self.time_offsets: Dict[str, float] = {}
    
    async def process_telemetry(self, device_id: str, telemetry_data: Dict[str, Any], connection_manager) -> None:
        """Process and relay telemetry data from a device."""
        # Validate telemetry format
        if not self._validate_telemetry_format(telemetry_data):
            logger.warning(f"Invalid telemetry format from device {device_id}: {telemetry_data}")
            await connection_manager.send_to_device(
                device_id,
                {"type": "error", "message": "Invalid telemetry format"}
            )
            return

        # Get paired client ID if it exists
        paired_client_id = connection_manager.device_to_client_mapping.get(device_id)
        if not paired_client_id:
            # Cache telemetry in case a client connects later
            self._buffer_telemetry(device_id, telemetry_data)
            return
        
        # Process telemetry data
        processed_data = self._process_telemetry_data(device_id, telemetry_data)
        
        # Ensure the message uses boatId as specified in protocol
        if "device_id" in processed_data:
            del processed_data["device_id"]
        processed_data["boatId"] = device_id
        
        # Relay to client
        await connection_manager.send_to_client(paired_client_id, processed_data)
    
    def _validate_telemetry_format(self, data: Dict[str, Any]) -> bool:
        """Validate that telemetry data follows the expected format."""
        # Check required base fields
        if not isinstance(data, dict):
            return False
            
        if data.get("type") != "telemetry":
            return False
            
        # Check for required fields
        required_fields = ["subtype", "sequence", "timestamp"]
        for field in required_fields:
            if field not in data:
                logger.warning(f"Missing required field in telemetry: {field}")
                return False
        
        # Check data field structure if it exists
        if "data" in data:
            if not isinstance(data["data"], dict):
                return False
                
            # If it's sensor_data, check for GPS fields
            if data.get("subtype") == "sensor_data" and "gps" in data["data"]:
                gps_data = data["data"]["gps"]
                if not isinstance(gps_data, dict):
                    return False
                    
                gps_fields = ["latitude", "longitude"]
                for field in gps_fields:
                    if field not in gps_data:
                        return False
        
        return True
    
    def _process_telemetry_data(self, device_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming telemetry data."""
        # Initialize trackers for this device if they don't exist
        if device_id not in self.sequence_trackers:
            self.sequence_trackers[device_id] = {}
        
        # Ensure device buffer exists
        if device_id not in self.telemetry_buffers:
            self.telemetry_buffers[device_id] = deque(maxlen=settings.telemetry_buffer_size)
        
        # Extract base values
        telemetry_type = data.get("subtype", "unknown")
        sequence = data.get("sequence", 0)
        timestamp = data.get("timestamp", time.time() * 1000)  # ms timestamp
        
        # Check for sequence gaps
        if telemetry_type in self.sequence_trackers[device_id]:
            expected_sequence = self.sequence_trackers[device_id][telemetry_type] + 1
            if sequence > expected_sequence:
                # Detected data loss
                gap = sequence - expected_sequence
                logger.warning(f"Telemetry sequence gap for device {device_id}: {gap} {telemetry_type} packets lost")
                
                # Add gap information to the telemetry data
                data["_meta"] = data.get("_meta", {})
                data["_meta"]["sequence_gap"] = gap
        
        # Update sequence tracker
        self.sequence_trackers[device_id][telemetry_type] = sequence
        
        # Handle timestamp synchronization
        if "system_time" in data:
            device_time = data["system_time"]  # Device's system time in ms
            server_time = time.time() * 1000   # Server's system time in ms
            
            # Calculate time offset between device and server
            self.time_offsets[device_id] = server_time - device_time
            
            # Add synchronized timestamp to the data
            data["synchronized_timestamp"] = timestamp + self.time_offsets.get(device_id, 0)
        
        # Store in buffer
        self._buffer_telemetry(device_id, data)
        
        return data
    
    def _buffer_telemetry(self, device_id: str, data: Dict[str, Any]) -> None:
        """Store telemetry in the buffer for the device."""
        if device_id not in self.telemetry_buffers:
            self.telemetry_buffers[device_id] = deque(maxlen=settings.telemetry_buffer_size)
        
        # Add to buffer
        self.telemetry_buffers[device_id].append(data)
    
    async def get_recent_telemetry(self, device_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent telemetry for a device (useful when a client first connects)."""
        if device_id not in self.telemetry_buffers:
            return []
        
        # Get the most recent telemetry up to the limit
        buffer = self.telemetry_buffers[device_id]
        return list(buffer)[-limit:] if buffer else []
    
    async def get_telemetry_stats(self, device_id: str) -> Dict[str, Any]:
        """Get telemetry statistics for a device."""
        stats = {
            "telemetry_count": 0,
            "telemetry_types": {},
            "sequence_gaps": {},
            "last_timestamp": None
        }
        
        if device_id in self.telemetry_buffers:
            buffer = self.telemetry_buffers[device_id]
            stats["telemetry_count"] = len(buffer)
            
            # Count by type
            type_counts = {}
            for item in buffer:
                telemetry_type = item.get("subtype", "unknown")
                type_counts[telemetry_type] = type_counts.get(telemetry_type, 0) + 1
            
            stats["telemetry_types"] = type_counts
            
            # Get latest timestamp
            if buffer:
                last_item = buffer[-1]
                stats["last_timestamp"] = last_item.get("timestamp")
        
        return stats 
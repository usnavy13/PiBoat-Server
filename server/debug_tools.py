import logging
import os
import json
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class MessageDebugger:
    """Utility to capture and log raw device messages for debugging."""
    
    def __init__(self, debug_dir="debug_logs"):
        self.debug_dir = debug_dir
        self.ensure_debug_dir()
        
    def ensure_debug_dir(self):
        """Ensure the debug directory exists."""
        os.makedirs(self.debug_dir, exist_ok=True)
        
    def capture_device_message(self, device_id, message):
        """Capture a raw device message to a debug file.
        Messages are appended to a single file per device."""
        try:
            filename = f"{self.debug_dir}/device_{device_id}_log.json"
            
            # Create entry for this message
            entry = {
                "timestamp": time.time(),
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "device_id": device_id,
                "message": message
            }
            
            # Read existing data if file exists
            messages = []
            if os.path.exists(filename):
                try:
                    with open(filename, 'r') as f:
                        messages = json.load(f)
                    if not isinstance(messages, list):
                        # Convert old format to new format
                        messages = [messages]
                except Exception as e:
                    logger.error(f"Error reading existing log file {filename}: {str(e)}")
                    messages = []
            
            # Append the new message
            messages.append(entry)
            
            # Write all messages back to the file
            with open(filename, 'w') as f:
                json.dump(messages, f, indent=2)
                
            logger.info(f"Appended device message to {filename}")
            return filename
        except Exception as e:
            logger.error(f"Failed to capture device message: {str(e)}")
            return None
            
    def analyze_device_messages(self, device_id=None):
        """Analyze captured messages to find patterns and issues."""
        results = {
            "total_messages": 0,
            "messages_by_type": {},
            "messages_without_type": 0,
            "messages_with_gps": 0,
            "example_gps_messages": []
        }
        
        path = Path(self.debug_dir)
        
        # Handle both old format (multiple files) and new format (single file per device)
        if device_id:
            # First check for single log file
            log_file = path / f"device_{device_id}_log.json"
            if log_file.exists():
                self._process_log_file(log_file, results)
            else:
                # Fall back to old format
                for file in path.glob(f"device_{device_id}_*.json"):
                    self._process_old_format_file(file, results)
        else:
            # Check for all device log files
            for file in path.glob("device_*_log.json"):
                self._process_log_file(file, results)
            
            # Also check old format files
            for file in path.glob("device_*_20*.json"):  # Files with timestamp in name
                self._process_old_format_file(file, results)
        
        return results
    
    def _process_log_file(self, file_path, results):
        """Process a log file containing multiple messages."""
        try:
            with open(file_path, 'r') as f:
                messages = json.load(f)
                
            if not isinstance(messages, list):
                messages = [messages]  # Handle case of single message
                
            for entry in messages:
                message = entry.get("message", {})
                results["total_messages"] += 1
                
                # Analyze message type
                msg_type = message.get("type")
                if msg_type:
                    results["messages_by_type"][msg_type] = results["messages_by_type"].get(msg_type, 0) + 1
                else:
                    results["messages_without_type"] += 1
                
                # Check for GPS data
                self._check_for_gps(message, results)
                
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {str(e)}")
    
    def _process_old_format_file(self, file_path, results):
        """Process a file in the old format (single message per file)."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                
            message = data.get("message", {})
            results["total_messages"] += 1
            
            # Analyze message type
            msg_type = message.get("type")
            if msg_type:
                results["messages_by_type"][msg_type] = results["messages_by_type"].get(msg_type, 0) + 1
            else:
                results["messages_without_type"] += 1
            
            # Check for GPS data
            self._check_for_gps(message, results)
                
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {str(e)}")
    
    def _check_for_gps(self, message, results):
        """Check if a message contains GPS data."""
        has_gps = False
        
        # Option 1: data.gps structure
        if "data" in message and isinstance(message["data"], dict) and "gps" in message["data"]:
            has_gps = True
        
        # Option 2: direct gps object
        elif "gps" in message and isinstance(message["gps"], dict):
            has_gps = True
            
        # Option 3: latitude/longitude directly in message
        elif "latitude" in message and "longitude" in message:
            has_gps = True
        
        if has_gps:
            results["messages_with_gps"] += 1
            # Store a few examples for analysis
            if len(results["example_gps_messages"]) < 3:
                results["example_gps_messages"].append(message)


# Singleton instance for global use
message_debugger = MessageDebugger() 
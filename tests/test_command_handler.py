import pytest
import time
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from server.command_handler import CommandHandler


@pytest.fixture
def command_handler():
    """Create a command handler instance for testing."""
    handler = CommandHandler()
    yield handler


@pytest.fixture
def connection_manager():
    """Create a mock connection manager for testing."""
    cm = MagicMock()
    cm.send_to_device = AsyncMock()
    cm.send_to_client = AsyncMock()
    cm.client_to_device_mapping = {}
    return cm


@pytest.mark.asyncio
async def test_process_command_paired(command_handler, connection_manager):
    """Test processing command when client is paired with device."""
    # Setup paired client and device
    client_id = "test-client-1"
    device_id = "test-device-1"
    connection_manager.client_to_device_mapping = {client_id: device_id}
    connection_manager.send_to_device.return_value = True
    
    # Create command data
    command_data = {
        "type": "command",
        "action": "move",
        "parameters": {"direction": "forward", "speed": 0.5}
    }
    
    # Process command
    await command_handler.process_command(client_id, device_id, command_data, connection_manager)
    
    # Check if command was sent to device
    connection_manager.send_to_device.assert_called_once()
    
    # Verify command has been processed correctly
    sent_command = connection_manager.send_to_device.call_args[0][1]
    assert sent_command["type"] == "command"
    assert sent_command["action"] == "move"
    assert sent_command["client_id"] == client_id
    assert "command_id" in sent_command
    assert "sequence" in sent_command
    assert "server_timestamp" in sent_command
    
    # Check if command was added to history
    assert device_id in command_handler.command_history
    assert len(command_handler.command_history[device_id]) == 1
    
    # Check if pending command was registered
    command_id = sent_command["command_id"]
    assert command_id in command_handler.pending_commands
    assert command_handler.pending_commands[command_id]["client_id"] == client_id
    assert command_handler.pending_commands[command_id]["device_id"] == device_id


@pytest.mark.asyncio
async def test_process_command_unpaired(command_handler, connection_manager):
    """Test processing command when client is not paired with device."""
    # Setup unpaired client and device
    client_id = "test-client-1"
    device_id = "test-device-1"
    connection_manager.client_to_device_mapping = {}  # Empty mapping = unpaired
    
    # Create command data
    command_data = {
        "type": "command",
        "action": "move",
        "parameters": {"direction": "forward", "speed": 0.5}
    }
    
    # Process command
    await command_handler.process_command(client_id, device_id, command_data, connection_manager)
    
    # Check if error was sent to client
    connection_manager.send_to_client.assert_called_once()
    error_message = connection_manager.send_to_client.call_args[0][1]
    assert error_message["type"] == "error"
    assert "Not paired with device" in error_message["message"]
    
    # Check that command was not sent to device
    connection_manager.send_to_device.assert_not_called()


@pytest.mark.asyncio
async def test_process_command_device_unavailable(command_handler, connection_manager):
    """Test processing command when device is unavailable."""
    # Setup paired client and device but device is unavailable
    client_id = "test-client-1"
    device_id = "test-device-1"
    connection_manager.client_to_device_mapping = {client_id: device_id}
    connection_manager.send_to_device.return_value = False  # Simulate device unavailable
    
    # Create command data
    command_data = {
        "type": "command",
        "action": "move",
        "parameters": {"direction": "forward", "speed": 0.5}
    }
    
    # Process command
    await command_handler.process_command(client_id, device_id, command_data, connection_manager)
    
    # Check if failure was sent to client
    connection_manager.send_to_client.assert_called_once()
    status_message = connection_manager.send_to_client.call_args[0][1]
    assert status_message["type"] == "command_status"
    assert status_message["status"] == "failed"
    assert "Device unavailable" in status_message["message"]


def test_process_command(command_handler):
    """Test command processing and metadata addition."""
    client_id = "test-client-1"
    device_id = "test-device-1"
    
    # Initial command with no metadata
    command_data = {
        "type": "command",
        "action": "move",
        "parameters": {"direction": "forward", "speed": 0.5}
    }
    
    # Process command
    processed = command_handler._process_command(client_id, device_id, command_data)
    
    # Check metadata added
    assert "command_id" in processed
    assert "server_timestamp" in processed
    assert "sequence" in processed
    assert "client_id" in processed
    assert processed["client_id"] == client_id
    assert processed["sequence"] == 1  # First command should be sequence 1
    
    # Process another command to check sequence increment
    command_data2 = {
        "type": "command",
        "action": "stop"
    }
    processed2 = command_handler._process_command(client_id, device_id, command_data2)
    
    # Check sequence incremented
    assert processed2["sequence"] == 2
    
    # Process command with existing command_id
    command_data3 = {
        "type": "command",
        "action": "turn",
        "command_id": "custom-id-123"
    }
    processed3 = command_handler._process_command(client_id, device_id, command_data3)
    
    # Check custom command_id preserved
    assert processed3["command_id"] == "custom-id-123"
    assert processed3["sequence"] == 3


def test_add_to_command_history(command_handler):
    """Test adding commands to history."""
    device_id = "test-device-1"
    
    # Add 110 commands to test history limit
    for i in range(110):
        command = {
            "type": "command",
            "action": "test",
            "sequence": i,
            "command_id": f"cmd-{i}"
        }
        command_handler._add_to_command_history(device_id, command)
    
    # Check history size limited to 100
    assert len(command_handler.command_history[device_id]) == 100
    
    # Check only the most recent commands are kept
    sequences = [cmd["sequence"] for cmd in command_handler.command_history[device_id]]
    assert min(sequences) == 10  # First 10 should be dropped
    assert max(sequences) == 109  # Last should be 109


@pytest.mark.asyncio
async def test_handle_command_acknowledgement(command_handler, connection_manager):
    """Test handling command acknowledgement from device."""
    # Setup
    client_id = "test-client-1"
    device_id = "test-device-1"
    command_id = "test-command-123"
    
    # Register a pending command
    command_handler.pending_commands[command_id] = {
        "client_id": client_id,
        "device_id": device_id,
        "timestamp": time.time(),
        "command": {"command_id": command_id, "action": "test"},
        "status": "pending"
    }
    
    # Create acknowledgement data
    ack_data = {
        "type": "command_ack",
        "command_id": command_id,
        "status": "success",
        "message": "Command executed successfully"
    }
    
    # Handle acknowledgement
    await command_handler.handle_command_acknowledgement(device_id, ack_data, connection_manager)
    
    # Check if status was relayed to client
    connection_manager.send_to_client.assert_called_once()
    status_message = connection_manager.send_to_client.call_args[0][1]
    assert status_message["type"] == "command_status"
    assert status_message["command_id"] == command_id
    assert status_message["status"] == "success"
    
    # Check if command was removed from pending
    assert command_id not in command_handler.pending_commands


@pytest.mark.asyncio
async def test_handle_unknown_command_acknowledgement(command_handler, connection_manager):
    """Test handling acknowledgement for unknown command."""
    # Create acknowledgement data for unknown command
    ack_data = {
        "type": "command_ack",
        "command_id": "unknown-command-id",
        "status": "success"
    }
    
    # Handle acknowledgement
    await command_handler.handle_command_acknowledgement("test-device-1", ack_data, connection_manager)
    
    # Check that nothing was sent to client
    connection_manager.send_to_client.assert_not_called()


@pytest.mark.asyncio
async def test_command_timeout(command_handler, connection_manager):
    """Test command timeout handling."""
    # Setup
    client_id = "test-client-1"
    device_id = "test-device-1"
    command_id = "test-command-123"
    
    # Register a pending command
    command_handler.pending_commands[command_id] = {
        "client_id": client_id,
        "device_id": device_id,
        "timestamp": time.time(),
        "command": {"command_id": command_id, "action": "test"},
        "status": "pending"
    }
    
    # Run timeout task with short timeout
    await command_handler._command_timeout(command_id, connection_manager, timeout=0.1)
    
    # Check if timeout notification was sent to client
    connection_manager.send_to_client.assert_called_once()
    timeout_message = connection_manager.send_to_client.call_args[0][1]
    assert timeout_message["type"] == "command_status"
    assert timeout_message["command_id"] == command_id
    assert timeout_message["status"] == "timeout"
    
    # Check if command was removed from pending
    assert command_id not in command_handler.pending_commands


def test_get_command_history(command_handler):
    """Test retrieving command history."""
    device_id = "test-device-1"
    
    # Add some commands to history
    for i in range(30):
        command = {
            "type": "command",
            "action": "test",
            "sequence": i,
            "command_id": f"cmd-{i}"
        }
        command_handler._add_to_command_history(device_id, command)
    
    # Get full history (limited to 20 by default)
    history = command_handler.get_command_history(device_id)
    assert len(history) == 20
    
    # Get history with custom limit
    limited_history = command_handler.get_command_history(device_id, limit=5)
    assert len(limited_history) == 5
    
    # Check that most recent commands are returned
    sequences = [cmd["sequence"] for cmd in limited_history]
    assert min(sequences) == 25  # For limit=5, should start at 30-5=25
    assert max(sequences) == 29  # Last should be 29 
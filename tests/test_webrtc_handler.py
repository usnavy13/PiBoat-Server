import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from server.webrtc_handler import WebRTCHandler


@pytest.fixture
def webrtc_handler():
    """Create a WebRTC handler instance for testing."""
    handler = WebRTCHandler()
    yield handler


@pytest.fixture
def connection_manager():
    """Create a mock connection manager for testing."""
    cm = MagicMock()
    cm.send_to_device = AsyncMock()
    cm.send_to_client = AsyncMock()
    cm.pair_device_with_client = AsyncMock()
    cm.device_connections = {}
    cm.client_to_device_mapping = {}
    cm.device_to_client_mapping = {}
    return cm


@pytest.mark.asyncio
async def test_handle_device_message_paired(webrtc_handler, connection_manager):
    """Test handling WebRTC message from device when paired with client."""
    # Setup paired device
    device_id = "test-device-1"
    client_id = "test-client-1"
    connection_manager.device_to_client_mapping = {device_id: client_id}
    
    # Create valid WebRTC message
    message = {
        "type": "webrtc",
        "subtype": "answer",
        "sdp": "dummy sdp data"
    }
    
    # Handle message
    await webrtc_handler.handle_device_message(device_id, message, connection_manager)
    
    # Check if message was relayed to client
    connection_manager.send_to_client.assert_called_once()
    sent_message = connection_manager.send_to_client.call_args[0][1]
    assert sent_message["type"] == "webrtc"
    assert sent_message["subtype"] == "answer"
    assert sent_message["boatId"] == device_id
    assert "sequence" in sent_message


@pytest.mark.asyncio
async def test_handle_device_message_unpaired(webrtc_handler, connection_manager):
    """Test handling WebRTC message from device when not paired with client."""
    # Setup unpaired device
    device_id = "test-device-1"
    connection_manager.device_to_client_mapping = {}
    
    # Create valid WebRTC message
    message = {
        "type": "webrtc",
        "subtype": "answer",
        "sdp": "dummy sdp data"
    }
    
    # Handle message
    await webrtc_handler.handle_device_message(device_id, message, connection_manager)
    
    # Check that message was not relayed (no paired client)
    connection_manager.send_to_client.assert_not_called()


@pytest.mark.asyncio
async def test_handle_device_message_invalid(webrtc_handler, connection_manager):
    """Test handling invalid WebRTC message from device."""
    # Setup paired device
    device_id = "test-device-1"
    client_id = "test-client-1"
    connection_manager.device_to_client_mapping = {device_id: client_id}
    
    # Create invalid WebRTC message (missing sdp)
    invalid_message = {
        "type": "webrtc",
        "subtype": "offer"
        # Missing sdp field for offer
    }
    
    # Handle message
    await webrtc_handler.handle_device_message(device_id, invalid_message, connection_manager)
    
    # Check that message was not relayed due to validation failure
    connection_manager.send_to_client.assert_not_called()


@pytest.mark.asyncio
async def test_handle_client_message_paired(webrtc_handler, connection_manager):
    """Test handling WebRTC message from client when paired with device."""
    # Setup paired client and device
    client_id = "test-client-1"
    device_id = "test-device-1"
    connection_manager.client_to_device_mapping = {client_id: device_id}
    
    # Create valid WebRTC message
    message = {
        "type": "webrtc",
        "subtype": "offer",
        "sdp": "dummy sdp data",
        "boatId": device_id
    }
    
    # Handle message
    await webrtc_handler.handle_client_message(client_id, device_id, message, connection_manager)
    
    # Check if message was relayed to device
    connection_manager.send_to_device.assert_called_once()
    sent_message = connection_manager.send_to_device.call_args[0][1]
    assert sent_message["type"] == "webrtc"
    assert sent_message["subtype"] == "offer"
    assert sent_message["boatId"] == device_id
    assert "sequence" in sent_message
    
    # Check if session was created for offer
    assert len(webrtc_handler.active_sessions) == 1
    session = list(webrtc_handler.active_sessions.values())[0]
    assert session["client_id"] == client_id
    assert session["device_id"] == device_id
    assert session["state"] == "offering"


@pytest.mark.asyncio
async def test_handle_client_message_unpaired_autopair(webrtc_handler, connection_manager):
    """Test handling WebRTC message from client when not paired but auto-pairing is possible."""
    # Setup unpaired client but with available device
    client_id = "test-client-1"
    device_id = "test-device-1"
    connection_manager.client_to_device_mapping = {}
    connection_manager.device_connections = {device_id: MagicMock(connected=True)}
    connection_manager.pair_device_with_client.return_value = True
    
    # Create valid WebRTC message
    message = {
        "type": "webrtc",
        "subtype": "offer",
        "sdp": "dummy sdp data",
        "boatId": device_id
    }
    
    # Handle message
    await webrtc_handler.handle_client_message(client_id, device_id, message, connection_manager)
    
    # Check if auto-pairing was attempted
    connection_manager.pair_device_with_client.assert_called_once_with(device_id, client_id)
    
    # Check if message was relayed to device after successful pairing
    connection_manager.send_to_device.assert_called_once()


@pytest.mark.asyncio
async def test_handle_client_message_unpaired_no_device(webrtc_handler, connection_manager):
    """Test handling WebRTC message from client when device is not available."""
    # Setup unpaired client with unavailable device
    client_id = "test-client-1"
    device_id = "test-device-1"
    connection_manager.client_to_device_mapping = {}
    connection_manager.device_connections = {}  # Device not connected
    
    # Create valid WebRTC message
    message = {
        "type": "webrtc",
        "subtype": "offer",
        "sdp": "dummy sdp data",
        "boatId": device_id
    }
    
    # Handle message
    await webrtc_handler.handle_client_message(client_id, device_id, message, connection_manager)
    
    # Check if error was sent to client
    connection_manager.send_to_client.assert_called_once()
    error_message = connection_manager.send_to_client.call_args[0][1]
    assert error_message["type"] == "error"
    assert "not available" in error_message["message"]
    
    # Check that message was not relayed to device
    connection_manager.send_to_device.assert_not_called()


@pytest.mark.asyncio
async def test_handle_client_message_invalid(webrtc_handler, connection_manager):
    """Test handling invalid WebRTC message from client."""
    # Setup paired client and device
    client_id = "test-client-1"
    device_id = "test-device-1"
    connection_manager.client_to_device_mapping = {client_id: device_id}
    
    # Create invalid WebRTC message (wrong type)
    invalid_message = {
        "type": "not_webrtc",
        "subtype": "offer",
        "sdp": "dummy sdp data"
    }
    
    # Handle message
    await webrtc_handler.handle_client_message(client_id, device_id, invalid_message, connection_manager)
    
    # Check if error was sent to client
    connection_manager.send_to_client.assert_called_once()
    error_message = connection_manager.send_to_client.call_args[0][1]
    assert error_message["type"] == "error"
    assert "Invalid WebRTC message format" in error_message["message"]
    
    # Check that message was not relayed to device
    connection_manager.send_to_device.assert_not_called()


def test_validate_webrtc_message(webrtc_handler):
    """Test WebRTC message validation."""
    # Valid offer from client
    valid_offer_client = {
        "type": "webrtc",
        "subtype": "offer",
        "sdp": "dummy sdp data"
    }
    
    # Valid answer from device
    valid_answer_device = {
        "type": "webrtc",
        "subtype": "answer",
        "sdp": "dummy sdp data"
    }
    
    # Valid ICE candidate
    valid_ice = {
        "type": "webrtc",
        "subtype": "ice_candidate",
        "candidate": "dummy ice candidate"
    }
    
    # Invalid offer (missing sdp)
    invalid_offer = {
        "type": "webrtc",
        "subtype": "offer"
    }
    
    # Invalid message (wrong type)
    invalid_type = {
        "type": "not_webrtc",
        "subtype": "offer",
        "sdp": "dummy sdp data"
    }
    
    # Invalid message (missing subtype)
    invalid_subtype = {
        "type": "webrtc"
    }
    
    # Invalid message (missing candidate for ice)
    invalid_ice = {
        "type": "webrtc",
        "subtype": "ice_candidate"
    }
    
    # Test validation
    assert webrtc_handler._validate_webrtc_message(valid_offer_client, is_device=False) == True
    assert webrtc_handler._validate_webrtc_message(valid_answer_device, is_device=True) == True
    assert webrtc_handler._validate_webrtc_message(valid_ice, is_device=True) == True
    assert webrtc_handler._validate_webrtc_message(valid_ice, is_device=False) == True
    
    assert webrtc_handler._validate_webrtc_message(invalid_offer, is_device=False) == False
    assert webrtc_handler._validate_webrtc_message(invalid_type, is_device=False) == False
    assert webrtc_handler._validate_webrtc_message(invalid_subtype, is_device=False) == False
    assert webrtc_handler._validate_webrtc_message(invalid_ice, is_device=False) == False
    assert webrtc_handler._validate_webrtc_message("not a dict", is_device=False) == False


@pytest.mark.asyncio
async def test_close_session(webrtc_handler, connection_manager):
    """Test closing a WebRTC session."""
    # Setup a session
    client_id = "test-client-1"
    device_id = "test-device-1"
    session_id = "test-session-123"
    
    webrtc_handler.active_sessions[session_id] = {
        "client_id": client_id,
        "device_id": device_id,
        "created_at": asyncio.get_event_loop().time(),
        "state": "connected"
    }
    
    # Close the session
    await webrtc_handler.close_session(session_id, connection_manager)
    
    # Check if close messages were sent to both parties
    assert connection_manager.send_to_client.call_count == 1
    assert connection_manager.send_to_device.call_count == 1
    
    # Check close message format
    client_message = connection_manager.send_to_client.call_args[0][1]
    assert client_message["type"] == "webrtc"
    assert client_message["subtype"] == "close"
    assert client_message["sessionId"] == session_id
    
    # Check if session was removed
    assert session_id not in webrtc_handler.active_sessions 
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from server.connection_manager import ConnectionManager, ConnectionState


@pytest.fixture
def connection_manager():
    """Create a connection manager instance for testing."""
    with patch('asyncio.create_task'):  # Prevent background tasks from running
        cm = ConnectionManager()
        yield cm


@pytest.mark.asyncio
async def test_connect_device(connection_manager):
    """Test device connection."""
    # Mock WebSocket
    websocket = AsyncMock()
    websocket.accept = AsyncMock()
    
    # Connect device
    await connection_manager.connect_device(websocket, "test-device-1")
    
    # Check if accept was called
    websocket.accept.assert_called_once()
    
    # Check if device was added to connections
    assert "test-device-1" in connection_manager.device_connections
    assert connection_manager.device_connections["test-device-1"].connected == True


@pytest.mark.asyncio
async def test_connect_client(connection_manager):
    """Test client connection."""
    # Mock WebSocket
    websocket = AsyncMock()
    websocket.accept = AsyncMock()
    
    # Connect client
    with patch.object(connection_manager, 'send_devices_list', AsyncMock()):
        await connection_manager.connect_client(websocket, "test-client-1")
    
    # Check if accept was called
    websocket.accept.assert_called_once()
    
    # Check if client was added to connections
    assert "test-client-1" in connection_manager.client_connections
    assert connection_manager.client_connections["test-client-1"].connected == True


@pytest.mark.asyncio
async def test_disconnect_device(connection_manager):
    """Test device disconnection."""
    # Setup: Connect a device first
    websocket = AsyncMock()
    await connection_manager.connect_device(websocket, "test-device-1")
    
    # Disconnect device
    await connection_manager.disconnect_device("test-device-1")
    
    # Check if device is marked as disconnected
    assert connection_manager.device_connections["test-device-1"].connected == False


@pytest.mark.asyncio
async def test_disconnect_client(connection_manager):
    """Test client disconnection."""
    # Setup: Connect a client first
    websocket = AsyncMock()
    with patch.object(connection_manager, 'send_devices_list', AsyncMock()):
        await connection_manager.connect_client(websocket, "test-client-1")
    
    # Disconnect client
    await connection_manager.disconnect_client("test-client-1")
    
    # Check if client is marked as disconnected
    assert connection_manager.client_connections["test-client-1"].connected == False


@pytest.mark.asyncio
async def test_pair_device_with_client(connection_manager):
    """Test pairing device with client."""
    # Setup: Connect device and client
    device_ws = AsyncMock()
    client_ws = AsyncMock()
    await connection_manager.connect_device(device_ws, "test-device-1")
    with patch.object(connection_manager, 'send_devices_list', AsyncMock()):
        await connection_manager.connect_client(client_ws, "test-client-1")
    
    # Pair device with client
    result = await connection_manager.pair_device_with_client("test-device-1", "test-client-1")
    
    # Check if pairing was successful
    assert result == True
    assert connection_manager.device_to_client_mapping["test-device-1"] == "test-client-1"
    assert connection_manager.client_to_device_mapping["test-client-1"] == "test-device-1"
    assert connection_manager.device_connections["test-device-1"].paired_id == "test-client-1"
    assert connection_manager.client_connections["test-client-1"].paired_id == "test-device-1"


@pytest.mark.asyncio
async def test_unpair_device_and_client(connection_manager):
    """Test unpairing device and client."""
    # Setup: Connect and pair a device and client
    device_ws = AsyncMock()
    client_ws = AsyncMock()
    await connection_manager.connect_device(device_ws, "test-device-1")
    with patch.object(connection_manager, 'send_devices_list', AsyncMock()):
        await connection_manager.connect_client(client_ws, "test-client-1")
    await connection_manager.pair_device_with_client("test-device-1", "test-client-1")
    
    # Unpair device and client
    await connection_manager.unpair_device_and_client("test-device-1", "test-client-1")
    
    # Check if unpairing was successful
    assert "test-device-1" not in connection_manager.device_to_client_mapping
    assert "test-client-1" not in connection_manager.client_to_device_mapping
    assert connection_manager.device_connections["test-device-1"].paired_id is None
    assert connection_manager.client_connections["test-client-1"].paired_id is None


@pytest.mark.asyncio
async def test_send_to_device(connection_manager):
    """Test sending data to a device."""
    # Setup: Connect a device
    websocket = AsyncMock()
    websocket.send_json = AsyncMock()
    await connection_manager.connect_device(websocket, "test-device-1")
    
    # Send data to device
    data = {"type": "test", "message": "Hello, device!"}
    result = await connection_manager.send_to_device("test-device-1", data)
    
    # Check if data was sent
    assert result == True
    websocket.send_json.assert_called_once_with(data, mode="text")


@pytest.mark.asyncio
async def test_send_to_client(connection_manager):
    """Test sending data to a client."""
    # Setup: Connect a client
    websocket = AsyncMock()
    websocket.send_json = AsyncMock()
    with patch.object(connection_manager, 'send_devices_list', AsyncMock()):
        await connection_manager.connect_client(websocket, "test-client-1")
    
    # Send data to client
    data = {"type": "test", "message": "Hello, client!"}
    result = await connection_manager.send_to_client("test-client-1", data)
    
    # Check if data was sent
    assert result == True
    websocket.send_json.assert_called_once_with(data, mode="text")


@pytest.mark.asyncio
async def test_send_devices_list(connection_manager):
    """Test sending devices list to a client."""
    # Setup: Connect a device and a client
    device_ws = AsyncMock()
    client_ws = AsyncMock()
    client_ws.send_json = AsyncMock()
    await connection_manager.connect_device(device_ws, "test-device-1")
    with patch.object(connection_manager, 'send_devices_list', AsyncMock()):
        await connection_manager.connect_client(client_ws, "test-client-1")
    
    # Replace mocked send_devices_list with real one for testing
    connection_manager.send_devices_list = ConnectionManager.send_devices_list.__get__(connection_manager, ConnectionManager)
    
    # Mock send_to_client to capture the message
    original_send_to_client = connection_manager.send_to_client
    connection_manager.send_to_client = AsyncMock()
    
    # Send devices list
    await connection_manager.send_devices_list("test-client-1")
    
    # Check if send_to_client was called with correct data
    connection_manager.send_to_client.assert_called_once()
    call_args = connection_manager.send_to_client.call_args[0]
    assert call_args[0] == "test-client-1"
    assert call_args[1]["type"] == "devices_list"
    assert len(call_args[1]["devices"]) == 1
    assert call_args[1]["devices"][0]["id"] == "test-device-1"


@pytest.mark.asyncio
async def test_device_reconnect(connection_manager):
    """Test device reconnection."""
    # Connect first device instance
    websocket1 = AsyncMock()
    websocket1.close = AsyncMock()
    await connection_manager.connect_device(websocket1, "test-device-1")
    
    # Connect second device instance with same ID (reconnect)
    websocket2 = AsyncMock()
    await connection_manager.connect_device(websocket2, "test-device-1")
    
    # Check if first connection was closed
    websocket1.close.assert_called_once()
    
    # Check if device uses the new websocket
    assert connection_manager.device_connections["test-device-1"].websocket == websocket2


@pytest.mark.asyncio
async def test_client_reconnect(connection_manager):
    """Test client reconnection."""
    # Connect first client instance
    websocket1 = AsyncMock()
    websocket1.close = AsyncMock()
    with patch.object(connection_manager, 'send_devices_list', AsyncMock()):
        await connection_manager.connect_client(websocket1, "test-client-1")
    
    # Connect second client instance with same ID (reconnect)
    websocket2 = AsyncMock()
    with patch.object(connection_manager, 'send_devices_list', AsyncMock()):
        await connection_manager.connect_client(websocket2, "test-client-1")
    
    # Check if first connection was closed
    websocket1.close.assert_called_once()
    
    # Check if client uses the new websocket
    assert connection_manager.client_connections["test-client-1"].websocket == websocket2


@pytest.mark.asyncio
async def test_close_all_connections(connection_manager):
    """Test closing all connections."""
    # Setup: Connect a device and a client
    device_ws = AsyncMock()
    device_ws.close = AsyncMock()
    client_ws = AsyncMock()
    client_ws.close = AsyncMock()
    
    await connection_manager.connect_device(device_ws, "test-device-1")
    with patch.object(connection_manager, 'send_devices_list', AsyncMock()):
        await connection_manager.connect_client(client_ws, "test-client-1")
    
    # Close all connections
    await connection_manager.close_all_connections()
    
    # Check if connections were closed
    device_ws.close.assert_called_once()
    client_ws.close.assert_called_once()
    
    # Check if connections were cleared
    assert len(connection_manager.device_connections) == 0
    assert len(connection_manager.client_connections) == 0
    assert len(connection_manager.device_to_client_mapping) == 0
    assert len(connection_manager.client_to_device_mapping) == 0 
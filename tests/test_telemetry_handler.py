import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from collections import deque

from server.telemetry_handler import TelemetryHandler


@pytest.fixture
def telemetry_handler():
    """Create a telemetry handler instance for testing."""
    with patch('server.config.settings.telemetry_buffer_size', 10):
        handler = TelemetryHandler()
        yield handler


@pytest.fixture
def connection_manager():
    """Create a mock connection manager for testing."""
    cm = MagicMock()
    cm.send_to_device = AsyncMock()
    cm.send_to_client = AsyncMock()
    cm.device_to_client_mapping = {}
    return cm


@pytest.mark.asyncio
async def test_process_valid_telemetry_paired(telemetry_handler, connection_manager):
    """Test processing valid telemetry when device is paired with client."""
    # Setup paired device
    connection_manager.device_to_client_mapping = {"test-device-1": "test-client-1"}
    
    # Create valid telemetry data
    telemetry_data = {
        "type": "telemetry",
        "subtype": "sensor_data",
        "sequence": 1,
        "timestamp": int(time.time() * 1000),
        "data": {
            "gps": {
                "latitude": 37.7749,
                "longitude": -122.4194
            }
        }
    }
    
    # Process telemetry
    await telemetry_handler.process_telemetry(
        "test-device-1", telemetry_data, connection_manager
    )
    
    # Check if telemetry was sent to client
    connection_manager.send_to_client.assert_called_once()
    call_args = connection_manager.send_to_client.call_args[0]
    assert call_args[0] == "test-client-1"
    assert call_args[1]["boatId"] == "test-device-1"
    assert call_args[1]["subtype"] == "sensor_data"


@pytest.mark.asyncio
async def test_process_valid_telemetry_unpaired(telemetry_handler, connection_manager):
    """Test processing valid telemetry when device is not paired with client."""
    # Setup unpaired device
    connection_manager.device_to_client_mapping = {}
    
    # Create valid telemetry data
    telemetry_data = {
        "type": "telemetry",
        "subtype": "sensor_data",
        "sequence": 1,
        "timestamp": int(time.time() * 1000),
        "data": {
            "gps": {
                "latitude": 37.7749,
                "longitude": -122.4194
            }
        }
    }
    
    # Process telemetry
    await telemetry_handler.process_telemetry(
        "test-device-1", telemetry_data, connection_manager
    )
    
    # Check if telemetry was buffered but not sent
    connection_manager.send_to_client.assert_not_called()
    assert "test-device-1" in telemetry_handler.telemetry_buffers
    assert len(telemetry_handler.telemetry_buffers["test-device-1"]) == 1


@pytest.mark.asyncio
async def test_process_invalid_telemetry(telemetry_handler, connection_manager):
    """Test processing invalid telemetry data."""
    # Invalid telemetry data (missing required fields)
    invalid_data = {
        "type": "telemetry",
        # Missing subtype, sequence, and timestamp
        "data": {}
    }
    
    # Process invalid telemetry
    await telemetry_handler.process_telemetry(
        "test-device-1", invalid_data, connection_manager
    )
    
    # Check if error was sent to device
    connection_manager.send_to_device.assert_called_once()
    call_args = connection_manager.send_to_device.call_args[0]
    assert call_args[0] == "test-device-1"
    assert call_args[1]["type"] == "error"
    assert "Invalid telemetry format" in call_args[1]["message"]


def test_validate_telemetry_format(telemetry_handler):
    """Test telemetry format validation."""
    # Valid telemetry
    valid_data = {
        "type": "telemetry",
        "subtype": "sensor_data",
        "sequence": 1,
        "timestamp": int(time.time() * 1000),
        "data": {
            "gps": {
                "latitude": 37.7749,
                "longitude": -122.4194
            }
        }
    }
    
    # Invalid telemetry (wrong type)
    invalid_type = {
        "type": "command",  # Not telemetry
        "subtype": "sensor_data",
        "sequence": 1,
        "timestamp": int(time.time() * 1000)
    }
    
    # Invalid telemetry (missing required fields)
    missing_fields = {
        "type": "telemetry",
        # Missing subtype, sequence, timestamp
    }
    
    # Invalid telemetry (malformed GPS data)
    invalid_gps = {
        "type": "telemetry",
        "subtype": "sensor_data",
        "sequence": 1,
        "timestamp": int(time.time() * 1000),
        "data": {
            "gps": {
                # Missing longitude
                "latitude": 37.7749
            }
        }
    }
    
    # Run validation tests
    assert telemetry_handler._validate_telemetry_format(valid_data) == True
    assert telemetry_handler._validate_telemetry_format(invalid_type) == False
    assert telemetry_handler._validate_telemetry_format(missing_fields) == False
    assert telemetry_handler._validate_telemetry_format(invalid_gps) == False
    assert telemetry_handler._validate_telemetry_format("not a dict") == False


def test_process_telemetry_data(telemetry_handler):
    """Test telemetry data processing."""
    # Create telemetry data with sequence
    device_id = "test-device-1"
    telemetry_data = {
        "type": "telemetry",
        "subtype": "sensor_data",
        "sequence": 1,
        "timestamp": int(time.time() * 1000),
        "data": {"value": 42}
    }
    
    # Process first telemetry packet
    processed = telemetry_handler._process_telemetry_data(device_id, telemetry_data)
    
    # Check sequence tracking
    assert device_id in telemetry_handler.sequence_trackers
    assert "sensor_data" in telemetry_handler.sequence_trackers[device_id]
    assert telemetry_handler.sequence_trackers[device_id]["sensor_data"] == 1
    
    # Process second telemetry packet with gap in sequence
    telemetry_data["sequence"] = 5  # Gap of 3
    processed = telemetry_handler._process_telemetry_data(device_id, telemetry_data)
    
    # Check sequence gap detection
    assert "_meta" in processed
    assert "sequence_gap" in processed["_meta"]
    assert processed["_meta"]["sequence_gap"] == 3  # Expected gap of 3


def test_buffer_telemetry(telemetry_handler):
    """Test telemetry buffering."""
    device_id = "test-device-1"
    
    # Create 15 telemetry items
    for i in range(15):
        telemetry_data = {
            "type": "telemetry",
            "subtype": "sensor_data",
            "sequence": i,
            "timestamp": int(time.time() * 1000),
            "data": {"value": i}
        }
        telemetry_handler._buffer_telemetry(device_id, telemetry_data)
    
    # Check buffer size is limited to 10 (set in fixture)
    assert len(telemetry_handler.telemetry_buffers[device_id]) == 10
    
    # Check only the latest 10 items are kept
    sequences = [item["sequence"] for item in telemetry_handler.telemetry_buffers[device_id]]
    assert min(sequences) == 5  # Items 0-4 should be dropped
    assert max(sequences) == 14  # Latest item should be 14


@pytest.mark.asyncio
async def test_get_recent_telemetry(telemetry_handler):
    """Test retrieving recent telemetry."""
    device_id = "test-device-1"
    
    # Add 5 telemetry items
    for i in range(5):
        telemetry_data = {
            "type": "telemetry",
            "subtype": "sensor_data",
            "sequence": i,
            "timestamp": int(time.time() * 1000),
            "data": {"value": i}
        }
        telemetry_handler._buffer_telemetry(device_id, telemetry_data)
    
    # Get recent telemetry with different limits
    all_telemetry = await telemetry_handler.get_recent_telemetry(device_id)
    limited_telemetry = await telemetry_handler.get_recent_telemetry(device_id, limit=2)
    
    # Check results
    assert len(all_telemetry) == 5  # All items
    assert len(limited_telemetry) == 2  # Limited to 2
    assert limited_telemetry[0]["sequence"] == 3  # Second-to-last
    assert limited_telemetry[1]["sequence"] == 4  # Last


@pytest.mark.asyncio
async def test_get_telemetry_stats(telemetry_handler):
    """Test retrieving telemetry statistics."""
    device_id = "test-device-1"
    
    # Add 3 sensor_data and 2 system_status telemetry items
    for i in range(5):
        subtype = "sensor_data" if i < 3 else "system_status"
        telemetry_data = {
            "type": "telemetry",
            "subtype": subtype,
            "sequence": i,
            "timestamp": int(time.time() * 1000),
            "data": {"value": i}
        }
        telemetry_handler._buffer_telemetry(device_id, telemetry_data)
    
    # Get telemetry stats
    stats = await telemetry_handler.get_telemetry_stats(device_id)
    
    # Check stats
    assert stats["telemetry_count"] == 5
    assert stats["telemetry_types"]["sensor_data"] == 3
    assert stats["telemetry_types"]["system_status"] == 2
    assert stats["last_timestamp"] is not None 
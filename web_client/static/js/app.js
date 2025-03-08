/**
 * PiBoat Control Client - Main JavaScript
 */

// Main application class
class PiBoatClient {
    constructor() {
        this.clientId = document.getElementById('client-id').value;
        this.serverUrl = document.getElementById('server-url').value;
        this.websocket = null;
        this.peerConnection = null;
        this.connected = false;
        this.selectedDeviceId = null;
        this.deviceList = [];
        this.telemetryData = {};
        this.commandCounter = 0;
        this.videoStream = null;
        this.logToServer = true; // Whether to send logs to the server
        
        // Map related properties
        this.map = null;
        this.boatMarker = null;
        this.boatPath = null;
        this.previousPositions = []; // Array of [lat, lng]
        this.positionData = []; // Array of {position: [lat, lng], timestamp: Date, heading: number}
        this.hasInitialPosition = false;
        this.userPannedMap = false; // Track if user has manually interacted with the map
        
        // Waypoint related properties
        this.waypoints = []; // Array of {lat, lng} waypoints
        this.waypointMarkers = []; // Array of waypoint markers
        this.waypointPath = null; // Polyline connecting waypoints
        this.waypointsEnabled = false; // Flag to indicate if waypoint mode is active
        
        // Initialize the application
        this.initEventListeners();
        this.initMap();
        this.consoleLog('Client initialized', 'info');
    }
    
    // Initialize all event listeners
    initEventListeners() {
        // Connection
        document.getElementById('connect-btn').addEventListener('click', () => this.toggleConnection());
        
        // Devices
        document.getElementById('refresh-devices-btn').addEventListener('click', () => this.refreshDevices());
        
        // Commands
        document.getElementById('stop-btn').addEventListener('click', () => this.sendStopCommand());
        document.getElementById('set-rudder-btn').addEventListener('click', () => this.sendRudderCommand());
        document.getElementById('set-throttle-btn').addEventListener('click', () => this.sendThrottleCommand());
        
        // Add event listeners for sliders to update their displayed values
        document.getElementById('rudder-position').addEventListener('input', (e) => {
            document.getElementById('rudder-value').textContent = e.target.value;
        });
        
        document.getElementById('throttle-value').addEventListener('input', (e) => {
            document.getElementById('throttle-display').textContent = e.target.value;
        });
        
        // Video
        document.getElementById('start-video-btn').addEventListener('click', () => this.startVideo());
        document.getElementById('stop-video-btn').addEventListener('click', () => this.stopVideo());
        
        // Console
        document.getElementById('clear-console-btn').addEventListener('click', () => this.clearConsole());
        
        // Map resizing
        window.addEventListener('resize', () => this.handleMapResize());
    }
    
    // Initialize the map
    initMap() {
        try {
            // Create map centered at a default location (will be updated when GPS data arrives)
            this.map = L.map('boat-map').setView([0, 0], 2);
            
            // Add satellite imagery tile layer
            L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
                maxZoom: 19
            }).addTo(this.map);
            
            // Create boat icon
            const boatIcon = L.icon({
                iconUrl: '/static/img/boat-icon.svg',
                iconSize: [32, 32],
                iconAnchor: [16, 16],
                popupAnchor: [0, -16]
            });
            
            // Create marker for the boat (will be positioned when GPS data arrives)
            this.boatMarker = L.marker([0, 0], {
                icon: boatIcon,
                title: 'PiBoat'
            });
            
            // Create empty feature group for boat path
            this.boatPath = L.featureGroup().addTo(this.map);
            
            // Create empty feature group for waypoints path
            this.waypointPath = L.featureGroup().addTo(this.map);
            
            // Add map controls
            L.control.scale().addTo(this.map);
            
            // Add custom control for clearing the path
            const clearPathControl = L.control({position: 'topright'});
            clearPathControl.onAdd = (map) => {
                const div = L.DomUtil.create('div', 'custom-map-control');
                div.innerHTML = '<button class="secondary-btn" title="Clear Path">Clear Path</button>';
                
                // Prevent click events from propagating to the map
                L.DomEvent.disableClickPropagation(div);
                
                div.onclick = () => this.clearBoatPath();
                return div;
            };
            clearPathControl.addTo(this.map);
            
            // Add custom control for toggling auto-center
            const autoCenterControl = L.control({position: 'topright'});
            autoCenterControl.onAdd = (map) => {
                const div = L.DomUtil.create('div', 'custom-map-control auto-center-control');
                div.innerHTML = '<button class="secondary-btn" title="Toggle Auto-Center">Follow Boat</button>';
                
                // Prevent click events from propagating to the map
                L.DomEvent.disableClickPropagation(div);
                
                div.onclick = () => {
                    this.userPannedMap = !this.userPannedMap;
                    const btn = div.querySelector('button');
                    if (this.userPannedMap) {
                        btn.textContent = 'Follow Boat';
                        btn.classList.remove('active');
                    } else {
                        btn.textContent = 'Following';
                        btn.classList.add('active');
                        // Center map on boat immediately
                        if (this.hasInitialPosition) {
                            this.map.setView(this.boatMarker.getLatLng(), this.map.getZoom());
                        }
                    }
                };
                return div;
            };
            autoCenterControl.addTo(this.map);
            
            // Add waypoint control
            const waypointControl = L.control({position: 'topright'});
            waypointControl.onAdd = (map) => {
                const div = L.DomUtil.create('div', 'custom-map-control waypoint-control');
                div.innerHTML = '<button class="secondary-btn" title="Set Waypoints">Set Waypoints</button>';
                
                // Prevent click events from propagating to the map
                L.DomEvent.disableClickPropagation(div);
                
                div.onclick = () => this.toggleWaypointMode();
                return div;
            };
            waypointControl.addTo(this.map);
            
            // Add clear waypoints control
            const clearWaypointsControl = L.control({position: 'topright'});
            clearWaypointsControl.onAdd = (map) => {
                const div = L.DomUtil.create('div', 'custom-map-control clear-waypoints-control');
                div.innerHTML = '<button class="secondary-btn" title="Clear Waypoints">Clear Waypoints</button>';
                
                // Prevent click events from propagating to the map
                L.DomEvent.disableClickPropagation(div);
                
                div.onclick = () => this.clearWaypoints();
                return div;
            };
            clearWaypointsControl.addTo(this.map);
            
            // Add send waypoints control
            const sendWaypointsControl = L.control({position: 'topright'});
            sendWaypointsControl.onAdd = (map) => {
                const div = L.DomUtil.create('div', 'custom-map-control send-waypoints-control');
                div.innerHTML = '<button class="primary-btn" title="Send Waypoints" disabled>Send Waypoints</button>';
                
                // Prevent click events from propagating to the map
                L.DomEvent.disableClickPropagation(div);
                
                div.onclick = () => this.sendWaypointsCommand();
                return div;
            };
            sendWaypointsControl.addTo(this.map);
            
            // Listen for map drag events to detect user interaction
            this.map.on('dragstart', () => {
                this.userPannedMap = true;
                const btn = document.querySelector('.auto-center-control button');
                if (btn) {
                    btn.textContent = 'Follow Boat';
                    btn.classList.remove('active');
                }
            });
            
            // Add map click handler for waypoints
            this.map.on('click', (e) => {
                if (this.waypointsEnabled) {
                    this.addWaypoint(e.latlng.lat, e.latlng.lng);
                }
            });
            
            this.consoleLog('Map initialized', 'info');
        } catch (error) {
            this.consoleLog(`Error initializing map: ${error.message}`, 'error');
        }
    }
    
    // Update boat position on map
    updateBoatPosition(latitude, longitude, heading) {
        if (!this.map || !this.boatMarker || !latitude || !longitude) return;
        
        try {
            const position = [latitude, longitude];
            const timestamp = new Date();
            
            // Store position with timestamp and heading
            this.positionData.push({
                position: position,
                timestamp: timestamp,
                heading: heading
            });
            
            // Limit the number of positions stored to prevent memory issues
            if (this.positionData.length > 1000) {
                this.positionData.shift();
            }
            
            // Update path with just the positions
            this.previousPositions = this.positionData.map(data => data.position);
            
            // Add the boat marker to the map if not added yet
            if (!this.hasInitialPosition) {
                this.boatMarker.setLatLng(position);
                this.boatMarker.addTo(this.map);
                this.map.setView(position, 15); // Zoom to boat position
                this.hasInitialPosition = true;
                
                // Add popup with boat info
                this.boatMarker.bindPopup(this.createBoatPopupContent(latitude, longitude, heading, timestamp));
            } else {
                // Update marker position
                this.boatMarker.setLatLng(position);
                
                // Update popup content
                const popup = this.boatMarker.getPopup();
                if (popup) {
                    popup.setContent(this.createBoatPopupContent(latitude, longitude, heading, timestamp));
                }
                
                // Only auto-pan if user hasn't manually panned the map
                if (!this.userPannedMap) {
                    this.map.setView(position, this.map.getZoom());
                } else if (!this.map.getBounds().contains(position)) {
                    // Option: Add visual indicator that boat is off-screen
                    // This could be implemented with a small arrow pointing to the boat
                }
            }
            
            // Use gradient coloring for path to show recency
            if (this.positionData.length > 1) {
                // Remove old path
                if (this.boatPath) {
                    this.boatPath.remove();
                }
                
                // Create a new gradient path by using multiple polylines
                const segments = this.createGradientPath();
                this.boatPath = L.featureGroup(segments).addTo(this.map);
                
                // Add click handler to the new path
                this.boatPath.on('click', (e) => {
                    // Find the closest point in our data to where user clicked
                    const clickedPoint = e.latlng;
                    let closestIdx = 0;
                    let closestDistance = Infinity;
                    
                    this.positionData.forEach((data, index) => {
                        const point = L.latLng(data.position[0], data.position[1]);
                        const distance = clickedPoint.distanceTo(point);
                        if (distance < closestDistance) {
                            closestDistance = distance;
                            closestIdx = index;
                        }
                    });
                    
                    // Show popup with info about this point
                    const data = this.positionData[closestIdx];
                    const content = this.createPathPointPopupContent(data);
                    
                    L.popup()
                        .setLatLng(data.position)
                        .setContent(content)
                        .openOn(this.map);
                });
            } else if (this.boatPath) {
                // Just one point, update the existing path
                this.boatPath.setLatLngs(this.previousPositions);
            }
            
            // Rotate marker based on heading if available
            if (heading !== undefined && heading !== null) {
                // This requires a custom marker with CSS rotation
                // For simplicity, we're just updating the popup text
            }
        } catch (error) {
            this.consoleLog(`Error updating boat position: ${error.message}`, 'error');
        }
    }
    
    // Create a gradient-colored path from old (blue) to recent (red)
    createGradientPath() {
        const segments = [];
        
        if (this.positionData.length < 2) {
            return segments;
        }
        
        // Create segments with colors based on recency
        for (let i = 0; i < this.positionData.length - 1; i++) {
            const ratio = i / (this.positionData.length - 1);
            
            // Color varies from blue (oldest) to red (newest)
            const r = Math.floor(255 * (1 - ratio));
            const g = 0;
            const b = Math.floor(255 * ratio);
            
            const color = `rgb(${r}, ${g}, ${b})`;
            
            const segment = L.polyline(
                [this.positionData[i].position, this.positionData[i+1].position],
                {
                    color: color,
                    weight: 3,
                    opacity: 0.7
                }
            );
            
            segments.push(segment);
        }
        
        return segments;
    }
    
    // Create popup content for boat marker
    createBoatPopupContent(latitude, longitude, heading, timestamp) {
        return `
            <strong>PiBoat</strong><br>
            Latitude: ${latitude.toFixed(6)}<br>
            Longitude: ${longitude.toFixed(6)}<br>
            Heading: ${heading || '--'}°<br>
            Time: ${timestamp.toLocaleTimeString()}
        `;
    }
    
    // Create popup content for path points
    createPathPointPopupContent(data) {
        return `
            <strong>Historical Position</strong><br>
            Latitude: ${data.position[0].toFixed(6)}<br>
            Longitude: ${data.position[1].toFixed(6)}<br>
            Heading: ${data.heading || '--'}°<br>
            Time: ${data.timestamp.toLocaleTimeString()}<br>
            Date: ${data.timestamp.toLocaleDateString()}
        `;
    }
    
    // Toggle connection (connect/disconnect)
    async toggleConnection() {
        if (this.connected) {
            this.disconnect();
        } else {
            await this.connect();
        }
    }
    
    // Connect to the relay server
    async connect() {
        if (this.connected) {
            this.consoleLog('Already connected', 'warning');
            return;
        }
        
        // Update UI to show connecting status
        this.updateConnectionStatus('connecting');
        
        // Get the server URL from the input field
        const serverUrl = document.getElementById('server-url').value.trim();
        if (!serverUrl) {
            this.consoleLog('Server URL is required', 'error');
            this.updateConnectionStatus('disconnected');
            return;
        }
        
        try {
            // Connect to the WebSocket server
            const wsUrl = `${serverUrl}/ws/client/${this.clientId}`.replace('http://', 'ws://').replace('https://', 'wss://');
            this.websocket = new WebSocket(wsUrl);
            
            // Set up WebSocket event handlers
            this.websocket.onopen = () => this.handleWebSocketOpen();
            this.websocket.onmessage = (event) => this.handleWebSocketMessage(event);
            this.websocket.onerror = (error) => this.handleWebSocketError(error);
            this.websocket.onclose = () => this.handleWebSocketClose();
            
            this.consoleLog(`Connecting to ${wsUrl}...`, 'info');
        } catch (error) {
            this.consoleLog(`Connection error: ${error.message}`, 'error');
            this.updateConnectionStatus('disconnected');
        }
    }
    
    // Disconnect from the server
    disconnect() {
        // If the connection is open, close it
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.close();
        }
        
        // Reset connection status
        this.connected = false;
        this.selectedDeviceId = null;
        this.updateConnectionStatus('disconnected');
        
        // Reset UI
        document.getElementById('connect-btn').textContent = 'Connect';
        
        // Update device list
        const deviceSelect = document.getElementById('device-select');
        deviceSelect.innerHTML = '<option value="">No devices available</option>';
        deviceSelect.disabled = true;
        
        // Disable controls
        document.getElementById('refresh-devices-btn').disabled = true;
        this.updateCommandControls(false);
        document.getElementById('start-video-btn').disabled = true;
        document.getElementById('stop-video-btn').disabled = true;
        
        // Reset video
        this.stopVideo();
        document.getElementById('video-status').textContent = 'No device connected';
        
        // Reset telemetry display
        document.getElementById('raw-telemetry-data').textContent = 'No telemetry data available';
        
        this.consoleLog('Disconnected from server', 'info');
    }
    
    // Handle WebSocket open event
    handleWebSocketOpen() {
        this.consoleLog('Connected to relay server', 'success');
        this.updateConnectionStatus('connected');
        
        // Enable the refresh devices button when connected
        document.getElementById('refresh-devices-btn').disabled = false;
    }
    
    // Handle WebSocket message event
    async handleWebSocketMessage(event) {
        try {
            const data = JSON.parse(event.data);
            const messageType = data.type || 'unknown';
            
            switch (messageType) {
                case 'ping':
                    await this.handlePing();
                    break;
                case 'devices_list':
                    await this.handleDevicesList(data);
                    break;
                case 'device_connected':
                    await this.handleDeviceConnected(data);
                    break;
                case 'telemetry':
                    await this.handleTelemetry(data);
                    break;
                case 'command_status':
                    await this.handleCommandStatus(data);
                    break;
                case 'webrtc':
                    await this.handleWebRTC(data);
                    break;
                case 'connection_status':
                    await this.handleConnectionStatus(data);
                    break;
                case 'error':
                    this.consoleLog(`Server error: ${data.message}`, 'error');
                    break;
                default:
                    this.consoleLog(`Received unknown message type: ${messageType}`, 'warning');
                    this.consoleLog(`Message content: ${JSON.stringify(data)}`, 'info');
            }
        } catch (error) {
            this.consoleLog(`Error handling WebSocket message: ${error.message}`, 'error');
            console.error('Raw message:', event.data);
        }
    }
    
    // Handle WebSocket error event
    handleWebSocketError(error) {
        this.consoleLog(`WebSocket error: ${error.message}`, 'error');
        this.updateConnectionStatus('disconnected');
    }
    
    // Handle WebSocket close event
    handleWebSocketClose() {
        if (this.connected) {
            this.consoleLog('Connection closed', 'warning');
            this.disconnect();
        }
    }
    
    // Handle ping message
    async handlePing() {
        await this.sendJson({ type: 'pong' });
    }
    
    // Handle devices list message
    async handleDevicesList(data) {
        const devices = data.devices || [];
        this.deviceList = devices;
        
        // Log the devices received
        this.consoleLog(`Received ${devices.length} device(s)`, 'info');
        
        // Update the device dropdown
        updateDeviceList(devices);
        
        // Re-enable the refresh button
        document.getElementById('refresh-devices-btn').disabled = false;
    }
    
    // Connect to the selected device to start receiving telemetry
    async connectToDevice(deviceId) {
        if (!this.connected) {
            this.consoleLog('Cannot connect to device: Not connected to server', 'warning');
            return;
        }
        
        if (!deviceId) {
            this.consoleLog('Cannot connect to device: No device ID provided', 'warning');
            return;
        }
        
        // Update the UI to show we're connecting
        document.getElementById('video-status').textContent = 'Connecting to device...';
        
        try {
            await this.sendJson({
                type: 'connect_device',
                deviceId: deviceId
            });
            
            this.consoleLog(`Connecting to device ${deviceId} for telemetry`, 'info');
            document.getElementById('video-status').textContent = 'Connected (telemetry only)';
            
            // Enable command controls since we're connected to a device now
            this.updateCommandControls(true);
        } catch (error) {
            this.consoleLog(`Error connecting to device: ${error.message}`, 'error');
            document.getElementById('video-status').textContent = 'Connection failed';
        }
    }
    
    // Handle connection status message
    async handleConnectionStatus(data) {
        const deviceId = data.deviceId;
        const status = data.status;
        
        this.consoleLog(`Device ${deviceId} is ${status}`, 'info');
        
        // Refresh device list
        this.refreshDevices();
        
        // If this is the currently selected device, update UI
        if (deviceId === this.selectedDeviceId && status === 'disconnected') {
            this.consoleLog(`Selected device ${deviceId} disconnected`, 'warning');
            document.getElementById('video-status').textContent = 'Device disconnected';
            
            // Disable command and video buttons
            this.updateCommandControls(false);
            
            // Close peer connection if it exists
            if (this.peerConnection) {
                this.peerConnection.close();
                this.peerConnection = null;
            }
        }
    }
    
    // Handle device connected message
    async handleDeviceConnected(data) {
        const deviceId = data.deviceId;
        const device = this.deviceList.find(d => d.id === deviceId);
        
        if (device) {
            this.consoleLog(`Device ${device.name || deviceId} connected successfully`, 'success');
            document.getElementById('video-status').textContent = 'Connected (telemetry only)';
            
            // Enable controls for the connected device
            this.updateCommandControls(true);
            
            // If this device is the one we selected, update UI
            if (deviceId === this.selectedDeviceId) {
                // Enable video controls
                document.getElementById('start-video-btn').disabled = false;
                
                // Clear any previous telemetry data
                this.telemetryData = {};
                this.updateTelemetryUI();
                
                // Make an explicit request for initial telemetry data
                try {
                    await this.sendJson({
                        type: 'get_telemetry',
                        deviceId: deviceId
                    });
                    this.consoleLog("Requested initial telemetry data", 'info');
                } catch (error) {
                    this.consoleLog(`Error requesting telemetry: ${error.message}`, 'error');
                }
            }
        }
    }
    
    // Handle telemetry message
    async handleTelemetry(data) {
        // Store telemetry by type
        const telemetryType = data.subtype || 'unknown';
        this.telemetryData[telemetryType] = data;
        
        // Log telemetry
        this.consoleLog(`Received ${telemetryType} telemetry`, 'telemetry');
        
        // Update UI with telemetry data
        this.updateTelemetryUI();
        
        // Update map if GPS data is available
        if (this.telemetryData.sensor_data && this.telemetryData.sensor_data.data && this.telemetryData.sensor_data.data.gps) {
            const gpsData = this.telemetryData.sensor_data.data.gps;
            this.updateBoatPosition(gpsData.latitude, gpsData.longitude, gpsData.heading);
        }
    }
    
    // Handle command status message
    async handleCommandStatus(data) {
        const commandId = data.command_id;
        const status = data.status;
        const message = data.message || '';
        
        if (status === 'success') {
            this.consoleLog(`Command ${commandId} succeeded: ${message}`, 'success');
        } else if (status === 'error') {
            this.consoleLog(`Command ${commandId} failed: ${message}`, 'error');
        } else {
            this.consoleLog(`Command ${commandId} status: ${status} - ${message}`, 'info');
        }
    }
    
    // Handle WebRTC message
    async handleWebRTC(data) {
        const subtype = data.subtype;
        
        switch (subtype) {
            case 'answer':
                await this.handleWebRTCAnswer(data);
                break;
            case 'ice_candidate':
                await this.handleWebRTCIceCandidate(data);
                break;
            case 'close':
                this.stopVideo();
                break;
            case 'error':
                await this.handleWebRTCError(data);
                break;
            default:
                this.consoleLog(`Received unknown WebRTC message subtype: ${subtype}`, 'warning');
                break;
        }
    }
    
    // Handle WebRTC answer message
    async handleWebRTCAnswer(data) {
        if (!this.peerConnection) {
            this.consoleLog('Received WebRTC answer but no peer connection exists', 'warning');
            return;
        }
        
        try {
            // Set the remote description (the answer from the device)
            const answer = new RTCSessionDescription({
                sdp: data.sdp,
                type: data.sdpType || 'answer'
            });
            
            await this.peerConnection.setRemoteDescription(answer);
            this.consoleLog('WebRTC answer processed', 'success');
        } catch (error) {
            this.consoleLog(`Error processing WebRTC answer: ${error.message}`, 'error');
        }
    }
    
    // Handle WebRTC ICE candidate message
    async handleWebRTCIceCandidate(data) {
        if (!this.peerConnection) {
            return;
        }
        
        try {
            const candidate = data.candidate;
            if (candidate) {
                await this.peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
            }
        } catch (error) {
            this.consoleLog(`Error adding ICE candidate: ${error.message}`, 'error');
        }
    }
    
    // Handle WebRTC error message
    async handleWebRTCError(data) {
        const errorType = data.error || 'unknown';
        const errorMessage = data.message || 'Unknown WebRTC error';
        
        this.consoleLog(`WebRTC error: ${errorType} - ${errorMessage}`, 'error');
        
        // Update UI
        document.getElementById('video-status').textContent = `Video error: ${errorType}`;
        
        // Handle specific error types
        if (errorType === 'codec_incompatible' || errorType === 'codec_negotiation_failed') {
            this.consoleLog('Video codec compatibility issue. Try with a different browser or device.', 'error');
            // Could attempt a fallback strategy here
        }
        
        // Close the connection if it exists
        if (this.peerConnection) {
            this.peerConnection.close();
            this.peerConnection = null;
            
            // Re-enable the start button
            document.getElementById('start-video-btn').disabled = false;
            document.getElementById('stop-video-btn').disabled = true;
        }
    }
    
    // Update telemetry UI with the latest data
    updateTelemetryUI() {
        // Format the telemetry data as JSON with proper indentation
        const formattedJson = JSON.stringify(this.telemetryData, null, 2);
        
        // Update the raw telemetry data display
        const rawTelemetryElement = document.getElementById('raw-telemetry-data');
        if (rawTelemetryElement) {
            rawTelemetryElement.textContent = formattedJson || 'No telemetry data available';
        } else {
            this.consoleLog('Raw telemetry element not found in DOM', 'warning');
        }
        
        // Update map if GPS data is available
        if (this.telemetryData.sensor_data && this.telemetryData.sensor_data.data && this.telemetryData.sensor_data.data.gps) {
            const gpsData = this.telemetryData.sensor_data.data.gps;
            this.updateBoatPosition(gpsData.latitude, gpsData.longitude, gpsData.heading);
        }
    }
    
    // Enable or disable command controls based on device selection
    updateCommandControls(enabled) {
        // Update the controls
        document.getElementById('stop-btn').disabled = !enabled;
        document.getElementById('rudder-position').disabled = !enabled;
        document.getElementById('set-rudder-btn').disabled = !enabled;
        document.getElementById('throttle-value').disabled = !enabled;
        document.getElementById('set-throttle-btn').disabled = !enabled;
    }

    // Select a device from the list
    selectDevice(deviceId) {
        this.selectedDeviceId = deviceId;
        const device = this.deviceList.find(d => d.id === deviceId);
        
        if (device) {
            // Instead of updating the list item styling, set the dropdown value
            const deviceSelect = document.getElementById('device-select');
            deviceSelect.value = deviceId;
            
            // Enable controls for the selected device
            updateUIForDeviceSelection(device);
            
            this.consoleLog(`Selected device: ${device.name || device.id}`, 'info');
            
            // Clear any existing telemetry data
            this.telemetryData = {};
            this.updateTelemetryUI();
            
            // Automatically connect to the device to start telemetry
            if (this.connected) {
                // First connect to the device
                this.connectToDevice(deviceId).then(() => {
                    // Then request initial telemetry data
                    setTimeout(() => {
                        this.requestTelemetryData();
                    }, 500); // Small delay to ensure connection is established
                });
            }
        }
    }
    
    // Send emergency stop command to the boat
    async sendStopCommand() {
        if (!this.connected || !this.selectedDeviceId) return;
        
        try {
            // Increment command counter
            this.commandCounter++;
            
            // Create command object
            const command = {
                type: 'command',
                command: 'stop',
                deviceId: this.selectedDeviceId,
                command_id: `${this.clientId}-${this.commandCounter}-${Date.now()}`,
                data: {}  // Stop command doesn't need additional data
            };
            
            // Send command
            await this.sendJson(command);
            this.consoleLog('Sent EMERGENCY STOP command', 'warning');
        } catch (error) {
            this.consoleLog(`Error sending stop command: ${error.message}`, 'error');
        }
    }
    
    // Send rudder position command to the boat
    async sendRudderCommand() {
        if (!this.connected || !this.selectedDeviceId) return;
        
        try {
            // Get rudder position value
            const rudderPosition = parseInt(document.getElementById('rudder-position').value, 10);
            
            // Increment command counter
            this.commandCounter++;
            
            // Create command object
            const command = {
                type: 'command',
                command: 'set_rudder',
                deviceId: this.selectedDeviceId,
                command_id: `${this.clientId}-${this.commandCounter}-${Date.now()}`,
                data: {
                    position: rudderPosition
                }
            };
            
            // Send command
            await this.sendJson(command);
            this.consoleLog(`Sent rudder position command: ${rudderPosition}%`, 'info');
        } catch (error) {
            this.consoleLog(`Error sending rudder command: ${error.message}`, 'error');
        }
    }
    
    // Send throttle command to the boat
    async sendThrottleCommand() {
        if (!this.connected || !this.selectedDeviceId) return;
        
        try {
            // Get throttle value
            const throttleValue = parseInt(document.getElementById('throttle-value').value, 10);
            
            // Increment command counter
            this.commandCounter++;
            
            // Create command object
            const command = {
                type: 'command',
                command: 'set_throttle',
                deviceId: this.selectedDeviceId,
                command_id: `${this.clientId}-${this.commandCounter}-${Date.now()}`,
                data: {
                    throttle: throttleValue
                }
            };
            
            // Send command
            await this.sendJson(command);
            this.consoleLog(`Sent throttle command: ${throttleValue}%`, 'info');
        } catch (error) {
            this.consoleLog(`Error sending throttle command: ${error.message}`, 'error');
        }
    }
    
    // Request devices list from the server
    async refreshDevices() {
        if (!this.connected) {
            this.consoleLog('Not connected to server', 'warning');
            return;
        }
        
        document.getElementById('refresh-devices-btn').disabled = true;
        this.consoleLog("Refreshing device list...", 'info');
        
        try {
            await this.sendJson({ type: 'devices_list' });
            this.consoleLog('Requested devices list', 'info');
            
            // Enable the button after a timeout even if we don't get a response
            setTimeout(() => {
                document.getElementById('refresh-devices-btn').disabled = false;
            }, 5000);
        } catch (error) {
            this.consoleLog(`Error requesting devices list: ${error.message}`, 'error');
            document.getElementById('refresh-devices-btn').disabled = false;
        }
    }
    
    // Start video stream
    async startVideo() {
        if (!this.connected || !this.selectedDeviceId) return;
        
        try {
            this.consoleLog(`Initializing video connection to device ${this.selectedDeviceId}`, 'info');
            document.getElementById('video-status').textContent = 'Initializing video...';
            
            // Close existing connection if any
            if (this.peerConnection) {
                this.peerConnection.close();
            }
            
            // Create a new peer connection
            this.peerConnection = new RTCPeerConnection({
                iceServers: [
                    { urls: 'stun:stun.l.google.com:19302' }
                ]
            });
            
            // Set up video receiver
            this.peerConnection.ontrack = (event) => {
                const videoElem = document.getElementById('remote-video');
                if (videoElem.srcObject !== event.streams[0]) {
                    videoElem.srcObject = event.streams[0];
                    this.consoleLog('Received video stream', 'success');
                    document.getElementById('video-status').textContent = 'Video stream active';
                    document.getElementById('stop-video-btn').disabled = false;
                }
            };
            
            // Set up ICE candidate handling
            this.peerConnection.onicecandidate = (event) => {
                if (event.candidate) {
                    this.sendJson({
                        type: 'webrtc',
                        subtype: 'ice_candidate',
                        deviceId: this.selectedDeviceId,
                        clientId: this.clientId,
                        candidate: event.candidate.toJSON()
                    });
                }
            };
            
            // Add connection state change handler
            this.peerConnection.onconnectionstatechange = () => {
                this.consoleLog(`WebRTC connection state: ${this.peerConnection.connectionState}`, 'info');
                if (this.peerConnection.connectionState === 'failed' || 
                    this.peerConnection.connectionState === 'closed') {
                    this.consoleLog('WebRTC connection failed or closed', 'error');
                    document.getElementById('video-status').textContent = 'Video connection failed';
                }
            };
            
            // Add a transceiver to receive video (IMPORTANT: this specifies we want to receive video)
            const transceiver = this.peerConnection.addTransceiver('video', {
                direction: 'recvonly'
            });
            
            // Create and send offer
            const offer = await this.peerConnection.createOffer({
                offerToReceiveVideo: true, // Explicitly state we want to receive video
                offerToReceiveAudio: false // We don't need audio
            });
            
            // Ensure SDP contains appropriate video codecs by modifying the SDP directly
            // This is more reliable than the codec parameter which isn't supported in all browsers
            let sdpLines = offer.sdp.split('\n');
            let videoSectionIndex = sdpLines.findIndex(line => line.startsWith('m=video'));
            
            if (videoSectionIndex !== -1) {
                // Ensure H.264 and VP8 are at the beginning of the codec list to prefer them
                // This modifies the payload ordering in the m=video line
                let videoLine = sdpLines[videoSectionIndex];
                let videoLineParts = videoLine.split(' ');
                
                // Find payload types for H.264 and VP8
                let h264Payload = null;
                let vp8Payload = null;
                
                for (let i = videoSectionIndex + 1; i < sdpLines.length; i++) {
                    if (sdpLines[i].startsWith('m=')) break; // Stop at next section
                    
                    if (sdpLines[i].includes('H264')) {
                        h264Payload = sdpLines[i].split(':')[0].split(' ')[1];
                    } else if (sdpLines[i].includes('VP8')) {
                        vp8Payload = sdpLines[i].split(':')[0].split(' ')[1];
                    }
                }
                
                // Reorder payload types in the m=video line to prefer H.264 and VP8
                if (h264Payload || vp8Payload) {
                    let newPayloadOrder = [h264Payload, vp8Payload].filter(Boolean);
                    let otherPayloads = videoLineParts.slice(3).filter(p => !newPayloadOrder.includes(p));
                    let newVideoLine = `${videoLineParts[0]} ${videoLineParts[1]} ${videoLineParts[2]} ${newPayloadOrder.join(' ')} ${otherPayloads.join(' ')}`;
                    sdpLines[videoSectionIndex] = newVideoLine.trim();
                }
            }
            
            // Apply the modified SDP
            offer.sdp = sdpLines.join('\n');
            
            // Ensure SDP has at least one video codec entry that the simulated device recognizes
            if (!offer.sdp.includes('VP8') && !offer.sdp.includes('H264')) {
                // If neither VP8 nor H264 is found, add explicit VP8 entry
                // Find the end of video section to add our codec
                let videoSectionEnd = sdpLines.length;
                for (let i = videoSectionIndex + 1; i < sdpLines.length; i++) {
                    if (sdpLines[i].startsWith('m=')) {
                        videoSectionEnd = i;
                        break;
                    }
                }
                
                // Add VP8 codec entry - format is standard WebRTC format
                let payloadType = 96; // Standard VP8 payload type
                let insertIndex = videoSectionEnd;
                sdpLines.splice(insertIndex, 0, `a=rtpmap:${payloadType} VP8/90000`);
                
                // Also add VP8 to the m=video line
                let videoLine = sdpLines[videoSectionIndex];
                sdpLines[videoSectionIndex] = `${videoLine} ${payloadType}`;
                
                // Rebuild the SDP
                offer.sdp = sdpLines.join('\n');
                this.consoleLog('Added VP8 codec to offer', 'info');
            }

            // Log the modified SDP for debugging
            this.consoleLog('Created offer with prioritized video codecs', 'info');
            
            await this.peerConnection.setLocalDescription(offer);
            
            // Generate a session ID
            const sessionId = `${this.clientId}-${this.selectedDeviceId}-${Date.now()}`;
            
            // Send the offer
            await this.sendJson({
                type: 'webrtc',
                subtype: 'offer',
                deviceId: this.selectedDeviceId,
                clientId: this.clientId,
                sdp: this.peerConnection.localDescription.sdp,
                sdpType: this.peerConnection.localDescription.type,
                sessionId: sessionId
            });
            
            document.getElementById('video-status').textContent = 'Connecting video...';
            this.consoleLog('Sent WebRTC offer to device', 'info');
            
            // Set a timeout to detect if connection fails
            setTimeout(() => {
                if (this.peerConnection && 
                    (this.peerConnection.connectionState === 'new' || 
                     this.peerConnection.connectionState === 'connecting')) {
                    this.consoleLog('WebRTC connection taking too long, may have failed', 'warning');
                    document.getElementById('video-status').textContent = 'Video connection timeout';
                }
            }, 10000); // 10 second timeout
            
        } catch (error) {
            this.consoleLog(`Error starting video: ${error.message}`, 'error');
            document.getElementById('video-status').textContent = 'Video setup failed';
        }
    }
    
    // Stop video stream
    stopVideo() {
        try {
            if (this.peerConnection) {
                // Send close message to device
                if (this.connected && this.selectedDeviceId) {
                    this.sendJson({
                        type: 'webrtc',
                        subtype: 'close',
                        deviceId: this.selectedDeviceId
                    });
                }
                
                // Close the peer connection
                this.peerConnection.close();
                this.peerConnection = null;
                
                // Update UI
                const videoElem = document.getElementById('remote-video');
                if (videoElem.srcObject) {
                    const tracks = videoElem.srcObject.getTracks();
                    tracks.forEach(track => track.stop());
                    videoElem.srcObject = null;
                }
                
                document.getElementById('video-status').textContent = 'Connected (telemetry only)';
                document.getElementById('stop-video-btn').disabled = true;
                document.getElementById('start-video-btn').disabled = false;
                
                this.consoleLog('Video stream stopped', 'info');
            }
        } catch (error) {
            this.consoleLog(`Error stopping video: ${error.message}`, 'error');
        }
    }
    
    // Send JSON data to the server
    async sendJson(data) {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            await this.websocket.send(JSON.stringify(data));
        } else {
            throw new Error('WebSocket not connected');
        }
    }
    
    // Update connection status
    updateConnectionStatus(status) {
        const statusIcon = document.getElementById('connection-icon');
        const statusText = document.getElementById('connection-text');
        const connectButton = document.getElementById('connect-btn');
        const refreshBtn = document.getElementById('refresh-devices-btn');
        
        if (!statusIcon || !statusText) return;
        
        // Remove existing classes
        statusIcon.classList.remove('disconnected', 'connecting', 'connected');
        
        switch(status) {
            case 'disconnected':
                statusIcon.classList.add('disconnected');
                statusText.textContent = 'Disconnected';
                connectButton.textContent = 'Connect';
                refreshBtn.disabled = true;
                this.connected = false;
                break;
            case 'connecting':
                statusIcon.classList.add('connecting');
                statusText.textContent = 'Connecting...';
                connectButton.textContent = 'Cancel';
                refreshBtn.disabled = true;
                break;
            case 'connected':
                statusIcon.classList.add('connected');
                statusText.textContent = 'Connected';
                connectButton.textContent = 'Disconnect';
                refreshBtn.disabled = false; // Enable refresh button when connected
                this.connected = true;
                // When connected, immediately request the device list
                this.refreshDevices();
                break;
        }
    }
    
    // Log message to console
    consoleLog(message, type = 'info') {
        const consoleOutput = document.getElementById('console-output');
        const timestamp = new Date().toLocaleTimeString();
        
        const logEntry = document.createElement('div');
        logEntry.className = type;
        logEntry.textContent = `[${timestamp}] ${message}`;
        
        consoleOutput.appendChild(logEntry);
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
        
        // Also log to browser console
        console.log(`[${type}] ${message}`);
        
        // Send log to server if enabled
        if (this.logToServer) {
            this.sendLogToServer(message, type);
        }
    }
    
    // Send log to server
    async sendLogToServer(message, type) {
        try {
            const response = await fetch('/api/log', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: message,
                    type: type,
                    client_id: this.clientId,
                    device_id: this.selectedDeviceId || 'none',
                    timestamp: new Date().toISOString()
                })
            });
            
            if (!response.ok) {
                console.error('Failed to send log to server');
            }
        } catch (error) {
            // Don't log this error to avoid infinite loop
            console.error('Error sending log to server:', error);
        }
    }
    
    // Clear console
    clearConsole() {
        document.getElementById('console-output').innerHTML = '';
    }
    
    // Clear the boat path history
    clearBoatPath() {
        this.previousPositions = [];
        this.positionData = [];
        if (this.boatPath) {
            this.boatPath.clearLayers();
            this.consoleLog('Boat path cleared', 'info');
        }
    }
    
    // Handle window resize to update map
    handleMapResize() {
        if (this.map) {
            // Need to call invalidateSize when the map container size changes
            this.map.invalidateSize();
            this.consoleLog('Map resized', 'info');
        }
    }
    
    // Toggle waypoint mode on/off
    toggleWaypointMode() {
        this.waypointsEnabled = !this.waypointsEnabled;
        
        // Update the button text and style
        const btn = document.querySelector('.waypoint-control button');
        if (btn) {
            if (this.waypointsEnabled) {
                btn.textContent = 'Cancel Waypoints';
                btn.classList.add('active');
                this.map.getContainer().style.cursor = 'crosshair';
                this.consoleLog('Waypoint mode enabled - click on the map to add waypoints', 'info');
            } else {
                btn.textContent = 'Set Waypoints';
                btn.classList.remove('active');
                this.map.getContainer().style.cursor = '';
                this.consoleLog('Waypoint mode disabled', 'info');
            }
        }
    }
    
    // Add a waypoint to the map
    addWaypoint(lat, lng) {
        if (!this.map) return;
        
        try {
            // Create waypoint object
            const waypoint = {
                latitude: parseFloat(lat.toFixed(6)),
                longitude: parseFloat(lng.toFixed(6))
            };
            
            // Add to waypoints array
            this.waypoints.push(waypoint);
            
            // Create waypoint marker
            const waypointIcon = L.divIcon({
                className: 'waypoint-marker',
                html: `<div class="waypoint-number">${this.waypoints.length}</div>`,
                iconSize: [24, 24],
                iconAnchor: [12, 12]
            });
            
            const marker = L.marker([lat, lng], {
                icon: waypointIcon,
                title: `Waypoint ${this.waypoints.length}`
            }).addTo(this.map);
            
            // Add popup with waypoint info and delete button
            const popupContent = `
                <div class="waypoint-popup">
                    <h3>Waypoint ${this.waypoints.length}</h3>
                    <p>Latitude: ${waypoint.latitude}</p>
                    <p>Longitude: ${waypoint.longitude}</p>
                    <button class="delete-waypoint-btn" data-index="${this.waypoints.length - 1}">Delete</button>
                </div>
            `;
            
            marker.bindPopup(popupContent);
            
            // Add click handler for delete button
            marker.on('popupopen', () => {
                const deleteBtn = document.querySelector('.delete-waypoint-btn');
                if (deleteBtn) {
                    deleteBtn.addEventListener('click', (e) => {
                        const index = parseInt(e.target.dataset.index, 10);
                        this.removeWaypoint(index);
                        this.map.closePopup();
                    });
                }
            });
            
            // Add to markers array
            this.waypointMarkers.push(marker);
            
            // Update waypoint path
            this.updateWaypointPath();
            
            // Enable send waypoints button if there are waypoints
            this.updateSendWaypointsButton();
            
            this.consoleLog(`Added waypoint ${this.waypoints.length}: ${waypoint.latitude}, ${waypoint.longitude}`, 'info');
        } catch (error) {
            this.consoleLog(`Error adding waypoint: ${error.message}`, 'error');
        }
    }
    
    // Remove a waypoint from the map
    removeWaypoint(index) {
        if (index < 0 || index >= this.waypoints.length) return;
        
        try {
            // Remove the waypoint and marker
            this.waypoints.splice(index, 1);
            
            // Remove all markers and recreate them (to update numbering)
            this.clearWaypointMarkers();
            
            // Recreate all markers with updated numbers
            this.waypoints.forEach((wp, i) => {
                const waypointIcon = L.divIcon({
                    className: 'waypoint-marker',
                    html: `<div class="waypoint-number">${i + 1}</div>`,
                    iconSize: [24, 24],
                    iconAnchor: [12, 12]
                });
                
                const marker = L.marker([wp.latitude, wp.longitude], {
                    icon: waypointIcon,
                    title: `Waypoint ${i + 1}`
                }).addTo(this.map);
                
                // Add popup with waypoint info and delete button
                const popupContent = `
                    <div class="waypoint-popup">
                        <h3>Waypoint ${i + 1}</h3>
                        <p>Latitude: ${wp.latitude}</p>
                        <p>Longitude: ${wp.longitude}</p>
                        <button class="delete-waypoint-btn" data-index="${i}">Delete</button>
                    </div>
                `;
                
                marker.bindPopup(popupContent);
                
                // Add click handler for delete button
                marker.on('popupopen', () => {
                    const deleteBtn = document.querySelector('.delete-waypoint-btn');
                    if (deleteBtn) {
                        deleteBtn.addEventListener('click', (e) => {
                            const idx = parseInt(e.target.dataset.index, 10);
                            this.removeWaypoint(idx);
                            this.map.closePopup();
                        });
                    }
                });
                
                this.waypointMarkers.push(marker);
            });
            
            // Update waypoint path
            this.updateWaypointPath();
            
            // Update send waypoints button
            this.updateSendWaypointsButton();
            
            this.consoleLog(`Removed waypoint ${index + 1}`, 'info');
        } catch (error) {
            this.consoleLog(`Error removing waypoint: ${error.message}`, 'error');
        }
    }
    
    // Clear all waypoint markers from the map
    clearWaypointMarkers() {
        // Remove all existing markers
        this.waypointMarkers.forEach(marker => {
            marker.remove();
        });
        
        // Clear the markers array
        this.waypointMarkers = [];
    }
    
    // Clear all waypoints
    clearWaypoints() {
        // Clear the waypoints array
        this.waypoints = [];
        
        // Clear the markers
        this.clearWaypointMarkers();
        
        // Clear the path
        if (this.waypointPath) {
            this.waypointPath.clearLayers();
        }
        
        // Update send waypoints button
        this.updateSendWaypointsButton();
        
        this.consoleLog('Cleared all waypoints', 'info');
    }
    
    // Update the path connecting waypoints
    updateWaypointPath() {
        if (!this.map) return;
        
        try {
            // Clear existing path
            if (this.waypointPath) {
                this.waypointPath.clearLayers();
            }
            
            if (this.waypoints.length > 1) {
                // Create waypoint path coordinates
                const pathCoords = this.waypoints.map(wp => [wp.latitude, wp.longitude]);
                
                // Create a polyline for the path
                const polyline = L.polyline(pathCoords, {
                    color: '#00FF00',
                    weight: 3,
                    opacity: 0.7,
                    dashArray: '10, 5',
                }).addTo(this.map);
                
                // Add to feature group
                this.waypointPath.addLayer(polyline);
            }
        } catch (error) {
            this.consoleLog(`Error updating waypoint path: ${error.message}`, 'error');
        }
    }
    
    // Update the send waypoints button
    updateSendWaypointsButton() {
        const btn = document.querySelector('.send-waypoints-control button');
        if (btn) {
            btn.disabled = this.waypoints.length === 0 || !this.connected || !this.selectedDeviceId;
        }
    }
    
    // Send waypoints command to the device
    async sendWaypointsCommand() {
        if (!this.connected || !this.selectedDeviceId || this.waypoints.length === 0) return;
        
        try {
            // Increment command counter
            this.commandCounter++;
            
            // Create command object
            let command;
            
            if (this.waypoints.length === 1) {
                // Single waypoint
                command = {
                    type: 'command',
                    command: 'set_waypoint',
                    deviceId: this.selectedDeviceId,
                    command_id: `${this.clientId}-${this.commandCounter}-${Date.now()}`,
                    data: {
                        latitude: this.waypoints[0].latitude,
                        longitude: this.waypoints[0].longitude,
                        mode: 'autonomous'
                    }
                };
                
                this.consoleLog(`Sending single waypoint command: ${this.waypoints[0].latitude}, ${this.waypoints[0].longitude}`, 'info');
            } else {
                // Multiple waypoints
                command = {
                    type: 'command',
                    command: 'set_waypoints',
                    deviceId: this.selectedDeviceId,
                    command_id: `${this.clientId}-${this.commandCounter}-${Date.now()}`,
                    data: {
                        waypoints: this.waypoints,
                        mode: 'autonomous'
                    }
                };
                
                this.consoleLog(`Sending ${this.waypoints.length} waypoints command`, 'info');
            }
            
            // Send command
            await this.sendJson(command);
            
            // Disable waypoint mode after sending
            if (this.waypointsEnabled) {
                this.toggleWaypointMode();
            }
        } catch (error) {
            this.consoleLog(`Error sending waypoints command: ${error.message}`, 'error');
        }
    }

    // Request telemetry data from the selected device
    async requestTelemetryData() {
        if (!this.connected || !this.selectedDeviceId) {
            this.consoleLog('Cannot request telemetry: No device selected or not connected', 'warning');
            return;
        }
        
        try {
            await this.sendJson({
                type: 'get_telemetry',
                deviceId: this.selectedDeviceId
            });
            this.consoleLog('Requested telemetry data', 'info');
        } catch (error) {
            this.consoleLog(`Error requesting telemetry: ${error.message}`, 'error');
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Initialize client
    window.piBoatClient = new PiBoatClient();
    
    // Make sure we run setupDeviceSelection to wire up the dropdown event listener
    setupDeviceSelection();
    
    // Add an explicit event listener for the refresh button
    document.getElementById('refresh-devices-btn').addEventListener('click', () => {
        if (window.piBoatClient) {
            window.piBoatClient.refreshDevices();
        }
    });
});

// Update the updateDeviceList function to work with the PiBoatClient
function updateDeviceList(devices) {
    const deviceSelect = document.getElementById('device-select');
    
    // Clear current options
    deviceSelect.innerHTML = '';
    
    if (!devices || devices.length === 0) {
        // If no devices, show "No devices" option
        const option = document.createElement('option');
        option.value = '';
        option.text = "No devices available";
        deviceSelect.appendChild(option);
        deviceSelect.disabled = true;
        return;
    }
    
    // Add initial "Select a device" option
    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.text = "Select a device...";
    deviceSelect.appendChild(defaultOption);
    deviceSelect.disabled = false;
    
    // Add devices to the dropdown
    devices.forEach(device => {
        const option = document.createElement('option');
        option.value = device.id;
        option.text = `${device.name || device.id} (${device.type || 'Unknown'})`;
        deviceSelect.appendChild(option);
    });
    
    // If there's a currently selected device in PiBoatClient, select it
    if (window.piBoatClient && window.piBoatClient.selectedDeviceId) {
        const deviceExists = Array.from(deviceSelect.options).some(option => {
            return option.value === window.piBoatClient.selectedDeviceId;
        });
        
        if (deviceExists) {
            deviceSelect.value = window.piBoatClient.selectedDeviceId;
        } else {
            // Previously selected device no longer exists
            window.piBoatClient.selectedDeviceId = null;
            updateUIForDeviceSelection(null);
        }
    }
}

// Fix the setupDeviceSelection function
function setupDeviceSelection() {
    const deviceSelect = document.getElementById('device-select');
    
    deviceSelect.addEventListener('change', (e) => {
        const selectedOption = deviceSelect.options[deviceSelect.selectedIndex];
        
        if (!selectedOption.value) {
            // "No devices" or "Select a device" option
            updateUIForDeviceSelection(null);
            if (window.piBoatClient) {
                window.piBoatClient.selectedDeviceId = null;
                document.getElementById('video-status').textContent = 'No device connected';
            }
            return;
        }
        
        const deviceId = selectedOption.value;
        if (window.piBoatClient) {
            // This will also automatically connect to the device
            window.piBoatClient.selectDevice(deviceId);
        }
    });
}

// Add this function if it doesn't exist yet
function updateUIForDeviceSelection(device) {
    const controls = document.querySelectorAll('.command-controls button, .command-controls input[type="range"]');
    const videoControls = document.querySelectorAll('.video-controls button');
    
    if (!device) {
        // No device selected, disable controls
        controls.forEach(control => control.disabled = true);
        videoControls.forEach(control => control.disabled = true);
        document.getElementById('video-status').textContent = 'No device connected';
        return;
    }
    
    // Enable controls
    controls.forEach(control => control.disabled = false);
    videoControls.forEach(control => control.disabled = false);
    document.getElementById('video-status').textContent = `Connected to ${device.name}`;
} 
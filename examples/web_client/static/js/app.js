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
        
        // Initialize the application
        this.initEventListeners();
        this.consoleLog('Client initialized', 'info');
    }
    
    // Initialize all event listeners
    initEventListeners() {
        // Connection
        document.getElementById('connect-btn').addEventListener('click', () => this.toggleConnection());
        
        // Devices
        document.getElementById('refresh-devices-btn').addEventListener('click', () => this.requestDevicesList());
        
        // Commands
        document.getElementById('command-name').addEventListener('change', (e) => this.updateCommandTemplate(e.target.value));
        document.getElementById('send-command-btn').addEventListener('click', () => this.sendCommand());
        
        // Video
        document.getElementById('start-video-btn').addEventListener('click', () => this.startVideo());
        document.getElementById('stop-video-btn').addEventListener('click', () => this.stopVideo());
        
        // Console
        document.getElementById('clear-console-btn').addEventListener('click', () => this.clearConsole());
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
        try {
            this.serverUrl = document.getElementById('server-url').value;
            const wsUrl = `${this.serverUrl}/ws/client/${this.clientId}`.replace('http://', 'ws://').replace('https://', 'wss://');
            
            this.updateConnectionStatus('connecting');
            this.consoleLog(`Connecting to ${wsUrl}...`, 'info');
            
            this.websocket = new WebSocket(wsUrl);
            
            // Set up event handlers
            this.websocket.onopen = () => this.handleWebSocketOpen();
            this.websocket.onmessage = (event) => this.handleWebSocketMessage(event);
            this.websocket.onerror = (error) => this.handleWebSocketError(error);
            this.websocket.onclose = () => this.handleWebSocketClose();
        } catch (error) {
            this.consoleLog(`Connection error: ${error.message}`, 'error');
            this.updateConnectionStatus('disconnected');
        }
    }
    
    // Disconnect from the relay server
    disconnect() {
        if (this.websocket) {
            this.websocket.close();
        }
        
        if (this.peerConnection) {
            this.peerConnection.close();
            this.peerConnection = null;
        }
        
        this.connected = false;
        this.updateConnectionStatus('disconnected');
        this.consoleLog('Disconnected from server', 'info');
        
        // Disable buttons
        document.getElementById('refresh-devices-btn').disabled = true;
        document.getElementById('command-name').disabled = true;
        document.getElementById('command-data').disabled = true;
        document.getElementById('send-command-btn').disabled = true;
        document.getElementById('start-video-btn').disabled = true;
        document.getElementById('stop-video-btn').disabled = true;
        
        // Update UI
        document.getElementById('video-status').textContent = 'No device connected';
        document.getElementById('connect-btn').textContent = 'Connect';
    }
    
    // Handle WebSocket open event
    handleWebSocketOpen() {
        this.connected = true;
        this.updateConnectionStatus('connected');
        this.consoleLog('Connected to server', 'success');
        document.getElementById('connect-btn').textContent = 'Disconnect';
        document.getElementById('refresh-devices-btn').disabled = false;
        
        // Request device list
        this.requestDevicesList();
    }
    
    // Handle WebSocket message event
    async handleWebSocketMessage(event) {
        try {
            const data = JSON.parse(event.data);
            const messageType = data.type;
            
            this.consoleLog(`Received ${messageType} message`, 'info');
            
            switch (messageType) {
                case 'ping':
                    await this.handlePing();
                    break;
                case 'devices_list':
                    await this.handleDevicesList(data);
                    break;
                case 'connection_status':
                    await this.handleConnectionStatus(data);
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
                case 'error':
                    this.consoleLog(`Server error: ${data.message}`, 'error');
                    break;
                default:
                    this.consoleLog(`Unknown message type: ${messageType}`, 'warning');
            }
        } catch (error) {
            this.consoleLog(`Error handling message: ${error.message}`, 'error');
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
        
        const deviceListElement = document.getElementById('device-list');
        deviceListElement.innerHTML = '';
        
        if (devices.length === 0) {
            const emptyItem = document.createElement('li');
            emptyItem.textContent = 'No devices available';
            emptyItem.className = 'empty-message';
            deviceListElement.appendChild(emptyItem);
        } else {
            devices.forEach(device => {
                const deviceItem = document.createElement('li');
                const isConnected = device.connected ? 'Connected' : 'Disconnected';
                deviceItem.textContent = `${device.id} (${isConnected})`;
                deviceItem.dataset.deviceId = device.id;
                
                if (device.id === this.selectedDeviceId) {
                    deviceItem.className = 'selected';
                }
                
                if (!device.connected) {
                    deviceItem.style.opacity = '0.5';
                }
                
                deviceItem.addEventListener('click', () => {
                    if (device.connected) {
                        this.selectDevice(device.id);
                    }
                });
                
                deviceListElement.appendChild(deviceItem);
            });
            
            this.consoleLog(`Received ${devices.length} devices`, 'info');
        }
    }
    
    // Handle connection status message
    async handleConnectionStatus(data) {
        const deviceId = data.deviceId;
        const status = data.status;
        
        this.consoleLog(`Device ${deviceId} is ${status}`, 'info');
        
        // Refresh device list
        this.requestDevicesList();
        
        // If this is the currently selected device, update UI
        if (deviceId === this.selectedDeviceId && status === 'disconnected') {
            this.consoleLog(`Selected device ${deviceId} disconnected`, 'warning');
            document.getElementById('video-status').textContent = 'Device disconnected';
            
            // Disable command and video buttons
            document.getElementById('command-name').disabled = true;
            document.getElementById('command-data').disabled = true;
            document.getElementById('send-command-btn').disabled = true;
            document.getElementById('start-video-btn').disabled = true;
            document.getElementById('stop-video-btn').disabled = true;
            
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
        const status = data.status || 'connected';
        
        this.consoleLog(`Device ${deviceId} connection status: ${status}`, 'info');
        
        if (status === 'connected') {
            // Update UI to show that telemetry is now active
            document.getElementById('video-status').textContent = 'Connected (telemetry only)';
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
    
    // Update telemetry UI with the latest data
    updateTelemetryUI() {
        // GPS data
        if (this.telemetryData.sensor_data && this.telemetryData.sensor_data.data) {
            const sensorData = this.telemetryData.sensor_data.data;
            
            // GPS
            if (sensorData.gps) {
                document.getElementById('gps-lat').textContent = `Latitude: ${sensorData.gps.latitude || '--'}`;
                document.getElementById('gps-lon').textContent = `Longitude: ${sensorData.gps.longitude || '--'}`;
                document.getElementById('gps-heading').textContent = `Heading: ${sensorData.gps.heading || '--'}°`;
                document.getElementById('gps-speed').textContent = `Speed: ${sensorData.gps.speed || '--'} knots`;
            }
            
            // System status
            if (sensorData.status) {
                document.getElementById('system-status').textContent = `Status: ${sensorData.status}`;
            }
            
            // Battery
            if (sensorData.battery) {
                document.getElementById('battery-level').textContent = `Battery: ${sensorData.battery.level || '--'}%`;
            }
            
            // System data
            if (sensorData.system) {
                document.getElementById('cpu-temp').textContent = `CPU Temp: ${sensorData.system.cpu_temp || '--'}°C`;
                document.getElementById('signal-strength').textContent = `Signal: ${sensorData.system.signal_strength || '--'} dBm`;
            }
            
            // Environment data
            if (sensorData.environment) {
                document.getElementById('water-temp').textContent = `Water Temp: ${sensorData.environment.water_temp || '--'}°C`;
                document.getElementById('air-temp').textContent = `Air Temp: ${sensorData.environment.air_temp || '--'}°C`;
                document.getElementById('air-pressure').textContent = `Pressure: ${sensorData.environment.air_pressure || '--'} hPa`;
                document.getElementById('humidity').textContent = `Humidity: ${sensorData.environment.humidity || '--'}%`;
            }
        }
    }
    
    // Select a device
    selectDevice(deviceId) {
        this.selectedDeviceId = deviceId;
        this.consoleLog(`Selected device ${deviceId}`, 'info');
        
        // Update UI
        const deviceItems = document.querySelectorAll('#device-list li');
        deviceItems.forEach(item => {
            if (item.dataset.deviceId === deviceId) {
                item.className = 'selected';
            } else {
                item.className = '';
            }
        });
        
        // Enable command buttons
        document.getElementById('command-name').disabled = false;
        document.getElementById('command-data').disabled = false;
        document.getElementById('send-command-btn').disabled = false;
        document.getElementById('start-video-btn').disabled = false;
        
        // Update video status
        document.getElementById('video-status').textContent = 'Video not started';
        
        // Set default command template
        this.updateCommandTemplate('get_status');

        // Connect to the device to start receiving telemetry
        this.connectToDevice(deviceId);
    }
    
    // Connect to the selected device to start receiving telemetry
    async connectToDevice(deviceId) {
        if (!this.connected || !deviceId) return;
        
        try {
            await this.sendJson({
                type: 'connect_device',
                deviceId: deviceId
            });
            
            this.consoleLog(`Connecting to device ${deviceId} for telemetry`, 'info');
            document.getElementById('video-status').textContent = 'Connected (telemetry only)';
        } catch (error) {
            this.consoleLog(`Error connecting to device: ${error.message}`, 'error');
        }
    }
    
    // Update command template based on selected command
    updateCommandTemplate(commandName) {
        const templateId = `template-${commandName}`;
        const template = document.getElementById(templateId);
        
        if (template) {
            document.getElementById('command-data').value = template.textContent.trim();
        }
    }
    
    // Request devices list from the server
    async requestDevicesList() {
        if (!this.connected) return;
        
        try {
            await this.sendJson({ type: 'devices_list' });
            this.consoleLog('Requesting devices list', 'info');
        } catch (error) {
            this.consoleLog(`Error requesting devices list: ${error.message}`, 'error');
        }
    }
    
    // Send a command to the device
    async sendCommand() {
        if (!this.connected || !this.selectedDeviceId) return;
        
        const commandName = document.getElementById('command-name').value;
        const commandDataStr = document.getElementById('command-data').value;
        
        try {
            // Parse command data
            const commandData = JSON.parse(commandDataStr);
            
            // Increment command counter
            this.commandCounter++;
            
            // Create command object
            const command = {
                type: 'command',
                command: commandName,
                deviceId: this.selectedDeviceId,
                command_id: `${this.clientId}-${this.commandCounter}-${Date.now()}`,
                data: commandData
            };
            
            // Send command
            await this.sendJson(command);
            this.consoleLog(`Sent command: ${commandName}`, 'info');
        } catch (error) {
            this.consoleLog(`Error sending command: ${error.message}`, 'error');
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
            
            // Create and send offer
            const offer = await this.peerConnection.createOffer();
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
        } catch (error) {
            this.consoleLog(`Error starting video: ${error.message}`, 'error');
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
    
    // Update connection status UI
    updateConnectionStatus(status) {
        const iconElement = document.getElementById('connection-icon');
        const textElement = document.getElementById('connection-text');
        
        iconElement.className = `icon ${status}`;
        
        switch (status) {
            case 'connected':
                textElement.textContent = 'Connected';
                break;
            case 'connecting':
                textElement.textContent = 'Connecting...';
                break;
            case 'disconnected':
                textElement.textContent = 'Disconnected';
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
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Initialize client
    window.piBoatClient = new PiBoatClient();
}); 
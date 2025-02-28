import asyncio
import json
import logging
import os
import time
import uuid
import random
import math
from datetime import datetime
from pathlib import Path
import fractions
import pkg_resources

import aiohttp
import websockets
import cv2
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCRtpSender
from av import VideoFrame
import numpy

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('simulated_device.log')
    ]
)
logger = logging.getLogger("SimulatedDevice")

# Log library versions for debugging
logger.info(f"aiortc version: {pkg_resources.get_distribution('aiortc').version}")
logger.info(f"av version: {pkg_resources.get_distribution('av').version}")
logger.info(f"websockets version: {pkg_resources.get_distribution('websockets').version}")

# Configuration
WS_SERVER_URL = "ws://localhost:8000/ws/device/{device_id}"
DEVICE_ID = f"simulated-boat-{uuid.uuid4().hex[:8]}"
TELEMETRY_INTERVAL = 1.0  # Send telemetry every 1 second


class FileVideoStreamTrack(VideoStreamTrack):
    """
    A video track that reads from a video file or displays a simple color pattern if no file is provided.
    """
    def __init__(self, file_path=None):
        super().__init__()
        self._counter = 0
        self._fps = 30
        self.width = 640
        self.height = 480
        self._timestamp = 0
        self.kind = "video"
        self._time_base = fractions.Fraction(1, 90000)
        
        # Define supported codecs to ensure compatibility
        self._supported_codecs = ["VP8", "H264"]
        logger.info(f"Video track initialized with supported codecs: {', '.join(self._supported_codecs)}")
        
        # If a video file is provided, open it for reading
        self.file_path = file_path
        self.cap = None
        if file_path and os.path.exists(file_path):
            self.cap = cv2.VideoCapture(file_path)
            if self.cap.isOpened():
                self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                self._fps = self.cap.get(cv2.CAP_PROP_FPS)
                if self._fps <= 0:
                    self._fps = 30  # Default if FPS cannot be determined
                logger.info(f"Opened video file {file_path} with {self.width}x{self.height} resolution at {self._fps}fps")
            else:
                logger.error(f"Failed to open video file {file_path}")
                self.cap = None
        else:
            logger.info(f"No video file provided or file doesn't exist, using test pattern")
        
        # Set up a simple static image for fallback
        self._static_image = numpy.zeros((self.height, self.width, 3), dtype=numpy.uint8)
        self._static_image[:, :, 0] = 255  # Make it red for easy identification
        
    def get_codec_compatibility(self, remote_sdp):
        """
        Check if the remote SDP offer contains compatible codecs.
        Returns a tuple (compatible, message) where compatible is a boolean
        and message contains details if not compatible.
        """
        if not remote_sdp:
            return (False, "No remote SDP provided")
            
        # Simple SDP parsing to check for codecs
        remote_codecs = []
        
        # Look for codec information in the SDP
        lines = remote_sdp.split("\n")
        for line in lines:
            # Check for rtpmap entries (which define codecs)
            if line.startswith("a=rtpmap:"):
                # Extract codec name from rtpmap
                codec_info = line.split(" ")[1].split("/")[0].upper()
                remote_codecs.append(codec_info)
                logger.info(f"Found codec in SDP: {codec_info}")
                
            # Also check for fmtp lines which might contain specific codec parameters
            elif line.startswith("a=fmtp:") and "profile-level-id" in line:
                remote_codecs.append("H264")  # H.264 specific parameters 
                logger.info("Detected H.264 parameters in SDP")
                
        # If no specific codec info was found but we see a video section,
        # assume basic compatibility rather than rejecting
        if not remote_codecs and "m=video" in remote_sdp:
            logger.info("No specific codec info found, but video section exists. Assuming compatibility.")
            return (True, "Assuming compatibility based on video section presence")
                
        # Check if we found any compatible codecs
        compatible_codecs = [c for c in remote_codecs if c in self._supported_codecs or c in ["H264", "VP8"]]
        
        if compatible_codecs:
            return (True, f"Found compatible codecs: {', '.join(compatible_codecs)}")
        elif remote_codecs:
            # If we found codecs but none are compatible, return false
            return (False, f"Found incompatible codecs: {', '.join(remote_codecs)}")
        else:
            # More permissive: if we have a video section but couldn't parse codecs, assume it's OK
            # Most browsers will support at least H.264 or VP8
            return (True, "No video codecs explicitly found in remote SDP, assuming default compatibility")
    
    async def recv(self):
        pts, time_base = await self._next_timestamp()
        
        try:
            # Try to read from video file if available
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret:
                    # If we've reached the end of the file, start over
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = self.cap.read()
                    if not ret:
                        # If still can't read, fall back to pattern
                        logger.warning("Failed to read from video file, using fallback pattern")
                        return await self._create_pattern_frame(pts, time_base)
                
                # Add timestamp to the frame
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cv2.putText(
                    frame, 
                    f"Simulated Boat - {timestamp}", 
                    (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    0.8, 
                    (255, 255, 255), 
                    2
                )
                
                # Create VideoFrame from numpy array
                video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
                video_frame.pts = pts
                video_frame.time_base = time_base
                return video_frame
            else:
                # If no video file is available, create a pattern
                return await self._create_pattern_frame(pts, time_base)
                
        except Exception as e:
            logger.error(f"Error in video frame generation: {e}")
            # Return a static frame on error
            frame = VideoFrame.from_ndarray(self._static_image, format="bgr24")
            frame.pts = pts
            frame.time_base = time_base
            return frame
    
    async def _create_pattern_frame(self, pts, time_base):
        """Create a simple color pattern as a fallback."""
        # Create a simple color pattern
        img = numpy.zeros((self.height, self.width, 3), dtype=numpy.uint8)
        
        # Increment counter
        self._counter = (self._counter + 1) % 360
        
        # Simple color gradient
        for y in range(self.height):
            for x in range(self.width):
                hue = (self._counter + y + x) % 180
                if hue < 60:
                    r, g, b = 255, int(hue * 4.25), 0
                elif hue < 120:
                    r, g, b = int((120 - hue) * 4.25), 255, 0
                else:
                    r, g, b = 0, 255, int((hue - 120) * 4.25)
                img[y, x] = [b, g, r]  # OpenCV uses BGR
        
        # Add timestamp to the frame
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            img, 
            f"Simulated Boat - {timestamp}", 
            (20, 40), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.8, 
            (255, 255, 255), 
            2
        )
        
        # Create VideoFrame from numpy array
        frame = VideoFrame.from_ndarray(img, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base
        return frame
            
    async def _next_timestamp(self):
        """Generate the next frame timestamp."""
        self._timestamp += int(90000 / self._fps)
        return self._timestamp, self._time_base
    
    def __del__(self):
        """Clean up resources when object is destroyed."""
        if self.cap and self.cap.isOpened():
            self.cap.release()


# Rename TestPatternVideoTrack to maintain compatibility with existing code
TestPatternVideoTrack = FileVideoStreamTrack
LoopedVideoStreamTrack = FileVideoStreamTrack

class SimulatedDevice:
    """
    Simulated autonomous boat device that connects to the relay server,
    sends telemetry data, and streams video via WebRTC.
    """
    def __init__(self, device_id, server_url, video_file=None):
        self.device_id = device_id
        self.server_url = server_url.format(device_id=device_id)
        self.video_file = video_file
        self.websocket = None
        self.peer_connections = {}
        self.command_log = []
        self.running = False
        
        # Initial random position in San Francisco Bay
        self.latitude = 37.7749 + (random.random() - 0.5) * 0.05
        self.longitude = -122.4194 + (random.random() - 0.5) * 0.05
        self.heading = random.random() * 360  # 0-360 degrees
        self.speed = random.random() * 5  # 0-5 knots
        self.battery = 100  # Battery percentage
        
        # For sequence numbering
        self.telemetry_sequence = 0
        
        logger.info(f"Initialized simulated device {device_id}")
        logger.info(f"Initial position: {self.latitude}, {self.longitude}")
    
    async def connect(self):
        """Connect to the WebSocket server."""
        logger.info(f"Connecting to server at {self.server_url}")
        
        try:
            self.websocket = await websockets.connect(self.server_url)
            logger.info("Connected to WebSocket server")
            self.running = True
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {str(e)}")
            return False
    
    async def run(self):
        """Main execution loop."""
        if not await self.connect():
            return
        
        # Start tasks
        tasks = [
            asyncio.create_task(self.telemetry_loop()),
            asyncio.create_task(self.message_handler())
        ]
        
        self.running = True
        await asyncio.gather(*tasks)
    
    def update_simulated_position(self):
        """Update the simulated boat position based on current heading and speed."""
        # Update position based on heading and speed
        # Simplified movement model - in reality would need proper geodesic calculations
        # This is just for simulation purposes
        lat_change = self.speed * 0.0001 * math.cos(math.radians(self.heading))
        lon_change = self.speed * 0.0001 * math.sin(math.radians(self.heading))
        
        self.latitude += lat_change
        self.longitude += lon_change
        
        # Randomly adjust heading and speed occasionally
        if random.random() < 0.1:  # 10% chance each update
            self.heading += (random.random() - 0.5) * 10  # +/- 5 degrees
            self.heading %= 360  # Keep in 0-360 range
            
        if random.random() < 0.05:  # 5% chance each update
            self.speed += (random.random() - 0.5)  # +/- 0.5 knots
            self.speed = max(0, min(10, self.speed))  # Clamp between 0-10 knots
        
        # Simulate battery drain
        self.battery -= 0.01  # Very slow drain for simulation
        self.battery = max(0, self.battery)  # Don't go below 0
    
    async def telemetry_loop(self):
        """Periodically send telemetry data to the server."""
        logger.info("Starting telemetry loop")
        
        while self.running:
            try:
                # Update simulated position
                self.update_simulated_position()
                
                # Create telemetry data
                telemetry = {
                    "type": "telemetry",
                    "subtype": "sensor_data",
                    "sequence": self.telemetry_sequence,
                    "timestamp": int(time.time() * 1000),
                    "system_time": int(time.time() * 1000),
                    "data": {
                        "gps": {
                            "latitude": self.latitude,
                            "longitude": self.longitude,
                            "heading": self.heading,
                            "speed": self.speed
                        },
                        "status": "autonomous_navigation",
                        "battery": {
                            "percentage": self.battery,
                            "voltage": 12.0 + (self.battery - 50) * 0.04,  # Simulate voltage drop
                            "current": 2.0 + random.random()  # Simulate current draw
                        },
                        "environmental": {
                            "water_temp": 15.0 + random.random() * 5,  # 15-20°C
                            "air_temp": 20.0 + random.random() * 10,  # 20-30°C
                            "water_depth": 15.0 + random.random() * 2,  # 15-17m
                            "wind_speed": 5.0 + random.random() * 5,  # 5-10 knots
                            "wind_direction": (self.heading + 180 + (random.random() - 0.5) * 45) % 360  # Roughly opposite to heading with some variation
                        }
                    }
                }
                
                # Send telemetry data
                await self.websocket.send(json.dumps(telemetry))
                logger.debug(f"Sent telemetry data: sequence={self.telemetry_sequence}")
                
                # Increment sequence number
                self.telemetry_sequence += 1
                
                # Wait for next telemetry interval
                await asyncio.sleep(TELEMETRY_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in telemetry loop: {str(e)}")
                if not self.running:
                    break
                await asyncio.sleep(1)  # Wait before retrying
    
    async def message_handler(self):
        """Handle incoming messages from the server."""
        logger.info("Starting message handler")
        
        while self.running:
            try:
                # Receive message
                message = await self.websocket.recv()
                data = json.loads(message)
                
                # Handle different message types
                message_type = data.get("type")
                
                if message_type == "webrtc":
                    await self.handle_webrtc_message(data)
                elif message_type == "command":
                    await self.handle_command(data)
                elif message_type == "ping":
                    # Respond to ping messages with a pong
                    pong = {
                        "type": "pong",
                        "timestamp": int(time.time() * 1000)
                    }
                    await self.websocket.send(json.dumps(pong))
                    logger.debug("Responded to ping with pong")
                else:
                    logger.warning(f"Unknown message type: {message_type}")
                
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Connection closed by server")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in message handler: {str(e)}")
                await asyncio.sleep(1)
    
    async def handle_webrtc_message(self, message):
        """Handle WebRTC signaling messages."""
        message_subtype = message.get("subtype")
        
        if message_subtype == "answer":
            # Handle SDP answer
            client_id = message.get("clientId")
            if not client_id:
                logger.warning("Received answer without client ID")
                return
                
            pc = self.peer_connections.get(client_id)
            if not pc:
                logger.warning(f"No peer connection for client {client_id}")
                return
                
            # Apply the remote description
            sdp = message.get("sdp")
            await pc.setRemoteDescription(
                RTCSessionDescription(sdp=sdp, type="answer")
            )
            logger.info(f"Set remote description from client {client_id}")
            
        elif message_subtype == "ice_candidate":
            # Handle ICE candidate
            client_id = message.get("clientId")
            candidate = message.get("candidate")
            
            if not client_id or not candidate:
                logger.warning("Invalid ICE candidate message")
                return
                
            pc = self.peer_connections.get(client_id)
            if not pc:
                logger.warning(f"No peer connection for client {client_id}")
                return
                
            await pc.addIceCandidate(candidate)
            logger.debug(f"Added ICE candidate from client {client_id}")
            
        elif message_subtype == "request_offer":
            # Client is requesting that we start a WebRTC connection
            client_id = message.get("clientId")
            if not client_id:
                logger.warning("Received request_offer without client ID")
                return
                
            await self.create_webrtc_offer(client_id)
            
        elif message_subtype == "offer":
            # Handle incoming offer from client
            # Get clientId from message - it might be in deviceId or clientId
            client_id = message.get("clientId")
            if not client_id:
                logger.info("No clientId found, checking alternative fields")
                client_id = message.get("client_id")
            
            if not client_id:
                logger.warning("Received offer without client ID")
                return
                
            logger.info(f"Received WebRTC offer from client {client_id}")
            
            # Create a new RTCPeerConnection with default configuration
            pc = RTCPeerConnection()
            self.peer_connections[client_id] = pc
            logger.info(f"Created peer connection for client {client_id}")
            
            # Set up the video track - use the video file if provided
            video_track = FileVideoStreamTrack(self.video_file)
            pc.addTrack(video_track)
            logger.info(f"Initialized video stream with {video_track.width}x{video_track.height} resolution at {video_track._fps}fps")
            
            # Set up ICE candidate handling
            @pc.on("icecandidate")
            async def on_icecandidate(candidate):
                if candidate:
                    try:
                        # Ensure all required properties exist
                        if not hasattr(candidate, 'candidate') or not candidate.candidate:
                            logger.warning(f"Skipping invalid ICE candidate (missing candidate string)")
                            return
                            
                        if not hasattr(candidate, 'sdpMid') or candidate.sdpMid is None:
                            logger.warning(f"ICE candidate missing sdpMid, using empty string")
                            sdpMid = ""
                        else:
                            sdpMid = candidate.sdpMid
                            
                        if not hasattr(candidate, 'sdpMLineIndex') or candidate.sdpMLineIndex is None:
                            logger.warning(f"ICE candidate missing sdpMLineIndex, using 0")
                            sdpMLineIndex = 0
                        else:
                            sdpMLineIndex = candidate.sdpMLineIndex
                            
                        message = {
                            "type": "webrtc",
                            "subtype": "ice_candidate",
                            "boatId": self.device_id,
                            "clientId": client_id,
                            "candidate": {
                                "candidate": candidate.candidate,
                                "sdpMid": sdpMid,
                                "sdpMLineIndex": sdpMLineIndex
                            }
                        }
                        await self.websocket.send(json.dumps(message))
                        logger.debug(f"Sent ICE candidate to client {client_id}")
                    except Exception as e:
                        logger.warning(f"Error sending ICE candidate: {str(e)}")
            
            # Apply the remote description (the offer)
            sdp = message.get("sdp")
            if not sdp:
                logger.warning("Received offer without SDP")
                return
                
            try:
                # Check codec compatibility first
                video_track = FileVideoStreamTrack(self.video_file)
                compatible, message = video_track.get_codec_compatibility(sdp)
                logger.info(f"Codec compatibility check: {message}")
                
                if not compatible:
                    # Send error to client
                    error_response = {
                        "type": "webrtc",
                        "subtype": "error",
                        "boatId": self.device_id,
                        "clientId": client_id,
                        "error": "codec_incompatible",
                        "message": message
                    }
                    await self.websocket.send(json.dumps(error_response))
                    logger.warning(f"Rejecting WebRTC offer due to codec incompatibility: {message}")
                    
                    # Clean up and return
                    if client_id in self.peer_connections:
                        await self.peer_connections[client_id].close()
                        del self.peer_connections[client_id]
                    return
                
                # Set the remote description (the offer)
                await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type="offer"))
                logger.info(f"Set remote offer from client {client_id}")
                
                try:
                    # Create and set the answer - with explicit error handling
                    answer = await pc.createAnswer()
                    
                    # Ensure we have valid media descriptions in the answer
                    if not answer.sdp or "m=video" not in answer.sdp:
                        logger.warning("No video stream in answer, checking codec compatibility")
                        # We could add fallback codec handling here if needed
                        # For now, just log and let the process continue
                    
                    await pc.setLocalDescription(answer)
                    
                    # Send the answer to the client
                    response = {
                        "type": "webrtc",
                        "subtype": "answer",
                        "boatId": self.device_id,
                        "clientId": client_id,
                        "sdp": pc.localDescription.sdp,
                        "sdpType": "answer"
                    }
                    await self.websocket.send(json.dumps(response))
                    logger.info(f"Sent answer to client {client_id}")
                    
                except ValueError as codec_error:
                    # This is likely a codec negotiation error
                    logger.error(f"Codec negotiation error: {str(codec_error)}")
                    error_response = {
                        "type": "webrtc",
                        "subtype": "error",
                        "boatId": self.device_id,
                        "clientId": client_id,
                        "error": "codec_negotiation_failed",
                        "message": f"Failed to negotiate compatible video codec: {str(codec_error)}"
                    }
                    await self.websocket.send(json.dumps(error_response))
                    raise  # Re-raise to trigger the cleanup in the outer exception handler
                
            except Exception as e:
                logger.error(f"Error processing WebRTC offer: {str(e)}")
                # Close the peer connection on error
                if client_id in self.peer_connections:
                    await self.peer_connections[client_id].close()
                    del self.peer_connections[client_id]
                    logger.info(f"Closed connection with client {client_id} due to error")
            
        elif message_subtype == "close":
            # Handle close request
            client_id = message.get("clientId")
            if not client_id:
                logger.warning("Received close without client ID")
                return
                
            if client_id in self.peer_connections:
                pc = self.peer_connections[client_id]
                await pc.close()
                del self.peer_connections[client_id]
                logger.info(f"Closed connection with client {client_id}")
            
        else:
            logger.warning(f"Unknown WebRTC message subtype: {message_subtype}")
    
    async def create_webrtc_offer(self, client_id):
        """Create and send a WebRTC offer to a client."""
        try:
            # Create a new RTCPeerConnection with default configuration
            pc = RTCPeerConnection()
            self.peer_connections[client_id] = pc
            logger.info(f"Created peer connection for client {client_id}")
            
            # Set up the video track - use the video file if provided
            video_track = FileVideoStreamTrack(self.video_file)
            pc.addTrack(video_track)
            logger.info(f"Initialized video stream with {video_track.width}x{video_track.height} resolution at {video_track._fps}fps")
            
            # Set up ICE candidate handling
            @pc.on("icecandidate")
            async def on_icecandidate(candidate):
                if candidate:
                    try:
                        # Ensure all required properties exist
                        if not hasattr(candidate, 'candidate') or not candidate.candidate:
                            logger.warning(f"Skipping invalid ICE candidate (missing candidate string)")
                            return
                            
                        if not hasattr(candidate, 'sdpMid') or candidate.sdpMid is None:
                            logger.warning(f"ICE candidate missing sdpMid, using empty string")
                            sdpMid = ""
                        else:
                            sdpMid = candidate.sdpMid
                            
                        if not hasattr(candidate, 'sdpMLineIndex') or candidate.sdpMLineIndex is None:
                            logger.warning(f"ICE candidate missing sdpMLineIndex, using 0")
                            sdpMLineIndex = 0
                        else:
                            sdpMLineIndex = candidate.sdpMLineIndex
                            
                        message = {
                            "type": "webrtc",
                            "subtype": "ice_candidate",
                            "boatId": self.device_id,
                            "clientId": client_id,
                            "candidate": {
                                "candidate": candidate.candidate,
                                "sdpMid": sdpMid,
                                "sdpMLineIndex": sdpMLineIndex
                            }
                        }
                        await self.websocket.send(json.dumps(message))
                        logger.debug(f"Sent ICE candidate to client {client_id}")
                    except Exception as e:
                        logger.warning(f"Error sending ICE candidate: {str(e)}")
            
            # Create offer
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
            
            # Send offer to client via relay server
            message = {
                "type": "webrtc",
                "subtype": "offer",
                "boatId": self.device_id,
                "clientId": client_id,
                "sdp": pc.localDescription.sdp
            }
            await self.websocket.send(json.dumps(message))
            logger.info(f"Sent WebRTC offer to client {client_id}")
        except Exception as e:
            logger.error(f"Error creating WebRTC offer: {str(e)}")
    
    async def handle_command(self, command):
        """Handle command messages from clients."""
        # Log the command for review (per user requirement)
        timestamp = datetime.now().isoformat()
        logged_command = {
            "timestamp": timestamp,
            "command": command
        }
        self.command_log.append(logged_command)
        
        # Also log to console and file
        logger.info(f"Received command: {json.dumps(command)}")
        
        # Write to a separate command log file
        with open("command_log.json", "a") as f:
            f.write(json.dumps(logged_command) + "\n")
        
        # Process different command types
        command_type = command.get("command")
        
        if command_type == "set_waypoint" or command_type == "set_waypoints":
            # Simulate accepting a waypoint command
            await self.acknowledge_command(command, "accepted")
            
            # In a real implementation, we would actually change course
            # For simulation, we'll just print what we would do
            if command_type == "set_waypoint":
                waypoint = command.get("data", {})
                lat = waypoint.get("latitude")
                lon = waypoint.get("longitude")
                logger.info(f"Would navigate to waypoint: {lat}, {lon}")
                
                # Simulate changing course toward the waypoint
                if lat and lon:
                    # Calculate heading to waypoint (simplified)
                    dx = lon - self.longitude
                    dy = lat - self.latitude
                    new_heading = math.degrees(math.atan2(dx, dy)) % 360
                    self.heading = new_heading
                    logger.info(f"Changing course to heading: {self.heading}°")
            
            elif command_type == "set_waypoints":
                waypoints = command.get("data", {}).get("waypoints", [])
                logger.info(f"Would navigate through {len(waypoints)} waypoints")
                
                # If there are waypoints, simulate heading toward the first one
                if waypoints and len(waypoints) > 0:
                    first = waypoints[0]
                    lat = first.get("latitude")
                    lon = first.get("longitude")
                    
                    if lat and lon:
                        # Calculate heading to waypoint (simplified)
                        dx = lon - self.longitude
                        dy = lat - self.latitude
                        new_heading = math.degrees(math.atan2(dx, dy)) % 360
                        self.heading = new_heading
                        logger.info(f"Changing course to heading: {self.heading}°")
        
        elif command_type == "emergency_stop":
            # Simulate emergency stop
            self.speed = 0
            logger.info("EMERGENCY STOP command received - stopping immediately")
            await self.acknowledge_command(command, "accepted")
            
        elif command_type == "set_speed":
            # Simulate changing speed
            new_speed = command.get("data", {}).get("speed", self.speed)
            logger.info(f"Changing speed from {self.speed} to {new_speed} knots")
            self.speed = new_speed
            await self.acknowledge_command(command, "accepted")
            
        elif command_type == "get_status":
            # Respond with current status
            status_data = {
                "type": "status_response",
                "command_id": command.get("command_id", str(uuid.uuid4())),
                "device_id": self.device_id,
                "data": {
                    "position": {
                        "latitude": self.latitude,
                        "longitude": self.longitude,
                        "heading": self.heading,
                        "speed": self.speed
                    },
                    "battery": {
                        "percentage": self.battery,
                        "voltage": 12.0 + (self.battery - 50) * 0.04,
                        "current": 2.0 + random.random()
                    },
                    "status": "autonomous_navigation",
                    "connection_quality": "good",
                    "timestamp": int(time.time() * 1000)
                }
            }
            await self.websocket.send(json.dumps(status_data))
            logger.info("Sent status response")
            await self.acknowledge_command(command, "accepted")
            
        else:
            logger.warning(f"Unknown command type: {command_type}")
            await self.acknowledge_command(command, "rejected", f"Unknown command: {command_type}")
    
    async def acknowledge_command(self, command, status, message=None):
        """Send command acknowledgement back to the server."""
        command_id = command.get("command_id", str(uuid.uuid4()))
        
        ack = {
            "type": "command_ack",
            "command_id": command_id,
            "status": status,
        }
        
        if message:
            ack["message"] = message
            
        await self.websocket.send(json.dumps(ack))
        logger.debug(f"Sent command acknowledgement: {status}")


async def main():
    # Check if a video file is provided as an environment variable
    video_file = os.environ.get("VIDEO_FILE")
    
    # Create and run the simulated device
    device = SimulatedDevice(
        device_id=DEVICE_ID,
        server_url=WS_SERVER_URL,
        video_file=video_file
    )
    
    logger.info(f"Starting simulated device: {DEVICE_ID}")
    if video_file and os.path.exists(video_file):
        logger.info(f"Using video file: {video_file}")
    else:
        logger.info(f"Using test pattern video stream")
    logger.info(f"WebSocket server: {WS_SERVER_URL.format(device_id=DEVICE_ID)}")
    
    try:
        await device.run()
    except KeyboardInterrupt:
        logger.info("Shutting down simulated device")
    except Exception as e:
        logger.error(f"Error running simulated device: {str(e)}")
    finally:
        # Cleanup
        logger.info("Simulation ended")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Simulation stopped by user") 
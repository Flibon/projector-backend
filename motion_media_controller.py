#!/usr/bin/env python3
"""
Motion-Based Media Controller for Raspberry Pi 5 with ESP32 Integration

This script monitors an ESP32 sensor for motion detection via serial connection,
switches between displaying an image (when motion is detected) and playing a video (when no motion),
and reports the video playback state to a remote API.

Usage:
    python3 motion_media_controller.py --video /path/to/video.mp4 --image /path/to/image.jpg

Dependencies:
    - pyserial
    - requests
    - VLC (cvlc command-line tool)
    - feh (image viewer)
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
from threading import Event, Lock, Thread

import requests
import serial

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("motion_controller.log")
    ]
)
logger = logging.getLogger(__name__)

# Global configuration
API_ENDPOINT = "https://backendlv8-production.up.railway.app/api/brightness/update"
DEVICE_ID = "AUTO_DEVICE_001"
ESP32_PORT = "/dev/ttyUSB0"
ESP32_BAUDRATE = 115200
API_UPDATE_INTERVAL = 10  # seconds


class ESP32Monitor:
    """Handles serial communication with ESP32 for motion detection."""
    
    def __init__(self, port, baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.motion_callback = None
        self.stop_event = Event()
        self.monitor_thread = None
        self.is_connected = False
    
    def connect(self):
        """Establish connection to ESP32."""
        logger.info(f"Connecting to ESP32 on {self.port}...")
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1
            )
            self.is_connected = True
            logger.info("ESP32 connection successful")
            return True
        except serial.SerialException as e:
            logger.error(f"Failed to connect to ESP32: {e}")
            return False
    
    def disconnect(self):
        """Close the serial connection."""
        self.stop_event.set()
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)
        
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            self.is_connected = False
            logger.info("Disconnected from ESP32")
    
    def register_motion_callback(self, callback):
        """Register a callback function for motion state changes."""
        self.motion_callback = callback
    
    def start_monitoring(self):
        """Start monitoring ESP32 data in a separate thread."""
        if not self.is_connected and not self.connect():
            logger.error("Cannot start monitoring - connection failed")
            return False
        
        self.stop_event.clear()
        self.monitor_thread = Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        logger.info("ESP32 monitoring started")
        return True
    
    def _process_data(self, data):
        """Process incoming data from ESP32."""
        try:
            # Try to parse as JSON
            parsed_data = json.loads(data)
            
            # Check for motion detection message
            if 'motion' in parsed_data:
                if self.motion_callback:
                    self.motion_callback(parsed_data['motion'])
                return parsed_data
        except json.JSONDecodeError:
            # Not JSON, look for text indicators
            if "Motion detected!" in data:
                if self.motion_callback:
                    self.motion_callback(True)
            elif "Motion stopped" in data:
                if self.motion_callback:
                    self.motion_callback(False)
        
        return data
    
    def _monitor_loop(self):
        """Main monitoring loop running in a separate thread."""
        if not self.serial_conn:
            logger.error("Serial connection not established")
            return
        
        # Clear any initial data
        self.serial_conn.reset_input_buffer()
        
        while not self.stop_event.is_set():
            try:
                if self.serial_conn.in_waiting:
                    line = self.serial_conn.readline().decode('utf-8').strip()
                    if line:
                        logger.debug(f"ESP32 data: {line}")
                        self._process_data(line)
            except serial.SerialException as e:
                logger.error(f"Serial error: {e}")
                # Try to reconnect
                self.is_connected = False
                time.sleep(5)
                self.connect()
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
            
            time.sleep(0.01)  # Small delay to prevent CPU hogging


class MediaController:
    """Controls video playback and image display."""
    
    def __init__(self, video_path, image_path):
        self.video_path = video_path
        self.image_path = image_path
        self.video_process = None
        self.image_process = None
        self.lock = Lock()
        self.is_video_playing = False
        self.is_image_displayed = False
        
        # Validate media files
        self._validate_files()
    
    def _validate_files(self):
        """Validate that the media files exist."""
        if not os.path.isfile(self.video_path):
            logger.error(f"Video file not found: {self.video_path}")
            raise FileNotFoundError(f"Video file not found: {self.video_path}")
        
        if not os.path.isfile(self.image_path):
            logger.error(f"Image file not found: {self.image_path}")
            raise FileNotFoundError(f"Image file not found: {self.image_path}")
        
        logger.info(f"Media files validated - Video: {self.video_path}, Image: {self.image_path}")
    
    def play_video(self):
        """Start video playback using VLC."""
        with self.lock:
            # First ensure image is closed
            self.close_image()
            
            # Check if video is already playing
            if self.is_video_playing and self.video_process:
                logger.debug("Video already playing")
                return
            
            try:
                # Use VLC for playback
                command = [
                    'cvlc', '--loop', '--fullscreen', '--no-osd',
                    '--no-video-title-show', self.video_path
                ]
                
                self.video_process = subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid
                )
                
                self.is_video_playing = True
                logger.info(f"Started video playback: {self.video_path}")
            except Exception as e:
                logger.error(f"Failed to play video: {e}")
    
    def display_image(self):
        """Display image using feh."""
        with self.lock:
            # First ensure video is closed
            self.close_video()
            
            # Check if image is already displayed
            if self.is_image_displayed and self.image_process:
                logger.debug("Image already displayed")
                return
            
            try:
                # Use feh for image display
                command = ['feh', '--fullscreen', '--hide-pointer', self.image_path]
                
                self.image_process = subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid
                )
                
                self.is_image_displayed = True
                logger.info(f"Displayed image: {self.image_path}")
            except Exception as e:
                logger.error(f"Failed to display image: {e}")
    
    def close_video(self):
        """Stop video playback."""
        if self.is_video_playing and self.video_process:
            try:
                os.killpg(os.getpgid(self.video_process.pid), signal.SIGTERM)
                self.video_process = None
                self.is_video_playing = False
                logger.info("Stopped video playback")
                time.sleep(0.5)  # Give system time to release resources
            except Exception as e:
                logger.error(f"Error stopping video: {e}")
    
    def close_image(self):
        """Close displayed image."""
        if self.is_image_displayed and self.image_process:
            try:
                os.killpg(os.getpgid(self.image_process.pid), signal.SIGTERM)
                self.image_process = None
                self.is_image_displayed = False
                logger.info("Closed image display")
                time.sleep(0.5)  # Give system time to release resources
            except Exception as e:
                logger.error(f"Error closing image: {e}")
    
    def cleanup(self):
        """Clean up all resources."""
        self.close_video()
        self.close_image()
        logger.info("Media controller cleaned up")


class APIService:
    """Handles API communication for brightness updates."""
    
    def __init__(self, api_url, device_id):
        self.api_url = api_url
        self.device_id = device_id
        self.full_url = f"{self.api_url}?deviceId={self.device_id}"
        self.last_reported_state = None
        self.update_thread = None
        self.stop_event = Event()
    
    def update_brightness(self, is_on):
        """Update brightness state via API."""
        try:
            payload = {"brightness": is_on}
            
            logger.info(f"Sending API update: brightness={is_on}")
            response = requests.post(self.full_url, json=payload, timeout=5)
            
            if response.status_code == 200:
                logger.info(f"API update successful: brightness={is_on}")
                self.last_reported_state = is_on
                return True
            else:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return False
        except requests.RequestException as e:
            logger.error(f"API request failed: {e}")
            return False
    
    def start_periodic_updates(self, get_state_callback, interval=10):
        """Start periodic API updates based on the provided callback."""
        self.stop_event.clear()
        self.update_thread = Thread(
            target=self._update_loop,
            args=(get_state_callback, interval)
        )
        self.update_thread.daemon = True
        self.update_thread.start()
        logger.info(f"Started periodic API updates (every {interval}s)")
    
    def stop_periodic_updates(self):
        """Stop the periodic update thread."""
        self.stop_event.set()
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=2)
        logger.info("Stopped periodic API updates")
    
    def _update_loop(self, get_state_callback, interval):
        """Loop that periodically checks state and updates the API."""
        while not self.stop_event.is_set():
            try:
                current_state = get_state_callback()
                
                # Only update if state has changed or never reported
                if self.last_reported_state is None or current_state != self.last_reported_state:
                    self.update_brightness(current_state)
            except Exception as e:
                logger.error(f"Error in API update loop: {e}")
            
            # Sleep in small increments to respond to stop event more quickly
            for _ in range(interval * 10):
                if self.stop_event.is_set():
                    break
                time.sleep(0.1)


class MotionMediaController:
    """Main controller class that integrates all components."""
    
    def __init__(self, video_path, image_path, esp32_port=ESP32_PORT):
        self.video_path = video_path
        self.image_path = image_path
        self.esp32_port = esp32_port
        
        # Initialize components
        self.esp32 = ESP32Monitor(port=self.esp32_port, baudrate=ESP32_BAUDRATE)
        self.media = MediaController(self.video_path, self.image_path)
        self.api = APIService(API_ENDPOINT, DEVICE_ID)
        
        # State tracking
        self.running = False
        self.motion_detected = False
        self.motion_start_time = 0
        self.motion_timeout = 3  # seconds to wait before acting on motion
    
    def motion_handler(self, motion_detected):
        """Handle motion state changes from ESP32."""
        if motion_detected != self.motion_detected:
            logger.info(f"Motion state changed: {'Detected' if motion_detected else 'Stopped'}")
            self.motion_detected = motion_detected
            
            if motion_detected:
                # Record when motion started
                self.motion_start_time = time.time()
                # Schedule transition after timeout
                Thread(target=self._handle_motion_after_timeout).start()
            else:
                # No motion, switch to video immediately
                self.media.play_video()
    
    def _handle_motion_after_timeout(self):
        """Handle motion detection after the specified timeout."""
        # Store the start time we're waiting for
        start_time = self.motion_start_time
        
        # Wait for the timeout
        time.sleep(self.motion_timeout)
        
        # Only proceed if motion is still detected and it's the same event
        if self.motion_detected and start_time == self.motion_start_time:
            logger.info(f"Motion sustained for {self.motion_timeout}s - displaying image")
            self.media.display_image()
    
    def get_brightness_state(self):
        """Return current brightness state for API updates."""
        # Brightness is ON (true) when video is playing
        return self.media.is_video_playing
    
    def start(self):
        """Start the controller and all its components."""
        logger.info("Starting Motion Media Controller")
        self.running = True
        
        # Register motion callback
        self.esp32.register_motion_callback(self.motion_handler)
        
        # Start ESP32 monitoring
        if not self.esp32.start_monitoring():
            logger.error("Failed to start ESP32 monitoring. Exiting.")
            return False
        
        # Start with video by default (no motion)
        self.media.play_video()
        
        # Start periodic API updates
        self.api.start_periodic_updates(self.get_brightness_state, interval=API_UPDATE_INTERVAL)
        
        logger.info("Motion Media Controller started successfully")
        return True
    
    def stop(self):
        """Stop the controller and clean up resources."""
        logger.info("Stopping Motion Media Controller")
        self.running = False
        
        # Stop API updates
        self.api.stop_periodic_updates()
        
        # Disconnect from ESP32
        self.esp32.disconnect()
        
        # Clean up media resources
        self.media.cleanup()
        
        logger.info("Motion Media Controller stopped")
    
    def run_forever(self):
        """Run the controller until interrupted."""
        try:
            logger.info("Controller running - press Ctrl+C to stop")
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.stop()


def signal_handler(sig, frame):
    """Handle system signals for clean shutdown."""
    logger.info(f"Received signal {sig}, shutting down...")
    if 'controller' in globals():
        controller.stop()
    sys.exit(0)


def main():
    """Main entry point for the application."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Motion-based media controller')
    parser.add_argument('--video', required=True, help='Path to video file')
    parser.add_argument('--image', required=True, help='Path to image file')
    parser.add_argument('--port', default=ESP32_PORT, help='ESP32 serial port')
    parser.add_argument('--log-level', default='INFO', 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       help='Set the logging level')
    
    args = parser.parse_args()
    
    # Configure logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Register signal handlers for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start the controller
    global controller
    controller = MotionMediaController(
        video_path=args.video,
        image_path=args.image,
        esp32_port=args.port
    )
    
    if controller.start():
        controller.run_forever()
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()

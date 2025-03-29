# main.py
import time
import logging
import signal
import sys
import os
from esp32_serial import ESP32Monitor
from media_controller import MediaController
from api_service import BrightnessAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("motion_media_controller.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('Main')

# Configuration
ESP32_PORT = '/dev/ttyUSB0'  # Adjust based on your system
ESP32_BAUDRATE = 115200
VIDEO_PATH = '/path/to/your/video.mp4'  # Replace with your video path
IMAGE_PATH = '/path/to/your/image.jpg'  # Replace with your image path
API_URL = 'https://backendlv8-production.up.railway.app/api/brightness/update'
DEVICE_ID = 'AUTO_DEVICE_001'

class MotionMediaController:
    def __init__(self):
        self.esp32 = ESP32Monitor(port=ESP32_PORT, baudrate=ESP32_BAUDRATE)
        self.media = MediaController(VIDEO_PATH, IMAGE_PATH)
        self.api = BrightnessAPI(API_URL, DEVICE_ID)
        self.running = False
    
    def motion_handler(self, motion_detected):
        """Handle motion state changes"""
        logger.info(f"Motion state changed: {'Detected' if motion_detected else 'Stopped'}")
        
        if motion_detected:
            # Motion detected: Display image, close video
            self.media.display_image()
        else:
            # No motion: Play video, close image
            self.media.play_video()
    
    def get_current_brightness_state(self):
        """Return current brightness state for API updates"""
        # Brightness is ON (true) when video is playing
        return self.media.is_video_playing
    
    def start(self):
        """Start the application"""
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
        self.api.start_periodic_updates(self.get_current_brightness_state, interval=10)
        
        logger.info("Motion Media Controller started successfully")
        return True
    
    def stop(self):
        """Stop the application and clean up resources"""
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
        """Run the application until interrupted"""
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.stop()

# Signal handler for graceful shutdown
def signal_handler(sig, frame):
    logger.info(f"Received signal {sig}, shutting down...")
    if 'controller' in globals():
        controller.stop()
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start the controller
    controller = MotionMediaController()
    if controller.start():
        controller.run_forever()
    else:
        sys.exit(1)

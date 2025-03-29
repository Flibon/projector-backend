# media_controller.py
import subprocess
import os
import signal
import logging
from threading import Lock
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Media_Controller')

class MediaController:
    def __init__(self, video_path, image_path):
        self.video_path = video_path
        self.image_path = image_path
        self.video_process = None
        self.image_process = None
        self.lock = Lock()
        self.is_video_playing = False
        self.is_image_displayed = False
        
    def play_video(self):
        """Start video playback using omxplayer"""
        with self.lock:
            # First ensure image is closed
            self.close_image()
            
            # Check if video is already playing
            if self.is_video_playing and self.video_process:
                logger.info("Video already playing")
                return
            
            try:
                # Use omxplayer for hardware accelerated playback on Raspberry Pi
                self.video_process = subprocess.Popen(
                    ['omxplayer', '--loop', '--no-osd', self.video_path],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid
                )
                self.is_video_playing = True
                logger.info(f"Started video playback: {self.video_path}")
            except Exception as e:
                logger.error(f"Failed to play video: {e}")
    
    def display_image(self):
        """Display image using feh"""
        with self.lock:
            # First ensure video is closed
            self.close_video()
            
            # Check if image is already displayed
            if self.is_image_displayed and self.image_process:
                logger.info("Image already displayed")
                return
            
            try:
                # Use feh for simple image display
                self.image_process = subprocess.Popen(
                    ['feh', '--fullscreen', '--hide-pointer', self.image_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid
                )
                self.is_image_displayed = True
                logger.info(f"Displayed image: {self.image_path}")
            except Exception as e:
                logger.error(f"Failed to display image: {e}")
    
    def close_video(self):
        """Stop video playback"""
        if self.is_video_playing and self.video_process:
            try:
                os.killpg(os.getpgid(self.video_process.pid), signal.SIGTERM)
                self.video_process = None
                self.is_video_playing = False
                logger.info("Stopped video playback")
                # Give system time to release resources
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Error stopping video: {e}")
    
    def close_image(self):
        """Close displayed image"""
        if self.is_image_displayed and self.image_process:
            try:
                os.killpg(os.getpgid(self.image_process.pid), signal.SIGTERM)
                self.image_process = None
                self.is_image_displayed = False
                logger.info("Closed image display")
                # Give system time to release resources
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Error closing image: {e}")
    
    def cleanup(self):
        """Clean up all resources"""
        self.close_video()
        self.close_image()
        logger.info("Media controller cleaned up")

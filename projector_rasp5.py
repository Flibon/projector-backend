#!/usr/bin/env python3
import serial
import time
import logging
import subprocess
import signal
import os
from datetime import datetime

# Configuration
UART_PORT = '/dev/ttyAMA0'  # or /dev/ttyS0 depending on your Pi model
BAUD_RATE = 115200
VIDEO_PATH = '/home/pi/video.mp4'
IMAGE_PATH = '/home/pi/image.jpg'
LOG_FILE = '/home/pi/speed_controller.log'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# Global variables
video_process = None
image_process = None
current_display = None  # 'video', 'image', or None
current_speed_state = None  # 1 for above threshold, 0 for below, None for unknown

def setup_serial():
    """Set up and return the serial connection to ESP32"""
    try:
        ser = serial.Serial(
            port=UART_PORT,
            baudrate=BAUD_RATE,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=1
        )
        logging.info("Serial connection established")
        return ser
    except serial.SerialException as e:
        logging.error(f"Failed to open serial port: {e}")
        return None

def kill_process(process):
    """Safely kill a subprocess"""
    if process and process.poll() is None:
        try:
            process.send_signal(signal.SIGTERM)
            process.wait(timeout=5)
            logging.info(f"Process terminated: {process.pid}")
        except subprocess.TimeoutExpired:
            process.kill()
            logging.warning(f"Process killed forcefully: {process.pid}")
        except Exception as e:
            logging.error(f"Error terminating process: {e}")

def play_video():
    """Start video playback using omxplayer"""
    global video_process, image_process, current_display
    
    # Kill image display if running
    if current_display == 'image':
        kill_process(image_process)
        image_process = None
    
    # Start video if not already playing
    if current_display != 'video':
        logging.info("Starting video playback")
        try:
            # Using omxplayer for hardware-accelerated playback
            video_process = subprocess.Popen(
                ['omxplayer', '--loop', '--no-osd', VIDEO_PATH],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            current_display = 'video'
            logging.info(f"Video playback started (PID: {video_process.pid})")
            return True
        except Exception as e:
            logging.error(f"Failed to start video: {e}")
            return False
    return True

def show_image():
    """Display static image using fbi"""
    global video_process, image_process, current_display
    
    # Kill video if playing
    if current_display == 'video':
        kill_process(video_process)
        video_process = None
    
    # Show image if not already showing
    if current_display != 'image':
        logging.info("Displaying static image")
        try:
            # Using fbi for framebuffer image display
            image_process = subprocess.Popen(
                ['fbi', '-a', '-T', '1', IMAGE_PATH],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            current_display = 'image'
            logging.info(f"Image display started (PID: {image_process.pid})")
            return True
        except Exception as e:
            logging.error(f"Failed to display image: {e}")
            return False
    return True

def send_brightness_status(ser, status):
    """Send brightness status to ESP32"""
    try:
        message = f"{status}\n"
        ser.write(message.encode('utf-8'))
        logging.info(f"Sent brightness status to ESP32: {status}")
        return True
    except Exception as e:
        logging.error(f"Failed to send brightness status: {e}")
        return False

def process_speed_data(ser, data):
    """Process speed threshold data from ESP32"""
    global current_speed_state
    
    try:
        value = data.strip()
        
        # Speed above threshold (>15 km/h)
        if value == "1" and current_speed_state != 1:
            logging.info("Speed above threshold detected")
            current_speed_state = 1
            
            # Show image and send brightness OFF (0)
            if show_image():
                send_brightness_status(ser, 0)
        
        # Speed below threshold (<15 km/h)
        elif value == "0" and current_speed_state != 0:
            logging.info("Speed below threshold detected")
            current_speed_state = 0
            
            # Play video and send brightness ON (1)
            if play_video():
                send_brightness_status(ser, 1)
        
        else:
            logging.debug(f"Received repeated or invalid data: {value}")
    
    except Exception as e:
        logging.error(f"Error processing speed data: {e}")

def main():
    """Main function to control video/image based on speed data"""
    # Set up serial connection
    ser = setup_serial()
    if not ser:
        logging.error("Exiting due to serial connection failure")
        return
    
    logging.info("Starting speed-based video/image controller...")
    
    # Initial state - assume below threshold (show video)
    play_video()
    send_brightness_status(ser, 1)
    
    try:
        while True:
            if ser.in_waiting > 0:
                # Read line from serial port
                data = ser.readline().decode('utf-8').strip()
                if data:
                    logging.info(f"Received data from ESP32: {data}")
                    process_speed_data(ser, data)
            
            # Check if processes are still running
            if current_display == 'video' and (video_process is None or video_process.poll() is not None):
                logging.warning("Video process terminated unexpectedly, restarting")
                play_video()
            
            elif current_display == 'image' and (image_process is None or image_process.poll() is not None):
                logging.warning("Image process terminated unexpectedly, restarting")
                show_image()
            
            # Small delay to reduce CPU usage
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        logging.info("Controller stopped by user")
    except Exception as e:
        logging.error(f"An error occurred: {e}")
    finally:
        # Clean up
        kill_process(video_process)
        kill_process(image_process)
        if ser and ser.is_open:
            ser.close()
            logging.info("Serial connection closed")

if __name__ == "__main__":
    main()

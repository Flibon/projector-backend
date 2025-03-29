# esp32_serial.py
import serial
import json
import logging
from threading import Thread, Event
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ESP32_Serial')

class ESP32Monitor:
    def __init__(self, port='/dev/ttyUSB0', baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.is_connected = False
        self.stop_event = Event()
        self.motion_detected = False
        self.motion_callback = None
        self.monitor_thread = None
        
    def connect(self):
        """Establish connection to ESP32"""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1
            )
            self.is_connected = True
            logger.info(f"Connected to ESP32 on {self.port}")
            return True
        except serial.SerialException as e:
            logger.error(f"Failed to connect to ESP32: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """Close the serial connection"""
        self.stop_event.set()
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)
        
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            self.is_connected = False
            logger.info("Disconnected from ESP32")
    
    def register_motion_callback(self, callback):
        """Register callback function to be called when motion state changes"""
        self.motion_callback = callback
    
    def _process_data(self, data):
        """Process incoming data from ESP32"""
        try:
            # Try to parse as JSON first
            parsed_data = json.loads(data)
            
            # Check if this is a motion detection message
            if 'motion' in parsed_data:
                new_motion_state = parsed_data['motion']
                
                # Only trigger callback if state has changed
                if self.motion_detected != new_motion_state:
                    self.motion_detected = new_motion_state
                    logger.info(f"Motion state changed: {self.motion_detected}")
                    
                    if self.motion_callback:
                        self.motion_callback(self.motion_detected)
            
            return parsed_data
        except json.JSONDecodeError:
            # Not JSON, look for specific text indicators
            if "Motion detected!" in data:
                if not self.motion_detected:
                    self.motion_detected = True
                    logger.info("Motion detected")
                    if self.motion_callback:
                        self.motion_callback(True)
            elif "Motion stopped" in data:
                if self.motion_detected:
                    self.motion_detected = False
                    logger.info("Motion stopped")
                    if self.motion_callback:
                        self.motion_callback(False)
            
            return data
    
    def start_monitoring(self):
        """Start monitoring ESP32 data in a separate thread"""
        if not self.is_connected:
            if not self.connect():
                logger.error("Cannot start monitoring - connection failed")
                return False
        
        self.stop_event.clear()
        self.monitor_thread = Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        logger.info("ESP32 monitoring started")
        return True
    
    def _monitor_loop(self):
        """Main monitoring loop running in a separate thread"""
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

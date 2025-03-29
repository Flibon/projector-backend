# api_service.py
import requests
import logging
import time
from threading import Thread, Event

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('API_Service')

class BrightnessAPI:
    def __init__(self, api_url, device_id):
        self.api_url = api_url
        self.device_id = device_id
        self.full_url = f"{self.api_url}?deviceId={self.device_id}"
        self.last_reported_state = None
        self.stop_event = Event()
        self.update_thread = None
        
    def update_brightness(self, is_on):
        """Update brightness state via API"""
        try:
            payload = {"brightness": is_on}
            response = requests.post(self.full_url, json=payload, timeout=5)
            
            if response.status_code == 200:
                logger.info(f"Successfully updated brightness to {is_on}")
                self.last_reported_state = is_on
                return True
            else:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return False
        except requests.RequestException as e:
            logger.error(f"Failed to update brightness: {e}")
            return False
    
    def start_periodic_updates(self, get_current_state_callback, interval=10):
        """Start a thread that periodically updates the API based on the current state"""
        self.stop_event.clear()
        self.update_thread = Thread(target=self._update_loop, args=(get_current_state_callback, interval))
        self.update_thread.daemon = True
        self.update_thread.start()
        logger.info(f"Started periodic API updates (every {interval}s)")
    
    def stop_periodic_updates(self):
        """Stop the periodic update thread"""
        self.stop_event.set()
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=2)
        logger.info("Stopped periodic API updates")
    
    def _update_loop(self, get_current_state_callback, interval):
        """Loop that periodically checks the current state and updates the API if needed"""
        while not self.stop_event.is_set():
            try:
                current_state = get_current_state_callback()
                
                # Only update if state has changed or never reported
                if self.last_reported_state is None or current_state != self.last_reported_state:
                    self.update_brightness(current_state)
            except Exception as e:
                logger.error(f"Error in update loop: {e}")
            
            # Sleep in small increments to respond to stop event more quickly
            for _ in range(interval * 10):
                if self.stop_event.is_set():
                    break
                time.sleep(0.1)

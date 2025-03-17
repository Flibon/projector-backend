import threading
import multiprocessing
import time
import serial
import smbus2
import psycopg2
from datetime import datetime

# PostgreSQL Connection Details
DB_HOST = "localhost"
DB_NAME = "vehicle_data"
DB_USER = "postgres"
DB_PASSWORD = "your_password"
CLIENT_ID = "001"

# GPS UART Setup
GPS_PORT = "/dev/serial0"  # or "/dev/ttyS0"
GPS_BAUDRATE = 9600

# Accelerometer (MPU6050) I2C Setup
MPU6050_ADDR = 0x68
bus = smbus2.SMBus(1)

# Wake up the MPU6050
bus.write_byte_data(MPU6050_ADDR, 0x6B, 0)

# Function to parse GPS data
def parse_gps(data):
    try:
        parts = data.split(",")
        if parts[0] == "$GPGGA":
            lat = float(parts[2]) if parts[2] else 0.0
            lon = float(parts[4]) if parts[4] else 0.0
            return lat, lon
    except Exception as e:
        print(f"GPS Parsing Error: {e}")
    return None, None

# Function to get GPS Data
def get_gps():
    gps_serial = serial.Serial(GPS_PORT, GPS_BAUDRATE, timeout=1)
    while True:
        try:
            data = gps_serial.readline().decode('utf-8', errors='ignore')
            lat, lon = parse_gps(data)
            if lat and lon:
                print(f"GPS: Latitude={lat}, Longitude={lon}")
                insert_data(lat, lon, None)  # No speed data from GPS
        except Exception as e:
            print(f"GPS Error: {e}")
        time.sleep(1)

# Function to get accelerometer speed (basic calculation)
def get_speed():
    while True:
        try:
            accel_x = bus.read_byte_data(MPU6050_ADDR, 0x3B)
            speed = accel_x * 0.1  # Simplified conversion (calibrate this)
            print(f"Speed: {speed} m/s")
            insert_data(None, None, speed)
        except Exception as e:
            print(f"Accelerometer Error: {e}")
        time.sleep(1)

# Function to insert data into PostgreSQL
def insert_data(lat, lon, speed):
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST
        )
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sensor_data (client_id, latitude, longitude, speed) VALUES (%s, %s, %s, %s)",
            (CLIENT_ID, lat, lon, speed),
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Database Error: {e}")

# Run GPS & Speed in Parallel
if __name__ == "__main__":
    gps_process = multiprocessing.Process(target=get_gps)
    speed_process = multiprocessing.Process(target=get_speed)

    gps_process.start()
    speed_process.start()

    gps_process.join()
    speed_process.join()

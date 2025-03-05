#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include "MPU6050.h"

const char* ssid = "your-SSID";
const char* password = "your-PASSWORD";
const char* serverUrl = "http://your-server-ip:5000/accelerometer"; // Replace with actual IP

MPU6050 mpu;

void setup() {
    Serial.begin(115200);
    WiFi.begin(ssid, password);
    
    while (WiFi.status() != WL_CONNECTED) {
        delay(1000);
        Serial.println("Connecting to WiFi...");
    }
    
    Serial.println("Connected to WiFi");

    Wire.begin();
    mpu.initialize();
    if (!mpu.testConnection()) {
        Serial.println("MPU6050 connection failed");
    }
}

/**
 * Continuously checks WiFi connection status and sends accelerometer data to a server.
 * If connected to WiFi, reads accelerometer data, converts it to g-force,
 * creates a JSON payload, and sends it to the specified server endpoint.
 * Logs the sent data and server response code to the serial monitor.
 * If disconnected from WiFi, logs a disconnection message.
 * The process repeats every 2 seconds.
 */


void loop() {
    if (WiFi.status() == WL_CONNECTED) {
        HTTPClient http;
        http.begin(serverUrl);
        http.addHeader("Content-Type", "application/json");

        // Read accelerometer data
        int16_t ax, ay, az;
        mpu.getAcceleration(&ax, &ay, &az);

        // Convert to g-force
        float x = ax / 16384.0;
        float y = ay / 16384.0;
        float z = az / 16384.0;

        // Create JSON payload
        String payload = "{\"x\":" + String(x) + ", \"y\":" + String(y) + ", \"z\":" + String(z) + "}";

        int httpResponseCode = http.POST(payload);
        Serial.println("Sent Data: " + payload);
        Serial.println("Response Code: " + String(httpResponseCode));

        http.end();
    } else {
        Serial.println("WiFi Disconnected");
    }

    delay(2000);  // Send data every 2 seconds
}

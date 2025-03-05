from flask import Flask, request, jsonify
import boto3
import requests

app = Flask(__name__)

# AWS S3 Config
AWS_BUCKET = "your-bucket-name"
AWS_ACCESS_KEY = "your-access-key"
AWS_SECRET_KEY = "your-secret-key"
S3_FILE_KEY = "data.txt"

# Projector API
PROJECTOR_IP = "192.168.1.100"  # Replace with your projector IP
PROJECTOR_API = f"http://{PROJECTOR_IP}/control"

# Initialize S3 Client
s3 = boto3.client("s3", aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY)

@app.route('/fetch_s3', methods=['GET'])
def fetch_from_s3():
    """Fetch data from AWS S3"""
    try:
        response = s3.get_object(Bucket=AWS_BUCKET, Key=S3_FILE_KEY)
        file_data = response['Body'].read().decode('utf-8')
        
        # Send data to the projector
        projector_response = requests.post(PROJECTOR_API, json={"data": file_data})
        
        return jsonify({"status": "success", "projector_response": projector_response.text})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/accelerometer', methods=['POST'])
def receive_accelerometer():
    """Receive accelerometer data from ESP32"""
    data = request.json
    print(f"Received Accelerometer Data: {data}")

    # Example: Adjust projection based on motion
    if abs(data['x']) > 1.5:  # Adjust threshold as needed
        requests.post(PROJECTOR_API, json={"adjust": "tilt_up" if data['x'] > 0 else "tilt_down"})
    
    return jsonify({"status": "received"})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)

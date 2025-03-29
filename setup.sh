#!/bin/bash
# setup.sh

echo "Setting up Motion Media Controller..."

# Install system dependencies
echo "Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y python3-pip omxplayer feh

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

# Create service file for autostart
echo "Creating systemd service..."
cat << EOF | sudo tee /etc/systemd/system/motion-media.service
[Unit]
Description=Motion Media Controller
After=network.target

[Service]
ExecStart=/usr/bin/python3 $(pwd)/main.py
WorkingDirectory=$(pwd)
StandardOutput=inherit
StandardError=inherit
Restart=always
User=$USER

[Install]
WantedBy=multi-user.target
EOF

# Enable service
sudo systemctl enable motion-media.service

echo "Setup complete! To start the service now, run: sudo systemctl start motion-media.service"

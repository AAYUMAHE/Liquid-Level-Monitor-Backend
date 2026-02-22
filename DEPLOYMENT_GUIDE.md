# Deployment Guide: Liquid Level Measurement System

## Overview

This guide covers deploying the FastAPI-based liquid level measurement system:
1. Local system deployment (for testing)
2. Raspberry Pi deployment (for 24/7 production)
3. Domain and remote access setup

---

## Part 1: Local System Deployment

### Prerequisites

```bash
# Python 3.8+ required
python3 --version

# Create virtual environment
cd /apps/workspace/tt
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate     # Windows
```

### Install Dependencies

Create a `requirements.txt` file:

```txt
fastapi
uvicorn[standard]
opencv-python
numpy
pandas
matplotlib
scipy
scikit-learn
scikit-image
openpyxl
python-multipart
```

Install:

```bash
pip install -r requirements.txt
```

### Run Locally

```bash
# Development mode (with auto-reload)
python main.py
# OR
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Access at: `http://localhost:8000`

### Test Endpoints

```bash
# Health check
curl http://localhost:8000/

# Check camera
curl http://localhost:8000/check_camera?index=0
```

---

## Part 2: Raspberry Pi Deployment

### Key Differences from Local System

| Aspect | Local System | Raspberry Pi |
|--------|--------------|--------------|
| OpenCV | `opencv-python` | `opencv-python-headless` (no GUI) |
| Performance | Fast | Slower - may need optimization |
| Camera | USB/Webcam | Pi Camera or USB |
| Memory | Usually 8GB+ | 1-8GB (model dependent) |
| Auto-start | Manual | Use systemd service |

### Raspberry Pi Setup

#### 1. Install OS
- Use Raspberry Pi OS Lite (64-bit recommended)
- Enable SSH during setup

#### 2. System Dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv
sudo apt install -y libatlas-base-dev libhdf5-dev
sudo apt install -y libharfbuzz0b libwebp6 libtiff5 libjasper1
sudo apt install -y libqtgui4 libqt4-test  # For OpenCV
```

#### 3. Enable Camera (if using Pi Camera)

```bash
sudo raspi-config
# Interface Options -> Camera -> Enable
sudo reboot
```

#### 4. Project Setup

```bash
# Clone/copy your project
mkdir -p ~/liquid-level
cd ~/liquid-level

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies (use headless OpenCV for Pi)
pip install fastapi uvicorn[standard]
pip install opencv-python-headless  # NOT opencv-python
pip install numpy pandas matplotlib scipy
pip install scikit-learn scikit-image
pip install openpyxl python-multipart
```

#### 5. Performance Optimization for Pi

Edit `detector.py` - reduce `max_dim` for faster processing:

```python
# In PMI_Edge_Detector.__init__
self.detector = PMI_Edge_Detector(max_dim=50)  # Reduced from 100
```

Consider reducing eigenvectors:

```python
PMI_Edge_Detector(num_eigenvecs=3, max_dim=50)  # Faster
```

---

## Part 3: Running as a Service (24/7)

### Create Systemd Service

```bash
sudo nano /etc/systemd/system/liquid-level.service
```

Add:

```ini
[Unit]
Description=Liquid Level Measurement API
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/liquid-level
Environment="PATH=/home/pi/liquid-level/venv/bin"
ExecStart=/home/pi/liquid-level/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable liquid-level
sudo systemctl start liquid-level

# Check status
sudo systemctl status liquid-level

# View logs
journalctl -u liquid-level -f
```

---

## Part 4: Domain and Remote Access

### Option A: Port Forwarding (Simple, Less Secure)

1. Router settings: Forward port 8000 to Raspberry Pi's local IP
2. Get your public IP: `curl ifconfig.me`
3. Point domain A record to your public IP
4. Access via: `http://yourdomain.com:8000`

### Option B: Reverse Proxy with Nginx (Recommended)

```bash
sudo apt install nginx
sudo nano /etc/nginx/sites-available/liquid-level
```

Add:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }
}
```

Enable:

```bash
sudo ln -s /etc/nginx/sites-available/liquid-level /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Option C: Cloudflare Tunnel (Best for Home Network)

No port forwarding needed - works behind NAT.

```bash
# Install cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb

# Login and create tunnel
cloudflared tunnel login
cloudflared tunnel create liquid-level
cloudflared tunnel route dns liquid-level yourdomain.com

# Run tunnel
cloudflared tunnel run --url http://localhost:8000 liquid-level
```

### Add SSL (HTTPS)

With Nginx, use Certbot:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

---

## Part 5: Quick Deployment Checklist

### Local Testing
- [ ] Create virtual environment
- [ ] Install requirements
- [ ] Run `python main.py`
- [ ] Test at `http://localhost:8000`
- [ ] Test camera/video upload

### Raspberry Pi
- [ ] Install Raspberry Pi OS
- [ ] Enable SSH and Camera
- [ ] Install system dependencies
- [ ] Copy project files
- [ ] Use `opencv-python-headless`
- [ ] Create systemd service
- [ ] Test locally on Pi

### Remote Access
- [ ] Choose method (Port Forward / Nginx / Cloudflare)
- [ ] Configure DNS (A record or Cloudflare)
- [ ] Set up SSL certificate
- [ ] Test remote access

---

## Troubleshooting

### Camera not detected on Pi
```bash
# Check if camera is recognized
ls /dev/video*
vcgencmd get_camera  # For Pi Camera
```

### Out of memory on Pi
- Reduce `max_dim` in detector
- Add swap space:
```bash
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile  # Set CONF_SWAPSIZE=1024
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

### Service won't start
```bash
journalctl -u liquid-level -n 50 --no-pager
```

---

## Summary

**Is deployment the same on local and Raspberry Pi?**

Mostly yes, with these differences:
1. Use `opencv-python-headless` on Pi (no GUI needed)
2. May need to reduce `max_dim` for performance
3. Use systemd for 24/7 operation
4. Need reverse proxy (Nginx) or tunnel for domain access

**Recommended approach:**
1. Test fully on local system first
2. Deploy to Pi with performance adjustments
3. Use Cloudflare Tunnel for easiest domain setup (no port forwarding)

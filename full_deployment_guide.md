# Complete Deployment Guide: Liquid Level Monitor System

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Server Requirements](#2-server-requirements)
3. [Initial Server Setup](#3-initial-server-setup)
4. [Python Environment Setup](#4-python-environment-setup)
5. [Application Deployment](#5-application-deployment)
6. [Systemd Service Configuration](#6-systemd-service-configuration)
7. [Nginx Installation & Configuration](#7-nginx-installation--configuration)
8. [SSL Certificate Setup](#8-ssl-certificate-setup)
9. [Frontend Deployment](#9-frontend-deployment)
10. [Camera/Video Device Setup](#10-cameravideo-device-setup)
11. [Firewall Configuration](#11-firewall-configuration)
12. [Testing the Deployment](#12-testing-the-deployment)
13. [Monitoring & Logging](#13-monitoring--logging)
14. [Backup & Recovery](#14-backup--recovery)
15. [Performance Optimization](#15-performance-optimization)
16. [Security Hardening](#16-security-hardening)

---

## 1. System Overview

### 1.1 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                            INTERNET                                  │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         NGINX (Port 443/80)                          │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  - SSL Termination                                           │    │
│  │  - Static File Serving (Frontend)                            │    │
│  │  - Reverse Proxy to Backend                                  │    │
│  │  - Video Stream Optimization                                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
┌───────────────────────────┐   ┌───────────────────────────────────┐
│   Static Frontend         │   │   FastAPI Backend (Port 8000)     │
│   /var/www/xyz.com/html   │   │   /apps/workspace/tt              │
│   - Vue.js 3 SPA          │   │   ┌───────────────────────────┐   │
│   - index.html            │   │   │ Endpoints:                │   │
│   - CSS/JS assets         │   │   │ - /video_feed (streaming) │   │
└───────────────────────────┘   │   │ - /upload_video           │   │
                                │   │ - /start, /stop           │   │
                                │   │ - /level, /roi            │   │
                                │   └───────────────────────────┘   │
                                │              │                     │
                                │              ▼                     │
                                │   ┌───────────────────────────┐   │
                                │   │ Camera/Video Source       │   │
                                │   │ - /dev/video0             │   │
                                │   │ - uploaded_videos/        │   │
                                │   └───────────────────────────┘   │
                                └───────────────────────────────────┘
```

### 1.2 Technology Stack

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Backend | FastAPI | 0.100+ | REST API server |
| ASGI Server | Uvicorn | 0.23+ | Production server |
| Video Processing | OpenCV | 4.8+ | Camera capture, frame processing |
| Image Analysis | scikit-image | 0.21+ | Edge detection |
| Data Processing | NumPy, Pandas | Latest | Numerical computation |
| Web Server | Nginx | 1.18+ | Reverse proxy, SSL |
| SSL | Let's Encrypt | - | HTTPS certificates |
| Frontend | Vue.js 3 | 3.3+ | User interface |
| Process Manager | systemd | - | Service management |

### 1.3 Data Flow

```
Camera/Video → OpenCV Capture → Frame Processing → Edge Detection
                                       │
                                       ▼
                              Level Calculation → Results Storage
                                       │
                                       ▼
                              API Response → Frontend Display
```

---

## 2. Server Requirements

### 2.1 Minimum Hardware Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 2 GB | 4+ GB |
| Storage | 20 GB | 50+ GB (for video storage) |
| Network | 10 Mbps | 100+ Mbps |

### 2.2 Software Requirements

| Software | Required Version |
|----------|-----------------|
| Ubuntu | 20.04 LTS or 22.04 LTS |
| Python | 3.8+ |
| Nginx | 1.18+ |
| OpenSSL | 1.1.1+ |

### 2.3 Network Requirements

| Port | Protocol | Purpose |
|------|----------|---------|
| 22 | TCP | SSH access |
| 80 | TCP | HTTP (redirect to HTTPS) |
| 443 | TCP | HTTPS |

---

## 3. Initial Server Setup

### 3.1 Update System

```bash
# Update package lists
sudo apt update

# Upgrade installed packages
sudo apt upgrade -y

# Install essential tools
sudo apt install -y curl wget git vim htop unzip software-properties-common
```

### 3.2 Create Application User (Optional but Recommended)

```bash
# Create dedicated user for the application
sudo useradd -m -s /bin/bash liquidlevel

# Add to necessary groups
sudo usermod -aG sudo liquidlevel
sudo usermod -aG video liquidlevel

# Set password
sudo passwd liquidlevel
```

### 3.3 Set System Timezone

```bash
# Set timezone
sudo timedatectl set-timezone Asia/Kolkata  # Change to your timezone

# Verify
timedatectl
```

### 3.4 Configure System Limits

Edit `/etc/security/limits.conf`:

```bash
sudo nano /etc/security/limits.conf
```

Add these lines at the end:

```
# Increase file descriptors for video streaming
www-data soft nofile 65535
www-data hard nofile 65535
liquidlevel soft nofile 65535
liquidlevel hard nofile 65535
```

---

## 4. Python Environment Setup

### 4.1 Install Python and pip

```bash
# Install Python 3 and development tools
sudo apt install -y python3 python3-pip python3-venv python3-dev

# Verify installation
python3 --version
pip3 --version
```

### 4.2 Install System Dependencies for OpenCV

```bash
# OpenCV system dependencies
sudo apt install -y \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
    libgl1-mesa-glx \
    libgtk-3-0 \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    v4l-utils
```

### 4.3 Create Virtual Environment

```bash
# Navigate to application directory
cd /apps/workspace/tt

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### 4.4 Install Python Dependencies

Create a `requirements.txt` file:

```bash
cat > requirements.txt << 'EOF'
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
python-multipart>=0.0.6
opencv-python-headless>=4.8.0
numpy>=1.24.0
pandas>=2.0.0
matplotlib>=3.7.0
scipy>=1.10.0
scikit-learn>=1.3.0
scikit-image>=0.21.0
openpyxl>=3.1.0
EOF
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 4.5 Verify Installation

```bash
# Test Python imports
python3 -c "
import fastapi
import uvicorn
import cv2
import numpy
import pandas
import scipy
import sklearn
import skimage
print('All dependencies installed successfully!')
print(f'OpenCV version: {cv2.__version__}')
print(f'FastAPI version: {fastapi.__version__}')
"
```

---

## 5. Application Deployment

### 5.1 Clone/Copy Application Files

```bash
# Create application directory
sudo mkdir -p /apps/workspace/tt
sudo chown -R $USER:$USER /apps/workspace

# Copy your application files
# If using git:
# git clone <your-repo> /apps/workspace/tt

# Or copy manually:
# cp -r /path/to/your/files/* /apps/workspace/tt/
```

### 5.2 Directory Structure

Ensure your directory looks like this:

```
/apps/workspace/tt/
├── main.py                 # FastAPI application entry point
├── camera_service.py       # Camera handling service
├── detector.py             # PMI Edge Detector
├── analyzer.py             # Result analyzer
├── requirements.txt        # Python dependencies
├── venv/                   # Virtual environment
├── uploaded_videos/        # Directory for uploaded videos (will be created)
└── session_output/         # Directory for output files (will be created)
```

### 5.3 Create Required Directories

```bash
cd /apps/workspace/tt

# Create directories with proper permissions
mkdir -p uploaded_videos session_output

# Set permissions
chmod 755 uploaded_videos session_output
```

### 5.4 Test Application Locally

```bash
# Activate virtual environment
source /apps/workspace/tt/venv/bin/activate

# Run application
cd /apps/workspace/tt
python3 -m uvicorn main:app --host 127.0.0.1 --port 8000

# In another terminal, test:
curl http://127.0.0.1:8000/
# Should return: {"status":"ok","message":"Backend is running"}
```

---

## 6. Systemd Service Configuration

### 6.1 Create Service File

```bash
sudo nano /etc/systemd/system/liquidlevel.service
```

Add the following content:

```ini
[Unit]
Description=Liquid Level Monitor - FastAPI Backend
Documentation=https://github.com/your-repo
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/apps/workspace/tt

# Virtual environment Python
ExecStart=/apps/workspace/tt/venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1

# Restart policy
Restart=always
RestartSec=5
StartLimitInterval=60
StartLimitBurst=3

# Environment
Environment="PATH=/apps/workspace/tt/venv/bin:/usr/bin"
Environment="PYTHONUNBUFFERED=1"

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=liquidlevel

# Security
NoNewPrivileges=true
PrivateTmp=true

# Resource limits
LimitNOFILE=65535
MemoryMax=2G

[Install]
WantedBy=multi-user.target
```

### 6.2 Set Directory Permissions

```bash
# Change ownership to www-data
sudo chown -R www-data:www-data /apps/workspace/tt

# Set proper permissions
sudo chmod -R 755 /apps/workspace/tt
sudo chmod -R 775 /apps/workspace/tt/uploaded_videos
sudo chmod -R 775 /apps/workspace/tt/session_output
```

### 6.3 Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable liquidlevel

# Start the service
sudo systemctl start liquidlevel

# Check status
sudo systemctl status liquidlevel
```

### 6.4 Service Management Commands

```bash
# Start service
sudo systemctl start liquidlevel

# Stop service
sudo systemctl stop liquidlevel

# Restart service
sudo systemctl restart liquidlevel

# View logs
sudo journalctl -u liquidlevel -f

# View last 100 lines of logs
sudo journalctl -u liquidlevel -n 100

# View logs since today
sudo journalctl -u liquidlevel --since today
```

---

## 7. Nginx Installation & Configuration

### 7.1 Install Nginx

```bash
# Install Nginx
sudo apt install -y nginx

# Verify installation
nginx -v

# Start and enable Nginx
sudo systemctl start nginx
sudo systemctl enable nginx
```

### 7.2 Create Site Configuration

```bash
sudo nano /etc/nginx/sites-available/xyz.com
```

Add the complete configuration:

```nginx
# ============================================================
# LIQUID LEVEL MONITOR - NGINX CONFIGURATION
# Domain: xyz.com
# ============================================================

# Upstream backend server
upstream liquidlevel_backend {
    server 127.0.0.1:8000;
    keepalive 64;
}

# ============================================================
# HTTP Server - Redirect to HTTPS
# ============================================================
server {
    listen 80;
    listen [::]:80;
    server_name xyz.com www.xyz.com;

    # Redirect all HTTP traffic to HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }

    # Allow Let's Encrypt verification
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
}

# ============================================================
# HTTPS Server - Main Configuration
# ============================================================
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name xyz.com www.xyz.com;

    # ----------------------------------------------------------
    # SSL Configuration
    # ----------------------------------------------------------
    ssl_certificate /etc/letsencrypt/live/xyz.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/xyz.com/privkey.pem;
    ssl_trusted_certificate /etc/letsencrypt/live/xyz.com/chain.pem;

    # SSL Session settings
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;

    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # OCSP Stapling
    ssl_stapling on;
    ssl_stapling_verify on;
    resolver 8.8.8.8 8.8.4.4 valid=300s;
    resolver_timeout 5s;

    # ----------------------------------------------------------
    # General Server Settings
    # ----------------------------------------------------------

    # Document root for frontend
    root /var/www/xyz.com/html;
    index index.html;

    # Logging
    access_log /var/log/nginx/xyz.com.access.log;
    error_log /var/log/nginx/xyz.com.error.log;

    # Client settings for large uploads
    client_max_body_size 500M;
    client_body_timeout 600s;
    client_header_timeout 60s;
    client_body_buffer_size 128k;
    client_body_temp_path /tmp/nginx_uploads;

    # Proxy timeouts (default for non-streaming)
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;

    # ----------------------------------------------------------
    # Security Headers
    # ----------------------------------------------------------
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # ----------------------------------------------------------
    # Frontend - Static Files
    # ----------------------------------------------------------
    location / {
        try_files $uri $uri/ /index.html;

        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # ----------------------------------------------------------
    # API: Video Feed (MJPEG Streaming) - CRITICAL CONFIGURATION
    # ----------------------------------------------------------
    location = /video_feed {
        proxy_pass http://liquidlevel_backend/video_feed;
        proxy_http_version 1.1;

        # Headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";

        # *** CRITICAL: Disable all buffering for live streaming ***
        proxy_buffering off;
        proxy_cache off;
        proxy_request_buffering off;

        # *** CRITICAL: Extended timeouts for long-lived stream ***
        proxy_connect_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_read_timeout 3600s;

        # *** CRITICAL: Disable compression for binary stream ***
        gzip off;

        # Enable chunked transfer
        chunked_transfer_encoding on;

        # TCP optimizations
        tcp_nodelay on;
        tcp_nopush off;
    }

    # ----------------------------------------------------------
    # API: Video Upload - Large File Handling
    # ----------------------------------------------------------
    location = /upload_video {
        proxy_pass http://liquidlevel_backend/upload_video;
        proxy_http_version 1.1;

        # Headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Large file upload settings
        client_max_body_size 500M;
        proxy_request_buffering off;

        # Extended timeouts for large uploads
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }

    # ----------------------------------------------------------
    # API: Frame Capture (for ROI selection)
    # ----------------------------------------------------------
    location = /capture_frame {
        proxy_pass http://liquidlevel_backend/capture_frame;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Frame capture may take time
        proxy_read_timeout 30s;
    }

    # ----------------------------------------------------------
    # API: Download Report
    # ----------------------------------------------------------
    location = /download_report {
        proxy_pass http://liquidlevel_backend/download_report;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Enable buffering for file downloads
        proxy_buffering on;
        proxy_buffer_size 128k;
        proxy_buffers 4 256k;
        proxy_busy_buffers_size 256k;
    }

    # ----------------------------------------------------------
    # API: All Other Endpoints
    # ----------------------------------------------------------
    location ~ ^/(start|stop|set_zero|level|check_camera|set_roi|clear_roi|roi)$ {
        proxy_pass http://liquidlevel_backend;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # ----------------------------------------------------------
    # Health Check Endpoint
    # ----------------------------------------------------------
    location = /health {
        proxy_pass http://liquidlevel_backend/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    # ----------------------------------------------------------
    # Deny access to hidden files
    # ----------------------------------------------------------
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
```

### 7.3 Enable Site Configuration

```bash
# Create symbolic link to enable site
sudo ln -s /etc/nginx/sites-available/xyz.com /etc/nginx/sites-enabled/

# Remove default site (optional)
sudo rm /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# If test passes, reload Nginx
sudo systemctl reload nginx
```

### 7.4 Create Frontend Directory

```bash
# Create directory for frontend files
sudo mkdir -p /var/www/xyz.com/html

# Set ownership
sudo chown -R www-data:www-data /var/www/xyz.com

# Create temporary index.html for testing
echo "<h1>Site is working!</h1>" | sudo tee /var/www/xyz.com/html/index.html
```

---

## 8. SSL Certificate Setup

### 8.1 Install Certbot

```bash
# Install Certbot with Nginx plugin
sudo apt install -y certbot python3-certbot-nginx
```

### 8.2 Obtain SSL Certificate

```bash
# Get certificate (interactive)
sudo certbot --nginx -d xyz.com -d www.xyz.com

# Or non-interactive:
sudo certbot --nginx -d xyz.com -d www.xyz.com \
    --non-interactive \
    --agree-tos \
    --email your-email@example.com \
    --redirect
```

### 8.3 Verify Auto-Renewal

```bash
# Test renewal process
sudo certbot renew --dry-run

# Check renewal timer
sudo systemctl status certbot.timer
```

### 8.4 Manual Certificate Renewal

```bash
# Force renewal
sudo certbot renew --force-renewal

# Reload Nginx after renewal
sudo systemctl reload nginx
```

---

## 9. Frontend Deployment

### 9.1 Prepare Frontend Code

First, update the backend URL in your Vue.js code. Edit the `frontendcode` file:

```javascript
// Find this line:
const backendUrl = "https://hire.aayushkundalwal.tech"

// Change to:
const backendUrl = "https://xyz.com"
```

### 9.2 Option A: Deploy as Single HTML File

If your frontend is a single Vue component file:

```bash
# Create the frontend HTML file
sudo nano /var/www/xyz.com/html/index.html
```

Create a complete HTML file with Vue 3 CDN:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Liquid Level Monitor</title>
    <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
    <script src="https://unpkg.com/axios/dist/axios.min.js"></script>
    <!-- Your styles here -->
</head>
<body>
    <div id="app">
        <!-- Your Vue template here -->
    </div>
    <script>
        // Your Vue.js code here
    </script>
</body>
</html>
```

### 9.3 Option B: Build Vue Project

If you have a full Vue.js project:

```bash
# Install Node.js if not installed
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Navigate to your frontend project
cd /path/to/your/vue-project

# Install dependencies
npm install

# Update backend URL in your .env or config file
echo "VITE_API_URL=https://xyz.com" > .env.production

# Build for production
npm run build

# Copy built files to Nginx web root
sudo cp -r dist/* /var/www/xyz.com/html/
```

### 9.4 Set Permissions

```bash
# Set proper ownership
sudo chown -R www-data:www-data /var/www/xyz.com

# Set permissions
sudo chmod -R 755 /var/www/xyz.com
```

---

## 10. Camera/Video Device Setup

### 10.1 Check Camera Availability

```bash
# List video devices
ls -la /dev/video*

# Get detailed info about video device
v4l2-ctl --list-devices

# Check camera capabilities
v4l2-ctl -d /dev/video0 --all
```

### 10.2 Grant Camera Access

```bash
# Add www-data to video group
sudo usermod -aG video www-data

# Verify group membership
groups www-data

# Set device permissions
sudo chmod 666 /dev/video0

# Make permission persistent with udev rule
echo 'KERNEL=="video[0-9]*", MODE="0666"' | sudo tee /etc/udev/rules.d/99-webcam.rules

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### 10.3 Restart Service After Camera Setup

```bash
# Restart the backend service
sudo systemctl restart liquidlevel

# Check if camera is accessible
curl http://localhost:8000/check_camera
```

---

## 11. Firewall Configuration

### 11.1 UFW Setup

```bash
# Enable UFW
sudo ufw enable

# Allow SSH
sudo ufw allow ssh

# Allow Nginx (HTTP and HTTPS)
sudo ufw allow 'Nginx Full'

# Check status
sudo ufw status verbose
```

### 11.2 Expected Output

```
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
80/tcp                     ALLOW       Anywhere
443/tcp                    ALLOW       Anywhere
22/tcp (v6)                ALLOW       Anywhere (v6)
80/tcp (v6)                ALLOW       Anywhere (v6)
443/tcp (v6)               ALLOW       Anywhere (v6)
```

---

## 12. Testing the Deployment

### 12.1 Test Backend Directly

```bash
# Health check
curl http://localhost:8000/

# Check camera
curl http://localhost:8000/check_camera

# Test video feed headers
curl -I http://localhost:8000/video_feed
```

### 12.2 Test Through Nginx

```bash
# Test HTTPS
curl -I https://xyz.com/

# Test backend proxy
curl https://xyz.com/health

# Test video feed headers
curl -I https://xyz.com/video_feed
```

### 12.3 Browser Testing

1. Open `https://xyz.com` in your browser
2. Check browser console for errors (F12 → Console)
3. Test video feed by clicking "Start"
4. Test video upload functionality
5. Verify ROI selection works

### 12.4 Test Video Streaming

```bash
# Test streaming with timeout
timeout 5 curl -s https://xyz.com/video_feed | head -c 1000

# Should output binary JPEG data
```

---

## 13. Monitoring & Logging

### 13.1 View Backend Logs

```bash
# Live logs
sudo journalctl -u liquidlevel -f

# Last 100 lines
sudo journalctl -u liquidlevel -n 100

# Logs from specific time
sudo journalctl -u liquidlevel --since "2024-01-01 00:00:00"

# Error logs only
sudo journalctl -u liquidlevel -p err
```

### 13.2 View Nginx Logs

```bash
# Access log
sudo tail -f /var/log/nginx/xyz.com.access.log

# Error log
sudo tail -f /var/log/nginx/xyz.com.error.log

# Combined view
sudo tail -f /var/log/nginx/*.log
```

### 13.3 System Monitoring

```bash
# CPU and memory usage
htop

# Disk usage
df -h

# Network connections
ss -tulpn

# Process list
ps aux | grep -E "(python|nginx|uvicorn)"
```

---

## 14. Backup & Recovery

### 14.1 Backup Script

Create `/opt/backup-liquidlevel.sh`:

```bash
#!/bin/bash

BACKUP_DIR="/backups/liquidlevel"
DATE=$(date +%Y%m%d_%H%M%S)
APP_DIR="/apps/workspace/tt"

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup application files
tar -czf $BACKUP_DIR/app_$DATE.tar.gz -C $APP_DIR .

# Backup Nginx config
cp /etc/nginx/sites-available/xyz.com $BACKUP_DIR/nginx_$DATE.conf

# Backup systemd service
cp /etc/systemd/system/liquidlevel.service $BACKUP_DIR/service_$DATE.service

# Keep only last 7 days of backups
find $BACKUP_DIR -mtime +7 -delete

echo "Backup completed: $DATE"
```

### 14.2 Schedule Backups

```bash
# Make script executable
sudo chmod +x /opt/backup-liquidlevel.sh

# Add to crontab (daily at 2 AM)
echo "0 2 * * * /opt/backup-liquidlevel.sh >> /var/log/backup.log 2>&1" | sudo tee -a /etc/crontab
```

---

## 15. Performance Optimization

### 15.1 Nginx Optimization

Edit `/etc/nginx/nginx.conf`:

```nginx
worker_processes auto;
worker_rlimit_nofile 65535;

events {
    worker_connections 4096;
    use epoll;
    multi_accept on;
}

http {
    # Basic settings
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;

    # Buffer sizes
    client_body_buffer_size 128k;
    client_max_body_size 500m;
    client_header_buffer_size 1k;
    large_client_header_buffers 4 16k;

    # Gzip (disabled for streaming, enabled for static)
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml application/json application/javascript application/xml;

    # Include site configs
    include /etc/nginx/sites-enabled/*;
}
```

### 15.2 System Optimization

Edit `/etc/sysctl.conf`:

```bash
# Network optimizations
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_tw_reuse = 1
```

Apply changes:

```bash
sudo sysctl -p
```

---

## 16. Security Hardening

### 16.1 SSH Security

Edit `/etc/ssh/sshd_config`:

```bash
# Disable root login
PermitRootLogin no

# Disable password authentication (use keys)
PasswordAuthentication no

# Limit users
AllowUsers your-username
```

### 16.2 Fail2Ban Setup

```bash
# Install fail2ban
sudo apt install -y fail2ban

# Create local config
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local

# Edit config
sudo nano /etc/fail2ban/jail.local
```

Add Nginx protection:

```ini
[nginx-http-auth]
enabled = true
port = http,https
filter = nginx-http-auth
logpath = /var/log/nginx/error.log
maxretry = 3
bantime = 3600

[nginx-limit-req]
enabled = true
port = http,https
filter = nginx-limit-req
logpath = /var/log/nginx/error.log
maxretry = 10
bantime = 7200
```

### 16.3 Automatic Security Updates

```bash
# Install unattended-upgrades
sudo apt install -y unattended-upgrades

# Enable automatic updates
sudo dpkg-reconfigure -plow unattended-upgrades
```

---

## Final Checklist

- [ ] Server updated and secured
- [ ] Python environment set up with all dependencies
- [ ] Application files deployed
- [ ] Systemd service created and running
- [ ] Nginx installed and configured
- [ ] SSL certificate obtained and configured
- [ ] Frontend deployed
- [ ] Camera permissions configured
- [ ] Firewall configured
- [ ] All endpoints tested
- [ ] Monitoring set up
- [ ] Backups configured

---

## Quick Reference Commands

```bash
# Service management
sudo systemctl status liquidlevel
sudo systemctl restart liquidlevel
sudo journalctl -u liquidlevel -f

# Nginx management
sudo nginx -t
sudo systemctl reload nginx
sudo tail -f /var/log/nginx/error.log

# SSL renewal
sudo certbot renew

# Test endpoints
curl https://xyz.com/
curl https://xyz.com/check_camera
curl -I https://xyz.com/video_feed
```

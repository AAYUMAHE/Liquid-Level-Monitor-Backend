# Nginx Troubleshooting Guide

## Table of Contents

1. [Quick Diagnostics](#1-quick-diagnostics)
2. [Common Errors & Solutions](#2-common-errors--solutions)
3. [Video Streaming Issues](#3-video-streaming-issues)
4. [File Upload Issues](#4-file-upload-issues)
5. [SSL/HTTPS Issues](#5-sslhttps-issues)
6. [Proxy Issues](#6-proxy-issues)
7. [Performance Issues](#7-performance-issues)
8. [Connection Issues](#8-connection-issues)
9. [CORS Issues](#9-cors-issues)
10. [Debug Mode & Advanced Diagnostics](#10-debug-mode--advanced-diagnostics)
11. [Configuration Validation](#11-configuration-validation)
12. [Log Analysis](#12-log-analysis)
13. [Common Nginx Misconfigurations](#13-common-nginx-misconfigurations)
14. [Emergency Recovery](#14-emergency-recovery)

---

## 1. Quick Diagnostics

### 1.1 Essential Commands

```bash
# Check if Nginx is running
sudo systemctl status nginx

# Test configuration syntax
sudo nginx -t

# Reload configuration (graceful)
sudo systemctl reload nginx

# Restart Nginx (harder restart)
sudo systemctl restart nginx

# View error log (live)
sudo tail -f /var/log/nginx/error.log

# View access log (live)
sudo tail -f /var/log/nginx/access.log

# Check what ports Nginx is listening on
sudo ss -tlpn | grep nginx

# Check Nginx process
ps aux | grep nginx
```

### 1.2 Quick Health Check Script

Create `/opt/nginx-health-check.sh`:

```bash
#!/bin/bash

echo "=== NGINX HEALTH CHECK ==="
echo ""

# Check if running
echo "1. Service Status:"
systemctl is-active nginx && echo "   OK: Nginx is running" || echo "   ERROR: Nginx is not running"

# Test config
echo ""
echo "2. Configuration Test:"
nginx -t 2>&1 | head -2

# Check ports
echo ""
echo "3. Listening Ports:"
ss -tlpn | grep nginx

# Check backend
echo ""
echo "4. Backend Connection:"
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/ && echo "   OK: Backend responding" || echo "   ERROR: Backend not responding"

# Check disk space
echo ""
echo "5. Disk Space:"
df -h / | tail -1

# Recent errors
echo ""
echo "6. Recent Errors (last 5):"
tail -5 /var/log/nginx/error.log

echo ""
echo "=== END HEALTH CHECK ==="
```

---

## 2. Common Errors & Solutions

### 2.1 Error: "nginx: [emerg] bind() to 0.0.0.0:80 failed (98: Address already in use)"

**Cause:** Another process is using port 80

**Solution:**

```bash
# Find what's using port 80
sudo lsof -i :80

# Or
sudo ss -tlpn | grep :80

# Kill the process or stop the service
sudo systemctl stop apache2  # If Apache is running

# Or force kill
sudo fuser -k 80/tcp
```

### 2.2 Error: "nginx: [emerg] open() '/etc/nginx/sites-enabled/xyz.com' failed (2: No such file or directory)"

**Cause:** Symbolic link is broken or file doesn't exist

**Solution:**

```bash
# Remove broken link
sudo rm /etc/nginx/sites-enabled/xyz.com

# Recreate symbolic link
sudo ln -s /etc/nginx/sites-available/xyz.com /etc/nginx/sites-enabled/

# Verify
ls -la /etc/nginx/sites-enabled/
```

### 2.3 Error: "nginx: [emerg] unknown directive 'proxy_pass'"

**Cause:** Missing `ngx_http_proxy_module` or syntax error

**Solution:**

```bash
# Check if proxy module is installed
nginx -V 2>&1 | grep -o 'http_proxy_module'

# If missing, reinstall nginx-full
sudo apt install nginx-full

# Common syntax errors:
# - Missing semicolon at end of line
# - Typo in directive name
# - Wrong context (proxy_pass in wrong block)
```

### 2.4 Error: "502 Bad Gateway"

**Cause:** Backend server is not responding

**Solution:**

```bash
# Check if backend is running
sudo systemctl status liquidlevel

# Test backend directly
curl -v http://127.0.0.1:8000/

# Check if backend port is listening
ss -tlpn | grep 8000

# If backend is down, start it
sudo systemctl start liquidlevel

# Check backend logs
sudo journalctl -u liquidlevel -n 50
```

### 2.5 Error: "504 Gateway Timeout"

**Cause:** Backend is taking too long to respond

**Solution:**

```nginx
# Increase timeout values in nginx config
location /api/ {
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
}
```

### 2.6 Error: "413 Request Entity Too Large"

**Cause:** Upload file size exceeds limit

**Solution:**

```nginx
# In http, server, or location block
client_max_body_size 500M;

# For upload-specific location
location /upload_video {
    client_max_body_size 500M;
    # ... other config
}
```

After changing, reload nginx:
```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## 3. Video Streaming Issues

### 3.1 Issue: Video Feed Not Loading

**Symptoms:**
- Blank video container
- Browser shows "waiting for server"
- Video loads but is extremely slow

**Diagnostic Steps:**

```bash
# Test video feed directly
curl -I http://127.0.0.1:8000/video_feed

# Expected response:
# HTTP/1.1 200 OK
# content-type: multipart/x-mixed-replace; boundary=frame

# Test through Nginx
curl -I https://xyz.com/video_feed
```

**Solution - Complete Video Streaming Config:**

```nginx
location = /video_feed {
    proxy_pass http://127.0.0.1:8000/video_feed;
    proxy_http_version 1.1;

    # Essential headers
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header Connection "";

    # CRITICAL: Disable all buffering
    proxy_buffering off;
    proxy_cache off;
    proxy_request_buffering off;

    # CRITICAL: Long timeouts
    proxy_connect_timeout 3600s;
    proxy_send_timeout 3600s;
    proxy_read_timeout 3600s;

    # CRITICAL: No compression
    gzip off;

    # Chunked encoding
    chunked_transfer_encoding on;

    # TCP optimizations
    tcp_nodelay on;
}
```

### 3.2 Issue: Video Stream is Choppy/Laggy

**Cause:** Buffering is enabled or buffer sizes are wrong

**Solution:**

```nginx
# Add to video_feed location
proxy_buffering off;
proxy_buffer_size 0;

# Also check if gzip is interfering
gzip off;
```

### 3.3 Issue: Video Stream Disconnects After 60 Seconds

**Cause:** Default proxy timeout

**Solution:**

```nginx
# Increase all timeouts
proxy_connect_timeout 3600s;
proxy_send_timeout 3600s;
proxy_read_timeout 3600s;

# Also add keepalive
proxy_set_header Connection "";
```

### 3.4 Issue: "Mixed Content" Error in Browser

**Cause:** Frontend using HTTPS, but video feed URL is HTTP

**Solution:**

```javascript
// In frontend code, ensure URL uses same protocol
const backendUrl = "https://xyz.com"  // Not http://

// Or use protocol-relative
const backendUrl = "//xyz.com"
```

### 3.5 Debug Video Streaming

```bash
# Test raw stream for 5 seconds
timeout 5 curl -s http://127.0.0.1:8000/video_feed > /tmp/video_test.bin
ls -la /tmp/video_test.bin

# Check if receiving data
timeout 5 curl -s http://127.0.0.1:8000/video_feed | wc -c

# Should return a number > 0 (bytes received)

# Check stream headers
curl -I -s http://127.0.0.1:8000/video_feed | head -20
```

---

## 4. File Upload Issues

### 4.1 Issue: Upload Fails with 413 Error

**Complete Solution:**

```nginx
# In http block (global)
http {
    client_max_body_size 500M;
}

# In server block
server {
    client_max_body_size 500M;
    client_body_timeout 600s;
    client_body_buffer_size 128k;
}

# In specific location
location = /upload_video {
    client_max_body_size 500M;
    proxy_request_buffering off;

    proxy_pass http://127.0.0.1:8000/upload_video;
    proxy_http_version 1.1;

    proxy_connect_timeout 600s;
    proxy_send_timeout 600s;
    proxy_read_timeout 600s;
}
```

### 4.2 Issue: Upload Times Out

**Solution:**

```nginx
location = /upload_video {
    # Increase all timeouts
    client_body_timeout 600s;
    proxy_connect_timeout 600s;
    proxy_send_timeout 600s;
    proxy_read_timeout 600s;

    # Stream directly to backend (don't buffer)
    proxy_request_buffering off;

    # ... rest of config
}
```

### 4.3 Issue: "Disk Full" or Temp File Errors

**Cause:** Nginx temp directory is full

**Solution:**

```bash
# Check temp directory
ls -la /var/lib/nginx/body/

# Clean up
sudo rm -rf /var/lib/nginx/body/*

# Configure different temp path in nginx.conf
client_body_temp_path /tmp/nginx_uploads 1 2;

# Ensure directory exists and has permissions
sudo mkdir -p /tmp/nginx_uploads
sudo chown www-data:www-data /tmp/nginx_uploads
```

### 4.4 Issue: Upload Works Locally But Not Through Nginx

**Debug Steps:**

```bash
# Test direct upload to backend
curl -X POST -F "file=@/path/to/video.mp4" http://127.0.0.1:8000/upload_video

# Test through Nginx
curl -X POST -F "file=@/path/to/video.mp4" https://xyz.com/upload_video

# Check Nginx error log
tail -f /var/log/nginx/error.log
```

---

## 5. SSL/HTTPS Issues

### 5.1 Issue: "SSL: error:0A000086:SSL routines::certificate verify failed"

**Cause:** SSL certificate issues

**Solution:**

```bash
# Check certificate validity
sudo openssl x509 -in /etc/letsencrypt/live/xyz.com/fullchain.pem -text -noout | grep -A2 "Validity"

# Renew certificate
sudo certbot renew --force-renewal

# Reload Nginx
sudo systemctl reload nginx
```

### 5.2 Issue: "NET::ERR_CERT_DATE_INVALID"

**Cause:** Certificate expired

**Solution:**

```bash
# Check expiration
sudo certbot certificates

# Renew
sudo certbot renew

# Test renewal
sudo certbot renew --dry-run
```

### 5.3 Issue: "SSL_ERROR_RX_RECORD_TOO_LONG"

**Cause:** HTTPS request sent to HTTP port

**Solution:**

```nginx
# Ensure server is listening on 443 with ssl
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;

    ssl_certificate /etc/letsencrypt/live/xyz.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/xyz.com/privkey.pem;
}
```

### 5.4 Issue: Mixed Content Warnings

**Cause:** HTTP resources on HTTPS page

**Solution:**

```nginx
# Add upgrade-insecure-requests header
add_header Content-Security-Policy "upgrade-insecure-requests" always;

# Or in frontend, ensure all URLs use https://
```

### 5.5 SSL Debug Commands

```bash
# Test SSL configuration
openssl s_client -connect xyz.com:443 -servername xyz.com

# Check certificate chain
openssl s_client -connect xyz.com:443 -showcerts

# Test SSL/TLS versions
nmap --script ssl-enum-ciphers -p 443 xyz.com

# Online test
# Use https://www.ssllabs.com/ssltest/
```

---

## 6. Proxy Issues

### 6.1 Issue: "upstream prematurely closed connection"

**Cause:** Backend closed connection unexpectedly

**Solution:**

```nginx
# Increase keepalive connections
upstream liquidlevel_backend {
    server 127.0.0.1:8000;
    keepalive 64;
}

location /api/ {
    proxy_http_version 1.1;
    proxy_set_header Connection "";
}
```

### 6.2 Issue: Request Headers Not Reaching Backend

**Solution:**

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8000;

    # Pass all important headers
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Port $server_port;

    # Pass original request headers
    proxy_pass_request_headers on;
}
```

### 6.3 Issue: Response Headers Missing

**Solution:**

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8000;

    # Don't hide upstream headers
    proxy_pass_header Server;
    proxy_pass_header X-Custom-Header;

    # Or pass all headers
    proxy_hide_header "";
}
```

### 6.4 Issue: Backend Returns Wrong URL in Redirects

**Solution:**

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8000/;

    # Fix redirects
    proxy_redirect http://127.0.0.1:8000/ https://xyz.com/;
    proxy_redirect http://localhost:8000/ https://xyz.com/;
}
```

---

## 7. Performance Issues

### 7.1 Issue: High CPU Usage

**Diagnosis:**

```bash
# Check Nginx processes
ps aux | grep nginx

# Check worker processes
top -p $(pgrep -d',' nginx)
```

**Solution:**

```nginx
# nginx.conf
worker_processes auto;  # Use number of CPU cores
worker_cpu_affinity auto;

events {
    worker_connections 4096;
    use epoll;
    multi_accept on;
}
```

### 7.2 Issue: High Memory Usage

**Solution:**

```nginx
# Limit buffer sizes
proxy_buffer_size 4k;
proxy_buffers 8 4k;
proxy_busy_buffers_size 8k;

# For streaming, disable buffers entirely
proxy_buffering off;
```

### 7.3 Issue: Slow Response Times

**Diagnosis:**

```bash
# Check response time through Nginx
time curl -o /dev/null -s -w "%{time_total}\n" https://xyz.com/

# Check response time directly to backend
time curl -o /dev/null -s -w "%{time_total}\n" http://127.0.0.1:8000/
```

**Solution:**

```nginx
# Enable keepalive to backend
upstream backend {
    server 127.0.0.1:8000;
    keepalive 64;
}

# Enable caching for static content
location ~* \.(js|css|png|jpg|jpeg|gif|ico)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}

# Enable gzip for text content
gzip on;
gzip_types text/plain application/json application/javascript text/css;
```

### 7.4 Issue: Connection Limits Reached

**Diagnosis:**

```bash
# Check current connections
ss -s

# Check Nginx connection status
curl http://localhost/nginx_status  # If stub_status is enabled
```

**Solution:**

```nginx
# Increase limits in nginx.conf
worker_rlimit_nofile 65535;

events {
    worker_connections 8192;
}

# In server block
limit_conn_zone $binary_remote_addr zone=conn_limit:10m;
limit_conn conn_limit 100;
```

Also increase system limits:

```bash
# Edit /etc/security/limits.conf
www-data soft nofile 65535
www-data hard nofile 65535

# Edit /etc/sysctl.conf
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535

# Apply
sudo sysctl -p
```

---

## 8. Connection Issues

### 8.1 Issue: "Connection Refused"

**Diagnosis:**

```bash
# Check if Nginx is running
systemctl status nginx

# Check if listening on port
ss -tlpn | grep -E ':80|:443'

# Check firewall
sudo ufw status
```

**Solution:**

```bash
# Start Nginx if not running
sudo systemctl start nginx

# Check for port conflicts
sudo lsof -i :80

# Open firewall ports
sudo ufw allow 'Nginx Full'
```

### 8.2 Issue: "Connection Timed Out"

**Diagnosis:**

```bash
# Check if server is reachable
ping xyz.com

# Check DNS
nslookup xyz.com

# Check route
traceroute xyz.com
```

**Solution:**

```bash
# Check DNS settings
cat /etc/resolv.conf

# Check firewall from outside
# (Use external tool or different network)
nmap -p 80,443 xyz.com
```

### 8.3 Issue: "Connection Reset by Peer"

**Cause:** Usually backend or Nginx closing connection

**Solution:**

```nginx
# Increase keepalive
keepalive_timeout 65;

# Add to upstream
upstream backend {
    server 127.0.0.1:8000;
    keepalive 64;
}

# Use HTTP 1.1
proxy_http_version 1.1;
proxy_set_header Connection "";
```

---

## 9. CORS Issues

### 9.1 Issue: "Access-Control-Allow-Origin" Missing

**Complete CORS Solution:**

```nginx
# In server or location block
location /api/ {
    # Handle preflight requests
    if ($request_method = 'OPTIONS') {
        add_header 'Access-Control-Allow-Origin' '*' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization' always;
        add_header 'Access-Control-Max-Age' 1728000;
        add_header 'Content-Type' 'text/plain; charset=utf-8';
        add_header 'Content-Length' 0;
        return 204;
    }

    # Add CORS headers to all responses
    add_header 'Access-Control-Allow-Origin' '*' always;
    add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
    add_header 'Access-Control-Allow-Headers' 'DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization' always;
    add_header 'Access-Control-Expose-Headers' 'Content-Length,Content-Range' always;

    proxy_pass http://127.0.0.1:8000;
    # ... rest of proxy config
}
```

### 9.2 Issue: CORS Works for GET but Not POST

**Cause:** Preflight (OPTIONS) request failing

**Solution:**

Make sure OPTIONS requests are handled before proxy_pass:

```nginx
location /api/ {
    # OPTIONS must be first
    if ($request_method = 'OPTIONS') {
        add_header 'Access-Control-Allow-Origin' '*';
        add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS';
        add_header 'Access-Control-Allow-Headers' 'Content-Type';
        return 204;
    }

    # Then proxy other requests
    proxy_pass http://127.0.0.1:8000;
}
```

### 9.3 Issue: CORS Headers Duplicated

**Cause:** Backend also sending CORS headers

**Solution:**

Either remove CORS from Nginx or from backend (FastAPI), not both.

To remove backend headers in Nginx:

```nginx
proxy_hide_header 'Access-Control-Allow-Origin';
proxy_hide_header 'Access-Control-Allow-Methods';
# Then add your own
add_header 'Access-Control-Allow-Origin' '*' always;
```

---

## 10. Debug Mode & Advanced Diagnostics

### 10.1 Enable Debug Logging

```nginx
# In nginx.conf or server block
error_log /var/log/nginx/error.log debug;

# Or for specific location only
location /api/ {
    error_log /var/log/nginx/api-debug.log debug;
}
```

**Warning:** Debug logging generates huge log files. Disable after debugging:

```nginx
error_log /var/log/nginx/error.log warn;
```

### 10.2 Log Request/Response Details

```nginx
# Custom log format
log_format detailed '$remote_addr - $remote_user [$time_local] '
                    '"$request" $status $body_bytes_sent '
                    '"$http_referer" "$http_user_agent" '
                    'rt=$request_time uct="$upstream_connect_time" '
                    'uht="$upstream_header_time" urt="$upstream_response_time"';

access_log /var/log/nginx/detailed.log detailed;
```

### 10.3 Test Specific Requests

```bash
# Verbose curl
curl -v https://xyz.com/video_feed 2>&1 | head -50

# Show only headers
curl -I https://xyz.com/

# Show timing
curl -w "@curl-format.txt" -o /dev/null -s https://xyz.com/

# Create curl-format.txt:
cat > /tmp/curl-format.txt << 'EOF'
    time_namelookup:  %{time_namelookup}s\n
       time_connect:  %{time_connect}s\n
    time_appconnect:  %{time_appconnect}s\n
   time_pretransfer:  %{time_pretransfer}s\n
      time_redirect:  %{time_redirect}s\n
 time_starttransfer:  %{time_starttransfer}s\n
                    ----------\n
         time_total:  %{time_total}s\n
EOF

curl -w "@/tmp/curl-format.txt" -o /dev/null -s https://xyz.com/
```

### 10.4 Monitor Connections in Real-Time

```bash
# Watch active connections
watch -n 1 'ss -s'

# Watch Nginx status (if enabled)
watch -n 1 'curl -s http://localhost/nginx_status'

# Watch error log
tail -f /var/log/nginx/error.log | grep -E 'error|crit|alert|emerg'
```

---

## 11. Configuration Validation

### 11.1 Syntax Check

```bash
# Basic syntax check
sudo nginx -t

# Verbose output
sudo nginx -T

# Check specific config file
sudo nginx -c /etc/nginx/nginx.conf -t
```

### 11.2 Common Syntax Errors

**Missing semicolon:**
```nginx
# Wrong
proxy_pass http://backend

# Correct
proxy_pass http://backend;
```

**Wrong context:**
```nginx
# Wrong (proxy_pass in http block)
http {
    proxy_pass http://backend;  # ERROR
}

# Correct (proxy_pass in location block)
http {
    server {
        location / {
            proxy_pass http://backend;  # OK
        }
    }
}
```

**Duplicate location:**
```nginx
# Wrong - duplicate locations
location /api/ { }
location /api/ { }  # ERROR

# Correct - unique locations
location /api/ { }
location /api/v2/ { }
```

### 11.3 Configuration Linting Tools

```bash
# Install gixy (Nginx config analyzer)
pip install gixy

# Run analysis
gixy /etc/nginx/nginx.conf

# Check for security issues
gixy --help
```

---

## 12. Log Analysis

### 12.1 Common Log Locations

```bash
/var/log/nginx/access.log      # Access log
/var/log/nginx/error.log       # Error log
/var/log/nginx/xyz.com.access.log  # Site-specific access
/var/log/nginx/xyz.com.error.log   # Site-specific errors
```

### 12.2 Log Analysis Commands

```bash
# Top 10 IPs by requests
awk '{print $1}' /var/log/nginx/access.log | sort | uniq -c | sort -rn | head -10

# Top 10 requested URLs
awk '{print $7}' /var/log/nginx/access.log | sort | uniq -c | sort -rn | head -10

# HTTP status code distribution
awk '{print $9}' /var/log/nginx/access.log | sort | uniq -c | sort -rn

# Find 500 errors
grep '" 500 ' /var/log/nginx/access.log

# Find slow requests (>5s)
awk '$NF > 5' /var/log/nginx/access.log

# Errors in last hour
awk -v date="$(date -d '1 hour ago' '+%d/%b/%Y:%H')" '$4 ~ date' /var/log/nginx/error.log
```

### 12.3 Real-Time Log Monitoring

```bash
# Monitor errors only
tail -f /var/log/nginx/error.log

# Monitor specific status codes
tail -f /var/log/nginx/access.log | grep --line-buffered '" 50[0-9] '

# Monitor specific endpoint
tail -f /var/log/nginx/access.log | grep --line-buffered '/video_feed'

# Combined monitoring
multitail /var/log/nginx/error.log /var/log/nginx/access.log
```

### 12.4 Log Rotation

Check log rotation config:

```bash
cat /etc/logrotate.d/nginx
```

Default configuration:

```
/var/log/nginx/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data adm
    sharedscripts
    postrotate
        [ -f /var/run/nginx.pid ] && kill -USR1 `cat /var/run/nginx.pid`
    endscript
}
```

---

## 13. Common Nginx Misconfigurations

### 13.1 Missing Trailing Slash in proxy_pass

```nginx
# These behave differently:

# URL: /api/users
location /api/ {
    proxy_pass http://backend/;    # Proxies to: http://backend/users
}

location /api/ {
    proxy_pass http://backend;     # Proxies to: http://backend/api/users
}
```

### 13.2 Location Block Priority

```nginx
# Priority order:
# 1. = exact match
# 2. ^~ prefix match
# 3. ~ or ~* regex match
# 4. / prefix match

location = /exact { }           # Highest priority
location ^~ /prefix { }         # Second priority
location ~ \.php$ { }           # Third priority
location / { }                  # Lowest priority
```

### 13.3 Wrong if Usage

```nginx
# BAD: if is evil in certain contexts
location / {
    if ($uri = /forbidden) {
        return 403;  # This might not work as expected
    }
}

# BETTER: Use separate location
location = /forbidden {
    return 403;
}
```

### 13.4 Buffering for Streaming

```nginx
# WRONG: Buffering enabled for streaming
location /video_feed {
    proxy_buffering on;  # This breaks streaming!
}

# CORRECT: Buffering disabled
location /video_feed {
    proxy_buffering off;
    proxy_cache off;
}
```

---

## 14. Emergency Recovery

### 14.1 Nginx Won't Start

```bash
# Check what's wrong
sudo nginx -t

# Check for port conflicts
sudo lsof -i :80
sudo lsof -i :443

# Check systemd status
sudo systemctl status nginx

# View detailed errors
sudo journalctl -u nginx --no-pager

# Reset to default config
sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.broken
sudo cp /etc/nginx/nginx.conf.default /etc/nginx/nginx.conf
sudo systemctl start nginx
```

### 14.2 Restore from Backup

```bash
# If you have backups
sudo cp /path/to/backup/nginx.conf /etc/nginx/nginx.conf
sudo cp /path/to/backup/xyz.com /etc/nginx/sites-available/

# Re-enable site
sudo ln -sf /etc/nginx/sites-available/xyz.com /etc/nginx/sites-enabled/

# Test and reload
sudo nginx -t && sudo systemctl reload nginx
```

### 14.3 Minimal Working Config

If all else fails, start with minimal config:

```nginx
# /etc/nginx/nginx.conf
user www-data;
worker_processes auto;
pid /run/nginx.pid;

events {
    worker_connections 768;
}

http {
    sendfile on;
    tcp_nopush on;
    types_hash_max_size 2048;
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;
    include /etc/nginx/sites-enabled/*;
}
```

```nginx
# /etc/nginx/sites-available/default
server {
    listen 80 default_server;
    root /var/www/html;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

### 14.4 Reset File Permissions

```bash
# Reset Nginx directory permissions
sudo chown -R root:root /etc/nginx
sudo chmod -R 755 /etc/nginx

# Reset log permissions
sudo chown -R www-data:adm /var/log/nginx
sudo chmod -R 755 /var/log/nginx

# Reset web root permissions
sudo chown -R www-data:www-data /var/www
sudo chmod -R 755 /var/www
```

---

## Quick Reference Card

### Essential Commands

| Command | Purpose |
|---------|---------|
| `sudo nginx -t` | Test configuration |
| `sudo systemctl reload nginx` | Reload config (graceful) |
| `sudo systemctl restart nginx` | Full restart |
| `sudo tail -f /var/log/nginx/error.log` | Watch errors |
| `sudo ss -tlpn \| grep nginx` | Check ports |

### Common Fixes

| Issue | Quick Fix |
|-------|-----------|
| 502 Bad Gateway | Check if backend is running |
| 413 Too Large | Add `client_max_body_size 500M;` |
| 504 Timeout | Increase `proxy_read_timeout` |
| Video choppy | Add `proxy_buffering off;` |
| CORS error | Add CORS headers in location block |
| SSL error | Run `sudo certbot renew` |

### Debug Checklist

1. [ ] Is Nginx running? (`systemctl status nginx`)
2. [ ] Config syntax OK? (`nginx -t`)
3. [ ] Is backend running? (`curl localhost:8000`)
4. [ ] Firewall open? (`ufw status`)
5. [ ] Correct permissions? (`ls -la /var/www`)
6. [ ] Check error logs (`tail /var/log/nginx/error.log`)

# WSL Deployment Guide — IAPT Lab Backend

Deploy the FastAPI liquid level measurement backend on WSL (Ubuntu) before moving to Raspberry Pi.

---

## Prerequisites

- **WSL 2** with Ubuntu installed (`wsl --install` from PowerShell if not set up)
- The project files accessible in WSL

---

## Step 1: Copy Project to WSL

From **PowerShell** (Windows):

```bash
# Option A: Copy the backend folder into WSL home directory
wsl cp -r /mnt/d/download/my_projects/IAPT_Lab/backend ~/iapt-backend
```

Or from inside **WSL terminal**:

```bash
cp -r /mnt/d/download/my_projects/IAPT_Lab/backend ~/iapt-backend
```

> **Tip:** Working from the WSL filesystem (`~/`) is much faster than `/mnt/d/` due to cross-filesystem overhead.

---

## Step 2: Install System Dependencies

```bash
sudo apt update && sudo apt install -y \
  python3 python3-pip python3-venv \
  libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender1
```

> The `libgl1-mesa-glx` and related packages are required by OpenCV — without them you'll get `ImportError: libGL.so.1: cannot open shared object file`.

---

## Step 3: Create Virtual Environment & Install Dependencies

```bash
cd ~/iapt-backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### If OpenCV fails to import

Replace `opencv-python` with the headless version (recommended for servers / Raspberry Pi too):

```bash
pip uninstall opencv-python -y
pip install opencv-python-headless
```

---

## Step 4: Run the Server

```bash
cd ~/iapt-backend
source venv/bin/activate
python main.py
```

Or with auto-reload for development:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Step 5: Access from Windows

WSL 2 shares `localhost` with Windows. Open your browser at:

| URL | Purpose |
|-----|---------|
| http://localhost:8000 | Health check |
| http://localhost:8000/docs | Swagger API docs |
| http://localhost:8000/video_feed | Live video feed |

Expected health check response:
```json
{"status": "ok", "message": "Backend is running"}
```

---

## Step 6: Test the API

From a **second WSL terminal** (or Windows PowerShell):

```bash
# Health check
curl http://localhost:8000

# Check camera (will likely fail in WSL — use video upload instead)
curl http://localhost:8000/check_camera?index=0

# Upload a test video
curl -X POST "http://localhost:8000/upload_video" -F "file=@/path/to/test_video.mp4"

# Start session with uploaded video (auto-fallback if no camera)
curl -X POST "http://localhost:8000/start?source=0&calibration=1.0"

# Get level reading
curl http://localhost:8000/level

# Stop session
curl -X POST "http://localhost:8000/stop"

# Download report
curl -O http://localhost:8000/download_report
```

---

## Important Notes for WSL

### No Physical Camera Access
WSL does **not** have direct USB camera access. Your options:

1. **Upload a video file** via `/upload_video` — the backend auto-falls back to uploaded videos when camera is unavailable
2. **USB passthrough** (WSL 2 only, requires `usbipd-win`):
   ```powershell
   # From Windows PowerShell (Admin)
   winget install usbipd
   usbipd list
   usbipd bind --busid <BUSID>
   usbipd attach --wsl --busid <BUSID>
   ```
   Then in WSL: `ls /dev/video*` to confirm

### Matplotlib Backend
If you see `Matplotlib is currently using agg` warnings, that's normal — the backend uses `savefig()` not `show()` so it works fine headless.

---

## Quick Reference

| Action | Command |
|--------|---------|
| Enter WSL | `wsl` (from PowerShell) |
| Activate venv | `source ~/iapt-backend/venv/bin/activate` |
| Start server | `python main.py` |
| Start with reload | `uvicorn main:app --host 0.0.0.0 --port 8000 --reload` |
| Stop server | `Ctrl + C` |
| Deactivate venv | `deactivate` |

---

## Next: Raspberry Pi Deployment

Once this works on WSL, the Raspberry Pi setup is nearly identical:
- Same Python dependencies (`pip install -r requirements.txt`)
- Use `opencv-python-headless` instead of `opencv-python`
- Raspberry Pi has native USB camera support (`/dev/video0`)
- See `DEPLOYMENT_GUIDE.md` for Pi-specific instructions

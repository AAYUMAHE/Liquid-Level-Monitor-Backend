# Local Deployment Guide

Step-by-step instructions to run the Liquid Level Measurement System on your local machine.

---

## Step 1: Check Prerequisites

```bash
# Check Python version (3.8+ required)
python3 --version

# Check pip
pip3 --version
```

If Python is not installed:
- **Ubuntu/Debian:** `sudo apt install python3 python3-pip python3-venv`
- **Windows:** Download from https://python.org
- **Mac:** `brew install python3`

---

## Step 2: Navigate to Project Directory

```bash
cd /apps/workspace/tt
```

---

## Step 3: Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate        # Linux/Mac
# OR
venv\Scripts\activate           # Windows (Command Prompt)
# OR
venv\Scripts\Activate.ps1       # Windows (PowerShell)
```

You should see `(venv)` in your terminal prompt.

---

## Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- FastAPI (web framework)
- Uvicorn (ASGI server)
- OpenCV (computer vision)
- NumPy, Pandas, Matplotlib (data processing)
- SciPy, scikit-learn, scikit-image (edge detection algorithms)

---

## Step 5: Run the Application

### Option A: Using Python directly
```bash
python main.py
```

### Option B: Using Uvicorn (recommended for development)
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The `--reload` flag auto-restarts the server when you make code changes.

---

## Step 6: Verify It's Running

Open your browser and go to:

| URL | Purpose |
|-----|---------|
| http://localhost:8000 | Health check |
| http://localhost:8000/docs | Swagger API documentation |
| http://localhost:8000/redoc | Alternative API docs |

You should see:
```json
{"status": "ok", "message": "Backend is running"}
```

---

## Step 7: Test Camera

```bash
# In a new terminal, test camera availability
curl http://localhost:8000/check_camera?index=0
```

Expected response if camera is available:
```json
{"available": true, "message": "Camera found and working"}
```

If no camera, you can upload a video instead.

---

## Step 8: Test Video Upload (Optional)

```bash
# Upload a test video
curl -X POST "http://localhost:8000/upload_video" \
  -F "file=@/path/to/your/video.mp4"
```

---

## Step 9: Test Full Workflow

### Start a session:
```bash
curl -X POST "http://localhost:8000/start?source=0&calibration=1.0"
```

### Set reference (zero point):
```bash
curl -X POST "http://localhost:8000/set_zero"
```

### Get current level:
```bash
curl http://localhost:8000/level
```

### Stop session:
```bash
curl -X POST "http://localhost:8000/stop"
```

### Download report:
```bash
curl -O http://localhost:8000/download_report
```

---

## Step 10: View Live Video Feed

Open in browser:
```
http://localhost:8000/video_feed
```

This shows the live camera feed with ROI overlay (if set).

---

## Common Issues & Fixes

### Issue: "No module named 'cv2'"
```bash
pip install opencv-python
```

### Issue: Camera not found
- Check if camera is connected
- Try different index: `curl http://localhost:8000/check_camera?index=1`
- Use video file instead of camera

### Issue: Port 8000 already in use
```bash
# Use a different port
uvicorn main:app --host 0.0.0.0 --port 8080
```

### Issue: Permission denied on camera (Linux)
```bash
sudo usermod -a -G video $USER
# Then logout and login again
```

### Issue: Slow processing
Edit `camera_service.py` line 37:
```python
self.detector = PMI_Edge_Detector(max_dim=50)  # Reduce from 100
```

---

## File Structure After Running

```
/apps/workspace/tt/
├── main.py
├── camera_service.py
├── detector.py
├── analyzer.py
├── requirements.txt
├── requirements-pi.txt
├── DEPLOYMENT_GUIDE.md
├── LOCAL_DEPLOYMENT.md
├── venv/                    # Virtual environment
├── uploaded_videos/         # Uploaded video files
└── session_output/          # Generated after running
    ├── Processed_Images/    # Edge detection frames
    ├── Final_Report.xlsx    # Data report
    └── Trend_Graph.png      # Level trend chart
```

---

## Quick Commands Reference

| Action | Command |
|--------|---------|
| Activate venv | `source venv/bin/activate` |
| Run server | `python main.py` |
| Run with reload | `uvicorn main:app --reload --host 0.0.0.0 --port 8000` |
| Stop server | `Ctrl + C` |
| Deactivate venv | `deactivate` |

---

## Next Steps

Once local deployment works:
1. Test with your camera or sample video
2. Verify ROI selection works
3. Check report generation
4. Proceed to Raspberry Pi deployment (see `DEPLOYMENT_GUIDE.md`)

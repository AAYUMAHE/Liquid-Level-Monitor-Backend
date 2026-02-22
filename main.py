print("Starting imports...")

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import cv2
import time
import shutil
import os

print("Imports done. Loading CameraService...")

from camera_service import CameraService

print("CameraService imported. Creating app...")

app = FastAPI()

print("FastAPI app created.")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Creating CameraService instance...")
camera_service = CameraService()
print("CameraService instance created.")


@app.get("/")
def health_check():
    return {"status": "ok", "message": "Backend2 is running"}


@app.get("/check_camera")
def check_camera(index: int = 0):
    """Check if a camera is available at the given index"""
    cap = cv2.VideoCapture(index)

    if cap.isOpened():
        ret, frame = cap.read()
        cap.release()

        if ret and frame is not None:
            return {"available": True, "message": "Camera found and working"}
        else:
            return {"available": False, "message": "Camera found but cannot read frames"}
    else:
        cap.release()
        return {"available": False, "message": "Camera not found"}


@app.post("/start")
def start(source: str = "0", calibration: float = 1.0, output_folder: str = "session_output", fps: float = 30.0):

    if source.isdigit():
        source_val = int(source)
    else:
        source_val = source  # video file path

    camera_service.save_dir = output_folder
    camera_service.target_fps = fps if fps > 0 else 30.0

    try:
        camera_service.start(source=source_val, calibration=calibration)
        return {"status": "started", "success": True, "fps": camera_service.target_fps}
    except Exception as e:
        return {"status": "error", "success": False, "message": str(e)}


@app.post("/stop")
def stop():
    camera_service.stop()
    return {"status": "stopped"}


@app.post("/set_zero")
def set_zero():
    camera_service.set_reference()
    return {"status": "reference_set"}


@app.post("/set_fps")
def set_fps(value: float = 30.0):
    """Change target FPS on-the-fly while running"""
    camera_service.target_fps = value if value > 0 else 30.0
    return {"status": "fps_set", "fps": camera_service.target_fps}


@app.post("/set_calibration")
def set_calibration(value: float = 1.0):
    """Change calibration factor on-the-fly"""
    camera_service.set_calibration(value)
    return {"status": "calibration_set", "value": value}


@app.post("/set_auto_lighting")
def set_auto_lighting(enabled: bool = True, clip_limit: float = 2.0):
    """Enable/disable auto lighting adjustment and set CLAHE clip limit"""
    camera_service.set_auto_lighting(enabled, clip_limit)
    return {
        "status": "auto_lighting_set",
        "enabled": camera_service.auto_lighting_enabled,
        "clip_limit": camera_service.clahe_clip_limit
    }


@app.get("/auto_lighting")
def get_auto_lighting():
    """Get current auto lighting settings"""
    return camera_service.get_auto_lighting_settings()


@app.get("/level")
def get_level():
    return camera_service.get_stats()


# ======================================================
# ROI (Region of Interest) ENDPOINTS
# ======================================================

@app.get("/capture_frame")
def capture_frame(source: str = "0"):
    """Capture a single frame for ROI selection"""
    if source.isdigit():
        source_val = int(source)
    else:
        source_val = source

    frame, error = camera_service.capture_frame(source_val)

    if error:
        return {"success": False, "message": error}

    # Encode frame as JPEG and return as base64
    import base64
    ret, buffer = cv2.imencode(".jpg", frame)
    if not ret:
        return {"success": False, "message": "Failed to encode frame"}

    frame_base64 = base64.b64encode(buffer).decode('utf-8')
    h, w = frame.shape[:2]

    return {
        "success": True,
        "image": frame_base64,
        "width": w,
        "height": h
    }


@app.post("/set_roi")
def set_roi(x1: int, y1: int, x2: int, y2: int):
    """Set the Region of Interest for processing"""
    camera_service.set_roi(x1, y1, x2, y2)
    return {
        "status": "roi_set",
        "roi": camera_service.get_roi()
    }


@app.post("/clear_roi")
def clear_roi():
    """Clear ROI - process full frame"""
    camera_service.clear_roi()
    return {"status": "roi_cleared"}


@app.get("/roi")
def get_roi():
    """Get current ROI coordinates"""
    roi = camera_service.get_roi()
    return {
        "roi": roi,
        "has_roi": roi is not None
    }


def generate_frames():
    while True:
        frame = camera_service.get_frame()
        if frame is None:
            continue

        ret, buffer = cv2.imencode(".jpg", frame)
        frame_bytes = buffer.tobytes()

        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")

        time.sleep(0.03)


@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generate_frames(),
                             media_type="multipart/x-mixed-replace; boundary=frame")



UPLOAD_FOLDER = "uploaded_videos"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.post("/upload_video")
async def upload_video(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"message": "Video uploaded", "path": file_path}



@app.get("/download_report")
def download_report():
    report_path = os.path.join(camera_service.save_dir, "Final_Report.xlsx")

    if not os.path.exists(report_path):
        return {"error": "Report not found. Run a session first."}

    return FileResponse(
        path=report_path,
        filename="Final_Report.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


print("All routes defined. Server ready to start.")

if __name__ == "__main__":
    print("Starting uvicorn server on port 8000...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
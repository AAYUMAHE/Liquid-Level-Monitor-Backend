import cv2
import os
import time
import threading
import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

print("Importing detector...")
from detector import PMI_Edge_Detector
print("Importing analyzer...")
from analyzer import ResultAnalyzer
print("Imports complete in camera_service.")


class CameraService:
    def __init__(self):
        print("Initializing CameraService...")
        self.running = False
        self.cap = None
        self.latest_frame = None
        self.current_level = 0.0
        self.ref_row = None
        self._last_row = None
        self.data_results = []
        self.calibration = 1.0
        self.save_dir = "session_output"
        self.frame_count = 0
        self.current_fps = 0.0
        self.current_processing_time = 0.0

        # ROI (Region of Interest) - None means full frame
        self.roi = None  # Format: (x1, y1, x2, y2)

        print("Creating PMI_Edge_Detector...")
        self.detector = PMI_Edge_Detector(max_dim=100)
        print("Creating ResultAnalyzer...")
        self.analyzer = ResultAnalyzer()
        print("CameraService initialized.")

    # ======================================================
    # SET ROI (Region of Interest)
    # ======================================================
    def set_roi(self, x1, y1, x2, y2):
        """Set the region of interest for processing"""
        # Ensure coordinates are in correct order
        self.roi = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        print(f"ROI set to: {self.roi}")

    def clear_roi(self):
        """Clear ROI - process full frame"""
        self.roi = None
        print("ROI cleared - using full frame")

    def get_roi(self):
        """Get current ROI coordinates"""
        return self.roi

    # ======================================================
    # CAPTURE SINGLE FRAME (for ROI selection)
    # ======================================================
    def capture_frame(self, source=0):
        """Capture a single frame from source for ROI selection"""
        if isinstance(source, str) and not source.isdigit():
            # Video file path
            cap = cv2.VideoCapture(source)
        else:
            # Camera index
            cap = cv2.VideoCapture(int(source) if isinstance(source, str) else source)

        if not cap.isOpened():
            # Try fallback to uploaded videos
            video_folder = "uploaded_videos"
            if os.path.exists(video_folder):
                videos = [
                    os.path.join(video_folder, f)
                    for f in os.listdir(video_folder)
                    if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv"))
                ]
                if videos:
                    cap = cv2.VideoCapture(videos[0])

        if not cap.isOpened():
            return None, "Cannot open video source"

        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return None, "Cannot read frame from source"

        return frame, None

    # ======================================================
    # START SYSTEM
    # ======================================================
    def start(self, source=0, calibration=1.0, output_folder="session_output"):

        if self.running:
            return

        self.calibration = calibration
        self.save_dir = output_folder

        os.makedirs(self.save_dir, exist_ok=True)
        os.makedirs(os.path.join(self.save_dir, "Processed_Images"), exist_ok=True)

        self.running = True
        self.ref_row = None
        self._last_row = None
        self.data_results = []
        self.frame_count = 0
        self.current_fps = 0.0
        self.current_processing_time = 0.0
        # Note: ROI is NOT reset here - it persists across sessions

        # ---------------------------------------
        # Try opening requested source
        # ---------------------------------------
        self.cap = cv2.VideoCapture(source)

        if not self.cap.isOpened():

            print("Primary source failed.")

            # If camera index failed → fallback to uploaded videos
            if isinstance(source, int):

                print("Camera not available. Searching uploaded_videos folder...")

                video_folder = "uploaded_videos"

                if os.path.exists(video_folder):

                    videos = [
                        os.path.join(video_folder, f)
                        for f in os.listdir(video_folder)
                        if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv"))
                    ]

                    if len(videos) > 0:
                        fallback_video = videos[0]
                        print(f"Using fallback video: {fallback_video}")
                        self.cap = cv2.VideoCapture(fallback_video)
                    else:
                        self.running = False
                        raise Exception("No camera and no video files found.")

                else:
                    self.running = False
                    raise Exception("uploaded_videos folder not found.")

            else:
                self.running = False
                raise Exception("Cannot open provided video file.")

        # Final safety check
        if not self.cap.isOpened():
            self.running = False
            raise Exception("Unable to open any video source.")

        threading.Thread(target=self._loop, daemon=True).start()

    # ======================================================
    # STOP SYSTEM
    # ======================================================
    def stop(self):
        self.running = False

        if self.cap:
            self.cap.release()

        self._save_report()

    # ======================================================
    # SET ZERO REFERENCE
    # ======================================================
    def set_reference(self):
        if self._last_row is None:
            raise Exception("No frame processed yet.")
        self.ref_row = self._last_row

    # ======================================================
    # GET CURRENT LEVEL
    # ======================================================
    def get_level(self):
        if self.current_level is None:
            return None
        return float(self.current_level)

    # ======================================================
    # GET STATS
    # ======================================================
    def get_stats(self):
        return {
            "level": self.get_level(),
            "fps": float(self.current_fps),
            "processing_time": float(self.current_processing_time),
            "frame_count": int(self.frame_count)
        }


    # ======================================================
    # GET LATEST FRAME
    # ======================================================
    def get_frame(self):
        return self.latest_frame

    # ======================================================
    # MAIN PROCESSING LOOP
    # ======================================================
    def _loop(self):

        while self.running:

            ret, frame = self.cap.read()
            if not ret:
                print("Video ended or frame read failed.")
                break

            # Draw ROI rectangle on display frame if ROI is set
            display_frame = frame.copy()
            if self.roi is not None:
                x1, y1, x2, y2 = self.roi
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                # Add label
                cv2.putText(display_frame, "ROI", (x1, y1 - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            self.latest_frame = display_frame
            self.frame_count += 1

            start_time = time.time()

            # -------- EXTRACT ROI FOR PROCESSING --------
            if self.roi is not None:
                x1, y1, x2, y2 = self.roi
                # Ensure ROI is within frame bounds
                h, w = frame.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                process_frame = frame[y1:y2, x1:x2]
            else:
                process_frame = frame

            # -------- PROCESS FRAME (ROI only) --------
            edge = self.detector.detect(process_frame)
            row = self.analyzer.get_subpixel_row(edge)
            self._last_row = row

            processing_time = time.time() - start_time
            fps = 1.0 / processing_time if processing_time > 0 else 0

            # Store for API access
            self.current_fps = fps
            self.current_processing_time = processing_time

            # -------- SAVE EDGE IMAGE --------
            ts = datetime.datetime.now().strftime("%H_%M_%S_%f")

            edge_uint8 = (edge * 255).astype(np.uint8)

            img_path = os.path.join(
                self.save_dir,
                "Processed_Images",
                f"frame_{self.frame_count}_{ts}.png"
            )

            cv2.imwrite(img_path, edge_uint8)

            # -------- CALCULATE HEIGHT --------
            height = None

            if self.ref_row is not None:
                height = round((self.ref_row - row) / self.calibration, 2)
                self.current_level = height

            # -------- STORE DATA --------
            self.data_results.append({
                "Frame_Number": self.frame_count,
                "Timestamp": ts,
                "SubPixel_Row": row,
                "Height_cm": height,
                "Processing_Time_sec": processing_time,
                "FPS": fps,
                "Image_Path": img_path
            })

            time.sleep(0.03)

        self.running = False
        self._save_report()

    # ======================================================
    # SAVE FINAL REPORT
    # ======================================================
    def _save_report(self):

        if not self.data_results:
            print("No data collected.")
            return

        df = pd.DataFrame(self.data_results)

        # Save Excel
        excel_path = os.path.join(self.save_dir, "Final_Report.xlsx")
        df.to_excel(excel_path, index=False)

        # Save Graph
        plt.figure(figsize=(10, 5))
        plt.plot(df["Height_cm"].fillna(0), marker='o')
        plt.title("Live Liquid Level Trend")
        plt.xlabel("Frame Number")
        plt.ylabel("Level (cm)")
        plt.grid(True)

        graph_path = os.path.join(self.save_dir, "Trend_Graph.png")
        plt.savefig(graph_path)
        plt.close()

        print("Session saved successfully.")

import cv2
import os
import time
import threading
import queue
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
        self.latest_frame = None        # Frame with UI overlay (for video feed)
        self.latest_frame_process = None # Clean frame (for analysis)
        self.frame_lock = threading.Lock()
        self.current_level = 0.0
        self.ref_row = None
        self._last_row = None
        self.data_results = []
        self.calibration = 1.0
        self.save_dir = "session_output"
        self.frame_count = 0
        self.current_fps = 0.0
        self.current_processing_time = 0.0
        self.target_fps = 120.0  # Boost default to 120 FPS
        self._fps_window = []
        
        # Async Save Queue - No maxsize limit to prevent frame drops
        self.save_queue = queue.Queue()
        self.dropped_frames = 0
        threading.Thread(target=self._save_loop, daemon=True).start()


        # ROI (Region of Interest) - None means full frame
        self.roi = None  # Format: (x1, y1, x2, y2)

        # Auto Lighting Adjustment Settings
        self.auto_lighting_enabled = True
        self.clahe_clip_limit = 2.0
        self.clahe_tile_grid_size = (8, 8)

        print("Creating PMI_Edge_Detector...")
        self.detector = PMI_Edge_Detector(max_dim=150)
        print("Creating ResultAnalyzer...")
        self.analyzer = ResultAnalyzer()
        print("CameraService initialized.")

    # ======================================================
    # AUTO LIGHTING ADJUSTMENT (CLAHE)
    # ======================================================
    def adjust_lighting(self, frame):
        """
        Balances frame contrast and lighting dynamically using CLAHE.
        Ensures the edge detector works flawlessly even if the room gets dark.
        """
        if frame is None:
            return None

        if not self.auto_lighting_enabled:
            return frame

        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        clahe = cv2.createCLAHE(
            clipLimit=self.clahe_clip_limit,
            tileGridSize=self.clahe_tile_grid_size
        )
        cl = clahe.apply(l_channel)

        merged_lab = cv2.merge((cl, a_channel, b_channel))
        balanced_frame = cv2.cvtColor(merged_lab, cv2.COLOR_LAB2BGR)

        return balanced_frame

    def set_auto_lighting(self, enabled, clip_limit=None):
        """Enable/disable auto lighting and optionally set clip limit"""
        self.auto_lighting_enabled = enabled
        if clip_limit is not None:
            self.clahe_clip_limit = max(0.1, min(10.0, clip_limit))
        print(f"Auto lighting: {enabled}, clip_limit: {self.clahe_clip_limit}")

    def get_auto_lighting_settings(self):
        """Get current auto lighting settings"""
        return {
            "enabled": self.auto_lighting_enabled,
            "clip_limit": self.clahe_clip_limit
        }

    # ======================================================
    # SET ROI (Region of Interest)
    # ======================================================
    def set_roi(self, x1, y1, x2, y2):
        """Set the region of interest for processing"""
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
            cap = cv2.VideoCapture(source)
        else:
            cap = cv2.VideoCapture(int(source) if isinstance(source, str) else source)

        if not cap.isOpened():
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
        self.dropped_frames = 0

        # Clear any leftover items from previous session
        while not self.save_queue.empty():
            try:
                self.save_queue.get_nowait()
            except queue.Empty:
                break

        self.cap = cv2.VideoCapture(source)

        if not self.cap.isOpened():

            print("Primary source failed.")

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

        if not self.cap.isOpened():
            self.running = False
            raise Exception("Unable to open any video source.")

        threading.Thread(target=self._capture_loop, daemon=True).start()
        threading.Thread(target=self._processing_loop, daemon=True).start()

    # ======================================================
    # STOP SYSTEM
    # ======================================================
    def stop(self):
        self.running = False

        # self.cap.release() is handled in _capture_loop

        # Wait a bit for threads to clean up or just return (daemon threads will die)
        # We can't easily wait for daemon threads, but we can signal them.
        # The processing loop will call _save_report when it exits.

    # ======================================================
    # SET CALIBRATION
    # ======================================================
    def set_calibration(self, value):
        """Change calibration factor on-the-fly"""
        self.calibration = max(0.1, value)
        print(f"Calibration set to: {self.calibration}")

    # ======================================================
    # SET ZERO REFERENCE
    # ======================================================
    def set_reference(self):
        if self._last_row is None:
            raise Exception("No frame processed yet.")
        self.ref_row = self._last_row
        self.current_level = 0.0 # Force immediate zero update
        print("Reference set. Level reset to 0.0")

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
            "frame_count": int(self.frame_count),
            "running": self.running
        }

    # ======================================================
    # GET LATEST FRAME
    # ======================================================
    def get_frame(self):
        return self.latest_frame

    # ======================================================
    # CAPTURE LOOP (RUNS AT TARGET FPS)
    # ======================================================
    def _capture_loop(self):
        print("Starting capture loop...")
        
        while self.running:
            if self.cap is None:
                time.sleep(0.1)
                continue

            ret, frame = self.cap.read()
            if not ret:
                print("Video ended or frame read failed.")
                self.running = False
                break

            # --- Apply auto lighting adjustment (CLAHE) ---
            frame = self.adjust_lighting(frame)

            # Draw ROI rectangle on display frame if ROI is set
            # --- Critical fix: Save CLEAN copy for processing before drawing UI ---
            display_frame = frame.copy()
            clean_process_frame = frame.copy() # Keep a clean copy!

            # Draw ROI rectangle on display frame if ROI is set
            if self.roi is not None:
                x1, y1, x2, y2 = self.roi
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(display_frame, "ROI", (x1, y1 - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            with self.frame_lock:
                self.latest_frame = display_frame
                self.latest_frame_process = clean_process_frame

            # Use target_fps to control frame delay for the FEED
            frame_delay = 1.0 / self.target_fps if self.target_fps > 0 else 0.033
            time.sleep(frame_delay)

        if self.cap:
            self.cap.release()
        print("Capture loop ended.")

    # ======================================================
    # PROCESSING LOOP (RUNS AS FAST AS POSSIBLE)
    # ======================================================
    def _processing_loop(self):
        print("Starting processing loop...")
        
        while self.running:
            
            # Get latest clean frame safely
            process_frame = None
            with self.frame_lock:
                if self.latest_frame_process is not None:
                    process_frame = self.latest_frame_process.copy()
            
            if process_frame is None:
                time.sleep(0.1)
                continue

            self.frame_count += 1
            start_time = time.time()

            # -------- EXTRACT ROI FOR PROCESSING --------
            if self.roi is not None:
                x1, y1, x2, y2 = self.roi
                h, w = process_frame.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                # Ensure coordinates are valid
                if x2 > x1 and y2 > y1:
                    img_for_detection = process_frame[y1:y2, x1:x2]
                else:
                    img_for_detection = process_frame
            else:
                img_for_detection = process_frame

            # -------- PROCESS FRAME --------
            # This is the heavy blocking call
            edge = self.detector.detect(img_for_detection)
            row = self.analyzer.get_subpixel_row(edge)
            self._last_row = row

            processing_time = time.time() - start_time
            
            # --- Throughput FPS Calculation ---
            now = time.time()
            self._fps_window.append(now)
            # Remove timestamps older than 1 second
            while self._fps_window and now - self._fps_window[0] > 1.0:
                self._fps_window.pop(0)
            
            # FPS is the number of frames processed in the last second
            fps = len(self._fps_window)

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
            
            # ASYNC SAVE: Use blocking put() to ensure ALL frames are saved
            # This matches the original behavior where cv2.imwrite was blocking
            self.save_queue.put((img_path, edge_uint8))

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
            
            # No sleep here - process frames as fast as possible like original code

        # Wait for all pending saves to complete before generating report
        print(f"Waiting for {self.save_queue.qsize()} pending saves to complete...")
        self.save_queue.join()
        print("All frames saved.")

        self._save_report()
        print("Processing loop ended and report saved.")


    # ======================================================
    # SAVE FINAL REPORT
    # ======================================================
    # ======================================================
    # ASYNC SAVE LOOP
    # ======================================================
    def _save_loop(self):
        print("Starting async save loop...")
        while True:
            try:
                path, img = self.save_queue.get()
                cv2.imwrite(path, img)
                self.save_queue.task_done()
            except Exception as e:
                print(f"Error saving image: {e}")

    # ======================================================
    # SAVE FINAL REPORT
    # ======================================================
    def _save_report(self):

        if not self.data_results:
            print("No data collected.")
            return

        df = pd.DataFrame(self.data_results)

        excel_path = os.path.join(self.save_dir, "Final_Report.xlsx")
        df.to_excel(excel_path, index=False)

        # Plot Trend Graph
        try:
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
        except Exception as e:
            print(f"Error plotting graph: {e}")

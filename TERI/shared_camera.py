# shared_camera.py
import cv2
import threading
import time
import subprocess
import numpy as np

shared_frame = None
proc = None
running = True
buffer = bytearray()
frame_lock = threading.Lock()

def camera_loop():
    """Background thread for camera capture."""
    global shared_frame, proc, buffer, running
    
    cmd = [
        "libcamera-vid", "-t", "0", "--nopreview",
        "-o", "-", "--codec", "mjpeg",
        "--width", "640", "--height", "480",
        "--framerate", "30"
    ]
    
    proc = subprocess.Popen(cmd, 
                          stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL,
                          bufsize=10**8)
    
    while running:
        chunk = proc.stdout.read(1024)
        if not chunk:
            time.sleep(0.01)
            continue
            
        with frame_lock:
            buffer.extend(chunk)
            pos = buffer.find(b'\xff\xd9')
            
            while pos != -1:
                frame_data = buffer[:pos+2]
                buffer = buffer[pos+2:]
                
                try:
                    frame = cv2.imdecode(
                        np.frombuffer(frame_data, dtype=np.uint8), 
                        cv2.IMREAD_COLOR
                    )
                    if frame is not None:
                        shared_frame = frame.copy()
                except Exception as e:
                    print(f"[Camera] Decode error: {e}")
                    
                pos = buffer.find(b'\xff\xd9')

def init_shared_camera():
    """Initialize camera subsystem."""
    global running
    running = True
    threading.Thread(target=camera_loop, daemon=True).start()
    print("[Camera] libcamera-vid pipeline started")

def capture_shared_frame():
    """Get latest camera frame."""
    with frame_lock:
        return shared_frame

def stop_shared_camera():
    """Cleanup camera resources."""
    global running, proc
    running = False
    if proc:
        proc.terminate()
    print("[Camera] Camera subsystem stopped")

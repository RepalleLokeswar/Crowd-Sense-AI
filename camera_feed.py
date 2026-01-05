import cv2

import time


def start_camera(source=0):
    """
    Simplified camera opener based on successful test_cv.py
    """
    print(f"DEBUG: Opening source: {source}")
    
    if isinstance(source, int):
        # Webcam: Try DirectShow first, then default
        print("DEBUG: Using CAP_DSHOW for webcam...")
        cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        if not cap.isOpened():
            print("DEBUG: CAP_DSHOW failed. Trying default backend...")
            cap = cv2.VideoCapture(source)
    else:
        # File: Use default
        print("DEBUG: Using default backend for file...")
        cap = cv2.VideoCapture(source)
    
    if not cap.isOpened():
        print("ERROR: Could not open camera/file.")
        return cap
        
    # Optional: Set resolution to standard 640x480 for webcam to ensure compatibility
    if isinstance(source, int):
         cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
         cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    # Debug properties
    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"DEBUG: Opened successfully. {width}x{height} @ {fps} FPS")
    
    # Warmup read
    print("DEBUG: Waiting 2.0s for camera warmup...")
    time.sleep(2.0)
    ret, frame = cap.read()
    if ret:
        print("DEBUG: Initial frame read OK.")
    else:
        print("DEBUG: WARNING - Initial frame read FAILED.")
        
    return cap



def read_frame(cap):
    """
    Reads a frame with high resiliency. 
    Retries up to 20 times (approx 2 seconds) before failing.
    """
    for i in range(20):
        ret, frame = cap.read()
        if ret and frame is not None:
             return frame
        
        sleep_time = 0.1
        print(f"DEBUG: Frame read failed (Attempt {i+1}/20). Retrying...")
        time.sleep(sleep_time)
        
    print("DEBUG: Failed to read frame from camera after 20 attempts.")
    return None

def stop_camera(cap):
    cap.release()

import cv2
from ultralytics import YOLO
import os

def test_yolo():
    print("--- YOLO VERIFICATION ---")
    
    # 1. Check Model File
    if not os.path.exists("yolov8n.pt"):
        print("ERROR: yolov8n.pt NOT FOUND in current directory!")
        return
        
    print(f"Model found: yolov8n.pt ({os.path.getsize('yolov8n.pt')} bytes)")
    
    # 2. Load Model
    try:
        model = YOLO("yolov8n.pt")
        print("Model loaded successfully.")
    except Exception as e:
        print(f"ERROR: Failed to load model. {e}")
        return

    # 3. Create/Load Test Image
    # Try to find a frame or create a dummy
    img_path = "backend/cam_0.jpg"
    if os.path.exists(img_path):
        print(f"Testing on {img_path}")
        frame = cv2.imread(img_path)
    else:
        print("Testing on Dummy Black Image")
        import numpy as np
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        
    # 4. Run Inference
    try:
        # Run with low confidence just to see *anything*
        results = model(frame, conf=0.1, verbose=False)
        
        detections = 0
        if results and results[0].boxes:
            for box in results[0].boxes:
                cls = int(box.cls[0])
                if cls == 0: # Person
                    detections += 1
                    
        print(f"SUCCESS: Inference ran. Found {detections} people (class 0).")
        
    except Exception as e:
        print(f"ERROR: Inference failed. {e}")

if __name__ == "__main__":
    test_yolo()

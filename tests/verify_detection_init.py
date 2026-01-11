
import sys
import os
import unittest
import numpy as np

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from detection import PeopleCountingSystem
    from re_id import ReIDGallery, FeatureExtractor
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

class TestDetectionInit(unittest.TestCase):
    def test_init(self):
        print("Testing PeopleCountingSystem Initialization...")
        # Mock models to avoid heavy loading if possible, but for integration test we can load them.
        # This might take a few seconds.
        
        # We can pass None for models if the class supports it, but detection.py loads them if None.
        # Let's try to init with mocked reid_gallery to save time/memory?
        # But detection.py uses FeatureExtractor in init if reid_gallery is None.
        
        # Let's actually initialize it. It safeguards against runtime errors in __init__.
        # We need to make sure yolo model exists. 'yolov8n.pt' is in root.
        
        if not os.path.exists("yolov8n.pt"):
             print("WARNING: yolov8n.pt not found in current directory. Downloading/Creating dummy might be needed.")
             # Ultralytics will auto-download usually.
        
        pcs = PeopleCountingSystem()
        self.assertIsNotNone(pcs)
        print("Initialization Successful.")
        
        # Test process_frame with a dummy black frame
        dummy_frame = np.zeros((360, 640, 3), dtype=np.uint8)
        processed_frame = pcs.process_frame(dummy_frame, run_inference=True) # First frame
        
        self.assertIsNotNone(processed_frame)
        self.assertEqual(processed_frame.shape, (360, 640, 3))
        print("Process Frame Successful.")

if __name__ == '__main__':
    unittest.main()

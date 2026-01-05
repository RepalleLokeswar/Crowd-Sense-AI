import cv2
import numpy as np

class HeatmapGenerator:
    def __init__(self, width=640, height=360, decay_factor=0.995):
        self.width = width
        self.height = height
        self.heatmap_accum = np.zeros((height, width), dtype=np.float32)
        self.decay_factor = decay_factor

    def update(self, detections):
        """
        detections: list of dicts with 'coords' (box) or 'centroid' 
        """
        # Decay existing heat
        self.heatmap_accum *= self.decay_factor
        
        for det in detections:
            # Check for centroid
            cx, cy = det.get('centroid', (None, None))
            if cx is None:
                # Calculate from coords
                x1, y1, x2, y2 = det['coords']
                cx = int((x1 + x2) / 2)
                cy = int(y2) # Feet level is better for heatmap
                
            # Boundary check
            cx = max(0, min(cx, self.width - 1))
            cy = max(0, min(cy, self.height - 1))
            
            # Add Heat Point (Simple spread)
            # We can just add 1.0 to the pixel and blur later, 
            # or add a small gaussian blob now. Adding to pixel is faster.
            try:
                self.heatmap_accum[int(cy), int(cx)] += 5.0
            except:
                pass
                
        # Clamp
        np.clip(self.heatmap_accum, 0, 255, out=self.heatmap_accum)

    def apply_overlay(self, frame, alpha=0.6):
        """ Returns the frame with heatmap overlay """
        frame_shape = frame.shape
        # Apply Gaussian Blur to smooth the points
        blob = cv2.GaussianBlur(self.heatmap_accum, (31, 31), 0)
        
        # Normalize to 0-255
        norm = cv2.normalize(blob, None, 0, 255, cv2.NORM_MINMAX)
        norm = np.uint8(norm)
        
        # Color Map
        heatmap_color = cv2.applyColorMap(norm, cv2.COLORMAP_JET)
        
        # Resize to target frame
        if (heatmap_color.shape[1] != frame_shape[1]) or (heatmap_color.shape[0] != frame_shape[0]):
            heatmap_color = cv2.resize(heatmap_color, (frame_shape[1], frame_shape[0]))
            
        # Blend
        return cv2.addWeighted(frame, 1 - alpha, heatmap_color, alpha, 0)

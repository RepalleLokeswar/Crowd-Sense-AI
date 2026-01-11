import cv2
import time
import time

from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort

from re_id import Config, FeatureExtractor, ReIDGallery
from camera_feed import start_camera
from zones import load_zones, zones as loaded_zones
from counting import calculate_centroid, Zone
from heatmap import HeatmapGenerator


class PeopleCountingSystem:
    """
    Handles:
    - YOLOv8 person detection
    - DeepSORT tracking
    - Re-identification (via re_id.py)
    - Zone-based counting
    """

    def __init__(self, yolo_model=None, reid_gallery=None):
        print("Initializing PeopleCountingSystem...")

        # ---------------- YOLO ----------------
        if yolo_model:
            self.yolo = yolo_model
        else:
            self.yolo = YOLO(Config.YOLO_MODEL)

        # ---------------- Tracker ----------------
        self.tracker = DeepSort(
            max_age=Config.MAX_AGE,
            n_init=Config.N_INIT,
            max_iou_distance=Config.MAX_IOU_DISTANCE,
            embedder="mobilenet"
        )

        # ---------------- Re-ID ----------------
        if reid_gallery:
            self.reid_gallery = reid_gallery
        else:
            feature_extractor = FeatureExtractor()
            self.reid_gallery = ReIDGallery(feature_extractor)

        # ---------------- Zones ----------------
        load_zones()  # loads zones.csv into zones.zones
        self.zones = self._convert_zones(loaded_zones)

        # ---------------- Camera ----------------
        # Camera is handled by main.py
        # self.cap = start_camera(source)

        # ---------------- Heatmap ----------------
        self.heatmap = HeatmapGenerator(640, 360)
        self.show_heatmap = False # Disabled per user request

        self.last_time = time.time()
        self.fps = 0

    def _convert_zones(self, loaded_zones):
        """Convert zone dictionaries to Zone objects"""
        colors = [
            (0, 255, 0),
            (255, 0, 0),
            (0, 0, 255),
            (0, 255, 255),
            (255, 0, 255)
        ]

        zone_objects = []
        for i, z in enumerate(loaded_zones):
            zone_objects.append(
                Zone(z["id"], z["coords"], colors[i % len(colors)], threshold=z.get("threshold", 10))
            )
        return zone_objects

    def detect_people(self, frame):
        """YOLOv8 person detection"""
        results = self.yolo(
            frame,
            conf=Config.YOLO_CONF,
            classes=Config.YOLO_CLASSES,
            verbose=False
        )

        detections = []
        if results and results[0].boxes is not None:
            for box in results[0].boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                w = x2 - x1
                h = y2 - y1
                conf = float(box.conf[0])
                # DeepSort expects [left, top, w, h]
                detections.append(([x1, y1, w, h], conf, "person"))

        return detections

    def process_frame(self, frame, run_inference=True):
        """Detection + Tracking + Re-ID + Zone counting"""
        current_time = time.time()
        
        # FPS Calculation
        if hasattr(self, 'last_time') and self.last_time > 0:
            dt = current_time - self.last_time
            if dt > 0:
                current_fps = 1.0 / dt
                # Simple smoothing
                self.fps = 0.9 * self.fps + 0.1 * current_fps
        self.last_time = current_time
        
        self.imH, self.imW = frame.shape[:2]
        
        detections = []
        if run_inference:
            detections = self.detect_people(frame)
            
            # DEBUG: Draw RAW YOLO Detections (Yellow)
            # for det in detections:
            #     bbox, conf, _ = det
            #     rx1, ry1, w, h = bbox
            #     rx2 = rx1 + w
            #     ry2 = ry1 + h
            #     cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (0, 255, 255), 1)
            #     # print(f"DEBUG: YOLO Box: {bbox} Conf: {conf:.2f}")
                
        # print(f"DEBUG: Sending to tracker: {detections}")
        tracks = self.tracker.update_tracks(detections, frame=frame)
        # print(f"DEBUG: Tracker returned {len(tracks)} tracks")

        heatmap_points = []
        for track in tracks:
            # Show tracks that are confirmed OR have at least 1 hit (immediate feedback)
            if not track.is_confirmed() and (not hasattr(track, 'hits') or track.hits < 1):
                continue

            track_id = track.track_id
            x1, y1, x2, y2 = map(int, track.to_ltrb())

            # Crop for Re-ID
            crop = frame[y1:y2, x1:x2]
            global_id = self.reid_gallery.get_global_id(track_id, crop)

            # Centroid
            cx, cy = calculate_centroid(x1, y1, x2, y2)

            heatmap_points.append({'centroid': (cx, cy)})

            current_zone = None
            for zone in self.zones:
                zone.count_entry(global_id, (cx, cy))
                if zone.is_inside((cx, cy)):
                    current_zone = zone.id

            color = Config.COLOR_GREEN if current_zone else Config.COLOR_BLUE
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, Config.BOX_THICKNESS)
            cv2.circle(frame, (cx, cy), 3, Config.COLOR_RED, -1)

            label = f"ID: {global_id}"
            if current_zone:
                # Strip C{n}: prefix for cleaner view
                display_zone = current_zone.split(':')[-1].strip()
                label += f" | {display_zone}"

            cv2.putText(
                frame,
                label,
                (x1, y1 - 10),
                Config.FONT,
                Config.FONT_SCALE,
                Config.COLOR_WHITE,
                Config.FONT_THICKNESS
            )
            
        # --- CLEANUP: Remove tracks that disappeared (Left frame / Track lost) ---
        # Get set of currently active global IDs from this frame's tracks
        current_frame_ids = {
            self.reid_gallery.get_global_id(t.track_id, None) 
            for t in tracks if t.is_confirmed()
        }
        
        # Check all zones for stale IDs
        for zone in self.zones:
            # Safe copy to iterate
            active_ids_copy = list(zone.active_ids)
            for gid in active_ids_copy:
                # If gid is valid (>=0) and NOT in current tracks, they are gone
                if gid >= 0 and gid not in current_frame_ids:
                    # Double check if we can easily map global ID back to verify?
                    # Since we only store global IDs in zone, this simple check works
                    # providing get_global_id returns the same consistent ID.
                    zone.remove_id(gid)
            
        # Update Heatmap (Batch)
        self.heatmap.update(heatmap_points)

        # Draw zones with counts
        for zone in self.zones:
            zone.draw(frame)

        # ---------------- HEATMAP ----------------
        # ---------------- HEATMAP ----------------
        if self.show_heatmap:
            frame = self.heatmap.apply_overlay(frame)
            
            # Save Heatmap Frame for Dashboard (Every ~0.5s)
            # Path: milestone4/frontend/heatmap.jpg
            if int(time.time() * 10) % 5 == 0: 
                try:
                    # Write to temp and rename for atomic update
                    cv2.imwrite("milestone4/frontend/heatmap_temp.jpg", frame)
                    import os
                    if os.path.exists("milestone4/frontend/heatmap_temp.jpg"):
                        os.replace("milestone4/frontend/heatmap_temp.jpg", "milestone4/frontend/heatmap.jpg")
                except Exception:
                    pass

        # ---------------- PREPARE DATA ----------------
        # Calculate Live Count (Active confirmed tracks in current frame)
        live_count = 0
        for track in tracks:
             # Relax check: since we skip frames, time_since_update might be 1 or 2
             if (track.is_confirmed() or (hasattr(track, 'hits') and track.hits >= 1)) and track.time_since_update <= 5:
                 live_count += 1
        
        # DEBUG LOGGING (Enabled)
        print(f"DEBUG: Inf={run_inference} Dets={len(detections)} Tracks={len(tracks)} Live={live_count} FPS={self.fps:.1f}")
        for t in tracks:
            if not t.is_confirmed():
                print(f"   -> Track {t.track_id} NOT CONFIRMED (hits={t.hits if hasattr(t, 'hits') else '?'}, age={t.age}, prob={t.state})")
        
        zone_data = []
        
        # ALERT CHECK
        from backend.state import state # Import here to avoid circular init issues if at top
        
        for z in self.zones:
            # Check Threshold
            if z.count > z.threshold:
                # Cooldown Check (e.g. 60 seconds)
                if current_time - z.last_alert_time > 60:
                     msg = f"Zone '{z.id}' Overcrowded! ({z.count}/{z.threshold})"
                     print(f"!!! ALERT TRIGGERED: {msg}")
                     state.add_alert(z.id, msg)
                     z.last_alert_time = current_time
            
            zone_data.append({
                "name": z.id,
                "count": z.count,
                "coords": z.coords,
                "threshold": z.threshold
            })

        self.latest_stats = {
            "live_count": live_count,
            "people_count": live_count,
            "total_visitors": self.reid_gallery.next_global_id - 1,
            "zones": zone_data
        }
        
        # REMOVED: Direct requests.post call
        # We now rely on main.py to aggregate and send
        
        return frame

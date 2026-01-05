import csv
import os
import cv2

os.makedirs("zones", exist_ok=True)

import csv
import os
import cv2
import json

os.makedirs("zones", exist_ok=True)

ZONE_COLORS = [
    (0,255,0),(255,0,0),(0,0,255),(0,255,255),(255,0,255)
]

class ZoneManager:
    def __init__(self, filepath="zones/zones.json"):
        self.filepath = filepath
        self.zones = []
        self.drawing = False
        self.ix, self.iy = -1, -1
        self.current_rect_coords = None
        self.new_zone_drawn = False
        self.zone_edited = False # New flag to signal main.py
        self.preview_mode = True
        self.edit_mode = False
        self.selected_zone_index = None
        self.load_zones()

    def load_zones(self):
        self.zones.clear()
        if not os.path.exists(self.filepath):
            return
        with open(self.filepath, 'r') as f:
            try:
                data = json.load(f)
                for z in data:
                    if "coords" in z:
                        self.zones.append({
                            "id": z["id"],
                            "coords": tuple(z["coords"]),
                            "threshold": z.get("threshold", 10)
                        })
            except json.JSONDecodeError:
                pass

    def save_zones(self):
        with open(self.filepath, 'w') as f:
            json.dump(self.zones, f, indent=4)

    def draw_existing_zones(self, frame):
        for i,z in enumerate(self.zones):
            x1,y1,x2,y2 = z["coords"]
            cv2.rectangle(frame,(x1,y1),(x2,y2),
                          ZONE_COLORS[i%5],2)
            cv2.putText(frame,z["id"],(x1,y1-8),
                        cv2.FONT_HERSHEY_SIMPLEX,0.6,
                        ZONE_COLORS[i%5],2)

    def draw_preview(self, frame):
        if self.current_rect_coords:
            x1,y1,x2,y2 = self.current_rect_coords
            cv2.rectangle(frame,(x1,y1),(x2,y2),(255,255,0),2)

    def handle_mouse(self, event, x, y, flags, param):
        if event==cv2.EVENT_LBUTTONDOWN:
            # print(f"DEBUG: Mouse down at {x}, {y}")
            self.drawing=True; self.ix,self.iy=x,y

        elif event==cv2.EVENT_MOUSEMOVE and self.drawing:
            self.current_rect_coords=(self.ix,self.iy,x,y)

        elif event==cv2.EVENT_LBUTTONUP:
            self.drawing=False
            x1,y1,x2,y2 = min(self.ix,x),min(self.iy,y),max(self.ix,x),max(self.iy,y)
            
            # Minimum size check to avoid accidental clicks
            if abs(x2-x1) < 5 or abs(y2-y1) < 5:
                self.current_rect_coords = None
                return

            if self.edit_mode and self.selected_zone_index is not None:
                self.zones[self.selected_zone_index]["coords"]=(x1,y1,x2,y2)
                self.edit_mode=False
                self.zone_edited=True # Signal update
                print(f"DEBUG: Zone {self.selected_zone_index} updated.")
            else:
                self.current_rect_coords=(x1,y1,x2,y2)
                self.new_zone_drawn=True
                print("DEBUG: New zone drawn.")

# Backward compatibility (Global instance)
default_manager = ZoneManager()
zones = default_manager.zones
load_zones = default_manager.load_zones
save_zones = default_manager.save_zones
draw_roi = default_manager.handle_mouse
draw_preview = default_manager.draw_preview
draw_existing_zones = default_manager.draw_existing_zones
current_rect_coords = default_manager.current_rect_coords
new_zone_drawn = default_manager.new_zone_drawn
edit_mode = default_manager.edit_mode
selected_zone_index = default_manager.selected_zone_index
preview_mode = default_manager.preview_mode

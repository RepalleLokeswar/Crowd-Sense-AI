import cv2
import time

# ===== Milestone 1 imports =====
import zones
from camera_feed import start_camera, read_frame, stop_camera

# ===== Milestone 2 imports =====
from detection import PeopleCountingSystem
import requests

print("""
INTEGRATED CROWD COUNT SYSTEM
-----------------------------
Controls:
M1:
  Mouse  : Draw zones
  N      : Name zone
  S      : Save zones
  E      : Edit zone
  D      : Delete zone
  C      : Clear zones

M2:
  H      : Toggle Heatmap
  Q / ESC: Quit
""")

# ---------- LOAD ZONES (M1) ----------
zones.load_zones()

import argparse
import argparse
import os
import tkinter as tk
from tkinter import simpledialog, messagebox

def parse_arguments():
    parser = argparse.ArgumentParser(description="People Counting System")
    parser.add_argument("--source", type=str, default="0", help="Video source (0, filename, url)")
    parser.add_argument("--headless", action="store_true", help="Run without UI windows")
    return parser.parse_args()

# Headless Main Loop for Background Thread
def run_detection_headless(args_source=None, stop_event=None, headless=True, state_manager=None):
    # Parse args if not provided path
    # If called from app.py, args_source is expected (or default)
    # If state_manager is provided, use it instead of HTTP requests

    # Determine source
    raw_source = args_source
    if raw_source is None: raw_source = "0"
    raw_source = str(raw_source).strip().strip("'").strip('"')
    
    print(f"DEBUG: Detection CWD: {os.getcwd()}")
    print(f"DEBUG: Raw Source: '{raw_source}'")
    
    sources = []
    
    if raw_source.isdigit():
        sources = [int(raw_source)]
    elif ',' in raw_source:
        # Multi-source
        parts = raw_source.split(',')
        processed = []
        for p in parts:
            p = p.strip().strip("'").strip('"')
            if p.isdigit():
                processed.append(int(p))
            else:
                if os.path.exists(p):
                    processed.append(os.path.abspath(p))
                else:
                    # Check relative to root
                    root = os.path.dirname(os.path.abspath(__file__))
                    rel = os.path.join(root, p)
                    
                    # Check relative to data/videos
                    vid_rel = os.path.join(root, 'data', 'videos', p)
                    
                    if os.path.exists(rel):
                        processed.append(rel)
                    elif os.path.exists(vid_rel):
                        processed.append(vid_rel)
                    else:
                        print(f"ERROR: Source file not found: {p}")
        sources = processed
    else:
        # Single File or single invalid string
        found = False
        # 1. Check direct/absolute
        if os.path.exists(raw_source):
            sources = [os.path.abspath(raw_source)]
            found = True
        else:
            # 2. Check relative
            root = os.path.dirname(os.path.abspath(__file__))
            rel = os.path.join(root, raw_source)
            vid_rel = os.path.join(root, 'data', 'videos', raw_source)
            
            if os.path.exists(rel):
                sources = [rel]
                found = True
            elif os.path.exists(vid_rel):
                sources = [vid_rel]
                found = True
        
    if not sources:
        # Fallback to webcam 0 if nothing valid found, but warn
        print(f"ERROR: No valid sources found for '{raw_source}'. Fallback to 0.")
        sources = [0]

    print(f"DEBUG: Final Resolved Sources: {sources}")
    
    # ---------- LOAD ZONES ----------
    zones.load_zones()

    # ---------- INIT MODELS ----------
    from ultralytics import YOLO
    from re_id import Config, FeatureExtractor, ReIDGallery
    
    # Simple retry/lock prevention
    try:
        shared_yolo = YOLO(Config.YOLO_MODEL)
        feature_extractor = FeatureExtractor()
        shared_gallery = ReIDGallery(feature_extractor)
    except Exception as e:
        print(f"Model Init Error: {e}")
        return

    # ---------- OPEN CAMERAS ----------
    from zones import ZoneManager
    caps = []
    systems = []
    zone_managers = []

    for i, src in enumerate(sources):
        cap = start_camera(src)
        if cap.isOpened():
            caps.append(cap)
            pcs = PeopleCountingSystem(yolo_model=shared_yolo, reid_gallery=shared_gallery)
            zm = ZoneManager(f"zones/zones_source_{i}.json")
            zone_managers.append(zm)
            pcs.zones = pcs._convert_zones(zm.zones)
            systems.append(pcs)
        else:
            print(f"Failed to open source: {src}")

    if not caps:
        print("No cameras available.")
        return

    print("Background Detection Loop Started...")
    max_reported_visitors = 0
    
    import math
    import numpy as np
    
    last_update = time.time() # Initialize timer
    last_frame_write = 0


    # MAIN LOOP
    while True:
        # CHECK STOP SIGNAL
        if stop_event and stop_event.is_set():
            print("DEBUG: Stop signal received (Direct Event). Exiting detection loop.")
            break
        # Also check state_manager stop event if available (redundancy)
        if state_manager and state_manager.stop_event.is_set():
             print("DEBUG: Stop signal received (State Manager). Exiting detection loop.")
             break
            
        try:
            frames = []
            active_sources = 0
            
            # Use 'active' flag to stop safely if needed? For now Infinite.
            
            for i, cap in enumerate(caps):
                frame = read_frame(cap)
                if frame is None:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    frame = read_frame(cap)
                    if frame is None:
                         frame = np.zeros((360, 640, 3), dtype=np.uint8)
                
                if frame is not None:
                    # Enforce standard resolution for web consistency & zone mapping
                    frame = cv2.resize(frame, (640, 360))
                    frame = systems[i].process_frame(frame)
                    
                    # Draw Zones? Yes, for the web view.
                    # We can use the PeopleCountingSystem's internal drawing or ZM
                    # ZM draw_preview is handy
                    if zone_managers[i].preview_mode:
                        zone_managers[i].draw_preview(frame)
                        # Existing zones are drawn by process_frame usually if configured
                    
                    cv2.putText(frame, f"CAM {i+1}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,0), 2)
                    frames.append(frame)
                    active_sources += 1
            
            if active_sources == 0:
                break
                
            # AGGREGATE & SEND
            total_live = 0
            aggregated_zones_by_cam = {}

            # Collect stats
            for i, sys in enumerate(systems):
                 stats = sys.latest_stats
                 total_live += stats.get("people_count", 0)
                 
                 cam_zones = []
                 for z in stats.get("zones", []):
                     nz = z.copy()
                     nz['name'] = f"C{i+1}: {z['name']}"
                     cam_zones.append(nz)
                 aggregated_zones_by_cam[str(i)] = cam_zones

            max_global_id = shared_gallery.next_global_id - 1
            current_total = max(max_global_id, total_live)
            
            if current_total > max_reported_visitors:
                max_reported_visitors = current_total

            # Send to Backend / State Manager
            if time.time() - last_update > 0.5: # 2 FPS update
                last_update = time.time() # Reset timer
                cam_status = {
                    str(i): {
                        "source": str(src),
                        "resolution": f"{systems[i].imW}x{systems[i].imH}",
                        "fps": systems[i].fps
                    } for i, src in enumerate(sources)
                }
                
                payload = {
                   "live_count": total_live,
                   "people_count": total_live,
                   "total_visitors": max_reported_visitors,
                   "zones": aggregated_zones_by_cam, 
                   "cameras": cam_status
                }
                
                cmds = []
                if state_manager:
                    # Direct Update
                    state_manager.update(payload)
                    cmds = state_manager.get_and_clear_commands()
                else:
                    try:
                        # Legacy HTTP Fallback
                        resp = requests.post("http://127.0.0.1:5001/update_count", json=payload, timeout=0.05)
                        if resp.status_code == 200:
                            data = resp.json()
                            cmds = data.get("commands", [])
                    except Exception:
                        pass
                
                # Process Commands
                for cmd in cmds:
                    action = cmd.get("action")
                    if action == "save_zones":
                        for zm in zone_managers: zm.save_zones()
                    elif action == "clear_zones":
                        for i, zm in enumerate(zone_managers):
                            zm.zones.clear(); systems[i].zones.clear(); zm.save_zones()
                    elif action == "update_zones":
                        new_zones = cmd.get("zones", [])
                        target_cam = cmd.get("cam_id") # e.g. "C1"

                        for i, zm in enumerate(zone_managers):
                            # If cam_id is provided, only update specific index. C1 -> 0
                            current_id_str = f"C{i+1}"
                            if target_cam and target_cam != current_id_str:
                                continue
                                
                            zm.zones = []
                            for nz in new_zones:
                                zm.zones.append({"id": nz["id"], "coords": tuple(nz["coords"]), "threshold": nz.get("threshold", 10)})
                            zm.save_zones()
                            systems[i].zones = systems[i]._convert_zones(zm.zones)

             # SAVE FRAMES TO DISK (For Web Feed)
            # Save to Project Root where app.py expects them
            
            # FPS Limiter for Disk Writes (25 FPS = 0.04s)
            # This prevents IO bottleneck and keeps "live" feed smooth enough
            # FPS Limiter for Disk Writes (Target ~15-20 FPS for web view)
            # 0.05s = 20 FPS. This reduces IO load significantly.
            if time.time() - last_frame_write > 0.05:
                last_frame_write = time.time()
                ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
                for i, frame in enumerate(frames):
                     try:
                         temp_path = os.path.join(ROOT_DIR, f"cam_{i}_temp.jpg")
                         final_path = os.path.join(ROOT_DIR, f"cam_{i}.jpg")
                         # Encode to buffer first to ensure write isn't blocking (somewhat)
                         # Actually cv2.imwrite is blocking.
                         cv2.imwrite(temp_path, frame)
                         if os.path.exists(temp_path):
                             os.replace(temp_path, final_path)
                     except: pass

             # --- SHOW LOCAL WINDOW IF NOT HEADLESS ---
            if not headless:
                for i, frame in enumerate(frames):
                    cv2.imshow(f"Camera {i+1}", frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            # Only sleep if we didn't process anything to avoid CPU spin
            # If we processed frames, we should loop immediately to keep up with camera
            if active_sources == 0 and headless:
                 time.sleep(0.01) 
            elif headless and active_sources > 0:
                 # Minimal yield to allow other threads (like Flask/OS) to run
                 time.sleep(0.001)


        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error in Detection Loop: {e}")
            time.sleep(1)

    # Cleanup
    for cap in caps: stop_camera(cap)
    for zm in zone_managers: zm.save_zones()
    shared_gallery.save_compact()

# Legacy Entry Point (Optional)
if __name__ == "__main__":
    args = parse_arguments()
    run_detection_headless(args.source, headless=args.headless)



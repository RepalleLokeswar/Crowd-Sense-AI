import os
import time
import json
from collections import deque

import cv2
import numpy as np
import torch


class Config:
    # ---------------- YOLO / Tracker ----------------
    YOLO_MODEL = "yolov8n.pt"
    YOLO_CONF = 0.25 # Lowered from 0.5 to catch more people
    YOLO_CLASSES = [0]

    MAX_AGE = 90
    N_INIT = 1  # Lowered from 3 to 1 to speed up confirmation with frame skipping
    MAX_IOU_DISTANCE = 0.95 # Relaxed from 0.7 to 0.95 to handle low FPS jumps

    # ---------------- Re-ID ----------------
    REID_SIMILARITY_THRESHOLD = 0.65
    REID_GALLERY_SIZE = 5
    # REID_MEMORY_TIME = 300
    REID_MEMORY_TIME = 63072000  # 2 Years
    REID_CONFIRM_FRAMES = 1 # Lowered from 3 to 1

    # ---------------- Drawing ----------------
    FONT = cv2.FONT_HERSHEY_SIMPLEX
    FONT_SCALE = 0.4
    FONT_THICKNESS = 1
    BOX_THICKNESS = 1

    COLOR_GREEN = (0, 255, 0)
    COLOR_RED = (0, 0, 255)
    COLOR_BLUE = (255, 0, 0)
    COLOR_WHITE = (255, 255, 255)
    COLOR_YELLOW = (0, 255, 255)
    COLOR_ORANGE = (0, 165, 255)


class FeatureExtractor:
    """Extracts appearance features using MobileNetV2"""

    def __init__(self):
        import torchvision.models as models
        import torchvision.transforms as transforms

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        mobilenet = models.mobilenet_v2(pretrained=True)
        self.model = torch.nn.Sequential(*list(mobilenet.children())[:-1])
        self.model = self.model.to(self.device)
        self.model.eval()

        self.transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])

    def extract(self, image_crop):
        if image_crop is None or image_crop.size == 0:
            return None
        try:
            rgb = cv2.cvtColor(image_crop, cv2.COLOR_BGR2RGB)
            img_tensor = self.transform(rgb).unsqueeze(0).to(self.device)
            with torch.no_grad():
                features = self.model(img_tensor)

            features = features.squeeze().cpu().numpy().flatten()
            norm = np.linalg.norm(features)
            if norm > 0:
                features = features / norm
            return features
        except Exception:
            return None


def cosine_similarity(feat1, feat2):
    if feat1 is None or feat2 is None:
        return 0.0

    feat1 = np.asarray(feat1).flatten()
    feat2 = np.asarray(feat2).flatten()

    if feat1.size == 0 or feat2.size == 0:
        return 0.0

    dot_product = np.dot(feat1, feat2)
    norm1 = np.linalg.norm(feat1)
    norm2 = np.linalg.norm(feat2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(dot_product / (norm1 * norm2))


class ReIDGallery:
    """
    Maintains global identity consistency using appearance features.
    """

    def __init__(self, feature_extractor: FeatureExtractor):
        self.feature_extractor = feature_extractor
        self.gallery = {}              # global_id -> {features, last_seen}
        self.track_to_global = {}      # track_id -> global_id
        self.next_global_id = 1
        self.track_feature_buffers = {}

        try:
            self._load_persistent_gallery()
        except Exception:
            pass

    # ---------------- Persistence ----------------
    def _persistent_paths(self):
        root = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(root, "data")
        json_path = os.path.join(data_dir, "reid_gallery.json")
        return json_path

    def _load_persistent_gallery(self):
        json_path = self._persistent_paths()
        if not os.path.exists(json_path):
            return

        with open(json_path, "r", encoding="utf-8") as f:
            try:
                raw = json.load(f)
            except Exception:
                return

        for gid_str, data in raw.items():
            try:
                gid = int(gid_str)
            except Exception:
                continue

            feats = data.get("features") or data.get("feature")
            last_seen = data.get("last_seen", time.time())
            if not feats:
                continue

            arr = np.asarray(feats, dtype=np.float32)
            vec = arr if arr.ndim == 1 else np.mean(arr, axis=0)

            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm

            self.gallery[gid] = {
                "features": deque([vec.astype(np.float32)],
                                  maxlen=Config.REID_GALLERY_SIZE),
                "last_seen": float(last_seen)
            }

        # CRITICAL FIX: Update next_global_id to avoid ID conflict/reset
        if self.gallery:
            self.next_global_id = max(self.gallery.keys()) + 1
        else:
            self.next_global_id = 1

    def save_compact(self, out_path=None):
        json_path = self._persistent_paths()
        if out_path is None:
            out_path = json_path

        if not self.gallery:
            print("DEBUG: Gallery is empty at save time!") # DEBUG
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({}, f)
            return out_path

        print(f"DEBUG: Saving {len(self.gallery)} identities to gallery.") # DEBUG

        out = {}
        for gid, data in self.gallery.items():
            last = float(data.get("last_seen", time.time()))
            arr = np.asarray(list(data.get("features", [])), dtype=np.float32)

            if arr.size == 0:
                vec = np.zeros(128, dtype=np.float32)
            elif arr.ndim == 1:
                vec = arr
            else:
                vec = np.mean(arr, axis=0)

            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm

            out[str(gid)] = {
                "last_seen": last,
                "feature": vec.astype(float).tolist()
            }

        json_dir = os.path.dirname(out_path)
        if json_dir and not os.path.exists(json_dir):
            os.makedirs(json_dir, exist_ok=True)

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)

        return out_path

    # ---------------- Matching ----------------
    def _find_best_match(self, features):
        best_id = None
        best_similarity = 0.0

        for global_id, data in self.gallery.items():
            for stored_features in data["features"]:
                sim = cosine_similarity(features, stored_features)
                if sim > best_similarity:
                    best_similarity = sim
                    best_id = global_id

        if best_similarity >= Config.REID_SIMILARITY_THRESHOLD:
            return best_id, best_similarity

        return None, 0.0

    def _update_gallery(self, global_id, image_crop):
        features = self.feature_extractor.extract(image_crop)
        if features is None:
            return

        if global_id not in self.gallery:
            self.gallery[global_id] = {
                "features": deque(maxlen=Config.REID_GALLERY_SIZE),
                "last_seen": time.time()
            }

        self.gallery[global_id]["features"].append(features)
        self.gallery[global_id]["last_seen"] = time.time()

    def _create_new_id(self):
        gid = self.next_global_id
        self.next_global_id += 1
        return gid

    # ---------------- Public API ----------------
    def get_global_id(self, track_id, image_crop):
        if track_id in self.track_to_global:
            gid = self.track_to_global[track_id]
            # OPTIMIZATION: Do NOT update gallery every frame.
            # Just update timestamp if needed, but skip heavy feature extraction.
            if gid in self.gallery:
                 self.gallery[gid]["last_seen"] = time.time()
            # self._update_gallery(gid, image_crop) # DISABLED for FPS
            return gid

        features = self.feature_extractor.extract(image_crop)
        if features is None:
            # print(f"DEBUG: Feature extraction failed for track {track_id}")
            return -int(track_id)

        # Try to match with existing gallery
        matched_id, similarity = self._find_best_match(features)
        if matched_id is not None:
            print(f"DEBUG: Matched track {track_id} to global {matched_id} (sim: {similarity:.2f})")
            self.track_to_global[track_id] = matched_id
            self._update_gallery(matched_id, image_crop)
            self.track_feature_buffers.pop(track_id, None)
            return matched_id

        # Buffer logic
        buf = self.track_feature_buffers.get(track_id)
        if buf is None:
            buf = []
            self.track_feature_buffers[track_id] = buf

        buf.append(features)
        # print(f"DEBUG: Track {track_id} buffer size: {len(buf)}")

        if len(buf) < Config.REID_CONFIRM_FRAMES:
            return -int(track_id)

        # Create new ID
        try:
            avg_feat = np.mean(np.stack(buf, axis=0), axis=0)
        except Exception:
            avg_feat = features

        # Double check match with average
        matched_id, similarity = self._find_best_match(avg_feat)
        if matched_id is not None:
            print(f"DEBUG: Matched track {track_id} (avg) to global {matched_id} (sim: {similarity:.2f})")
            self.track_to_global[track_id] = matched_id
            self._update_gallery(matched_id, image_crop)
            del self.track_feature_buffers[track_id]
            return matched_id

        gid = self._create_new_id()
        print(f"DEBUG: Creating NEW identity {gid} for track {track_id}")
        self.track_to_global[track_id] = gid
        self._update_gallery(gid, image_crop)
        self.track_feature_buffers.pop(track_id, None)
        return gid

    def remove_track(self, track_id):
        if track_id in self.track_to_global:
            gid = self.track_to_global[track_id]
            if gid in self.gallery:
                self.gallery[gid]["last_seen"] = time.time()
            del self.track_to_global[track_id]

    def cleanup_old_entries(self):
        now = time.time()
        to_remove = []

        for gid, data in self.gallery.items():
            if now - data["last_seen"] > Config.REID_MEMORY_TIME:
                to_remove.append(gid)

        for gid in to_remove:
            del self.gallery[gid]

        if to_remove:
            print(f"Cleaned up {len(to_remove)} old gallery entries")

import cv2
import base64
import numpy as np
from typing import List, Dict, Any, Tuple
from ultralytics import YOLO
import backend.config as config
from backend.rules_kb import RULES_REGISTRY, get_rule_info

_yolo_model = None
_pose_model = None

def get_yolo_model():
    global _yolo_model
    if _yolo_model is None:
        _yolo_model = YOLO(config.MODEL_PATH)
    return _yolo_model

def get_pose_model():
    global _pose_model
    if _pose_model is None:
        _pose_model = YOLO(config.POSE_MODEL_PATH)
    return _pose_model

def encode_frame_to_base64(frame: np.ndarray, quality: int = 80) -> str:
    """Encode OpenCV frame to JPEG base64 string."""
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    success, buffer = cv2.imencode('.jpg', frame, encode_params)
    if not success:
        return ""
    return base64.b64encode(buffer).decode('utf-8')

class VideoAnalyzer:
    def __init__(self):
        self.model = get_yolo_model()
        self.pose_model = get_pose_model()

    def analyze_video(self, video_path: str) -> Dict[str, Any]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")

        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / video_fps
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        sample_interval = max(1, int(round(video_fps / config.SAMPLE_FPS)))

        frame_idx = 0
        timeline_events: List[Dict[str, Any]] = []

        # Tracking state
        cashier_ever_seen = False
        consecutive_cashier_absent_sec = 0.0
        prev_sec = 0.0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_interval == 0:
                sec = round(frame_idx / video_fps, 2)
                dt = max(0.1, sec - prev_sec) if prev_sec > 0 else 0.5
                prev_sec = sec

                res = self.model(frame, verbose=False, conf=config.CONF_THRESHOLD)
                boxes = res[0].boxes

                cabin_persons = []
                phones = []
                cups = []
                bags = []
                laptops = []
                tables = []

                for b in boxes:
                    cls_id = int(b.cls[0])
                    name = self.model.names[cls_id]
                    conf = float(b.conf[0])
                    bx = b.xyxy[0].cpu().numpy().tolist()

                    if name == "person":
                        # Ignore background people walking in the glass corridor (y2 < 310 for 848h or < 0.38*height)
                        if bx[3] >= height * 0.36:
                            cabin_persons.append({"box": bx, "conf": conf})
                    elif name == "laptop":
                        laptops.append({"box": bx, "conf": conf})
                    elif name == "cell phone":
                        phones.append({"box": bx, "conf": conf})
                    elif name in ("cup", "bottle", "bowl", "wine glass"):
                        cups.append({"box": bx, "conf": conf, "label": name})
                    elif name in ("handbag", "backpack", "suitcase"):
                        bags.append({"box": bx, "conf": conf, "label": name})
                    elif name == "dining table":
                        tables.append({"box": bx, "conf": conf})

                # Determine desk bounds dynamically
                if tables:
                    desk_box = tables[0]["box"]
                else:
                    desk_box = [0.15 * width, 0.42 * height, 0.85 * width, 0.75 * height]

                # Check cashier presence (person sitting behind table, y2 > 0.48*height)
                cashier_in_chair = False
                visitors_in_cabin = []

                for p in cabin_persons:
                    bx = p["box"]
                    # If person bottom is in lower half of image and near desk -> Cashier
                    if bx[3] > height * 0.48 and (bx[0] + bx[2])/2 > width * 0.25:
                        cashier_in_chair = True
                    else:
                        visitors_in_cabin.append(p)

                if cashier_in_chair:
                    cashier_ever_seen = True
                    consecutive_cashier_absent_sec = 0.0
                elif cashier_ever_seen:
                    consecutive_cashier_absent_sec += dt

                # RULE 1: Multiple visitors / unauthorized person in cabin
                # If there are >= 2 visitors inside the cabin simultaneously (total cabin persons >= 3 with cashier or >= 2 without cashier)
                if len(visitors_in_cabin) >= 2 or len(cabin_persons) >= 3:
                    timeline_events.append({
                        "rule_code": "UNAUTHORIZED_PERSON",
                        "timestamp_sec": sec,
                        "confidence": 0.92,
                        "frame": frame.copy(),
                        "note": f"Обнаружено {len(cabin_persons)} чел. в кассовом узле"
                    })

                # RULE 2: Cashier Left Desk Unattended
                # If cashier was working, and then left the chair for >= 3.0 seconds while laptop is present
                if cashier_ever_seen and consecutive_cashier_absent_sec >= 3.0:
                    rule_to_trigger = "UNATTENDED_UNLOCKED_TERMINAL" if len(laptops) > 0 else "UNATTENDED_DESK_ITEMS"
                    timeline_events.append({
                        "rule_code": rule_to_trigger,
                        "timestamp_sec": sec,
                        "confidence": 0.88,
                        "frame": frame.copy(),
                        "note": "Кассир покинул рабочее место без блокировки АРМ/уборки ценностей"
                    })

                # RULE 3: Phone Usage by Cashier
                # Cell phone must be in the cashier operational area (y > 0.42*height)
                for ph in phones:
                    pbx = ph["box"]
                    p_cy = (pbx[1] + pbx[3]) / 2
                    if p_cy > height * 0.38 and ph["conf"] > 0.30:
                        timeline_events.append({
                            "rule_code": "PHONE_USAGE",
                            "timestamp_sec": sec,
                            "confidence": ph["conf"],
                            "frame": frame.copy(),
                            "note": "Использование мобильного телефона в рабочей зоне кассира"
                        })

                # RULE 4: Drink or Food on the Desk
                for c in cups:
                    cbx = c["box"]
                    c_cy = (cbx[1] + cbx[3]) / 2
                    c_cx = (cbx[0] + cbx[2]) / 2
                    if desk_box[1] <= c_cy <= desk_box[3] and desk_box[0] <= c_cx <= desk_box[2]:
                        timeline_events.append({
                            "rule_code": "FOOD_OR_DRINK",
                            "timestamp_sec": sec,
                            "confidence": c["conf"],
                            "frame": frame.copy(),
                            "note": f"Напиток ({c['label']}) на кассовом столе"
                        })

                # RULE 5: Personal Bag / Jacket on the Desk
                for b in bags:
                    bbx = b["box"]
                    b_cy = (bbx[1] + bbx[3]) / 2
                    b_cx = (bbx[0] + bbx[2]) / 2
                    # Bag resting on the cashier table
                    if desk_box[1] <= b_cy <= desk_box[3] and desk_box[0] <= b_cx <= desk_box[2]:
                        timeline_events.append({
                            "rule_code": "PERSONAL_ITEMS_ON_DESK",
                            "timestamp_sec": sec,
                            "confidence": b["conf"],
                            "frame": frame.copy(),
                            "note": f"Личная сумка/вещь ({b['label']}) на кассовом столе"
                        })

            frame_idx += 1

        cap.release()

        # Aggregate detected events into contiguous violation episodes
        violations = self._aggregate_violations(timeline_events, duration)
        verdict = "violation" if len(violations) > 0 else "no_violation"

        return {
            "verdict": verdict,
            "violations": violations
        }

    def _aggregate_violations(self, events: List[Dict[str, Any]], duration: float) -> List[Dict[str, Any]]:
        if not events:
            return []

        # Group by rule_code
        rule_groups: Dict[str, List[Dict[str, Any]]] = {}
        for ev in events:
            code = ev["rule_code"]
            rule_groups.setdefault(code, []).append(ev)

        violations = []

        for code, group in rule_groups.items():
            # Robust filtering of transient false spikes:
            # Need at least 2 sampled frames (>= 1.0 second duration) to confirm a violation episode
            min_required = 2
            if len(group) < min_required:
                continue

            # Cluster events into contiguous intervals (gap <= 3.5s)
            clusters: List[List[Dict[str, Any]]] = []
            curr_cluster = [group[0]]
            for ev in group[1:]:
                if ev["timestamp_sec"] - curr_cluster[-1]["timestamp_sec"] <= 3.5:
                    curr_cluster.append(ev)
                else:
                    clusters.append(curr_cluster)
                    curr_cluster = [ev]
            if curr_cluster:
                clusters.append(curr_cluster)

            for cluster in clusters:
                if len(cluster) < min_required:
                    continue

                best_ev = max(cluster, key=lambda x: x["confidence"])
                peak_time = best_ev["timestamp_sec"]
                rule_info = get_rule_info(code)

                # Select 1 to 3 best evidence frames
                selected_evs = [cluster[0]]
                if len(cluster) > 2:
                    mid = cluster[len(cluster) // 2]
                    if mid not in selected_evs:
                        selected_evs.append(mid)
                if len(cluster) > 4:
                    last = cluster[-1]
                    if last not in selected_evs and len(selected_evs) < 3:
                        selected_evs.append(last)

                evidence_frames = []
                for ev in selected_evs[:3]:
                    b64_img = encode_frame_to_base64(ev["frame"], quality=85)
                    evidence_frames.append({
                        "timestamp_sec": round(ev["timestamp_sec"], 1),
                        "image_base64": b64_img
                    })

                violations.append({
                    "type": rule_info["title"],
                    "timecode_sec": round(peak_time, 1),
                    "description": rule_info["description_template"],
                    "evidence_frames": evidence_frames
                })

        return violations

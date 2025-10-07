from ultralytics import YOLO
import cv2
import numpy as np
import time

model = YOLO("yolov8n-pose.pt")

video_path = "sample-4.mp4"
cap = cv2.VideoCapture(video_path)

worker_data = {}
workstation_zones = {}  # {zone_id: (x1, y1, x2, y2)}
zone_ownership = {}  # {zone_id: person_id} - Siapa yang terakhir di zona ini
person_to_zone = {}  # {person_id: zone_id} - Mapping person ke zona nya
track_to_person = {}  # {track_id: person_id} - MEMORY: Track ID pernah jadi person ID apa

# Keypoints
HAND_KEYPOINTS = [9, 10]
SHOULDER_KEYPOINTS = [5, 6]
HEAD_KEYPOINT = 0
HIP_KEYPOINTS = [11, 12]

# Thresholds
ACTIVITY_THRESHOLD = 8
IDLE_TIMEOUT = 3
AWAY_TIMEOUT = 2
VISIBILITY_THRESHOLD = 0.5
ZONE_MARGIN = 140  # Zona individual per orang
ZONE_CALIBRATION_FRAMES = 30
ZONE_OVERLAP_THRESHOLD = 0.6  # 60% overlap baru dianggap zona sama (lebih ketat, tidak mudah merge)
ZONE_MIN_DISTANCE = 80  # Jarak minimum diperkecil (tidak merge zona yang berdekatan)
REID_TIMEOUT = 15  # Detik untuk "ingat" orang yang hilang (diperpanjang)

next_person_id = 1  
next_zone_id = 1

def get_person_center(keypoints, visibility):
    """Dapatkan posisi center pekerja"""
    visible_points = []
    for idx in [HEAD_KEYPOINT] + SHOULDER_KEYPOINTS + HIP_KEYPOINTS:
        if visibility[idx] > VISIBILITY_THRESHOLD:
            visible_points.append(keypoints[idx])
    
    if len(visible_points) > 0:
        center = np.mean(visible_points, axis=0)
        return int(center[0]), int(center[1])
    return None

def calculate_zone_distance(zone1, zone2):
    """Hitung jarak center antara 2 zona"""
    x1_1, y1_1, x2_1, y2_1 = zone1
    x1_2, y1_2, x2_2, y2_2 = zone2
    
    # Center points
    cx1 = (x1_1 + x2_1) / 2
    cy1 = (y1_1 + y2_1) / 2
    cx2 = (x1_2 + x2_2) / 2
    cy2 = (y1_2 + y2_2) / 2
    
    return np.sqrt((cx1 - cx2)**2 + (cy1 - cy2)**2)

def calculate_zone_overlap(zone1, zone2):
    """Hitung overlap antara 2 zona (IoU)"""
    x1_1, y1_1, x2_1, y2_1 = zone1
    x1_2, y1_2, x2_2, y2_2 = zone2
    
    # Intersection
    x_left = max(x1_1, x1_2)
    y_top = max(y1_1, y1_2)
    x_right = min(x2_1, x2_2)
    y_bottom = min(y2_1, y2_2)
    
    if x_right < x_left or y_bottom < y_top:
        return 0.0
    
    intersection = (x_right - x_left) * (y_bottom - y_top)
    area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
    area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
    union = area1 + area2 - intersection
    
    return intersection / union if union > 0 else 0

def find_matching_zone(center, current_zones):
    """Cari zona yang matching dengan posisi center"""
    if center is None:
        return None
    
    x, y = center
    for zone_id, zone in current_zones.items():
        x1, y1, x2, y2 = zone
        if x1 <= x <= x2 and y1 <= y <= y2:
            return zone_id
    return None

def find_or_create_zone(center, current_time):
    """Cari zona existing atau buat baru (TIDAK mudah merge)"""
    global next_zone_id
    
    if center is None:
        return None
    
    x, y = center
    new_zone = (
        x - ZONE_MARGIN,
        y - ZONE_MARGIN,
        x + ZONE_MARGIN,
        y + ZONE_MARGIN
    )
    
    # Cek overlap dengan zona existing (hanya merge jika overlap sangat tinggi)
    for zone_id, existing_zone in workstation_zones.items():
        overlap = calculate_zone_overlap(new_zone, existing_zone)
        
        # Hanya merge jika overlap >60% (hampir identik)
        if overlap > ZONE_OVERLAP_THRESHOLD:
            return zone_id
    
    # Buat zona baru untuk setiap orang
    zone_id = next_zone_id
    next_zone_id += 1
    workstation_zones[zone_id] = new_zone
    print(f"📍 Created new zone {zone_id} at position ({x}, {y})")
    return zone_id

def reid_person(track_id, center, current_time):
    """Re-identify person berdasarkan TRACK ID MEMORY & ZONA"""
    global next_person_id
    
    if center is None:
        return track_id
    
    # PRIORITAS 1: Cek apakah track ID ini sudah pernah muncul sebelumnya
    if track_id in track_to_person:
        old_person_id = track_to_person[track_id]
        if old_person_id in worker_data:
            # Track ID yang sama = orang yang sama!
            return old_person_id
    
    # PRIORITAS 2: Cari zona yang matching dengan posisi sekarang
    zone_id = find_matching_zone(center, workstation_zones)
    
    # PRIORITAS 3: Jika tidak ada zona matching, coba buat/cari zona
    if zone_id is None:
        zone_id = find_or_create_zone(center, current_time)
    
    # PRIORITAS 4: Cek apakah zona ini punya owner
    if zone_id is not None and zone_id in zone_ownership:
        old_person_id = zone_ownership[zone_id]
        
        # ATURAN: 1 zona = 1 orang, SELALU gunakan person ID yang sudah ada
        if old_person_id in worker_data:
            person_to_zone[old_person_id] = zone_id
            # Simpan track ID memory
            track_to_person[track_id] = old_person_id
            return old_person_id
    
    # PRIORITAS 5: Person baru di zona baru
    person_id = next_person_id
    next_person_id += 1
    
    if zone_id is not None:
        zone_ownership[zone_id] = person_id
        person_to_zone[person_id] = zone_id
        print(f"🆕 New worker detected: Person {person_id} at Zone {zone_id}")
    
    # Simpan track ID memory
    track_to_person[track_id] = person_id
    
    return person_id

def is_in_zone(center, zone):
    """Cek apakah posisi center ada di dalam zona"""
    if center is None or zone is None:
        return True
    
    x, y = center
    x1, y1, x2, y2 = zone
    return x1 <= x <= x2 and y1 <= y <= y2

def calculate_activity_score(pose1, pose2, vis1, vis2):
    """Hitung skor aktivitas"""
    if pose1 is None or pose2 is None:
        return 0
    
    score = 0
    
    for hand_idx in HAND_KEYPOINTS:
        if vis1[hand_idx] > VISIBILITY_THRESHOLD and vis2[hand_idx] > VISIBILITY_THRESHOLD:
            movement = np.linalg.norm(pose1[hand_idx] - pose2[hand_idx])
            score += movement * 2.0
    
    for shoulder_idx in SHOULDER_KEYPOINTS:
        if vis1[shoulder_idx] > VISIBILITY_THRESHOLD and vis2[shoulder_idx] > VISIBILITY_THRESHOLD:
            movement = np.linalg.norm(pose1[shoulder_idx] - pose2[shoulder_idx])
            score += movement * 1.0
    
    return score

def format_time(seconds):
    """Format waktu"""
    minutes = int(seconds // 60)
    hours = minutes // 60
    minutes = minutes % 60
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"

def is_valid_detection(visibility):
    """Cek apakah deteksi valid"""
    head_visible = visibility[HEAD_KEYPOINT] > VISIBILITY_THRESHOLD
    shoulders_visible = (visibility[5] > VISIBILITY_THRESHOLD and 
                        visibility[6] > VISIBILITY_THRESHOLD)
    return head_visible or shoulders_visible

frame_count = 0
fps = cap.get(cv2.CAP_PROP_FPS) or 30

print("🎥 Starting video analysis with ReID...")
print("📍 Tracking workers across camera movements...")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    
    frame_count += 1
    current_time = time.time()
    
    # Track dengan YOLO
    results = model.track(frame, conf=0.5, persist=True, verbose=False)
    
    active_tracks = set()  # Track ID yang terdeteksi di frame ini
    
    for result in results:
        if not hasattr(result, "keypoints") or result.boxes.id is None:
            continue
        
        track_ids = result.boxes.id.int().cpu().tolist()
        
        for idx, track_id in enumerate(track_ids):
            active_tracks.add(track_id)
            
            keypoints = result.keypoints.xy[idx].cpu().numpy()
            visibility = result.keypoints.conf[idx].cpu().numpy()
            
            if not is_valid_detection(visibility):
                continue
            
            center = get_person_center(keypoints, visibility)
            
            # Re-identify person
            person_id = reid_person(track_id, center, current_time)
            
            # Inisialisasi data jika perlu
            if person_id not in worker_data:
                zone_id = find_or_create_zone(center, current_time)
                
                worker_data[person_id] = {
                    "last_pose": keypoints,
                    "last_visibility": visibility,
                    "last_update": current_time,
                    "last_activity_time": current_time,
                    "last_seen": current_time,
                    "working_time": 0,
                    "idle_time": 0,
                    "away_time": 0,
                    "status": "working",
                    "last_activity_score": 0,
                    "center": center,
                    "zone_id": zone_id,
                    "calibration_frames": 0,
                    "track_ids": {track_id}  # Set of track IDs yang pernah dikaitkan
                }
            else:
                # Update track IDs yang dikaitkan
                worker_data[person_id]["track_ids"].add(track_id)
            
            data = worker_data[person_id]
            data["last_seen"] = current_time
            
            # Update zona jika masih kalibrasi
            zone_id = person_to_zone.get(person_id)
            if zone_id and data["calibration_frames"] < ZONE_CALIBRATION_FRAMES and center:
                x, y = center
                old_zone = workstation_zones[zone_id]
                x1, y1, x2, y2 = old_zone
                new_zone = (
                    min(x1, x - ZONE_MARGIN),
                    min(y1, y - ZONE_MARGIN),
                    max(x2, x + ZONE_MARGIN),
                    max(y2, y + ZONE_MARGIN)
                )
                workstation_zones[zone_id] = new_zone
                data["calibration_frames"] += 1
            
            # Cek zona
            current_zone = workstation_zones.get(zone_id) if zone_id else None
            in_zone = is_in_zone(center, current_zone)
            
            # Hitung activity score
            activity_score = calculate_activity_score(
                keypoints, 
                data["last_pose"],
                visibility,
                data["last_visibility"]
            )
            
            time_delta = current_time - data["last_update"]
            
            # Update status
            if not in_zone:
                if data["status"] != "away":
                    if current_time - data["last_update"] > AWAY_TIMEOUT:
                        data["status"] = "away"
                        print(f"⚠️  Worker {person_id} left workstation")
                data["away_time"] += time_delta
            else:
                if activity_score > ACTIVITY_THRESHOLD:
                    if data["status"] != "working":
                        data["status"] = "working"
                        if data.get("was_away"):
                            print(f"✅ Worker {person_id} returned and working")
                            data["was_away"] = False
                    data["working_time"] += time_delta
                    data["last_activity_time"] = current_time
                else:
                    if current_time - data["last_activity_time"] > IDLE_TIMEOUT:
                        if data["status"] == "working":
                            data["status"] = "idle"
                            print(f"💤 Worker {person_id} is idle")
                        data["idle_time"] += time_delta
                    else:
                        data["working_time"] += time_delta
            
            if data["status"] == "away":
                data["was_away"] = True
            
            data["last_pose"] = keypoints
            data["last_visibility"] = visibility
            data["last_update"] = current_time
            data["center"] = center
            
            # Visualisasi
            x1, y1, x2, y2 = result.boxes.xyxy[idx].int().tolist()
            
            if data["status"] == "working":
                color = (0, 255, 0)
            elif data["status"] == "idle":
                color = (0, 165, 255)
            else:
                color = (0, 0, 255)
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # Draw zona
            if zone_id in workstation_zones:
                zx1, zy1, zx2, zy2 = workstation_zones[zone_id]
                zone_color = (0, 0, 200) if in_zone else (0, 0, 200)
                cv2.rectangle(frame, (int(zx1), int(zy1)), (int(zx2), int(zy2)), zone_color, 1)
                
                # Label zona
                cv2.putText(frame, f"Zone {zone_id}", (int(zx1), int(zy1) - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)
            
            if center:
                cv2.circle(frame, center, 5, (255, 255, 0), -1)
            
            for kp_idx in HAND_KEYPOINTS + SHOULDER_KEYPOINTS:
                if visibility[kp_idx] > VISIBILITY_THRESHOLD:
                    x, y = int(keypoints[kp_idx][0]), int(keypoints[kp_idx][1])
                    cv2.circle(frame, (x, y), 3, (255, 0, 0), -1)
            
            # Info text
            cv2.putText(frame, f"P{person_id} (T{track_id})", (x1, y1 - 40),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
            status_text = f"{data['status'].upper()} | {format_time(data['working_time'])}"
            cv2.putText(frame, status_text, (x1, y1 - 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2)
            
            if data['away_time'] > 0:
                away_text = f"Away: {format_time(data['away_time'])}"
                cv2.putText(frame, away_text, (x1, y1 - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 2)
    
    # Summary
    total_workers = len(worker_data)
    working = sum(1 for w in worker_data.values() if w["status"] == "working")
    idle = sum(1 for w in worker_data.values() if w["status"] == "idle")
    away = sum(1 for w in worker_data.values() if w["status"] == "away")
    
    overlay = frame.copy()
    cv2.rectangle(overlay, (5, 5), (450, 100), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
    
    cv2.putText(frame, f"Workers: {total_workers} | Zones: {len(workstation_zones)}", (10, 25),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(frame, f"Working: {working}  |  Idle: {idle}  |  Away: {away}", (10, 50),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(frame, f"Frame: {frame_count} | ReID Active", (10, 75),
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 255, 100), 1)
    
    cv2.imshow("Worker Tracking with ReID", frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

# Summary
print("\n" + "="*60)
print("📊 WORK ACTIVITY SUMMARY (with ReID)")
print("="*60)

for person_id, data in sorted(worker_data.items()):
    total_time = data['working_time'] + data['idle_time'] + data['away_time']
    
    if total_time > 0:
        work_pct = (data['working_time'] / total_time) * 100
        idle_pct = (data['idle_time'] / total_time) * 100
        away_pct = (data['away_time'] / total_time) * 100
    else:
        work_pct = idle_pct = away_pct = 0
    
    track_ids = data.get('track_ids', set())
    print(f"\n👷 Person ID {person_id} (Track IDs: {sorted(track_ids)})")
    print(f"  ├─ Zone: {person_to_zone.get(person_id, 'N/A')}")
    print(f"  ├─ Working Time:  {format_time(data['working_time'])}  ({work_pct:.1f}%)")
    print(f"  ├─ Idle Time:     {format_time(data['idle_time'])}  ({idle_pct:.1f}%)")
    print(f"  ├─ Away Time:     {format_time(data['away_time'])}  ({away_pct:.1f}%)")
    print(f"  └─ Efficiency:    {work_pct:.1f}%")

print("\n" + "="*60)
print(f"✅ Total Workstations Detected: {len(workstation_zones)}")
print("="*60)
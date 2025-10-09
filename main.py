from ultralytics import YOLO
import cv2
import numpy as np
import time
import csv

model = YOLO("yolov8n-pose.pt")

# Path video
video_path = "sample-puterako.mp4"

# DEFINISI ZONA WORKSTATION (x1, y1, x2, y2)
# Format: {zone_id: (x1, y1, x2, y2, "nama_zona")}
WORKSTATION_ZONES = {
    # Video Puterako Zone sample-puterako.mp4
    1: (10, 50, 350, 550, "Workstation A"),
    2: (450, 50, 750, 550, "Workstation B"),
    
    # Sample-1
    # 1: (150, 100, 650, 450, "Workstation A"),
    
    # Tambahkan zona sesuai kebutuhan
}



worker_data = {}
zone_ownership = {}  # {zone_id: person_id}
person_to_zone = {}  # {person_id: zone_id}
track_to_person = {}  # {track_id: person_id}

# Keypoints
HAND_KEYPOINTS = [9, 10]
SHOULDER_KEYPOINTS = [5, 6]
HEAD_KEYPOINT = 0
HIP_KEYPOINTS = [11, 12]
EAR_KEYPOINTS = [3, 4]

# Thresholds
ACTIVITY_THRESHOLD = 8
IDLE_TIMEOUT = 3
AWAY_TIMEOUT = 2
VISIBILITY_THRESHOLD = 0.5
REID_TIMEOUT = 15

next_person_id = 1

csv_rows = []
for zone_id, zone_data in WORKSTATION_ZONES.items():
    zone_name = zone_data[4] if len(zone_data) > 4 else f"Zone {zone_id}"
    active = idle = away = 0
    for data in worker_data.values():
        if person_to_zone.get(data["zone_id"]) == zone_id or data["zone_id"] == zone_id:
            if data["status"] == "working":
                active += 1
            elif data["status"] == "idle":
                idle += 1
            elif data["status"] == "away":
                away += 1
    csv_rows.append([zone_name, active, idle, away])

with open("workstation_summary.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["workstation", "Total Active", "Total Idle", "Total Away"])
    writer.writerows(csv_rows)

print("📁 Summary saved to workstation_summary.csv")
# ============================================
# HELPER FUNCTIONS
# ============================================

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

def find_zone_by_position(center):
    """Cari zona berdasarkan posisi center"""
    if center is None:
        return None
    
    x, y = center
    for zone_id, zone_data in WORKSTATION_ZONES.items():
        x1, y1, x2, y2 = zone_data[:4]
        if x1 <= x <= x2 and y1 <= y <= y2:
            return zone_id
    return None

def is_in_zone(center, zone_id):
    """Cek apakah posisi center ada di dalam zona"""
    if center is None or zone_id is None or zone_id not in WORKSTATION_ZONES:
        return False
    
    x, y = center
    x1, y1, x2, y2 = WORKSTATION_ZONES[zone_id][:4]
    return x1 <= x <= x2 and y1 <= y <= y2

def reid_person(track_id, center, current_time):
    """Re-identify person berdasarkan TRACK ID & ZONA"""
    global next_person_id
    
    if center is None:
        return None
    
    # PRIORITAS 1: Track ID yang sama = person yang sama
    if track_id in track_to_person:
        old_person_id = track_to_person[track_id]
        if old_person_id in worker_data:
            return old_person_id
    
    # PRIORITAS 2: Cari zona dari posisi
    zone_id = find_zone_by_position(center)
    
    if zone_id is None:
        return None
    
    # PRIORITAS 3: Cek ownership zona
    if zone_id in zone_ownership:
        old_person_id = zone_ownership[zone_id]
        if old_person_id in worker_data:
            # 1 zona = 1 person
            track_to_person[track_id] = old_person_id
            return old_person_id
    
    # PRIORITAS 4: Person baru di zona ini
    person_id = next_person_id
    next_person_id += 1
    
    zone_ownership[zone_id] = person_id
    person_to_zone[person_id] = zone_id
    track_to_person[track_id] = person_id
    
    zone_name = WORKSTATION_ZONES[zone_id][4] if len(WORKSTATION_ZONES[zone_id]) > 4 else f"Zone {zone_id}"
    print(f"🆕 New worker detected: Person {person_id} at {zone_name}")
    
    return person_id

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

def draw_zones(frame):
    """Gambar semua zona workstation dan info status/durasi di dalamnya"""
    current_time = time.time()
    for zone_id, zone_data in WORKSTATION_ZONES.items():
        x1, y1, x2, y2 = zone_data[:4]
        zone_name = zone_data[4] if len(zone_data) > 4 else f"Zone {zone_id}"
        
        # Zona border
        color = (100, 100, 100)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        
        # Label zona
        cv2.putText(frame, zone_name, (x1 + 5, y1 + 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Status okupansi & info
        if zone_id in zone_ownership:
            person_id = zone_ownership[zone_id]
            data = worker_data.get(person_id)
            if data:
                # Tampilkan semua status dan durasi
                info_texts = [
                    ("WORKING", data["working_time"], (0, 255, 0)),
                    ("IDLE", data["idle_time"], (0, 165, 255)),
                    ("AWAY", data["away_time"], (0, 0, 255)),
                ]
                for i, (label, duration, color_info) in enumerate(info_texts):
                    text = f"{label}: {format_time(duration)}"
                    cv2.putText(frame, text, (x1 + 5, y1 + 45 + i*20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_info, 2)
        else:
            # Zona kosong, tampilkan durasi kosong
            empty_key = f"zone_{zone_id}_empty_since"
            if not hasattr(draw_zones, "empty_times"):
                draw_zones.empty_times = {}
            if empty_key not in draw_zones.empty_times:
                draw_zones.empty_times[empty_key] = current_time
            empty_duration = current_time - draw_zones.empty_times[empty_key]
            cv2.putText(frame, f"Empty: {format_time(empty_duration)}", (x1 + 5, y1 + 45),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 2)
        # Reset waktu kosong jika zona baru terisi
        if zone_id in zone_ownership:
            empty_key = f"zone_{zone_id}_empty_since"
            if hasattr(draw_zones, "empty_times") and empty_key in draw_zones.empty_times:
                draw_zones.empty_times[empty_key] = current_time

# ============================================
# MAIN LOOP
# ============================================



cap = cv2.VideoCapture(video_path)
frame_count = 0
fps = cap.get(cv2.CAP_PROP_FPS) or 30

output_path = "output_tracking.mp4"
frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))


print("🎥 Starting worker tracking...")
print(f"📍 Monitoring {len(WORKSTATION_ZONES)} workstations")
print("="*60)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    
    frame_count += 1
    current_time = time.time()
    
    # Gambar zona terlebih dahulu
    draw_zones(frame)
    
    # Track dengan YOLO
    results = model.track(frame, conf=0.7, persist=True, verbose=False)
    
    active_persons = set()
    
    for result in results:
        if not hasattr(result, "keypoints") or result.boxes.id is None:
            continue
        
        track_ids = result.boxes.id.int().cpu().tolist()
        
        for idx, track_id in enumerate(track_ids):
            keypoints = result.keypoints.xy[idx].cpu().numpy()
            visibility = result.keypoints.conf[idx].cpu().numpy()
            
            if not is_valid_detection(visibility):
                continue
            
            center = get_person_center(keypoints, visibility)
            
            # Re-identify person
            person_id = reid_person(track_id, center, current_time)
            
            if person_id is None:
                # Orang di luar zona, skip
                continue
            
            active_persons.add(person_id)
            
            # Inisialisasi data jika perlu
            if person_id not in worker_data:
                zone_id = person_to_zone.get(person_id)
                
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
                    "track_ids": {track_id}
                }
            else:
                worker_data[person_id]["track_ids"].add(track_id)
            
            data = worker_data[person_id]
            data["last_seen"] = current_time
            
            # Cek zona
            zone_id = person_to_zone.get(person_id)
            in_zone = is_in_zone(center, zone_id)
            
            # Hitung activity score
            activity_score = calculate_activity_score(
                keypoints, 
                data["last_pose"],
                visibility,
                data["last_visibility"]
            )
            
            time_delta = current_time - data["last_update"]
            # time_delta = 1.0 / fps

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
            
            # Highlight zona aktif
            if zone_id in WORKSTATION_ZONES:
                zx1, zy1, zx2, zy2 = WORKSTATION_ZONES[zone_id][:4]
                zone_color = (0, 255, 0) if in_zone else (0, 0, 255)
                cv2.rectangle(frame, (zx1, zy1), (zx2, zy2), zone_color, 3)
            
            if center:
                cv2.circle(frame, center, 5, (255, 255, 0), -1)
            
            # Keypoints
            for kp_idx in HAND_KEYPOINTS + SHOULDER_KEYPOINTS + EAR_KEYPOINTS:
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
    
    # Summary overlay
    total_workers = len(worker_data)
    working = sum(1 for w in worker_data.values() if w["status"] == "working")
    idle = sum(1 for w in worker_data.values() if w["status"] == "idle")
    away = sum(1 for w in worker_data.values() if w["status"] == "away")
    
    overlay = frame.copy()
    cv2.rectangle(overlay, (5, 5), (450, 100), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
    
    cv2.putText(frame, f"Workers: {total_workers} | Zones: {len(WORKSTATION_ZONES)}", (10, 25),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(frame, f"Working: {working}  |  Idle: {idle}  |  Away: {away}", (10, 50),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(frame, f"Frame: {frame_count}", (10, 75),
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 255, 100), 1)
    
    cv2.imshow("Worker Tracking - Hardcoded Zones", frame)
    
    out.write(frame)  # Tambahkan ini untuk menyimpan frame ke video

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
out.release()
cv2.destroyAllWindows()

# ============================================
# FINAL SUMMARY
# ============================================

print("\n" + "="*60)
print("📊 WORK ACTIVITY SUMMARY")
print("="*60)

for person_id, data in sorted(worker_data.items()):
    total_time = data['working_time'] + data['idle_time'] + data['away_time']
    
    if total_time > 0:
        work_pct = (data['working_time'] / total_time) * 100
        idle_pct = (data['idle_time'] / total_time) * 100
        away_pct = (data['away_time'] / total_time) * 100
    else:
        work_pct = idle_pct = away_pct = 0
    
    zone_id = person_to_zone.get(person_id)
    zone_name = "N/A"
    if zone_id and zone_id in WORKSTATION_ZONES:
        zone_name = WORKSTATION_ZONES[zone_id][4] if len(WORKSTATION_ZONES[zone_id]) > 4 else f"Zone {zone_id}"
    
    track_ids = data.get('track_ids', set())
    print(f"\n👷 Person ID {person_id} (Track IDs: {sorted(track_ids)})")
    print(f"  ├─ Location: {zone_name}")
    print(f"  ├─ Working Time:  {format_time(data['working_time'])}  ({work_pct:.1f}%)")
    print(f"  ├─ Idle Time:     {format_time(data['idle_time'])}  ({idle_pct:.1f}%)")
    print(f"  ├─ Away Time:     {format_time(data['away_time'])}  ({away_pct:.1f}%)")
    print(f"  └─ Efficiency:    {work_pct:.1f}%")

print("\n" + "="*60)
print(f"✅ Monitored Workstations: {len(WORKSTATION_ZONES)}")
print("="*60)
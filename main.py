from ultralytics import YOLO
import cv2
import numpy as np
import time

model = YOLO("yolov8n-pose.pt")

video_path = "sample.mp4"  
cap = cv2.VideoCapture(video_path)

worker_data = {}  

# Threshold perubahan pose (semakin kecil semakin sensitif)
POSE_CHANGE_THRESHOLD = 15
IDLE_TIMEOUT = 5  # detik sebelum dinyatakan idle

def calculate_pose_change(pose1, pose2):
    """Hitung perubahan pose antar frame (L2 distance antar keypoints)"""
    if pose1 is None or pose2 is None:
        return 0
    return np.linalg.norm(pose1 - pose2)

def format_time(seconds):
    """Ubah detik jadi format menit/jam"""
    minutes = int(seconds // 60)
    hours = minutes // 60
    minutes = minutes % 60
    if hours > 0:
        return f"{hours} hour {minutes} min"
    return f"{minutes} min"

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    results = model.predict(frame, conf=0.6, verbose=False)
    current_time = time.time()

    for result in results:
        if not hasattr(result, "keypoints"):
            continue

        for idx, kps in enumerate(result.keypoints.xy):
            person_id = idx  
            keypoints = kps.cpu().numpy()

            if person_id not in worker_data:
                worker_data[person_id] = {
                    "last_pose": keypoints,
                    "last_update": current_time,
                    "active_time": 0,
                    "status": "active"
                }

            data = worker_data[person_id]
            pose_diff = calculate_pose_change(keypoints, data["last_pose"])

            if pose_diff > POSE_CHANGE_THRESHOLD:
                # Aktif bekerja
                if data["status"] == "idle":
                    data["status"] = "active"
                    data["last_update"] = current_time
                else:
                    # Tambah waktu aktif
                    data["active_time"] += current_time - data["last_update"]
                    data["last_update"] = current_time
            else:
                # Tidak banyak bergerak
                if current_time - data["last_update"] > IDLE_TIMEOUT:
                    data["status"] = "idle"

            # Simpan pose terbaru
            data["last_pose"] = keypoints

            # Draw bounding box
            x1, y1, x2, y2 = result.boxes.xyxy[idx].int().tolist()
            color = (0, 255, 0) if data["status"] == "active" else (0, 0, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
             # Draw keypoints
            for kp in keypoints:
                x, y = int(kp[0]), int(kp[1])
                cv2.circle(frame, (x, y), 4, (255, 0, 0), -1)  

            conf = float(result.boxes.conf[idx])
            # Tampilkan status & waktu kerja
            text = f"{data['status'].capitalize()} | {format_time(data['active_time'])} | {conf:.2f}"
            cv2.putText(frame, text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    cv2.imshow("Work Activity Tracking", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

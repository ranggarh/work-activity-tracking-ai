from ultralytics import YOLO
import cv2
import numpy as np
import time
from datetime import datetime
import multiprocessing
import json
import signal
import pandas as pd
import os
import threading
import socket
import pickle
import struct
import queue
with open("config.json") as f:
    config = json.load(f)

# =========================
# Helper Functions
# =========================

def frame_server(frame_queue, host='localhost', port=9999):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(1)
    print(f"[FrameServer] Listening on {host}:{port}")
    while True:
        print("[FrameServer] Waiting for client connection...")
        conn, addr = server_socket.accept()
        print(f"[FrameServer] Client connected: {addr}")

        # Flush frame_queue to avoid sending old frames
        try:
            while not frame_queue.empty():
                frame_queue.get_nowait()
        except Exception:
            pass

        try:
            while True:
                try:
                    cam_idx, frame_rgb = frame_queue.get(timeout=1)
                    data = pickle.dumps((cam_idx, frame_rgb))
                    msg = struct.pack("Q", len(data)) + data
                    conn.sendall(msg)
                except queue.Empty:
                    continue
        except Exception as e:
            print(f"[FrameServer] Error: {e}")
            conn.close()
    server_socket.close()

def format_time(seconds):
    minutes = int(seconds // 60)
    hours = minutes // 60
    minutes = minutes % 60
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"

def is_work_time(now, work_start, work_end, overtime):
    in_work = False
    if work_start and work_end:
        sh, sm = map(int, work_start.split(":"))
        eh, em = map(int, work_end.split(":"))
        start = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
        end = now.replace(hour=eh, minute=em, second=0, microsecond=0)
        if start <= now <= end:
            in_work = True
    for ot in overtime:
        osh, osm, oeh, oem = ot
        ot_start = now.replace(hour=osh, minute=osm, second=0, microsecond=0)
        ot_end = now.replace(hour=oeh, minute=oem, second=0, microsecond=0)
        if ot_start <= now <= ot_end:
            in_work = True
    return in_work

def is_break_time(now, break_times):
    for sh, sm, eh, em in break_times:
        start = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
        end = now.replace(hour=eh, minute=em, second=0, microsecond=0)
        if start <= now <= end:
            return True
    return False

def get_person_center(keypoints, visibility, HEAD_KEYPOINT, SHOULDER_KEYPOINTS, HIP_KEYPOINTS, VISIBILITY_THRESHOLD):
    visible_points = []
    for idx in [HEAD_KEYPOINT] + SHOULDER_KEYPOINTS + HIP_KEYPOINTS:
        if visibility[idx] > VISIBILITY_THRESHOLD:
            visible_points.append(keypoints[idx])
    if len(visible_points) > 0:
        center = np.mean(visible_points, axis=0)
        return int(center[0]), int(center[1])
    return None

def find_zone_by_position(center, WORKSTATION_ZONES):
    if center is None:
        return None
    x, y = center
    for zone_id, zone_data in WORKSTATION_ZONES.items():
        x1, y1, x2, y2 = zone_data[:4]
        if x1 <= x <= x2 and y1 <= y <= y2:
            return zone_id
    return None

def is_in_zone(center, zone_id, WORKSTATION_ZONES):
    if center is None or zone_id is None or zone_id not in WORKSTATION_ZONES:
        return False
    x, y = center
    x1, y1, x2, y2 = WORKSTATION_ZONES[zone_id][:4]
    return x1 <= x <= x2 and y1 <= y <= y2

def calculate_activity_score(pose1, pose2, vis1, vis2, HAND_KEYPOINTS, SHOULDER_KEYPOINTS, VISIBILITY_THRESHOLD):
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

def is_valid_detection(visibility, HEAD_KEYPOINT, VISIBILITY_THRESHOLD):
    head_visible = visibility[HEAD_KEYPOINT] > VISIBILITY_THRESHOLD
    shoulders_visible = (visibility[5] > VISIBILITY_THRESHOLD and visibility[6] > VISIBILITY_THRESHOLD)
    return head_visible or shoulders_visible

def draw_zones(frame, WORKSTATION_ZONES, worker_data, zone_ownership, format_time):
    current_time = time.time()
    for zone_id, zone_data in WORKSTATION_ZONES.items():
        x1, y1, x2, y2 = zone_data[:4]
        zone_name = zone_data[4] if len(zone_data) > 4 else f"Zone {zone_id}"
        # Default color abu-abu
        color = (100, 100, 100)
        # Jika ada pekerja di zona ini, cek statusnya
        if zone_id in zone_ownership:
            person_id = zone_ownership[zone_id]
            data = worker_data.get(person_id)
            if data:
                if data["status"] == "away":
                    color = (0, 0, 255)      # Merah untuk away
                elif data["status"] == "idle":
                    color = (0, 165, 255)    # Oranye untuk idle
                elif data["status"] == "working":
                    color = (0, 255, 0)      # Hijau untuk working
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, zone_name, (x1 + 5, y1 + 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        if zone_id in zone_ownership:
            person_id = zone_ownership[zone_id]
            data = worker_data.get(person_id)
            if data:
                info_texts = [
                    # ("WORKING", data["working_time"], (0, 255, 0)),
                    # ("IDLE", data["idle_time"], (0, 165, 255)),
                    # ("AWAY", data["away_time"], (0, 0, 255)),
                ]
                for i, (label, duration, color_info) in enumerate(info_texts):
                    text = f"{label}: {format_time(duration)}"
                    cv2.putText(frame, text, (x1 + 5, y1 + 45 + i*20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_info, 2)
        else:
            empty_key = f"zone_{zone_id}_empty_since"
            if not hasattr(draw_zones, "empty_times"):
                draw_zones.empty_times = {}
            if empty_key not in draw_zones.empty_times:
                draw_zones.empty_times[empty_key] = current_time
            empty_duration = current_time - draw_zones.empty_times[empty_key]
            # cv2.putText(frame, f"Empty: {format_time(empty_duration)}", (x1 + 5, y1 + 45),
            #             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 2)
        if zone_id in zone_ownership:
            empty_key = f"zone_{zone_id}_empty_since"
            if hasattr(draw_zones, "empty_times") and empty_key in draw_zones.empty_times:
                draw_zones.empty_times[empty_key] = current_time


def save_camera_summary_xlsx(cam_idx, WORKSTATION_ZONES, zone_ownership, worker_data, filename):
    import pandas as pd
    import os

    now_dt = datetime.now()
    today_str = now_dt.strftime("%Y-%m-%d")
    rows = []
    for zone_id, zone_data in WORKSTATION_ZONES.items():
        zone_name = zone_data[4] if len(zone_data) > 4 else f"Zone {zone_id}"
        person_id = zone_ownership.get(zone_id)
        if person_id and person_id in worker_data:
            w = worker_data[person_id]
            rows.append({
                "Timestamp": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "Camera": cam_idx,
                "Zone": zone_name,
                "Working Time": format_time(w['working_time']),
                "Idle Time": format_time(w['idle_time']),
                "Away Time": format_time(w['away_time']),
            })
        else:
            rows.append({
                "Timestamp": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "Camera": cam_idx,
                "Zone": zone_name,
                "Working Time": "0s",
                "Idle Time": "0s",
                "Away Time": "0s",
            })
    df_new = pd.DataFrame(rows)

    if not os.path.isfile(filename):
        df_new.to_excel(filename, index=False)
    else:
        df_old = pd.read_excel(filename)
        # Cek tanggal pada baris terakhir
        if not df_old.empty:
            last_date = str(df_old.iloc[-1]["Timestamp"])[:10]
        else:
            last_date = None
        if last_date == today_str:
            # Update baris yang ada (replace semua data hari ini)
            # Filter baris yang bukan hari ini
            df_old = df_old[df_old["Timestamp"].str[:10] != today_str]
            df_result = pd.concat([df_old, df_new], ignore_index=True)
            df_result.to_excel(filename, index=False)
        else:
            # Hari baru, tambah baris baru
            df_result = pd.concat([df_old, df_new], ignore_index=True)
            df_result.to_excel(filename, index=False)

# =========================
# Tracking Function
# =========================

def run_tracking(cam_idx, VIDEO_SOURCE, WORKSTATION_ZONES, break_times, work_start, work_end, overtime, frame_queue, stop_event=None):
    """
    Modified tracking function that sends frames to queue instead of showing windows
    """
    # Keypoints & Thresholds
    HAND_KEYPOINTS = [9, 10]
    SHOULDER_KEYPOINTS = [5, 6]
    HEAD_KEYPOINT = 0
    HIP_KEYPOINTS = [11, 12]
    ACTIVITY_THRESHOLD = 8
    IDLE_TIMEOUT = 3
    AWAY_TIMEOUT = 5
    VISIBILITY_THRESHOLD = 0.5

    model = YOLO("yolov8n-pose.pt")
    worker_data = {}
    zone_ownership = {}
    person_to_zone = {}
    track_to_person = {}
    next_person_id = 1

    print(f"\n=== Camera {cam_idx} ===")
    print(f"🔌 Connecting to video source: {VIDEO_SOURCE}")
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    if VIDEO_SOURCE.startswith("rtsp://") or VIDEO_SOURCE.startswith("http://"):
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not cap.isOpened():
        print(f"❌ Error: Cannot connect to video source {VIDEO_SOURCE}")
        return

    frame_count = 0
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    fps_display = 0
    fps_timer = time.time()
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(f"output_tracking_cam{cam_idx}.mp4", fourcc, fps, (640, 360))

    last_xlsx_update = time.time()
    xlsx_filename = f"summary_cam{cam_idx}.xlsx"

    while True:
        if stop_event is not None and stop_event.is_set():
            print(f"[INFO] Camera {cam_idx} received stop event, exiting...")
            break
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.resize(frame, (640, 360))
        frame_count += 1
        current_time = time.time()
        now_dt = datetime.now()
        break_active = is_break_time(now_dt, break_times)
        work_active = is_work_time(now_dt, work_start, work_end, overtime)

        if frame_count % 10 == 0:
            elapsed = current_time - fps_timer
            if elapsed > 0:
                fps_display = 10 / elapsed
            fps_timer = current_time

        draw_zones(frame, WORKSTATION_ZONES, worker_data, zone_ownership, format_time)
        results = model.track(frame, conf=0.2, persist=True, verbose=False)
        active_persons = set()

        for result in results:
            if not hasattr(result, "keypoints") or result.boxes.id is None:
                continue
            track_ids = result.boxes.id.int().cpu().tolist()
            for idx, track_id in enumerate(track_ids):
                keypoints = result.keypoints.xy[idx].cpu().numpy()
                visibility = result.keypoints.conf[idx].cpu().numpy()
                for i, (x, y) in enumerate(keypoints):
                    if visibility[i] > 0.5:
                        cv2.circle(frame, (int(x), int(y)), 3, (0, 255, 0), -1)
                skeleton_pairs = [
                    (0, 5), (0, 6), (5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12), (11, 12)
                ]
                for a, b in skeleton_pairs:
                    if visibility[a] > 0.5 and visibility[b] > 0.5:
                        pt1 = tuple(map(int, keypoints[a]))
                        pt2 = tuple(map(int, keypoints[b]))
                        cv2.line(frame, pt1, pt2, (255, 0, 0), 2)
                if not is_valid_detection(visibility, HEAD_KEYPOINT, VISIBILITY_THRESHOLD):
                    continue
                center = get_person_center(keypoints, visibility, HEAD_KEYPOINT, SHOULDER_KEYPOINTS, HIP_KEYPOINTS, VISIBILITY_THRESHOLD)
                
                if track_id in track_to_person:
                    person_id = track_to_person[track_id]
                else:
                    zone_id = find_zone_by_position(center, WORKSTATION_ZONES)
                    if zone_id is None:
                        continue
                    if zone_id in zone_ownership:
                        person_id = zone_ownership[zone_id]
                    else:
                        person_id = next_person_id
                        next_person_id += 1
                        zone_ownership[zone_id] = person_id
                        person_to_zone[person_id] = zone_id
                    track_to_person[track_id] = person_id

                active_persons.add(person_id)
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
                zone_id = person_to_zone.get(person_id)
                in_zone = is_in_zone(center, zone_id, WORKSTATION_ZONES)
                activity_score = calculate_activity_score(
                    keypoints, 
                    data["last_pose"],
                    visibility,
                    data["last_visibility"],
                    HAND_KEYPOINTS,
                    SHOULDER_KEYPOINTS,
                    VISIBILITY_THRESHOLD
                )
                time_delta = current_time - data["last_update"]
                if work_active and not break_active:
                    if not in_zone:
                        if data["status"] != "away":
                            if current_time - data["last_update"] > AWAY_TIMEOUT:
                                data["status"] = "away"
                        data["away_time"] += time_delta
                    else:
                        if activity_score > ACTIVITY_THRESHOLD:
                            if data["status"] != "working":
                                data["status"] = "working"
                                if data.get("was_away"):
                                    data["was_away"] = False
                            data["working_time"] += time_delta
                            data["last_activity_time"] = current_time
                        else:
                            if current_time - data["last_activity_time"] > IDLE_TIMEOUT:
                                if data["status"] == "working":
                                    data["status"] = "idle"
                                data["idle_time"] += time_delta
                            else:
                                data["working_time"] += time_delta
                data["last_pose"] = keypoints
                data["last_visibility"] = visibility
                data["last_update"] = current_time
                data["center"] = center

        current_time = time.time()
        for person_id, data in worker_data.items():
            if person_id not in active_persons:
                if current_time - data["last_seen"] > AWAY_TIMEOUT:
                    if data["status"] != "away":
                        data["status"] = "away"
                    data["away_time"] += current_time - data["last_update"]
                data["last_update"] = current_time

        total_workers = len(worker_data)
        working = sum(1 for w in worker_data.values() if w["status"] == "working")
        idle = sum(1 for w in worker_data.values() if w["status"] == "idle")
        away = sum(1 for w in worker_data.values() if w["status"] == "away")

        overlay = frame.copy()
        cv2.rectangle(overlay, (5, 5), (450, 100), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
        now_dt = datetime.now()
        timestamp_str = now_dt.strftime("%H:%M:%S")
        cv2.putText(frame, f"Camera {cam_idx} [{timestamp_str}]", (10, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,255), 2)
        cv2.putText(frame, f"Workers: {total_workers} | Zones: {len(WORKSTATION_ZONES)}", (10, 35),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"Working: {working}  |  Idle: {idle}  |  Away: {away}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"FPS: {fps_display:.2f} (Video: {fps:.2f})", (10, 85),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        out.write(frame)

        if time.time() - last_xlsx_update > 300:  # 300 detik = 5 menit
            save_camera_summary_xlsx(cam_idx, WORKSTATION_ZONES, zone_ownership, worker_data, xlsx_filename)
            last_xlsx_update = time.time()

        # Send frame to queue (non-blocking)
        try:
            if not frame_queue.full():
                if frame is not None and frame.shape == (360, 640, 3):
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frame_queue.put((cam_idx, frame_rgb), block=False)
                else:
                    print(f"[WARNING] Frame shape invalid: {frame.shape if frame is not None else None}")
        except Exception as e:
            print(f"[ERROR] Queue put error: {e}")

    cap.release()
    out.release()
    print(f"\nCamera {cam_idx} Summary:")
    print(f"Total Worker : {total_workers}")
    print(f"Total Zone   : {len(WORKSTATION_ZONES)}")
    for zone_id, zone_data in WORKSTATION_ZONES.items():
        zone_name = zone_data[4] if len(zone_data) > 4 else f"Zone {zone_id}"
        person_id = zone_ownership.get(zone_id)
        if person_id and person_id in worker_data:
            w = worker_data[person_id]
            print(f"Zone {zone_name}:")
            print(f"  Working Time: {format_time(w['working_time'])}")
            print(f"  Idle Time   : {format_time(w['idle_time'])}")
            print(f"  Away Time   : {format_time(w['away_time'])}")
        else:
            print(f"Zone {zone_name}:")
            print(f"  Working Time: 0s")
            print(f"  Idle Time   : 0s")
            print(f"  Away Time   : 0s")
    print("="*60)
    
def terminate_all(jobs):
    for p in jobs:
        if p.is_alive():
            p.terminate()
            p.join()

# =========================
# Multiprocessing Main
# =========================

if __name__ == "__main__":
    VIDEO_SOURCES = config["video_sources"]
    frame_queue = multiprocessing.Queue(maxsize=30)
    jobs = []
    server_thread = threading.Thread(target=frame_server, args=(frame_queue,), daemon=True)
    server_thread.start()
    for idx, (src, cam_config) in enumerate(VIDEO_SOURCES, start=1):
        zones = cam_config.get("zones", {})
        breaks = cam_config.get("breaks", [])
        work_start = cam_config.get("work_start", "")
        work_end = cam_config.get("work_end", "")
        overtime = cam_config.get("overtime", [])
        p = multiprocessing.Process(target=run_tracking, args=(idx, src, zones, breaks, work_start, work_end, overtime, frame_queue))
        p.start()
        jobs.append(p)

    def signal_handler(sig, frame):
        print("Ctrl+C detected, terminating all processes...")
        terminate_all(jobs)
        exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        for p in jobs:
            p.join()
    except KeyboardInterrupt:
        terminate_all(jobs)
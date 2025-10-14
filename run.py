import multiprocessing
from scheduler import SchedulerGUI
from main import run_tracking
import json

def terminate_all(jobs):
    for p in jobs:
        if p.is_alive():
            p.terminate()
            p.join()


if __name__ == "__main__":
    # Load config
    with open("config.json") as f:
        config = json.load(f)
    VIDEO_SOURCES = config["video_sources"]

    frame_queue = multiprocessing.Queue(maxsize=30)
    stop_events = []
    jobs = []
    for idx, (src, cam_config) in enumerate(VIDEO_SOURCES, start=1):
        zones = cam_config.get("zones", {})
        breaks = cam_config.get("breaks", [])
        work_start = cam_config.get("work_start", "")
        work_end = cam_config.get("work_end", "")
        overtime = cam_config.get("overtime", [])
        stop_event = multiprocessing.Event()
        p = multiprocessing.Process(
            target=run_tracking,
            args=(idx, src, zones, breaks, work_start, work_end, overtime, frame_queue, stop_event)
        )
        p.start()
        jobs.append(p)
        stop_events.append(stop_event)

    app = SchedulerGUI(frame_queue=frame_queue, jobs=jobs, stop_events=stop_events)
    app.mainloop()

    # Cleanup
    for ev in stop_events:
        ev.set()
    for p in jobs:
        p.join()
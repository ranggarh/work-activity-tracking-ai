import tkinter as tk
from tkinter import messagebox
import json
from datetime import datetime


class SchedulerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Scheduler Config")
        self.geometry("600x700")
        self.break_entries = []
        self.video_entries = []

        # Load config jika ada
        self.config_data = None
        try:
            with open("config.json") as f:
                self.config_data = json.load(f)
        except Exception:
            self.config_data = None

        # Tanggal hari ini
        today = datetime.now().strftime("%A, %d %B %Y")
        tk.Label(self, text=f"Tanggal: {today}", font=("Arial", 12, "bold")).pack(pady=5)

        # Jam kerja
        frame_work = tk.Frame(self)
        frame_work.pack(pady=5)
        tk.Label(frame_work, text="Jam Mulai Kerja (HH:MM):").grid(row=0, column=0)
        self.start_work = tk.Entry(frame_work, width=8)
        self.start_work.grid(row=0, column=1)
        tk.Label(frame_work, text="Jam Selesai Kerja (HH:MM):").grid(row=1, column=0)
        self.end_work = tk.Entry(frame_work, width=8)
        self.end_work.grid(row=1, column=1)

        # Jam istirahat (bisa lebih dari satu)
        tk.Label(self, text="Jam Istirahat (bisa lebih dari satu):", font=("Arial", 10, "bold")).pack()
        self.break_frame = tk.Frame(self)
        self.break_frame.pack()
        # Jika ada config, isi break dari config
        if self.config_data and "breaks" in self.config_data:
            for br in self.config_data["breaks"]:
                self.add_break_entry(br)
        else:
            self.add_break_entry()
        tk.Button(self, text="Tambah Jam Istirahat", command=self.add_break_entry).pack(pady=2)

        # Jam lembur
        frame_ot = tk.Frame(self)
        frame_ot.pack(pady=5)
        tk.Label(frame_ot, text="Jam Mulai Lembur (HH:MM):").grid(row=0, column=0)
        self.start_ot = tk.Entry(frame_ot, width=8)
        self.start_ot.grid(row=0, column=1)
        tk.Label(frame_ot, text="Jam Selesai Lembur (HH:MM):").grid(row=1, column=0)
        self.end_ot = tk.Entry(frame_ot, width=8)
        self.end_ot.grid(row=1, column=1)

        # Daftar kamera/source
        tk.Label(self, text="Daftar Kamera/Source:", font=("Arial", 10, "bold")).pack(pady=5)
        self.video_frame = tk.Frame(self)
        self.video_frame.pack()
        # Jika ada config, isi kamera dan zona dari config
        if self.config_data and "video_sources" in self.config_data:
            for src, zones in self.config_data["video_sources"]:
                self.add_video_entry(src, zones)
        else:
            self.add_video_entry()
        tk.Button(self, text="Tambah Kamera", command=self.add_video_entry).pack(pady=2)

        # Tombol simpan
        tk.Button(self, text="Simpan Setting", command=self.save_config, bg="#4CAF50", fg="white").pack(pady=10)

        # Isi jam kerja dan lembur jika ada config
        if self.config_data:
            self.start_work.insert(0, self.config_data.get("work_start", ""))
            self.end_work.insert(0, self.config_data.get("work_end", ""))
            ot = self.config_data.get("overtime")
            if ot:
                self.start_ot.insert(0, f"{ot[0]:02d}:{ot[1]:02d}")
                self.end_ot.insert(0, f"{ot[2]:02d}:{ot[3]:02d}")

    def add_break_entry(self, value=None):
        row = len(self.break_entries)
        start = tk.Entry(self.break_frame, width=8)
        end = tk.Entry(self.break_frame, width=8)
        tk.Label(self.break_frame, text=f"Istirahat {row+1} Mulai (HH:MM):").grid(row=row, column=0)
        start.grid(row=row, column=1)
        tk.Label(self.break_frame, text="Selesai (HH:MM):").grid(row=row, column=2)
        end.grid(row=row, column=3)
        if value:
            start.insert(0, f"{value[0]:02d}:{value[1]:02d}")
            end.insert(0, f"{value[2]:02d}:{value[3]:02d}")
        self.break_entries.append((start, end))

    def add_video_entry(self, src_val="", zones=None):
        row = len(self.video_entries)
        cam_frame = tk.Frame(self.video_frame)
        cam_frame.pack(pady=5, fill="x")
        src = tk.Entry(cam_frame, width=30)
        tk.Label(cam_frame, text=f"Source {row+1} (RTSP/MP4):").grid(row=0, column=0)
        src.grid(row=0, column=1)
        if src_val:
            src.insert(0, src_val)
        # Frame untuk zona per kamera
        zone_frame = tk.Frame(cam_frame)
        zone_frame.grid(row=1, column=0, columnspan=2, sticky="w")
        zone_entries = []
        if zones:
            for zid in sorted(zones.keys(), key=lambda x: int(x)):
                zone = zones[zid]
                zone_str = f"{zone[0]},{zone[1]},{zone[2]},{zone[3]},{zone[4]}"
                self.add_zone_entry(zone_frame, zone_entries, zone_str)
        else:
            self.add_zone_entry(zone_frame, zone_entries)
        tk.Button(cam_frame, text="Tambah Zona", command=lambda: self.add_zone_entry(zone_frame, zone_entries)).grid(row=2, column=0, pady=2)
        self.video_entries.append((src, zone_entries))

    def add_zone_entry(self, parent, zone_entries, value=""):
        row = len(zone_entries)
        zone = tk.Entry(parent, width=40)
        tk.Label(parent, text=f"Zona {row+1} (x1,y1,x2,y2,Nama):").grid(row=row, column=0)
        zone.grid(row=row, column=1)
        if value:
            zone.insert(0, value)
        zone_entries.append(zone)

    def save_config(self):
        try:
            work_start = self.start_work.get()
            work_end = self.end_work.get()
            breaks = []
            for start, end in self.break_entries:
                sh, sm = map(int, start.get().split(":"))
                eh, em = map(int, end.get().split(":"))
                breaks.append((sh, sm, eh, em))
            ot_start = self.start_ot.get()
            ot_end = self.end_ot.get()
            overtime = None
            if ot_start and ot_end:
                osh, osm = map(int, ot_start.split(":"))
                oeh, oem = map(int, ot_end.split(":"))
                overtime = (osh, osm, oeh, oem)
            video_sources = []
            for src, zone_entries in self.video_entries:
                src_val = src.get().strip()
                zones = {}
                zone_id = 1
                for zone in zone_entries:
                    zone_val = zone.get().strip()
                    zone_parts = zone_val.split(",")
                    if len(zone_parts) == 5 and all(zone_parts[:4]):
                        try:
                            x1, y1, x2, y2 = map(int, zone_parts[:4])
                            name = zone_parts[4].strip()
                            zones[zone_id] = (x1, y1, x2, y2, name)
                            zone_id += 1
                        except Exception:
                            continue
                if src_val and zones:
                    video_sources.append((src_val, zones))
            config = {
                "work_start": work_start,
                "work_end": work_end,
                "breaks": breaks,
                "overtime": overtime,
                "video_sources": video_sources,
                "date": datetime.now().strftime("%Y-%m-%d")
            }
            with open("config.json", "w") as f:
                json.dump(config, f, indent=2)
            messagebox.showinfo("Config Tersimpan", "Setting berhasil disimpan ke config.json!")
        except Exception as e:
            messagebox.showerror("Error", f"Format salah!\n{e}")

if __name__ == "__main__":
    app = SchedulerGUI()
    app.mainloop()
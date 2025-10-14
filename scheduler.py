import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
from datetime import datetime
from PIL import Image, ImageTk
import threading
import multiprocessing
import queue
import time


class SchedulerGUI(tk.Tk):
    def __init__(self, frame_queue=None):
        super().__init__()
        self.title("Work Activity Tracking Scheduler by Puterako")
        self.geometry("1200x800")
        
        # Shared queue for frames
        self.frame_queue = frame_queue
        self.camera_labels = {}  # Store label widgets for each camera
        self.running = True
        
        # Load config
        self.config_data = None
        self.schedule_templates = {}
        try:
            with open("config.json") as f:
                self.config_data = json.load(f)
                self.schedule_templates = self.config_data.get("schedule_templates", {})
        except Exception:
            pass

        header = tk.Frame(self, bg="#FFFFFF", height=60)
        header.pack(fill="x")

        # Logo kiri
        try:
            logo_img = tk.PhotoImage(file="logo_puterako.png").subsample(4, 4)
            logo_label = tk.Label(header, image=logo_img, bg="#FFFFFF")
            logo_label.image = logo_img
            logo_label.pack(side="left", padx=15, pady=10)
        except:
            pass

        # Tanggal kanan
        today = datetime.now().strftime("%A, %d %B %Y")
        date_label = tk.Label(header, text=f"📅 {today}", font=("Arial", 14, "bold"),
                            bg="#FFFFFF", fg="black")
        date_label.pack(side="right", padx=15, pady=10)

        # Notebook untuk tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Tab 1: Live Tracking
        self.create_live_tracking_tab()
        
        # Tab 2: Template Jadwal
        self.create_template_tab()
        
        # Tab 3: Konfigurasi Kamera
        self.create_camera_tab()

        # Bottom buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=10)
        tk.Button(btn_frame, text="💾 Simpan Konfigurasi", command=self.save_config,
                 bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), 
                 padx=20, pady=10).pack(side="right")
        
        # Start frame update thread if queue is provided
        if self.frame_queue:
            self.start_frame_update_thread()
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_live_tracking_tab(self):
        """Create tab for live camera feeds"""
        live_tab = tk.Frame(self.notebook)
        self.notebook.add(live_tab, text="📹 Live Tracking")

        # Control panel
        control_frame = tk.Frame(live_tab, bg="#f0f0f0", height=50)
        control_frame.pack(fill="x", padx=5, pady=5)
        
        tk.Label(control_frame, text="Live Camera Feeds", font=("Arial", 14, "bold"),
                bg="#f0f0f0").pack(side="left", padx=10)
        
        self.status_label = tk.Label(control_frame, text="● Streaming", 
                                     font=("Arial", 10), fg="green", bg="#f0f0f0")
        self.status_label.pack(side="right", padx=10)

        # Canvas with scrollbar for camera grid
        canvas_frame = tk.Frame(live_tab)
        canvas_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        canvas = tk.Canvas(canvas_frame, bg="#2b2b2b")
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        self.camera_container = tk.Frame(canvas, bg="#2b2b2b")
        
        self.camera_container.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.camera_container, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind mouse wheel
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # Initialize camera display widgets
        self.init_camera_widgets()

    def init_camera_widgets(self):
        """Initialize display widgets for each camera"""
        if not self.config_data or "video_sources" not in self.config_data:
            return
        
        num_cameras = len(self.config_data["video_sources"])
        cols = 2  # Bisa diubah sesuai kebutuhan

        for idx in range(num_cameras):
            row = idx // cols
            col = idx % cols
            
            cam_frame = tk.LabelFrame(self.camera_container, 
                                    text=f"Camera {idx + 1}",
                                    bg="#1e1e1e", fg="white",
                                    font=("Arial", 10, "bold"),
                                    padx=5, pady=5)
            cam_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            
            # Ubah ukuran label video jadi kecil
            video_label = tk.Label(cam_frame, bg="black", width=320, height=180)
            video_label.pack()
            
            info_label = tk.Label(cam_frame, text="Waiting for feed...", 
                                bg="#1e1e1e", fg="gray", font=("Arial", 9))
            info_label.pack(pady=5)
            
            self.camera_labels[idx + 1] = {
                'video': video_label,
                'info': info_label,
                'last_update': 0
            }
        
        for i in range(cols):
            self.camera_container.columnconfigure(i, weight=1)
    def start_frame_update_thread(self):
        """Start background thread to update frames from queue"""
        def update_frames():
            last_frame_time = time.time()
            while self.running:
                try:
                    # Get frame from queue (with timeout)
                    cam_idx, frame_rgb = self.frame_queue.get(timeout=0.1)
                    print(f"[DEBUG] Frame received for camera {cam_idx} at {time.strftime('%H:%M:%S')}")
                    last_frame_time = time.time()
                    # Update GUI in main thread
                    self.after(0, self.update_camera_display, cam_idx, frame_rgb)
                except queue.Empty:
                    # Jika lebih dari 2 detik tidak ada frame, log
                    if time.time() - last_frame_time > 2:
                        print("[DEBUG] Tidak ada frame baru dalam 2 detik")
                        last_frame_time = time.time()
                    continue
                except Exception as e:
                    print(f"[ERROR] Error updating frame: {e}")
                    continue

        thread = threading.Thread(target=update_frames, daemon=True)
        thread.start()

    def update_camera_display(self, cam_idx, frame_rgb):
        """Update camera display with new frame (runs in main thread)"""
        if cam_idx not in self.camera_labels:
            print(f"[WARNING] cam_idx {cam_idx} not in camera_labels")
            return

        try:
            # Ambil ukuran label video
            video_label = self.camera_labels[cam_idx]['video']
            label_width = video_label.winfo_width() or 320
            label_height = video_label.winfo_height() or 180

            # Resize frame dengan rasio yang sesuai (fit, tidak crop)
            img = Image.fromarray(frame_rgb)
            img = img.resize((label_width, label_height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image=img)
            video_label.configure(image=photo)
            video_label.image = photo  # Keep reference

            current_time = datetime.now().strftime("%H:%M:%S")
            self.camera_labels[cam_idx]['info'].configure(
                text=f"Last update: {current_time}",
                fg="lime"
            )
            self.camera_labels[cam_idx]['last_update'] = datetime.now().timestamp()
            print(f"[DEBUG] Frame displayed for camera {cam_idx} at {current_time}")

        except Exception as e:
            print(f"[ERROR] Error displaying frame for camera {cam_idx}: {e}")
    def create_template_tab(self):
        template_tab = tk.Frame(self.notebook)
        self.notebook.add(template_tab, text="📋 Template Jadwal")

        # Frame untuk daftar template
        list_frame = tk.LabelFrame(template_tab, text="Daftar Template", padx=10, pady=10)
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Listbox untuk template
        scroll_y = tk.Scrollbar(list_frame, orient="vertical")
        self.template_listbox = tk.Listbox(list_frame, yscrollcommand=scroll_y.set, height=8)
        scroll_y.config(command=self.template_listbox.yview)
        scroll_y.pack(side="right", fill="y")
        self.template_listbox.pack(fill="both", expand=True)
        self.template_listbox.bind('<<ListboxSelect>>', self.on_template_select)

        # Load existing templates
        for name in self.schedule_templates.keys():
            self.template_listbox.insert(tk.END, name)

        # Frame untuk edit template
        edit_frame = tk.LabelFrame(template_tab, text="Edit Template", padx=10, pady=10)
        edit_frame.pack(fill="both", padx=10, pady=10)

        # Nama template
        tk.Label(edit_frame, text="Nama Template:").grid(row=0, column=0, sticky="w", pady=5)
        self.template_name = tk.Entry(edit_frame, width=30)
        self.template_name.grid(row=0, column=1, columnspan=2, sticky="ew", pady=5)

        # Jam kerja
        tk.Label(edit_frame, text="Jam Kerja:").grid(row=1, column=0, sticky="w", pady=5)
        self.tmpl_work_start = tk.Entry(edit_frame, width=10)
        self.tmpl_work_start.grid(row=1, column=1, pady=5)
        tk.Label(edit_frame, text="s/d").grid(row=1, column=2)
        self.tmpl_work_end = tk.Entry(edit_frame, width=10)
        self.tmpl_work_end.grid(row=1, column=3, pady=5)

        # Istirahat
        tk.Label(edit_frame, text="Istirahat (HH:MM-HH:MM, pisah koma):").grid(row=2, column=0, sticky="w", pady=5)
        self.tmpl_breaks = tk.Entry(edit_frame, width=40)
        self.tmpl_breaks.grid(row=2, column=1, columnspan=3, sticky="ew", pady=5)
        tk.Label(edit_frame, text="Contoh: 12:00-13:00, 15:00-15:15", 
                font=("Arial", 8), fg="gray").grid(row=3, column=1, columnspan=3, sticky="w")

        # Lembur (bisa multiple)
        tk.Label(edit_frame, text="Lembur (HH:MM-HH:MM, pisah koma):").grid(row=4, column=0, sticky="w", pady=5)
        self.tmpl_overtime = tk.Entry(edit_frame, width=40)
        self.tmpl_overtime.grid(row=4, column=1, columnspan=3, sticky="ew", pady=5)
        tk.Label(edit_frame, text="Contoh: 17:00-19:00, 20:00-22:00", 
                font=("Arial", 8), fg="gray").grid(row=5, column=1, columnspan=3, sticky="w")

        edit_frame.columnconfigure(1, weight=1)
        edit_frame.columnconfigure(3, weight=1)

        # Buttons
        btn_frame = tk.Frame(edit_frame)
        btn_frame.grid(row=6, column=0, columnspan=4, pady=10)
        tk.Button(btn_frame, text="➕ Tambah/Update Template", 
                 command=self.save_template, bg="#2196F3", fg="white").pack(side="left", padx=5)
        tk.Button(btn_frame, text="🗑️ Hapus Template", 
                 command=self.delete_template, bg="#f44336", fg="white").pack(side="left", padx=5)
        tk.Button(btn_frame, text="🔄 Clear", 
                 command=self.clear_template_form).pack(side="left", padx=5)

    def create_camera_tab(self):
        camera_tab = tk.Frame(self.notebook)
        self.notebook.add(camera_tab, text="🎥 Konfigurasi Kamera")

        # Toolbar
        toolbar = tk.Frame(camera_tab)
        toolbar.pack(fill="x", padx=10, pady=5)
        tk.Button(toolbar, text="➕ Tambah Kamera", command=self.add_camera_row,
                 bg="#2196F3", fg="white").pack(side="left", padx=5)

        # Scrollable frame untuk kamera
        canvas = tk.Canvas(camera_tab)
        scrollbar = tk.Scrollbar(camera_tab, orient="vertical", command=canvas.yview)
        self.camera_frame = tk.Frame(canvas)
        
        self.camera_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.camera_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=10)
        scrollbar.pack(side="right", fill="y")

        # Bind mouse wheel
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        self.camera_entries = []
        
        # Load existing cameras
        if self.config_data and "video_sources" in self.config_data:
            for src_data in self.config_data["video_sources"]:
                if len(src_data) == 2:
                    src, config = src_data
                    zones = config.get("zones", {})
                    work_start = config.get("work_start", "")
                    work_end = config.get("work_end", "")
                    breaks = config.get("breaks", [])
                    overtime = config.get("overtime", [])
                    self.add_camera_row(src, zones, work_start, work_end, breaks, overtime)
        else:
            self.add_camera_row()
    
    def add_break_entry(self, parent, break_entries, value=""):
        row = len(break_entries)
        start = tk.Entry(parent, width=8)
        end = tk.Entry(parent, width=8)
        tk.Label(parent, text=f"Istirahat {row+1} Mulai (HH:MM):").grid(row=row, column=0)
        start.grid(row=row, column=1)
        tk.Label(parent, text="Selesai (HH:MM):").grid(row=row, column=2)
        end.grid(row=row, column=3)
        if value:
            start.insert(0, value[0])
            end.insert(0, value[1])
        if row > 0:
            btn = tk.Button(parent, text="Hapus", command=lambda: self.remove_break_entry(parent, break_entries, row), width=6, padx=2, bg="#f44336", fg="white")
            btn.grid(row=row, column=4)
        else:
            btn = None
        break_entries.append((start, end, btn))
        
    def remove_ot_entry(self, parent, ot_entries, idx):
        for widget in parent.grid_slaves(row=idx):
            widget.destroy()
        ot_entries.pop(idx)
        for i, (start, end, btn) in enumerate(ot_entries):
            start.grid(row=i, column=1)
            end.grid(row=i, column=3)
            if btn is not None:
                btn.grid(row=i, column=4)
                btn.config(command=lambda i=i: self.remove_ot_entry(parent, ot_entries, i))
                
    def add_ot_entry(self, parent, ot_entries, value=""):
        row = len(ot_entries)
        start = tk.Entry(parent, width=8)
        end = tk.Entry(parent, width=8)
        tk.Label(parent, text=f"Lembur {row+1} Mulai (HH:MM):").grid(row=row, column=0)
        start.grid(row=row, column=1)
        tk.Label(parent, text="Selesai (HH:MM):").grid(row=row, column=2)
        end.grid(row=row, column=3)
        if value:
            start.insert(0, value[0])
            end.insert(0, value[1])
        if row > 0:
            btn = tk.Button(parent, text="Hapus", command=lambda: self.remove_ot_entry(parent, ot_entries, row), width=6, padx=2, bg="#f44336", fg="white")
            btn.grid(row=row, column=4)
        else:
            btn = None
        ot_entries.append((start, end, btn))

    def add_camera_row(self, src_val="", zones=None, work_start="", work_end="", breaks=None, overtime=None):
        row_num = len(self.camera_entries)
        
        # Main frame untuk kamera
        cam_frame = tk.LabelFrame(self.camera_frame, text=f"Kamera {row_num + 1}", 
                                  padx=10, pady=10, relief="groove", bd=2)
        cam_frame.pack(fill="x", padx=5, pady=5)

        # Row 1: Source dan Template
        row1 = tk.Frame(cam_frame)
        row1.pack(fill="x", pady=5)
        
        tk.Label(row1, text="Source:", width=12, anchor="w").pack(side="left")
        src_entry = tk.Entry(row1, width=40)
        src_entry.pack(side="left", padx=5)
        if src_val:
            src_entry.insert(0, src_val)

        tk.Label(row1, text="Template:", width=10, anchor="w").pack(side="left", padx=(20, 0))
        template_combo = ttk.Combobox(row1, width=20, state="readonly")
        template_combo['values'] = ["-- Custom --"] + list(self.schedule_templates.keys())
        template_combo.current(0)
        template_combo.pack(side="left", padx=5)
        template_combo.bind('<<ComboboxSelected>>', 
                          lambda e, entries=(None,): self.apply_template(e, entries))

        # Row 2: Jam Kerja
        row2 = tk.Frame(cam_frame)
        row2.pack(fill="x", pady=5)
        
        tk.Label(row2, text="Jam Kerja:", width=12, anchor="w").pack(side="left")
        work_start_entry = tk.Entry(row2, width=10)
        work_start_entry.pack(side="left", padx=5)
        work_start_entry.insert(0, work_start)
        
        tk.Label(row2, text="s/d").pack(side="left")
        work_end_entry = tk.Entry(row2, width=10)
        work_end_entry.pack(side="left", padx=5)
        work_end_entry.insert(0, work_end)

        # Row 3: Istirahat
        row3 = tk.Frame(cam_frame)
        row3.pack(fill="x", pady=5)
        tk.Label(row3, text="Istirahat:", width=12, anchor="w").pack(side="left")
        break_frame = tk.Frame(row3)
        break_frame.pack(side="left")
        break_entries = []
        if breaks:
            for br in breaks:
                start = f"{br[0]:02d}:{br[1]:02d}"
                end = f"{br[2]:02d}:{br[3]:02d}"
                self.add_break_entry(break_frame, break_entries, (start, end))
        else:
            self.add_break_entry(break_frame, break_entries)
        tk.Button(row3, text="Tambah Istirahat", command=lambda: self.add_break_entry(break_frame, break_entries)).pack(side="left", padx=5)

        # Row 4: Lembur
        row4 = tk.Frame(cam_frame)
        row4.pack(fill="x", pady=5)
        tk.Label(row4, text="Lembur:", width=12, anchor="w").pack(side="left")
        ot_frame = tk.Frame(row4)
        ot_frame.pack(side="left")
        ot_entries = []
        if overtime:
            if isinstance(overtime[0], list):  # multiple
                for ot in overtime:
                    start = f"{ot[0]:02d}:{ot[1]:02d}"
                    end = f"{ot[2]:02d}:{ot[3]:02d}"
                    self.add_ot_entry(ot_frame, ot_entries, (start, end))
            elif len(overtime) == 4:
                start = f"{overtime[0]:02d}:{overtime[1]:02d}"
                end = f"{overtime[2]:02d}:{overtime[3]:02d}"
                self.add_ot_entry(ot_frame, ot_entries, (start, end))
        else:
            self.add_ot_entry(ot_frame, ot_entries)
        tk.Button(row4, text="Tambah Lembur", command=lambda: self.add_ot_entry(ot_frame, ot_entries)).pack(side="left", padx=5)

        # Row 5: Zona
        row5 = tk.Frame(cam_frame)
        row5.pack(fill="x", pady=5)
        
        tk.Label(row5, text="Zona:", width=12, anchor="w").pack(side="left", anchor="n")
        zone_text = scrolledtext.ScrolledText(row5, width=60, height=4)
        zone_text.pack(side="left", padx=5)
        
        if zones:
            zone_lines = []
            for zid in sorted(zones.keys(), key=lambda x: int(x) if str(x).isdigit() else 0):
                zone = zones[zid]
                zone_lines.append(f"{zone[0]},{zone[1]},{zone[2]},{zone[3]},{zone[4]}")
            zone_text.insert("1.0", "\n".join(zone_lines))
        
        tk.Label(row5, text="Format: x1,y1,x2,y2,Nama\n(satu zona per baris)", 
                font=("Arial", 8), fg="gray").pack(side="left", anchor="n")

        # Button hapus
        tk.Button(cam_frame, text="🗑️ Hapus Kamera", 
                 command=lambda: self.remove_camera(cam_frame),
                 bg="#f44336", fg="white").pack(anchor="e", pady=5)

        # Update template combo binding with actual entries
        template_combo.bind('<<ComboboxSelected>>', 
                          lambda e: self.apply_template(e, {
                              'work_start': work_start_entry,
                              'work_end': work_end_entry,
                              'breaks': break_entries,
                              'overtime': ot_entries,
                              'template': template_combo
                          }))

        self.camera_entries.append({
            'frame': cam_frame,
            'source': src_entry,
            'template': template_combo,
            'work_start': work_start_entry,
            'work_end': work_end_entry,
            'breaks': break_entries,
            'overtime': ot_entries,
            'zones': zone_text
        })

    def remove_break_entry(self, parent, break_entries, idx):
        for widget in parent.grid_slaves(row=idx):
            widget.destroy()
        break_entries.pop(idx)
        for i, (start, end, btn) in enumerate(break_entries):
            start.grid(row=i, column=1)
            end.grid(row=i, column=3)
            if btn is not None:
                btn.grid(row=i, column=4)
                btn.config(command=lambda i=i: self.remove_break_entry(parent, break_entries, i))
            
    def remove_camera(self, frame):
        for i, entry in enumerate(self.camera_entries):
            if entry['frame'] == frame:
                frame.destroy()
                self.camera_entries.pop(i)
                # Update numbering
                for j, e in enumerate(self.camera_entries):
                    e['frame'].config(text=f"Kamera {j + 1}")
                break

    def on_template_select(self, event):
        selection = self.template_listbox.curselection()
        if selection:
            template_name = self.template_listbox.get(selection[0])
            template = self.schedule_templates[template_name]
            
            self.template_name.delete(0, tk.END)
            self.template_name.insert(0, template_name)
            
            self.tmpl_work_start.delete(0, tk.END)
            self.tmpl_work_start.insert(0, template.get('work_start', ''))
            
            self.tmpl_work_end.delete(0, tk.END)
            self.tmpl_work_end.insert(0, template.get('work_end', ''))
            
            breaks = template.get('breaks', [])
            breaks_str = ", ".join([f"{b[0]:02d}:{b[1]:02d}-{b[2]:02d}:{b[3]:02d}" for b in breaks])
            self.tmpl_breaks.delete(0, tk.END)
            self.tmpl_breaks.insert(0, breaks_str)
            
            overtime = template.get('overtime', [])
            self.tmpl_overtime.delete(0, tk.END)
            if overtime:
                if len(overtime) == 4 and isinstance(overtime[0], int):
                    self.tmpl_overtime.insert(0, f"{overtime[0]:02d}:{overtime[1]:02d}-{overtime[2]:02d}:{overtime[3]:02d}")
                elif isinstance(overtime, list):
                    ot_strs = []
                    for ot in overtime:
                        if len(ot) == 4:
                            ot_strs.append(f"{ot[0]:02d}:{ot[1]:02d}-{ot[2]:02d}:{ot[3]:02d}")
                    self.tmpl_overtime.insert(0, ", ".join(ot_strs))

    def clear_template_form(self):
        self.template_name.delete(0, tk.END)
        self.tmpl_work_start.delete(0, tk.END)
        self.tmpl_work_end.delete(0, tk.END)
        self.tmpl_breaks.delete(0, tk.END)
        self.tmpl_overtime.delete(0, tk.END)
        self.template_listbox.selection_clear(0, tk.END)

    def save_template(self):
        name = self.template_name.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Nama template harus diisi!")
            return
        
        try:
            template = {
                'work_start': self.tmpl_work_start.get().strip(),
                'work_end': self.tmpl_work_end.get().strip(),
                'breaks': [],
                'overtime': []
            }
            
            # Parse breaks
            breaks_str = self.tmpl_breaks.get().strip()
            if breaks_str:
                for break_range in breaks_str.split(','):
                    break_range = break_range.strip()
                    if '-' in break_range:
                        start, end = break_range.split('-')
                        sh, sm = map(int, start.strip().split(':'))
                        eh, em = map(int, end.strip().split(':'))
                        template['breaks'].append([sh, sm, eh, em])
            
            # Parse overtime (multiple)
            overtime_str = self.tmpl_overtime.get().strip()
            if overtime_str:
                for ot_range in overtime_str.split(','):
                    ot_range = ot_range.strip()
                    if '-' in ot_range:
                        start, end = ot_range.split('-')
                        osh, osm = map(int, start.strip().split(':'))
                        oeh, oem = map(int, end.strip().split(':'))
                        template['overtime'].append([osh, osm, oeh, oem])
            
            self.schedule_templates[name] = template
            
            # Update listbox
            if name not in self.template_listbox.get(0, tk.END):
                self.template_listbox.insert(tk.END, name)
            
            # Update all comboboxes
            for entry in self.camera_entries:
                current = entry['template'].get()
                entry['template']['values'] = ["-- Custom --"] + list(self.schedule_templates.keys())
                entry['template'].set(current)
            
            messagebox.showinfo("Success", f"Template '{name}' berhasil disimpan!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Format salah!\n{e}")

    def delete_template(self):
        selection = self.template_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Pilih template yang akan dihapus!")
            return
        
        template_name = self.template_listbox.get(selection[0])
        if messagebox.askyesno("Konfirmasi", f"Hapus template '{template_name}'?"):
            del self.schedule_templates[template_name]
            self.template_listbox.delete(selection[0])
            self.clear_template_form()
            
            # Update all comboboxes
            for entry in self.camera_entries:
                if entry['template'].get() == template_name:
                    entry['template'].current(0)
                entry['template']['values'] = ["-- Custom --"] + list(self.schedule_templates.keys())

    def apply_template(self, event, entries):
        template_name = entries['template'].get()
        if template_name == "-- Custom --":
            return

        template = self.schedule_templates.get(template_name)
        if not template:
            return

        # Apply jam kerja
        entries['work_start'].delete(0, tk.END)
        entries['work_start'].insert(0, template.get('work_start', ''))
        entries['work_end'].delete(0, tk.END)
        entries['work_end'].insert(0, template.get('work_end', ''))

        # Apply breaks (istirahat)
        breaks = template.get('breaks', [])
        for start, end, *_ in entries['breaks']:
            start.delete(0, tk.END)
            end.delete(0, tk.END)
        while len(entries['breaks']) < len(breaks):
            self.add_break_entry(start.master, entries['breaks'])
        for i, br in enumerate(breaks):
            s = f"{br[0]:02d}:{br[1]:02d}"
            e = f"{br[2]:02d}:{br[3]:02d}"
            entries['breaks'][i][0].delete(0, tk.END)
            entries['breaks'][i][0].insert(0, s)
            entries['breaks'][i][1].delete(0, tk.END)
            entries['breaks'][i][1].insert(0, e)

        # Apply overtime (lembur)
        overtime = template.get('overtime', [])
        for start, end, *_ in entries['overtime']:
            start.delete(0, tk.END)
            end.delete(0, tk.END)
        while len(entries['overtime']) < len(overtime):
            self.add_ot_entry(start.master, entries['overtime'])
        for i, ot in enumerate(overtime):
            s = f"{ot[0]:02d}:{ot[1]:02d}"
            e = f"{ot[2]:02d}:{ot[3]:02d}"
            entries['overtime'][i][0].delete(0, tk.END)
            entries['overtime'][i][0].insert(0, s)
            entries['overtime'][i][1].delete(0, tk.END)
            entries['overtime'][i][1].insert(0, e)

    def save_config(self):
        try:
            video_sources = []
            
            for entry in self.camera_entries:
                src = entry['source'].get().strip()
                if not src:
                    continue
                
                work_start = entry['work_start'].get().strip()
                work_end = entry['work_end'].get().strip()
                
                # Parse breaks
                breaks = []
                for start, end, *_ in entry['breaks']:
                    s = start.get().strip()
                    e = end.get().strip()
                    if s and e:
                        sh, sm = map(int, s.split(':'))
                        eh, em = map(int, e.split(':'))
                        breaks.append([sh, sm, eh, em])

                overtime = []
                for start, end, *_ in entry['overtime']:
                    s = start.get().strip()
                    e = end.get().strip()
                    if s and e:
                        osh, osm = map(int, s.split(':'))
                        oeh, oem = map(int, e.split(':'))
                        overtime.append([osh, osm, oeh, oem])
                
                # Parse zones
                zones = {}
                zone_text = entry['zones'].get("1.0", tk.END).strip()
                if zone_text:
                    zone_id = 1
                    for line in zone_text.split('\n'):
                        line = line.strip()
                        if not line:
                            continue
                        parts = line.split(',')
                        if len(parts) == 5:
                            x1, y1, x2, y2 = map(int, parts[:4])
                            name = parts[4].strip()
                            zones[zone_id] = [x1, y1, x2, y2, name]
                            zone_id += 1
                
                video_sources.append([src, {
                    "zones": zones,
                    "work_start": work_start,
                    "work_end": work_end,
                    "breaks": breaks,
                    "overtime": overtime
                }])
            
            config = {
                "video_sources": video_sources,
                "schedule_templates": self.schedule_templates,
                "date": datetime.now().strftime("%Y-%m-%d")
            }
            
            with open("config.json", "w") as f:
                json.dump(config, f, indent=2)
            
            messagebox.showinfo("Sukses", "Konfigurasi berhasil disimpan ke config.json!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Gagal menyimpan!\n{e}")

    def on_closing(self):
        """Handle window closing"""
        self.running = False
        self.destroy()


if __name__ == "__main__":
    app = SchedulerGUI()
    app.mainloop()
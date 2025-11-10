import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
from datetime import datetime
from PIL import Image, ImageTk
import threading
import socket
import pickle
import struct
import time

class SchedulerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Work Activity Tracking Scheduler by Puterako")
        self.geometry("1200x800")

        self.camera_labels = {}  # Store label widgets for each camera

        # Socket client attributes
        self.client_socket = None
        self.frame_thread = None
        self.running = False
        
        self.pc_connections = {}
        self.pc_configs = []
        self.load_pc_configs()
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
        
        # Tab 4: Konfigurasi PC Multi
        self.create_pc_config_tab()

        # Tab 5: Multi-PC Connection
        self.create_multi_connection_tab()

        # Bottom buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=10)
        tk.Button(btn_frame, text="💾 Simpan Konfigurasi", command=self.save_config,
                bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), 
                padx=20, pady=10).pack(side="right", padx=5)
        tk.Button(btn_frame, text="💾 Simpan PC Config", command=self.save_pc_config,
                bg="#2196F3", fg="white", font=("Arial", 11, "bold"), 
                padx=20, pady=10).pack(side="right")

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def load_pc_configs(self):
        """Load configurations for multiple PCs"""
        try:
            with open("scheduler_config.json") as f:
                scheduler_config = json.load(f)
                self.pc_configs = scheduler_config.get("pc_list", [])
        except Exception:
            # Default configuration
            self.pc_configs = [
                {
                    "pc_id": 1, 
                    "ip": "192.168.1.100", 
                    "port": 9999, 
                    "name": "PC-1", 
                    "cameras": [
                        {"name": "Camera 1", "source": "0", "camera_id": 1}
                    ],
                    "camera_count": 1
                }
            ]
    
    def create_pc_config_tab(self):
        """Create PC configuration tab"""
        pc_tab = tk.Frame(self.notebook)
        self.notebook.add(pc_tab, text="🖥️ Konfigurasi PC")

        # Toolbar
        toolbar = tk.Frame(pc_tab)
        toolbar.pack(fill="x", padx=10, pady=5)
        tk.Button(toolbar, text="➕ Tambah PC", command=self.add_pc_row,
                bg="#2196F3", fg="white").pack(side="left", padx=5)

        # Scrollable frame
        canvas = tk.Canvas(pc_tab)
        scrollbar = tk.Scrollbar(pc_tab, orient="vertical", command=canvas.yview)
        self.pc_config_frame = tk.Frame(canvas)
        
        self.pc_config_frame.bind("<Configure>", 
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        canvas.create_window((0, 0), window=self.pc_config_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=10)
        scrollbar.pack(side="right", fill="y")

        self.pc_entries = []
        
        # Load existing PC configs with proper camera list formatting
        for pc_config in self.pc_configs:
            cameras = pc_config.get("cameras", [])
            camera_list = ""
            
            # Format camera list as text
            if isinstance(cameras, list) and cameras:
                camera_lines = []
                for cam in cameras:
                    if isinstance(cam, dict):
                        cam_name = cam.get("name", f"Camera {cam.get('camera_id', 1)}")
                        cam_source = cam.get("source", "")
                        camera_lines.append(f"{cam_name}: {cam_source}")
                camera_list = "\n".join(camera_lines)
            
            self.add_pc_row(
                name=pc_config.get("name", ""), 
                ip=pc_config.get("ip", ""),
                port=pc_config.get("port", 9999), 
                cameras=len(cameras),
                camera_list=camera_list  # Pass dengan nama parameter
            )

    def add_pc_row(self, name="", ip="", port=9999, cameras=10, camera_list=""):
        """Add PC configuration row with camera references (NOT sources)"""
        row_num = len(self.pc_entries)
        
        pc_frame = tk.LabelFrame(self.pc_config_frame, text=f"PC {row_num + 1}", 
                                padx=10, pady=10)
        pc_frame.pack(fill="x", padx=5, pady=5)

        # Row 1: Name and IP (SAMA)
        row1 = tk.Frame(pc_frame)
        row1.pack(fill="x", pady=5)
        
        tk.Label(row1, text="PC Name:", width=10).pack(side="left")
        name_entry = tk.Entry(row1, width=25)
        name_entry.pack(side="left", padx=5)
        name_entry.insert(0, name)

        tk.Label(row1, text="IP:", width=5).pack(side="left", padx=(20, 0))
        ip_entry = tk.Entry(row1, width=15)
        ip_entry.pack(side="left", padx=5)
        ip_entry.insert(0, ip)
        
        tk.Label(row1, text="Port:").pack(side="left")
        port_entry = tk.Entry(row1, width=8)
        port_entry.pack(side="left", padx=5)
        port_entry.insert(0, str(port))

        # Row 2: Camera Assignment (BARU - TIDAK ADA SOURCE!)
        row2 = tk.Frame(pc_frame)
        row2.pack(fill="x", pady=5)
        
        tk.Label(row2, text="Assigned Cameras:", width=15, anchor="w").pack(side="left", anchor="n")
        
        # Checkboxes untuk setiap kamera yang sudah dikonfigurasi
        camera_frame = tk.Frame(row2)
        camera_frame.pack(side="left", padx=5)
        
        camera_checkboxes = []
        
        # Load dari konfigurasi kamera yang sudah ada
        if self.config_data and "video_sources" in self.config_data:
            for idx, src_data in enumerate(self.config_data["video_sources"]):
                if len(src_data) == 2:
                    src, config = src_data
                    
                    var = tk.BooleanVar()
                    checkbox = tk.Checkbutton(
                        camera_frame, 
                        text=f"Kamera {idx+1}: {src[:40]}...", 
                        variable=var,
                        anchor="w"
                    )
                    checkbox.pack(anchor="w")
                    camera_checkboxes.append((var, idx+1, src))
        
        # Jika tidak ada kamera terkonfigurasi
        if not camera_checkboxes:
            tk.Label(camera_frame, text="⚠️ Belum ada kamera dikonfigurasi!\nSilakan konfigurasi di tab 'Konfigurasi Kamera' dulu.", 
                    fg="orange", justify="left").pack(anchor="w")

        # Helper text
        tk.Label(row2, text="✓ Pilih kamera mana saja yang\ndikelola oleh PC ini", 
                font=("Arial", 8), fg="gray", justify="left").pack(side="left", anchor="n", padx=(10, 0))

        # Row 3: Status and Test (SAMA)
        row3 = tk.Frame(pc_frame)
        row3.pack(fill="x", pady=5)
        
        tk.Button(row3, text="🔍 Test Connection", 
                command=lambda: self.test_pc_connection_detailed(ip_entry.get(), int(port_entry.get() or 9999), name_entry.get()),
                bg="#4CAF50", fg="white").pack(side="left")
        
        status_label = tk.Label(row3, text="Not tested", fg="gray")
        status_label.pack(side="left", padx=10)

        # Remove button
        tk.Button(pc_frame, text="🗑️ Remove PC", 
                command=lambda: self.remove_pc_row(pc_frame),
                bg="#f44336", fg="white").pack(anchor="e", pady=5)

        self.pc_entries.append({
            'frame': pc_frame, 
            'name': name_entry, 
            'ip': ip_entry,
            'port': port_entry, 
            'camera_checkboxes': camera_checkboxes,  # BARU!
            'status': status_label
        })
    def remove_pc_row(self, frame):
        """Remove PC configuration row"""
        for i, entry in enumerate(self.pc_entries):
            if entry['frame'] == frame:
                frame.destroy()
                self.pc_entries.pop(i)
                break

    def create_multi_connection_tab(self):
        """Create multi-PC connection tab"""
        conn_tab = tk.Frame(self.notebook)
        self.notebook.add(conn_tab, text="🔗 Multi-PC Connection")

        # Control Panel
        control_frame = tk.LabelFrame(conn_tab, text="Connection Control", padx=10, pady=10)
        control_frame.pack(fill="x", padx=10, pady=10)

        # Master controls
        master_frame = tk.Frame(control_frame)
        master_frame.pack(fill="x", pady=10)
        
        tk.Button(master_frame, text="🔗 Connect All PCs", command=self.connect_all_pcs,
                bg="#4CAF50", fg="white", font=("Arial", 11, "bold")).pack(side="left", padx=5)
        tk.Button(master_frame, text="❌ Disconnect All", command=self.disconnect_all_pcs,
                bg="#f44336", fg="white", font=("Arial", 11, "bold")).pack(side="left", padx=5)
        
        self.connection_status = tk.Label(master_frame, text="Status: Ready", 
                                        font=("Arial", 10, "bold"), fg="blue")
        self.connection_status.pack(side="right", padx=10)

        # PC Status List
        status_frame = tk.LabelFrame(conn_tab, text="PC Status", padx=10, pady=10)
        status_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.pc_status_container = tk.Frame(status_frame)
        self.pc_status_container.pack(fill="both", expand=True)
        
        self.pc_status_widgets = {}
        self.refresh_pc_status_display()

    def refresh_pc_status_display(self):
        """Enhanced PC status display with camera details"""
        # Clear existing widgets
        for widget in self.pc_status_container.winfo_children():
            widget.destroy()
        
        self.pc_status_widgets.clear()
        
        for pc_config in self.pc_configs:
            pc_id = pc_config.get("pc_id")
            cameras = pc_config.get("cameras", [])
            
            pc_frame = tk.LabelFrame(self.pc_status_container, 
                                text=f"PC-{pc_id}: {pc_config.get('name', 'Unknown')}",
                                padx=10, pady=10)
            pc_frame.pack(fill="x", padx=5, pady=5)

            # Info row
            info_frame = tk.Frame(pc_frame)
            info_frame.pack(fill="x", pady=5)
            
            ip_port = f"IP: {pc_config.get('ip', 'N/A')}:{pc_config.get('port', 'N/A')}"
            camera_count = len(cameras)
            tk.Label(info_frame, text=f"{ip_port} | Cameras: {camera_count}").pack(side="left")
            
            status_label = tk.Label(info_frame, text="● Disconnected", fg="red")
            status_label.pack(side="right")

            # Camera list
            if cameras:
                cam_frame = tk.Frame(pc_frame)
                cam_frame.pack(fill="x", pady=5)
                
                tk.Label(cam_frame, text="Cameras:", font=("Arial", 9, "bold")).pack(anchor="w")
                for camera in cameras[:3]:  # Show max 3 cameras
                    cam_text = f"  • {camera.get('name', 'Camera')} → {camera.get('source', 'Unknown')[:40]}..."
                    tk.Label(cam_frame, text=cam_text, font=("Arial", 8), fg="gray").pack(anchor="w")
                
                if len(cameras) > 3:
                    tk.Label(cam_frame, text=f"  ... and {len(cameras)-3} more cameras", 
                            font=("Arial", 8), fg="gray").pack(anchor="w")

            # Control buttons
            btn_frame = tk.Frame(pc_frame)
            btn_frame.pack(pady=5)
            
            tk.Button(btn_frame, text="Connect", 
                    command=lambda pc=pc_config: self.connect_to_pc_with_cameras(pc),
                    bg="#4CAF50", fg="white", width=10).pack(side="left", padx=5)
            tk.Button(btn_frame, text="Disconnect", 
                    command=lambda pc_id=pc_id: self.disconnect_from_pc(pc_id),
                    bg="#f44336", fg="white", width=10).pack(side="left")

            self.pc_status_widgets[pc_id] = status_label
    def create_live_tracking_tab(self):
        """Create tab for live camera feeds with multi-PC support"""
        live_tab = tk.Frame(self.notebook)
        self.notebook.add(live_tab, text="📹 Live Tracking")

        # Control panel
        control_frame = tk.Frame(live_tab, bg="#f0f0f0", height=50)
        control_frame.pack(fill="x", padx=5, pady=5)
        
        tk.Label(control_frame, text="Live Camera Feeds", font=("Arial", 14, "bold"),
                bg="#f0f0f0").pack(side="left", padx=10)
        
        self.status_label = tk.Label(control_frame, text="● Disconnected", 
                                    font=("Arial", 10), fg="red", bg="#f0f0f0")
        self.status_label.pack(side="right", padx=10)

        # Mode selection (NEW!)
        mode_frame = tk.Frame(control_frame, bg="#f0f0f0")
        mode_frame.pack(side="right", padx=20)
        
        self.mode_var = tk.StringVar(value="single")
        tk.Radiobutton(mode_frame, text="Single PC", variable=self.mode_var, value="single",
                    bg="#f0f0f0", command=self.change_connection_mode).pack(side="left")
        tk.Radiobutton(mode_frame, text="Multi PC", variable=self.mode_var, value="multi",
                    bg="#f0f0f0", command=self.change_connection_mode).pack(side="left")

        btn_frame = tk.Frame(control_frame)
        btn_frame.pack(side="right")
        tk.Button(btn_frame, text="Connect", command=self.smart_connect).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Disconnect", command=self.smart_disconnect).pack(side="left", padx=5)

        # Camera display area
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

        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # Initialize camera display
        self.init_smart_camera_widgets()
        
    def change_connection_mode(self):
        """Change between single PC and multi PC mode"""
        self.smart_disconnect()  # Disconnect current connections
        self.init_smart_camera_widgets()  # Refresh camera display
        
    def smart_connect(self):
        """Smart connect based on mode"""
        if self.mode_var.get() == "multi":
            self.connect_all_pcs_with_cameras()
        else:
            self.connect_to_server()  # Original single PC connection

    def smart_disconnect(self):
        """Smart disconnect based on mode"""
        if self.mode_var.get() == "multi":
            self.disconnect_all_pcs()
        else:
            self.disconnect_from_server()  # Original single PC disconnection

    def init_smart_camera_widgets(self):
        """Initialize camera widgets based on mode"""
        # Clear existing widgets
        for widget in self.camera_container.winfo_children():
            widget.destroy()
        self.camera_labels.clear()

        if self.mode_var.get() == "multi":
            self.init_multi_pc_camera_widgets()
        else:
            self.init_single_pc_camera_widgets()
            
    def init_multi_pc_camera_widgets(self):
        """Initialize widgets for multi-PC camera display"""
        cols = 3
        camera_count = 0
        
        print(f"[DEBUG] Initializing multi-PC camera widgets...")
        print(f"[DEBUG] PC configs: {self.pc_configs}")
        
        for pc_config in self.pc_configs:
            pc_name = pc_config.get("name", f"PC-{pc_config.get('pc_id')}")
            cameras = pc_config.get("cameras", [])
            pc_id = pc_config.get("pc_id")
            
            print(f"[DEBUG] Processing PC-{pc_id} ({pc_name}) with {len(cameras)} cameras")
            
            for camera_info in cameras:
                row = camera_count // cols
                col = camera_count % cols
                
                cam_name = camera_info.get("name", f"Camera {camera_info.get('camera_id')}")
                # PERBAIKAN: Use camera_id properly (sesuai dengan config)
                camera_id = camera_info.get('camera_id', camera_count + 1)
                
                # PENTING: global_cam_id harus sama dengan yang dibuat di receive_multi_pc_frames
                global_cam_id = f"{pc_id}-{camera_id}"  # Format: "1-1", "1-2", "2-1", dst
                
                print(f"[DEBUG] Creating widget for global_cam_id: {global_cam_id}")
                print(f"[DEBUG] Camera info: {camera_info}")
                
                cam_frame = tk.LabelFrame(self.camera_container, 
                                        text=f"{pc_name} | {cam_name}",
                                        bg="#1e1e1e", fg="white",
                                        font=("Arial", 10, "bold"),
                                        padx=5, pady=5)
                cam_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
                
                video_label = tk.Label(cam_frame, bg="black", width=280, height=160)
                video_label.pack()
                
                info_text = f"Waiting for {pc_name}...\nCamera ID: {camera_id}\nSource: {camera_info.get('source', 'Unknown')[:25]}..."
                info_label = tk.Label(cam_frame, text=info_text, 
                                    bg="#1e1e1e", fg="gray", font=("Arial", 8), justify="left")
                info_label.pack(pady=5)
                
                self.camera_labels[global_cam_id] = {
                    'video': video_label,
                    'info': info_label,
                    'last_update': 0,
                    'pc_name': pc_name,
                    'cam_name': cam_name,
                    'source': camera_info.get('source', ''),
                    'pc_id': pc_id,
                    'camera_id': camera_id
                }
                
                print(f"[DEBUG] Added camera label: {global_cam_id}")
                camera_count += 1
        
        # Configure grid weights
        for i in range(cols):
            self.camera_container.columnconfigure(i, weight=1)
            
        print(f"[DEBUG] Total camera labels created: {len(self.camera_labels)}")
        print(f"[DEBUG] Camera labels keys: {list(self.camera_labels.keys())}")

    def init_single_pc_camera_widgets(self):
        """Initialize widgets for single PC camera display (original)"""
        if not self.config_data or "video_sources" not in self.config_data:
            return
        
        num_cameras = len(self.config_data["video_sources"])
        cols = 2

        for idx in range(num_cameras):
            row = idx // cols
            col = idx % cols
            
            cam_frame = tk.LabelFrame(self.camera_container, 
                                    text=f"Camera {idx + 1}",
                                    bg="#1e1e1e", fg="white",
                                    font=("Arial", 10, "bold"),
                                    padx=5, pady=5)
            cam_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            
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

    
    def connect_to_pc(self, pc_config):
        """Connect to a specific PC"""
        pc_id = pc_config.get("pc_id")
        if pc_id in self.pc_connections:
            return  # Already connected
        
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(5)
            client_socket.connect((pc_config["ip"], pc_config["port"]))
            
            self.pc_connections[pc_id] = {
                'socket': client_socket,
                'config': pc_config
            }
            
            if pc_id in self.pc_status_widgets:
                self.pc_status_widgets[pc_id].config(text="● Connected", fg="green")
            
            messagebox.showinfo("Success", f"Connected to PC-{pc_id}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Cannot connect to PC-{pc_id}:\n{e}")

    def disconnect_from_pc(self, pc_id):
        """Disconnect from specific PC"""
        if pc_id in self.pc_connections:
            try:
                self.pc_connections[pc_id]['socket'].close()
            except:
                pass
            del self.pc_connections[pc_id]
            
            if pc_id in self.pc_status_widgets:
                self.pc_status_widgets[pc_id].config(text="● Disconnected", fg="red")

    def test_pc_connection_detailed(self, ip, port, name):
        """Test connection to PC with detailed feedback"""
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(3)
            test_socket.connect((ip, port))
            test_socket.close()
            
            # Update status in PC entries if exists
            for entry in self.pc_entries:
                if entry['name'].get() == name and entry['ip'].get() == ip:
                    entry['status'].config(text="✅ Connection OK", fg="green")
                    break
            
            messagebox.showinfo("Test Connection", f"✅ Connection to {name} ({ip}:{port}) successful!")
            
        except Exception as e:
            # Update status in PC entries if exists
            for entry in self.pc_entries:
                if entry['name'].get() == name and entry['ip'].get() == ip:
                    entry['status'].config(text="❌ Connection Failed", fg="red")
                    break
            
            messagebox.showerror("Test Connection", f"❌ Connection to {name} failed:\n{e}")

    def connect_all_pcs(self):
        """Connect to all configured PCs (basic version)"""
        if not self.pc_configs:
            messagebox.showwarning("Warning", "No PCs configured! Please configure PCs first.")
            return

        self.connection_status.config(text="Status: Connecting to all PCs...", fg="orange")
        
        connected_count = 0
        for pc_config in self.pc_configs:
            try:
                self.connect_to_pc(pc_config)
                connected_count += 1
            except Exception as e:
                print(f"[ERROR] Failed to connect to {pc_config['name']}: {e}")
        
        status_text = f"Status: {connected_count}/{len(self.pc_configs)} PCs Connected"
        self.connection_status.config(
            text=status_text, 
            fg="green" if connected_count > 0 else "red"
        )
    
    def connect_all_pcs_with_cameras(self):
        """Connect to all PCs and track their cameras"""
        if not self.pc_configs:
            messagebox.showwarning("Warning", "No PCs configured! Please configure PCs first.")
            return

        self.connection_status.config(text="Status: Connecting to all PCs...", fg="orange")
        
        connected_pcs = 0
        total_cameras = 0
        
        for pc_config in self.pc_configs:
            try:
                result = self.connect_to_pc_with_cameras(pc_config)
                if result:
                    connected_pcs += 1
                    total_cameras += len(pc_config.get("cameras", []))
            except Exception as e:
                print(f"[ERROR] Failed to connect to {pc_config['name']}: {e}")
        
        status_text = f"Status: {connected_pcs}/{len(self.pc_configs)} PCs Connected"
        if total_cameras > 0:
            status_text += f" | {total_cameras} Cameras"
        
        self.connection_status.config(
            text=status_text, 
            fg="green" if connected_pcs > 0 else "red"
        )
    def connect_to_pc_with_cameras(self, pc_config):
        """Connect to PC and start receiving camera feeds"""
        pc_id = pc_config.get("pc_id")
        if pc_id in self.pc_connections:
            return True  # Already connected
        
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(5)
            client_socket.connect((pc_config["ip"], pc_config["port"]))
            
            self.pc_connections[pc_id] = {
                'socket': client_socket,
                'config': pc_config,
                'thread': None,
                'camera_count': len(pc_config.get("cameras", [])),
                'status': 'connected'
            }
            
            # Start frame receiving thread
            thread = threading.Thread(
                target=self.receive_multi_pc_frames, 
                args=(pc_id,), 
                daemon=True
            )
            thread.start()
            self.pc_connections[pc_id]['thread'] = thread
            
            if pc_id in self.pc_status_widgets:
                self.pc_status_widgets[pc_id].config(text="● Connected", fg="green")
            
            pc_name = pc_config.get("name", f"PC-{pc_id}")
            camera_count = len(pc_config.get("cameras", []))
            print(f"[INFO] Connected to {pc_name} with {camera_count} cameras")
            return True
            
        except Exception as e:
            if pc_id in self.pc_status_widgets:
                self.pc_status_widgets[pc_id].config(text="● Failed", fg="red")
            print(f"[ERROR] Failed to connect to {pc_config['name']}: {e}")
            return False

    def receive_multi_pc_frames(self, pc_id):
        """Receive frames from specific PC"""
        if pc_id not in self.pc_connections:
            return
        
        client_socket = self.pc_connections[pc_id]['socket']
        pc_config = self.pc_connections[pc_id]['config']
        
        data = b""
        payload_size = struct.calcsize("Q")
        
        print(f"[INFO] Started receiving frames from PC-{pc_id}")
        
        while pc_id in self.pc_connections:
            try:
                while len(data) < payload_size:
                    packet = client_socket.recv(4096)
                    if not packet:
                        return
                    data += packet
                
                packed_msg_size = data[:payload_size]
                data = data[payload_size:]
                msg_size = struct.unpack("Q", packed_msg_size)[0]
                
                while len(data) < msg_size:
                    data += client_socket.recv(4096)
                
                frame_data = data[:msg_size]
                data = data[msg_size:]
                
                # Frame data format: (cam_idx, frame_rgb) - cam_idx adalah INTEGER asli (1, 2, 3, dst)
                cam_idx, frame_rgb = pickle.loads(frame_data)
                
                print(f"[DEBUG] Received from PC-{pc_id}: cam_idx={cam_idx} (type: {type(cam_idx)})")
                
                # PERBAIKAN: Pastikan cam_idx adalah integer, bukan string yang sudah diformat
                if isinstance(cam_idx, str):
                    # Jika masih berupa string, parse ulang
                    try:
                        cam_idx = int(cam_idx.split('-')[-1])  # Ambil angka terakhir
                    except:
                        cam_idx = 1  # Default fallback
                
                # Create proper global camera ID: PC_ID-CAM_IDX 
                global_cam_id = f"{pc_id}-{cam_idx}"  # Format: "1-1", "1-2", "2-1", dst
                
                print(f"[DEBUG] Created global_cam_id: {global_cam_id}")
                
                # Update display in main thread
                self.after(0, self.update_multi_pc_camera_display, global_cam_id, frame_rgb, pc_config)
                
            except Exception as e:
                print(f"[ERROR] PC-{pc_id} receive error: {e}")
                if pc_id in self.pc_connections:
                    del self.pc_connections[pc_id]
                break

    def update_multi_pc_camera_display(self, global_cam_id, frame_rgb, pc_config):
        """Update multi-PC camera display with frame"""
        print(f"[DEBUG] Updating display for camera: {global_cam_id}")
        print(f"[DEBUG] Available camera labels: {list(self.camera_labels.keys())}")
        
        if global_cam_id not in self.camera_labels:
            print(f"[WARNING] Camera {global_cam_id} not found in labels")
            return

        try:
            camera_info = self.camera_labels[global_cam_id]
            video_label = camera_info['video']
            
            label_width = video_label.winfo_width() or 280
            label_height = video_label.winfo_height() or 160

            img = Image.fromarray(frame_rgb)
            img = img.resize((label_width, label_height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image=img)
            video_label.configure(image=photo)
            video_label.image = photo

            current_time = datetime.now().strftime("%H:%M:%S")
            pc_name = camera_info.get('pc_name', 'Unknown PC')
            cam_name = camera_info.get('cam_name', 'Unknown Camera')
            
            info_text = f"🟢 {pc_name} | {cam_name}\nLast: {current_time}"
            camera_info['info'].configure(text=info_text, fg="lime")
            camera_info['last_update'] = datetime.now().timestamp()
            
            print(f"[SUCCESS] Updated camera {global_cam_id} display")
            
        except Exception as e:
            print(f"[ERROR] Error updating camera {global_cam_id}: {e}")
        
    def disconnect_all_pcs(self):
        """Disconnect from all PCs"""
        pc_ids = list(self.pc_connections.keys())
        for pc_id in pc_ids:
            self.disconnect_from_pc(pc_id)
        
        self.connection_status.config(text="Status: All Disconnected", fg="red")
        
    def save_pc_config(self):
        """Save PC configuration with camera references"""
        try:
            pc_list = []
            for i, entry in enumerate(self.pc_entries):
                name = entry['name'].get().strip()
                ip = entry['ip'].get().strip()
                port = int(entry['port'].get() or 9999)
                
                # Get selected cameras
                assigned_cameras = []
                camera_checkboxes = entry.get('camera_checkboxes', [])
                
                for var, cam_id, cam_source in camera_checkboxes:
                    if var.get():  # Jika checkbox dicentang
                        # Ambil detail dari config_data
                        if self.config_data and "video_sources" in self.config_data:
                            src_data = self.config_data["video_sources"][cam_id-1]
                            if len(src_data) == 2:
                                src, config = src_data
                                assigned_cameras.append({
                                    "name": f"Camera {cam_id}",
                                    "source": src,
                                    "camera_id": cam_id,
                                    "config_ref": cam_id  # Reference ke config asli
                                })
                
                if name and ip and assigned_cameras:  # Harus ada kamera assigned
                    pc_list.append({
                        "pc_id": i + 1, 
                        "name": name, 
                        "ip": ip, 
                        "port": port, 
                        "cameras": assigned_cameras,
                        "camera_count": len(assigned_cameras)
                    })
            
            config = {"pc_list": pc_list}
            with open("scheduler_config.json", "w") as f:
                json.dump(config, f, indent=2)
            
            self.pc_configs = pc_list
            self.refresh_pc_status_display()
            messagebox.showinfo("Success", f"PC configuration saved! Total: {len(pc_list)} PCs")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
        
    def connect_to_server(self):
        if self.running:
            return
        self.running = True
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client_socket.connect(('localhost', 9999))
            self.status_label.config(text="● Connected", fg="green")
            self.frame_thread = threading.Thread(target=self.receive_frames, daemon=True)
            self.frame_thread.start()
        except Exception as e:
            messagebox.showerror("Error", f"Cannot connect to server: {e}")
            self.status_label.config(text="● Disconnected", fg="red")
            self.running = False

    def disconnect_from_server(self):
        self.running = False
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
        self.status_label.config(text="● Disconnected", fg="red")

    def receive_frames(self):
        data = b""
        payload_size = struct.calcsize("Q")
        while self.running:
            try:
                while len(data) < payload_size:
                    packet = self.client_socket.recv(4096)
                    if not packet:
                        return
                    data += packet
                packed_msg_size = data[:payload_size]
                data = data[payload_size:]
                msg_size = struct.unpack("Q", packed_msg_size)[0]
                while len(data) < msg_size:
                    data += self.client_socket.recv(4096)
                frame_data = data[:msg_size]
                data = data[msg_size:]
                cam_idx, frame_rgb = pickle.loads(frame_data)
                self.after(0, self.update_camera_display, cam_idx, frame_rgb)
            except Exception as e:
                print(f"[ERROR] Socket receive error: {e}")
                self.disconnect_from_server()
                break

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

    def update_camera_display(self, cam_idx, frame_rgb):
        """Update camera display with new frame (runs in main thread)"""
        if cam_idx not in self.camera_labels:
            print(f"[WARNING] cam_idx {cam_idx} not in camera_labels")
            return

        try:
            video_label = self.camera_labels[cam_idx]['video']
            label_width = video_label.winfo_width() or 320
            label_height = video_label.winfo_height() or 180

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
                    away_timeout = config.get("away_timeout", 5)  # Default 5 menit
                    self.add_camera_row(src, zones, work_start, work_end, breaks, overtime, away_timeout)
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

    def add_camera_row(self, src_val="", zones=None, work_start="", work_end="", breaks=None, overtime=None, away_timeout=5):
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

        # Row 2: Jam Kerja dan Away Timeout
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

        # Tambahan: Away Timeout
        tk.Label(row2, text="Away Timeout:", width=12, anchor="w").pack(side="left", padx=(20, 0))
        away_timeout_entry = tk.Entry(row2, width=8)
        away_timeout_entry.pack(side="left", padx=5)
        away_timeout_entry.insert(0, str(away_timeout))
        tk.Label(row2, text="menit", font=("Arial", 8)).pack(side="left")
        
        # Helper text
        tk.Label(row2, text="(toleransi hilang sebelum dihitung away)", 
                font=("Arial", 8), fg="gray").pack(side="left", padx=(5, 0))

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
            'zones': zone_text,
            'away_timeout': away_timeout_entry  # Tambahan
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
                
                # Parse away timeout
                try:
                    away_timeout = int(entry['away_timeout'].get().strip())
                    if away_timeout < 1:
                        away_timeout = 5  # Default minimum 1 menit
                except:
                    away_timeout = 5  # Default 5 menit
                
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
                    "overtime": overtime,
                    "away_timeout": away_timeout  # Tambahan
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
        self.disconnect_from_server()
        self.destroy()
        
if __name__ == "__main__":
    app = SchedulerGUI()
    app.mainloop()
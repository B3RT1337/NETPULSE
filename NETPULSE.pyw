import os
import sys
import tkinter as tk
import psutil
import socket
import threading
import time
import queue
import subprocess
import platform
import os
import sys
from collections import deque

def resource_path(filename):
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, filename)


class NETPULSE:

    BG = "#080B10"
    PANEL = "#101720"
    BORDER = "#202D3A"
    GREEN = "#00F5A0"
    BLUE = "#00BFFF"
    RED = "#FF4655"
    ORANGE = "#FFB347"
    WHITE = "#E5EDF5"
    MUTED = "#718096"

    def __init__(self, root):

        self.root = root
        self.root.title("NETPULSE")
        self.root.geometry("250x250")
        # Center the fixed-size window on the screen.
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        pos_x = (screen_w - 250) // 2
        pos_y = (screen_h - 250) // 2
        self.root.geometry(f"250x250+{pos_x}+{pos_y}")
        self.root.resizable(False, False)
        self.root.configure(bg=self.BG)
        # Load the app icon from the script folder or PyInstaller bundle.
        bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(bundle_dir, "netpulse.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except tk.TclError:
                pass
        self.root.attributes("-topmost", True)

        self.running = True
        self.data_queue = queue.Queue()

        self.stop_event = threading.Event()

        self.prev_net = psutil.net_io_counters()
        self.prev_time = time.monotonic()

        self.download_history = deque(
            [0] * 35, maxlen=35
        )

        self.upload_history = deque(
            [0] * 35, maxlen=35
        )

        psutil.cpu_percent(interval=None)

        self.create_ui()
        self.create_loading_screen()
        self.splash_active = True
        self.loading_finished = False
        self.loading_started = time.monotonic()
        # Keep the intro visible long enough to actually see it, even on
        # very fast connections.
        self.minimum_loading_seconds = 4.0
        self.result_display_seconds = 1.1
        self.loading_step = 0
        self.loading_progress = 8
        self.loading_messages = [
            "INITIALIZING NETWORK",
            "CONNECTING TO 1.1.1.1",
            "CHECKING GOOGLE DNS",
            "MEASURING CONNECTION",
        ]
        self.animate_loading()

        self.worker = threading.Thread(
            target=self.monitor_worker,
            daemon=True
        )
        self.worker.start()

        self.root.after(100, self.process_queue)

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close
        )

        self.root.bind("<Escape>", lambda e: self.close())
        self.root.bind("<q>", lambda e: self.close())

    def create_ui(self):

        # A compact grid prevents the graph from being pushed below
        # the fixed 250x250 window.
        content = tk.Frame(self.root, bg=self.BG, width=238, height=238)
        content.place(relx=0.5, rely=0.5, anchor="center")
        self.dashboard = content
        content.grid_propagate(False)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(5, weight=1)

        header = tk.Frame(content, bg=self.BG)
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(5, 2))
        tk.Label(
            header, text="NETPULSE", bg=self.BG, fg=self.GREEN,
            font=("Consolas", 12, "bold")
        ).pack(side="left")
        self.status = tk.Label(
            header, text="CHECKING", bg=self.BG, fg=self.ORANGE,
            font=("Consolas", 7, "bold")
        )
        self.status.pack(side="right")

        tk.Frame(content, bg=self.BORDER, height=1).grid(
            row=1, column=0, sticky="ew", padx=8, pady=1
        )

        stats = tk.Frame(content, bg=self.BG)
        stats.grid(row=2, column=0, sticky="ew", padx=6, pady=2)
        self.cpu = self.metric(stats, "CPU", "0%", 0)
        self.ram = self.metric(stats, "RAM", "0%", 1)
        self.tcp = self.metric(stats, "TCP", "0", 2)

        traffic = tk.Frame(content, bg=self.BG)
        traffic.grid(row=3, column=0, sticky="ew", padx=6, pady=2)
        self.download = self.traffic_card(
            traffic, "DOWNLOAD", "0 KB/s", self.BLUE, 0
        )
        self.upload = self.traffic_card(
            traffic, "UPLOAD", "0 KB/s", self.GREEN, 1
        )

        details = tk.Frame(content, bg=self.BG)
        details.grid(row=4, column=0, sticky="ew", padx=9, pady=2)
        self.latency = tk.Label(
            details, text="LATENCY: --", bg=self.BG, fg=self.WHITE,
            font=("Consolas", 7)
        )
        self.latency.pack(side="left")
        self.interface = tk.Label(
            details, text="IF: --", bg=self.BG, fg=self.MUTED,
            font=("Consolas", 7)
        )
        self.interface.pack(side="right")

        graph_box = tk.Frame(
            content, bg=self.PANEL,
            highlightbackground=self.BORDER, highlightthickness=1
        )
        graph_box.grid(
            row=5, column=0, sticky="nsew", padx=8, pady=(2, 2)
        )
        graph_box.grid_columnconfigure(0, weight=1)
        graph_box.grid_rowconfigure(1, weight=1)
        tk.Label(
            graph_box, text="LIVE TRAFFIC", bg=self.PANEL, fg=self.MUTED,
            font=("Consolas", 7, "bold")
        ).grid(row=0, column=0, sticky="w", padx=6, pady=(2, 0))
        self.canvas = tk.Canvas(
            graph_box, bg=self.PANEL, highlightthickness=0,
            height=48, bd=0
        )
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 3))
        self.canvas.bind("<Configure>", lambda event: self.draw_graph())

        footer = tk.Frame(content, bg=self.BG)
        footer.grid(row=6, column=0, sticky="ew", padx=9, pady=(1, 4))
        self.uptime = tk.Label(
            footer, text="UPTIME: 00:00:00", bg=self.BG,
            fg=self.MUTED, font=("Consolas", 7)
        )
        self.uptime.pack(side="left")
        tk.Button(
            footer, text="X", command=self.close, bg=self.PANEL,
            fg=self.RED, activebackground=self.BORDER,
            activeforeground=self.RED, relief="flat",
            font=("Consolas", 8, "bold"), cursor="hand2", width=2,
            padx=0, pady=0
        ).pack(side="right")

        self.started = time.monotonic()
        self.root.after(1000, self.update_uptime)

    def create_loading_screen(self):

        self.dashboard.place_forget()

        self.splash = tk.Frame(
            self.root, bg=self.BG, width=238, height=238
        )
        self.splash.place(relx=0.5, rely=0.5, anchor="center")
        self.splash.pack_propagate(False)

        tk.Label(
            self.splash, text="NETPULSE", bg=self.BG, fg=self.GREEN,
            font=("Consolas", 17, "bold")
        ).pack(pady=(35, 5))

        tk.Label(
            self.splash, text="SYSTEM & NETWORK MONITORING", bg=self.BG,
            fg=self.MUTED, font=("Consolas", 8, "bold")
        ).pack(pady=(0, 23))

        self.loading_text = tk.Label(
            self.splash, text="INITIALIZING NETWORK", bg=self.BG,
            fg=self.BLUE, font=("Consolas", 8, "bold")
        )
        self.loading_text.pack(pady=(0, 10))

        self.loading_bar = tk.Canvas(
            self.splash, width=184, height=7, bg=self.PANEL,
            highlightthickness=0, bd=0
        )
        self.loading_bar.pack()

        self.loading_detail = tk.Label(
            self.splash, text="PLEASE WAIT...", bg=self.BG,
            fg=self.MUTED, font=("Consolas", 7)
        )
        self.loading_detail.pack(pady=(9, 0))

        tk.Label(
            self.splash, text="Made by iotb3r7", bg=self.BG,
            fg=self.MUTED, font=("Consolas", 8)
        ).pack(side="bottom", pady=(0, 13))

    def animate_loading(self):

        if not self.running or not self.splash_active:
            return

        message = self.loading_messages[self.loading_step % len(self.loading_messages)]
        self.loading_text.config(text=message)
        self.loading_step += 1

        self.loading_progress += 9
        if self.loading_progress > 92:
            self.loading_progress = 18

        self.loading_bar.delete("all")
        self.loading_bar.create_rectangle(
            0, 0, 184, 7, fill=self.PANEL, outline=self.PANEL
        )
        self.loading_bar.create_rectangle(
            0, 0, int(184 * self.loading_progress / 100), 7,
            fill=self.BLUE, outline=self.BLUE
        )

        self.root.after(650, self.animate_loading)

    def finish_loading(self, data):

        if not self.splash_active:
            self.update_display(data)
            return

        if self.loading_finished:
            return
        self.loading_finished = True
        self.update_display(data)

        if data["internet"]:
            latency = data["latency"] or 0
            if latency < 80:
                quality = "FAST CONNECTION"
                color = self.GREEN
            elif latency < 180:
                quality = "STABLE CONNECTION"
                color = self.BLUE
            else:
                quality = "SLOW CONNECTION"
                color = self.ORANGE
            detail = f"{quality}  |  {latency:.0f} ms"
        elif data["interfaces"]:
            detail = "NETWORK FOUND - NO INTERNET"
            color = self.ORANGE
        else:
            detail = "NO NETWORK CONNECTION"
            color = self.RED

        self.loading_text.config(text=detail, fg=color)
        self.loading_detail.config(text="STARTING DASHBOARD...", fg=self.MUTED)
        self.loading_bar.delete("all")
        self.loading_bar.create_rectangle(0, 0, 184, 7, fill=self.PANEL, outline=self.PANEL)
        self.loading_bar.create_rectangle(0, 0, 184, 7, fill=color, outline=color)

        elapsed = time.monotonic() - self.loading_started
        remaining_ms = max(
            0,
            int((self.minimum_loading_seconds - elapsed) * 1000)
        )
        result_ms = int(self.result_display_seconds * 1000)
        self.root.after(remaining_ms + result_ms, self.show_dashboard)

    def show_dashboard(self):

        if not self.running:
            return

        self.splash_active = False
        self.splash.destroy()
        self.dashboard.place(relx=0.5, rely=0.5, anchor="center")
        self.draw_graph()


    def metric(self, parent, title, value, column):

        box = tk.Frame(
            parent,
            bg=self.PANEL,
            highlightbackground=self.BORDER,
            highlightthickness=1
        )

        box.grid(
            row=0,
            column=column,
            sticky="ew",
            padx=3
        )

        parent.grid_columnconfigure(
            column, weight=1
        )

        tk.Label(
            box,
            text=title,
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Consolas", 8, "bold")
        ).pack(pady=(2, 0))

        label = tk.Label(
            box,
            text=value,
            bg=self.PANEL,
            fg=self.GREEN,
            font=("Consolas", 15, "bold")
        )
        label.pack(pady=(0, 2))

        return label

    def traffic_card(
        self, parent, title, value, color, column
    ):

        box = tk.Frame(
            parent,
            bg=self.PANEL,
            highlightbackground=self.BORDER,
            highlightthickness=1
        )

        box.grid(
            row=0,
            column=column,
            sticky="ew",
            padx=3
        )

        parent.grid_columnconfigure(
            column, weight=1
        )

        tk.Label(
            box,
            text=title,
            bg=self.PANEL,
            fg=color,
            font=("Consolas", 8, "bold")
        ).pack(anchor="center", padx=3, pady=(3, 0))

        label = tk.Label(
            box,
            text=value,
            bg=self.PANEL,
            fg=self.WHITE,
            font=("Consolas", 11, "bold")
        )
        label.pack(anchor="center", pady=(0, 3))

        return label

    @staticmethod
    def check_internet():

        hosts = [
            ("1.1.1.1", 443),
            ("8.8.8.8", 443)
        ]

        for host, port in hosts:

            try:
                start = time.perf_counter()

                with socket.create_connection(
                    (host, port),
                    timeout=2
                ):
                    latency = (
                        time.perf_counter() - start
                    ) * 1000

                return True, latency

            except OSError:
                continue

        return False, None

    @staticmethod
    def get_interfaces():

        interfaces = psutil.net_if_stats()
        active = []

        for name, stats in interfaces.items():

            if not stats.isup:
                continue

            if name.lower() in (
                "lo", "loopback"
            ):
                continue

            active.append(name)

        return active

    def monitor_worker(self):

        next_network_check = 0
        internet = False
        latency = None
        interfaces = []

        while not self.stop_event.is_set():

            try:

                now = time.monotonic()

                # Network speeds

                current_net = psutil.net_io_counters()

                elapsed = max(
                    now - self.prev_time,
                    0.001
                )

                download = max(
                    0,
                    current_net.bytes_recv -
                    self.prev_net.bytes_recv
                ) / elapsed

                upload = max(
                    0,
                    current_net.bytes_sent -
                    self.prev_net.bytes_sent
                ) / elapsed

                self.prev_net = current_net
                self.prev_time = now

                # CPU / RAM

                cpu = psutil.cpu_percent(
                    interval=None
                )

                ram = psutil.virtual_memory().percent

                # TCP connections

                try:
                    tcp = len(
                        psutil.net_connections(
                            kind="tcp"
                        )
                    )
                except (psutil.AccessDenied, OSError):
                    tcp = None

                # Check internet every 5 seconds

                if now >= next_network_check:

                    interfaces = self.get_interfaces()

                    if interfaces:
                        internet, latency = (
                            self.check_internet()
                        )
                    else:
                        internet = False
                        latency = None

                    next_network_check = now + 5

                self.data_queue.put({
                    "cpu": cpu,
                    "ram": ram,
                    "tcp": tcp,
                    "download": download,
                    "upload": upload,
                    "internet": internet,
                    "latency": latency,
                    "interfaces": interfaces
                })

            except Exception as error:

                self.data_queue.put({
                    "error": str(error)
                })

            self.stop_event.wait(1)

    @staticmethod
    def format_speed(value):

        if value >= 1_000_000:
            return f"{value / 1_000_000:.2f} MB/s"

        if value >= 1_000:
            return f"{value / 1_000:.1f} KB/s"

        return f"{value:.0f} B/s"

    def process_queue(self):

        if not self.running:
            return

        latest = None

        try:
            while True:
                latest = self.data_queue.get_nowait()

        except queue.Empty:
            pass

        if latest:
            if "error" in latest:
                self.status.config(
                    text="MONITOR ERROR",
                    fg=self.RED
                )
            else:
                if self.splash_active:
                    if not self.loading_finished:
                        self.finish_loading(latest)
                else:
                    self.update_display(latest)

        self.root.after(100, self.process_queue)

    def update_display(self, data):

        self.cpu.config(
            text=f"{data['cpu']:.0f}%"
        )

        self.ram.config(
            text=f"{data['ram']:.0f}%"
        )

        self.tcp.config(
            text=(
                str(data["tcp"])
                if data["tcp"] is not None
                else "N/A"
            )
        )

        down = data["download"]
        up = data["upload"]

        self.download.config(
            text=self.format_speed(down)
        )

        self.upload.config(
            text=self.format_speed(up)
        )

        # Actual connection state

        if data["internet"]:

            self.status.config(
                text="● INTERNET CONNECTED",
                fg=self.GREEN
            )

        elif data["interfaces"]:

            self.status.config(
                text="● NO INTERNET",
                fg=self.ORANGE
            )

        else:

            self.status.config(
                text="● OFFLINE",
                fg=self.RED
            )

        # Latency

        latency = data["latency"]

        if latency is not None and data["internet"]:

            self.latency.config(
                text=f"LATENCY: {latency:.0f} ms",
                fg=self.GREEN
            )

        else:

            self.latency.config(
                text="LATENCY: --",
                fg=self.RED
            )

        # Interface

        names = data["interfaces"]

        self.interface.config(
            text=(
                "IF: " + names[0][:12]
                if names else "IF: NONE"
            )
        )

        self.download_history.append(down)
        self.upload_history.append(up)

        self.draw_graph()

    def draw_graph(self):

        canvas = self.canvas
        canvas.delete("all")

        width = canvas.winfo_width()
        height = canvas.winfo_height()

        if width < 10 or height < 10:
            return

        padding = 8

        max_value = max(
            max(self.download_history),
            max(self.upload_history),
            1024
        ) * 1.2

        graph_width = width - padding * 2
        graph_height = height - padding * 2

        # Grid

        for i in range(3):

            y = (
                padding +
                graph_height * i / 2
            )

            canvas.create_line(
                padding, y,
                width - padding, y,
                fill=self.BORDER
            )

        def draw(values, color):

            points = []

            for i, value in enumerate(values):

                x = (
                    padding +
                    i / (len(values) - 1) *
                    graph_width
                )

                y = (
                    padding + graph_height -
                    (value / max_value) * graph_height
                )

                points.extend([x, y])

            canvas.create_line(
                *points,
                fill=color,
                width=2,
                smooth=True
            )

        draw(self.download_history, self.BLUE)
        draw(self.upload_history, self.GREEN)

    def update_uptime(self):

        if not self.running:
            return

        seconds = int(
            time.monotonic() - self.started
        )

        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        self.uptime.config(
            text=f"UPTIME: {hours:02}:{minutes:02}:{seconds:02}"
        )

        self.root.after(
            1000,
            self.update_uptime
        )

    def close(self):

        if not self.running:
            return

        self.running = False
        self.stop_event.set()

        self.root.destroy()


def main():

    root = tk.Tk()

    NETPULSE(root)
    try:
        root.iconbitmap(resource_path("netpulse.ico"))
    except Exception as e:
        print("Icon loading error:", e)

    root.mainloop()


if __name__ == "__main__":
    main()

"""PC Dual Audio — GUI ringan + sembunyi ke tray (stdlib tkinter; tray via pystray opsional)."""
import json
import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from audio_router import DualRouter, query_device_lists

BG = "#121212"
SURFACE = "#1E1E1E"
CARD = "#242424"
FG = "#FFFFFF"
MUTED = "#B0B0B0"
ACCENT = "#BB86FC"
ACCENT2 = "#03DAC6"
ERROR = "#CF6679"

CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config() -> dict:
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(cfg: dict) -> None:
    try:
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except OSError:
        pass


def make_icon(running: bool):
    """Ikon tray 64px via Pillow; None bila Pillow tak ada."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    color = ACCENT2 if running else "#888888"
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([4, 4, 60, 60], radius=14, fill=color)
    d.polygon([(26, 20), (26, 44), (46, 32)], fill="#000000")
    return img


class TrayController:
    """Ikon tray pystray di thread daemon. Tanpa pystray -> no-op (tombol Sembunyi pakai minimize biasa)."""

    def __init__(self, app: "App"):
        self.app = app
        self.icon = None
        self._thread = None

    @property
    def available(self) -> bool:
        try:
            import pystray  # noqa: F401
            return True
        except ImportError:
            return False

    def _menu(self):
        import pystray
        running = self.app.router is not None and self.app.router.running
        return pystray.Menu(
            pystray.MenuItem("Buka", lambda: self.app.after(0, self.app.show_window), default=True),
            pystray.MenuItem("Stop" if running else "Mulai",
                             lambda: self.app.after(0, self.app.toggle)),
            pystray.MenuItem("Mode: Mirror" if self.app.mode.get() != "mirror" else "Mode: Split (L/R)",
                             lambda: self.app.after(0, self.app.flip_mode)),
            pystray.MenuItem("Keluar", lambda: self.app.after(0, self.app.quit_all)),
        )

    def show(self):
        if not self.available or self.icon is not None:
            return
        import pystray
        running = self.app.router is not None and self.app.router.running
        self.icon = pystray.Icon("dual-audio", make_icon(running), "Dual Audio", menu=self._menu())
        self._thread = threading.Thread(target=self.icon.run, daemon=True)
        self._thread.start()

    def refresh(self):
        if self.icon is not None:
            try:
                running = self.app.router is not None and self.app.router.running
                self.icon.icon = make_icon(running)
                self.icon.menu = self._menu()
                self.icon.update_menu()
            except Exception:  # noqa: BLE001 - tray best-effort
                pass

    def hide(self):
        icon, self.icon = self.icon, None
        if icon is not None:
            try:
                icon.stop()
            except Exception:  # noqa: BLE001 - best-effort
                pass


class App(tk.Tk):
    def __init__(self, start_minimized: bool = False):
        super().__init__()
        self.title("Dual Audio — Internal + Bluetooth")
        self.geometry("560x640")
        self.configure(bg=BG)
        self.router: DualRouter | None = None
        self.tray = TrayController(self)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("TLabel", background=CARD, foreground=FG, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=BG, foreground=FG, font=("Segoe UI", 16, "bold"))
        style.configure("Sub.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("Status.TLabel", background=CARD, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("TButton", background=ACCENT, foreground="#000000",
                        font=("Segoe UI", 10, "bold"), padding=10, borderwidth=0)
        style.map("TButton", background=[("active", ACCENT2), ("disabled", "#444444")])
        style.configure("Stop.TButton", background=ERROR, foreground="#FFFFFF")
        style.map("Stop.TButton", background=[("active", "#E57373")])
        style.configure("TCombobox", fieldbackground=SURFACE, background=SURFACE,
                        foreground=FG, arrowcolor=ACCENT)
        style.configure("Horizontal.TScale", background=CARD, troughcolor=SURFACE)

        header = ttk.Frame(self, style="TFrame")
        header.pack(fill="x", padx=20, pady=(20, 4))
        ttk.Label(header, text="Dual Audio", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Bareng ke internal + Bluetooth, atau split kiri/kanan.",
                  style="Sub.TLabel").pack(anchor="w")

        self.card = ttk.Frame(self, style="Card.TFrame", padding=16)
        self.card.pack(fill="both", expand=True, padx=20, pady=12)

        cfg = load_config()
        self.mode = tk.StringVar(value=cfg.get("mode", "mirror"))
        mode_row = ttk.Frame(self.card, style="Card.TFrame")
        mode_row.pack(fill="x", pady=(0, 12))
        ttk.Label(mode_row, text="Mode").pack(side="left")
        ttk.Radiobutton(mode_row, text="Mirror (sama)", value="mirror", variable=self.mode,
                        command=self._on_mode).pack(side="left", padx=(16, 8))
        ttk.Radiobutton(mode_row, text="Split (L/R)", value="split", variable=self.mode,
                        command=self._on_mode).pack(side="left")

        self.in_var, self.out1_var, self.out2_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.in_idx, self.out1_idx, self.out2_idx = {}, {}, {}
        self.cb_in = self._combo("Sumber (input / Stereo Mix)", self.in_var)
        self.cb_out1 = self._combo("Output 1 — Internal", self.out1_var)
        self.cb_out2 = self._combo("Output 2 — Bluetooth", self.out2_var)

        btn_row = ttk.Frame(self.card, style="Card.TFrame")
        btn_row.pack(fill="x", pady=(4, 8))
        ttk.Button(btn_row, text="↻ Refresh device", command=self.refresh_devices).pack(side="left")
        ttk.Button(btn_row, text="⬇ Sembunyi ke tray", command=self.hide_to_tray).pack(side="right")

        self.g1 = tk.DoubleVar(value=cfg.get("g1", 1.0))
        self.g2 = tk.DoubleVar(value=cfg.get("g2", 1.0))
        self._slider("Volume Internal", self.g1)
        self._slider("Volume Bluetooth", self.g2)

        self.btn = ttk.Button(self.card, text="▶  MULAI", command=self.toggle)
        self.btn.pack(fill="x", pady=(16, 4))
        self.status = ttk.Label(self.card, text="Siap. Pilih device lalu MULAI.",
                                style="Status.TLabel", wraplength=480)
        self.status.pack(fill="x", pady=(4, 0))

        self.refresh_devices(restore=cfg)
        if start_minimized or cfg.get("minimized"):
            self._autostart(cfg)

    # ---- widgets ----
    def _combo(self, label, var):
        ttk.Label(self.card, text=label).pack(anchor="w", pady=(8, 2))
        cb = ttk.Combobox(self.card, textvariable=var, state="readonly", width=60)
        cb.pack(fill="x")
        return cb

    def _slider(self, label, var):
        row = ttk.Frame(self.card, style="Card.TFrame")
        row.pack(fill="x", pady=(8, 0))
        ttk.Label(row, text=label).pack(side="left")
        val = ttk.Label(row, text="100%", width=6)
        val.pack(side="right")

        def upd(_e=None):
            val.config(text=f"{int(var.get() * 100)}%")
            if self.router:
                self.router.set_gains(self.g1.get(), self.g2.get())

        ttk.Scale(self.card, from_=0.0, to=1.5, variable=var,
                  command=lambda _e: upd()).pack(fill="x")
        upd()

    # ---- logic ----
    def refresh_devices(self, restore: dict | None = None):
        inputs, outputs = query_device_lists()
        if not inputs and not outputs:
            self.set_status("sounddevice belum terpasang / tak ada device. pip install -r pc/requirements.txt")
            return
        self.in_idx = {label: i for i, label in inputs}
        self.out1_idx = {label: i for i, label in outputs}
        self.out2_idx = dict(self.out1_idx)
        self.cb_in["values"] = [label for _, label in inputs]
        self.cb_out1["values"] = [label for _, label in outputs]
        self.cb_out2["values"] = [label for _, label in outputs]
        restore = restore or {}
        self.in_var.set(restore.get("in_label", inputs[0][1]) if restore.get("in_label") in self.in_idx else inputs[0][1])
        self.out1_var.set(restore.get("o1_label", outputs[0][1]) if restore.get("o1_label") in self.out1_idx else outputs[0][1])
        last = outputs[-1][1] if len(outputs) > 1 else outputs[0][1]
        self.out2_var.set(restore.get("o2_label", last) if restore.get("o2_label") in self.out2_idx else last)
        self.set_status(f"{len(inputs)} input, {len(outputs)} output ketemu.")

    def set_status(self, msg):
        self.status.config(text=msg)

    def _persist(self):
        save_config({"in_label": self.in_var.get(), "o1_label": self.out1_var.get(),
                     "o2_label": self.out2_var.get(), "mode": self.mode.get(),
                     "g1": self.g1.get(), "g2": self.g2.get(), "minimized": True})

    def _on_mode(self):
        if self.router:
            self.router.set_mode(self.mode.get())
        self.tray.refresh()

    def flip_mode(self):
        self.mode.set("split" if self.mode.get() == "mirror" else "mirror")
        self._on_mode()
        self.set_status(f"Mode: {self.mode.get()}.")

    def _autostart(self, cfg: dict):
        """Jalan otomatis pakai config terakhir, langsung sembunyi ke tray."""
        self.refresh_devices(restore=cfg)
        try:
            dev_in = self.in_idx[self.in_var.get()]
            dev_o1 = self.out1_idx[self.out1_var.get()]
            dev_o2 = self.out2_idx[self.out2_var.get()]
        except KeyError:
            return
        if dev_o1 == dev_o2:
            return
        self._start_router(dev_in, dev_o1, dev_o2)
        self.hide_to_tray(silent=True)

    def _start_router(self, dev_in, dev_o1, dev_o2) -> bool:
        r = DualRouter(dev_in, dev_o1, dev_o2, mode=self.mode.get())
        r.set_gains(self.g1.get(), self.g2.get())
        r.on_status = lambda m: self.after(0, lambda: self.set_status(m))
        try:
            r.start()
        except Exception as e:  # noqa: BLE001 - tampilkan ke user
            messagebox.showerror("Gagal start", str(e))
            return False
        self.router = r
        self.btn.config(text="■  STOP", style="Stop.TButton")
        m = "bersamaan (mirror)" if self.mode.get() == "mirror" else "split L→Internal, R→BT"
        self.set_status(f"Jalan: {m}. Tutup jendela = sembunyi ke tray.")
        self._persist()
        self.tray.refresh()
        return True

    def toggle(self):
        if self.router and self.router.running:
            self.router.stop()
            self.router = None
            self.btn.config(text="▶  MULAI", style="TButton")
            self.set_status("Berhenti.")
            self.tray.refresh()
            return
        try:
            dev_in = self.in_idx[self.in_var.get()]
            dev_o1 = self.out1_idx[self.out1_var.get()]
            dev_o2 = self.out2_idx[self.out2_var.get()]
        except KeyError:
            messagebox.showwarning("Device", "Pilih semua device dulu.")
            return
        if dev_o1 == dev_o2:
            messagebox.showwarning("Device", "Output 1 dan 2 harus beda.")
            return
        self._start_router(dev_in, dev_o1, dev_o2)

    # ---- tray ----
    def hide_to_tray(self, silent: bool = False):
        if not self.tray.available:
            self.iconify()  # fallback: minimize biasa bila pystray tak ada
            if not silent:
                self.set_status("pystray belum dipasang — jendela di-minimize biasa. pip install pystray")
            return
        self.withdraw()
        self.tray.show()
        self.tray.refresh()

    def show_window(self):
        self.tray.hide()
        self.deiconify()
        self.lift()

    def quit_all(self):
        self.tray.hide()
        if self.router:
            self.router.stop()
        self.destroy()

    def on_close(self):
        if self.router and self.router.running:
            self.hide_to_tray()  # tutup jendela = jalan terus di tray
        else:
            self.quit_all()


if __name__ == "__main__":
    import sys
    app = App(start_minimized="--tray" in sys.argv)
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()

"""PC Dual Audio — 2 lagu beda jalan bareng (BT lagu A, internal lagu B)."""
import json
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from dual_player import SlotPlayer, has_ffmpeg, list_outputs

BG = "#121212"
CARD = "#242424"
FG = "#FFFFFF"
MUTED = "#B0B0B0"
ACCENT = "#BB86FC"
ACCENT2 = "#03DAC6"
ERROR = "#CF6679"
SURFACE = "#1E1E1E"

CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
ICON_A = "🔊"
ICON_B = "🎧"


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
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([4, 4, 60, 60], radius=14, fill=ACCENT2 if running else "#888888")
    d.polygon([(26, 20), (26, 44), (46, 32)], fill="#000000")
    return img


class Tray:
    def __init__(self, app):
        self.app, self.icon = app, None

    @property
    def available(self) -> bool:
        try:
            import pystray  # noqa: F401
            return True
        except ImportError:
            return False

    def show(self):
        if not self.available or self.icon is not None:
            return
        import pystray
        a, b = self.app.playing()
        self.icon = pystray.Icon("dual", make_icon(a or b), "Dual Audio",
                                menu=pystray.Menu(
                                    pystray.MenuItem("Buka", lambda: self.app.after(0, self.app.show_window), default=True),
                                    pystray.MenuItem("Keluar", lambda: self.app.after(0, self.app.quit_all))))
        threading.Thread(target=self.icon.run, daemon=True).start()

    def refresh(self):
        if self.icon is not None:
            try:
                a, b = self.app.playing()
                self.icon.icon = make_icon(a or b)
            except Exception:  # noqa: BLE001 - tray best-effort
                pass

    def hide(self):
        icon, self.icon = self.icon, None
        if icon is not None:
            try:
                icon.stop()
            except Exception:  # noqa: BLE001
                pass


class SlotCard:
    """Satu kartu = satu file + satu output + play/stop + volume."""

    def __init__(self, parent, app, title, icon, cfg: dict):
        self.app, self.icon = app, icon
        self.player: SlotPlayer | None = None
        fr = ttk.Frame(parent, style="Card.TFrame", padding=14)
        fr.pack(fill="x", pady=(0, 12))
        self.fr = fr

        ttk.Label(fr, text=f"{icon}  {title}", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.file_lbl = ttk.Label(fr, text="Belum ada file", style="Status.TLabel", wraplength=480)
        self.file_lbl.pack(anchor="w", pady=(6, 0))

        row = ttk.Frame(fr, style="Card.TFrame")
        row.pack(fill="x", pady=(8, 0))
        ttk.Label(row, text="File:").pack(side="left")
        ttk.Button(row, text="📂 Pilih…", command=self.pick).pack(side="left", padx=(8, 0))

        self.dev_var = tk.StringVar()
        self.dev_idx: dict = {}
        self.cb = ttk.Combobox(fr, textvariable=self.dev_var, state="readonly", width=58)
        self.cb.pack(fill="x", pady=(8, 0))
        self.cb.bind("<<ComboboxSelected>>", lambda _e: self._rebind())

        self.g = tk.DoubleVar(value=cfg.get("g", 1.0))
        self.loop = tk.BooleanVar(value=cfg.get("loop", False))
        srow = ttk.Frame(fr, style="Card.TFrame")
        srow.pack(fill="x", pady=(8, 0))
        ttk.Label(srow, text="Volume").pack(side="left")
        self.g_lbl = ttk.Label(srow, text=f"{int(self.g.get()*100)}%", width=6)
        self.g_lbl.pack(side="right")
        ttk.Checkbutton(srow, text="🔁 Ulangi", variable=self.loop).pack(side="right", padx=(0, 12))
        ttk.Scale(fr, from_=0.0, to=1.5, variable=self.g,
                  command=lambda _e: self._on_gain()).pack(fill="x")

        brow = ttk.Frame(fr, style="Card.TFrame")
        brow.pack(fill="x", pady=(10, 0))
        self.btn = ttk.Button(brow, text="▶  PUTAR", command=self.toggle)
        self.btn.pack(fill="x")
        self.st = ttk.Label(fr, text="Siap.", style="Status.TLabel")
        self.st.pack(anchor="w", pady=(4, 0))

        self.refresh_devices()
        if cfg.get("file") and os.path.exists(cfg["file"]):
            self.load_file(cfg["file"], quiet=True)
        if cfg.get("dev") in self.dev_idx.values():
            for label, i in self.dev_idx.items():
                if i == cfg["dev"]:
                    self.dev_var.set(label)
                    self._rebind()
                    break

    # -- device --
    def refresh_devices(self):
        outs = list_outputs()
        keep = self.dev_var.get()
        self.dev_idx = {label: i for i, label in outs}
        self.cb["values"] = [label for _, label in outs]
        if keep in self.dev_idx:
            self.dev_var.set(keep)
        elif outs:
            self.dev_var.set(outs[0][1])
        self._rebind(quiet=True)

    def _on_gain(self):
        self.g_lbl.config(text=f"{int(self.g.get()*100)}%")
        if self.player:
            self.player.gain = self.g.get()

    def _rebind(self, quiet: bool = False):
        if self.player and self.player.playing:
            if not quiet:
                messagebox.showinfo("Device", "Stop dulu sebelum ganti output.")
            for label, i in self.dev_idx.items():
                if self.player and i == self.player.device:
                    self.dev_var.set(label)
                    break
            return
        self.player = None

    def _device(self) -> int:
        try:
            return self.dev_idx[self.dev_var.get()]
        except KeyError:
            raise RuntimeError("Pilih output device dulu.")

    # -- file --
    def pick(self):
        path = filedialog.askopenfilename(
            title=f"Pilih lagu {self.icon}",
            filetypes=[("Audio", "*.mp3 *.wav *.m4a *.ogg *.flac"), ("Semua", "*.*")])
        if path:
            self.load_file(path)

    def load_file(self, path: str, quiet: bool = False):
        try:
            p = SlotPlayer(self._device())
        except RuntimeError as e:
            if not quiet:
                messagebox.showwarning("Device", str(e))
            return
        p.gain, p.loop = self.g.get(), self.loop.get()
        p.on_error = lambda m: self.app.after(0, lambda: self.st.config(text=f"Error: {m}"))
        try:
            p.load(path)
        except RuntimeError as e:
            if not quiet:
                messagebox.showerror("File", str(e))
            else:
                self.st.config(text=f"File lama gagal dibuka: {e}")
            return
        self.player = p
        name = os.path.basename(path)
        mins, secs = int(p.duration // 60), int(p.duration % 60)
        self.file_lbl.config(text=f"🎵 {name}  ({mins}:{secs:02d})")
        self.st.config(text="File siap. Tekan PUTAR.")
        self.app.persist()

    # -- transport --
    def toggle(self):
        if self.player and self.player.playing:
            self.player.stop()
            self.btn.config(text="▶  PUTAR", style="TButton")
            self.st.config(text="Berhenti.")
            self.app.tray.refresh()
            return
        if self.player is None or not self.player.file:
            messagebox.showwarning("File", f"Pilih lagu {self.icon} dulu.")
            return
        try:
            dev = self._device()
        except RuntimeError as e:
            messagebox.showwarning("Device", str(e))
            return
        if self.player.device != dev:
            old = self.player
            p = SlotPlayer(dev)
            p.load(old.file)
            p.on_error = old.on_error
            self.player = p
        self.player.gain, self.player.loop = self.g.get(), self.loop.get()
        try:
            self.player.play()
        except RuntimeError as e:
            messagebox.showerror("Putar", str(e))
            return
        self.btn.config(text="■  STOP", style="Stop.TButton")
        other = "🎧" if self.icon == ICON_A else "🔊"
        self.st.config(text=f"Jalan. {other} bisa muter lagu lain.")
        self.app.tray.refresh()

    def config(self) -> dict:
        return {"file": self.player.file if self.player else "",
                "dev": self.player.device if self.player else self.dev_idx.get(self.dev_var.get(), -1),
                "g": self.g.get(), "loop": self.loop.get()}

    def playing(self) -> bool:
        return bool(self.player and self.player.playing)

    def stop(self):
        if self.player:
            self.player.stop()


class App(tk.Tk):
    def __init__(self, start_minimized: bool = False):
        super().__init__()
        self.title("Dual Audio — 2 Lagu Beda Bersamaan")
        self.geometry("580x760")
        self.configure(bg=BG)
        self.tray = Tray(self)

        style = ttk.Style(self)
        style.theme_use("clam")
        for s, kw in [("TFrame", dict(background=BG)),
                      ("Card.TFrame", dict(background=CARD)),
                      ("TLabel", dict(background=CARD, foreground=FG, font=("Segoe UI", 10))),
                      ("Title.TLabel", dict(background=BG, foreground=FG, font=("Segoe UI", 16, "bold"))),
                      ("Sub.TLabel", dict(background=BG, foreground=MUTED, font=("Segoe UI", 10))),
                      ("Status.TLabel", dict(background=CARD, foreground=MUTED, font=("Segoe UI", 9))),
                      ("TButton", dict(background=ACCENT, foreground="#000000", font=("Segoe UI", 10, "bold"), padding=8, borderwidth=0)),
                      ("Stop.TButton", dict(background=ERROR, foreground="#FFFFFF")),
                      ("TCombobox", dict(fieldbackground=SURFACE, background=SURFACE, foreground=FG, arrowcolor=ACCENT)),
                      ("Horizontal.TScale", dict(background=CARD, troughcolor=SURFACE)),
                      ("TCheckbutton", dict(background=CARD, foreground=FG))]:
            style.configure(s, **kw)
        style.map("TButton", background=[("active", ACCENT2), ("disabled", "#444444")])

        cfg = load_config()
        hdr = ttk.Frame(self, style="TFrame")
        hdr.pack(fill="x", padx=20, pady=(20, 4))
        ttk.Label(hdr, text="Dual Audio", style="Title.TLabel").pack(anchor="w")
        sub = "ffmpeg ✓ MP3 bisa" if has_ffmpeg() else "ffmpeg ✗ — cuma WAV (pasang ffmpeg biar MP3)"
        ttk.Label(hdr, text=f"Pilih 2 lagu + 2 output. Jalan bareng. {sub}", style="Sub.TLabel").pack(anchor="w")

        body = ttk.Frame(self, style="TFrame", padding=0)
        body.pack(fill="both", expand=True, padx=20, pady=12)
        self.slot_a = SlotCard(body, self, "Slot A — Internal", ICON_A, cfg.get("a", {}))
        self.slot_b = SlotCard(body, self, "Slot B — Bluetooth", ICON_B, cfg.get("b", {}))

        row = ttk.Frame(self, style="TFrame")
        row.pack(fill="x", padx=20, pady=(0, 16))
        ttk.Button(row, text="⬇ Sembunyi ke tray", command=self.hide_to_tray).pack(fill="x")

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        if start_minimized:
            self.after(300, lambda: self.hide_to_tray(silent=True))

    # -- app-level --
    def playing(self):
        return self.slot_a.playing(), self.slot_b.playing()

    def persist(self):
        save_config({"a": self.slot_a.config(), "b": self.slot_b.config()})

    def hide_to_tray(self, silent: bool = False):
        self.persist()
        if not self.tray.available:
            self.iconify()
            if not silent:
                messagebox.showinfo("Tray", "pystray belum ada — minimize biasa.\npip install pystray")
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
        self.slot_a.stop()
        self.slot_b.stop()
        self.destroy()

    def on_close(self):
        self.persist()
        if self.playing()[0] or self.playing()[1]:
            self.hide_to_tray()
        else:
            self.quit_all()


if __name__ == "__main__":
    import sys
    app = App(start_minimized="--tray" in sys.argv)
    app.mainloop()

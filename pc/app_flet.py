"""Dual Audio — UI Flet (Material asli). Logic di dual_player.py, ringan.

Jalan:  flet run pc/app_flet.py
Build:  flet pack pc/app_flet.py --name DualAudio
"""
import asyncio
import json
import os

import flet as ft

from dual_player import SlotPlayer, has_ffmpeg, list_outputs

CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
ICON_A, ICON_B = "🔊", "🎧"


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


class Slot:
    """Satu kartu: file + output + play/stop + volume."""

    def __init__(self, page: ft.Page, title: str, icon: str, cfg: dict):
        self.page, self.icon = page, icon
        self.player: SlotPlayer | None = None
        self.devs: dict = {}
        self.file_path = ""

        self.file_lbl = ft.Text("Belum ada file", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.dev_dd = ft.Dropdown(label="Output device", options=[], expand=True,
                                  on_select=lambda _e: self._rebind())
        self.vol_lbl = ft.Text(f"Volume {int(cfg.get('g', 100))}%", size=12)
        self.vol = ft.Slider(min=0, max=150, value=cfg.get("g", 100), divisions=150,
                             on_change=self._on_vol)
        self.loop = ft.Checkbox(label="Ulangi", value=cfg.get("loop", False))
        self.status = ft.Text("Siap.", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.btn = ft.FilledButton(f"▶ PUTAR {icon}", on_click=self.toggle, expand=True)

        async def pick(_e):
            r = await page.pick_files_async(dialog_title=f"Lagu {icon}",
                                            allowed_extensions=["mp3", "wav", "m4a", "ogg", "flac"])
            if r and r.files:
                self.load(r.files[0].path)

        self.card = ft.Card(content=ft.Container(
            content=ft.Column([
                ft.Text(f"{icon}  {title}", size=16, weight=ft.FontWeight.BOLD),
                self.file_lbl,
                ft.Row([ft.OutlinedButton("📂 Pilih lagu", on_click=pick)]),
                self.dev_dd,
                ft.Row([ft.Text("Volume"), self.vol_lbl]),
                self.vol,
                self.loop,
                self.btn,
                self.status,
            ], spacing=8),
            padding=16,
        ))

        self.refresh_devices()
        old = cfg.get("file", "")
        if old and os.path.exists(old):
            self.load(old, quiet=True)
        if cfg.get("dev", -1) in self.devs.values():
            for label, i in self.devs.items():
                if i == cfg["dev"]:
                    self.dev_dd.value = label
                    break
            self.page.update()

    # -- device --
    def refresh_devices(self):
        keep = self.dev_dd.value
        self.devs = {label: i for i, label in list_outputs()}
        self.dev_dd.options = [ft.dropdown.Option(label) for label in self.devs]
        if keep in self.devs:
            self.dev_dd.value = keep
        elif self.devs:
            self.dev_dd.value = next(iter(self.devs))

    def _rebind(self):
        if self.player and self.player.playing:
            self.status.value = "Stop dulu sebelum ganti output."
            for label, i in self.devs.items():
                if self.player.device == i:
                    self.dev_dd.value = label
                    break
            self.page.update()
            return
        self.player = None

    def device(self) -> int:
        try:
            return self.devs[self.dev_dd.value]
        except KeyError:
            raise RuntimeError("Pilih output device dulu.")

    # -- file --
    def load(self, path: str, quiet: bool = False):
        try:
            dev = self.device()
        except RuntimeError as e:
            if not quiet:
                self._snack(str(e))
            return
        p = SlotPlayer(dev)
        p.gain, p.loop = self.vol.value / 100, self.loop.value
        p.on_error = lambda m: self._from_thread(f"Error: {m}")
        try:
            p.load(path)
        except RuntimeError as e:
            self.status.value = f"Gagal buka: {e}"
            self.page.update()
            return
        self.file_path, self.player = path, p
        mins, secs = int(p.duration // 60), int(p.duration % 60)
        self.file_lbl.value = f"🎵 {os.path.basename(path)}  ({mins}:{secs:02d})"
        self.status.value = "File siap. Tekan PUTAR."
        self.page.update()

    def _on_vol(self, _e):
        self.vol_lbl.value = f"Volume {int(self.vol.value)}%"
        if self.player:
            self.player.gain = self.vol.value / 100
        self.page.update()

    # -- transport --
    def toggle(self, _e=None):
        if self.player and self.player.playing:
            self.player.stop()
            self.btn.text = f"▶ PUTAR {self.icon}"
            self.status.value = "Berhenti."
            self.page.update()
            return
        if self.player is None or not self.player.file:
            self._snack(f"Pilih lagu {self.icon} dulu.")
            return
        try:
            dev = self.device()
        except RuntimeError as e:
            self._snack(str(e))
            return
        if self.player.device != dev:
            old = self.player
            p = SlotPlayer(dev)
            p.load(old.file)
            p.on_error = old.on_error
            self.player = p
        self.player.gain, self.player.loop = self.vol.value / 100, self.loop.value
        try:
            self.player.play()
        except RuntimeError as e:
            self._snack(str(e))
            return
        other = "🎧" if self.icon == ICON_A else "🔊"
        self.btn.text = f"■ STOP {self.icon}"
        self.status.value = f"Jalan. {other} bisa muter lagu lain."
        self.page.update()

    def _snack(self, msg: str):
        self.page.open(ft.SnackBar(ft.Text(msg)))
        self.page.update()

    def _from_thread(self, msg: str):
        self.status.value = msg
        try:
            self.page.update()
        except Exception:  # noqa: BLE001 - page mungkin tutup
            pass

    def config(self) -> dict:
        dev = self.player.device if self.player else self.devs.get(self.dev_dd.value or "", -1)
        return {"file": self.player.file if self.player else self.file_path,
                "dev": dev, "g": self.vol.value, "loop": self.loop.value}

    def playing(self) -> bool:
        return bool(self.player and self.player.playing)

    def stop(self):
        if self.player:
            self.player.stop()


async def main(page: ft.Page):
    page.title = "Dual Audio"
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.DEEP_PURPLE)
    page.scroll = ft.ScrollMode.AUTO
    page.window.width, page.window.height = 560, 800

    cfg = load_config()
    slot_a = Slot(page, "Slot A — Internal", ICON_A, cfg.get("a", {"g": 100}))
    slot_b = Slot(page, "Slot B — Bluetooth", ICON_B, cfg.get("b", {"g": 100}))

    page.appbar = ft.AppBar(title=ft.Text("Dual Audio — 2 lagu bareng"), center_title=False)
    sub = "MP3 bisa (ffmpeg ✓)" if has_ffmpeg() else "cuma WAV — pasang ffmpeg biar MP3"
    page.add(
        ft.Text(f"Pilih 2 lagu + 2 output. Jalan bareng. {sub}",
                color=ft.Colors.ON_SURFACE_VARIANT),
        slot_a.card,
        slot_b.card,
        ft.OutlinedButton("↻ Refresh device",
                          on_click=lambda _e: (slot_a.refresh_devices(), slot_b.refresh_devices(), page.update())),
    )

    async def on_close(_e):
        save_config({"a": slot_a.config(), "b": slot_b.config()})
        slot_a.stop()
        slot_b.stop()
        await page.window.destroy_async()

    page.on_window_event = lambda e: asyncio.ensure_future(on_close(e)) \
        if e.data == "close" else None


if __name__ == "__main__":
    ft.run(main)

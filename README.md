# Dual Audio: 2 lagu beda jalan bareng

Slot A → speaker internal, Slot B → Bluetooth. Lagu beda, jalan bersamaan.

## PC — `DualAudio-v2.exe` (di Releases)

Jalankan EXE. Tanpa install. Butuh `ffmpeg` di PATH biar MP3 bisa (tanpa itu cuma WAV).

- Kartu A: pilih lagu + output internal → PUTAR
- Kartu B: pilih lagu + output Bluetooth → PUTAR
- Volume + loop (🔁) tiap slot. Config tersimpan otomatis.

Dev:
```bash
pip install -r pc/requirements.txt
python pc/app_flet.py          # UI Flet (Material)
python pc/test_dual_player.py  # test inti
```

## Android — APK (di Releases)

Install APK di HP fisik, BT konek. Buka aplikasi:

- Slot A → internal, Slot B → Bluetooth (default otomatis)
- 📂 Pilih lagu tiap slot (MP3/M4A/OGG, decode native) — kosong = nada uji
- ▶ PUTAR BARENG. Jalan di foreground service, tutup aplikasi aman.
- Tile Quick Settings "Dual Audio": tambah manual sekali, ketuk = start/stop.

Dev: buka `android/` di Android Studio, `assembleDebug`.

## Batasan

OS batasi rute audio tingkat sistem — solusi ini kirim manual 2 stream. Audio aplikasi pihak ketiga (Spotify/YouTube) di Android butuh `AudioPlaybackCapture` — belum ada.

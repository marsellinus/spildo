# Dual Audio: Internal + Bluetooth

2 aplikasi terpisah. Ringan, jalan background.

## PC (`pc/`)

```bash
pip install -r pc/requirements.txt
python pc/app_gui.py            # buka GUI
python pc/app_gui.py --tray     # langsung jalan minim + sembunyi ke tray
```

- GUI Material-ish gelap: pilih input/output, mode Mirror/Split, volume tiap output.
- Tutup jendela saat jalan = sembunyi ke tray, audio tetap jalan.
- Klik kanan ikon tray: Buka / Mulai / Stop / ganti mode / Keluar.
- Config terakhir (device, mode, volume) tersimpan di `pc/config.json`, auto-jalan saat `--tray`.
- Tanpa `pystray`: fallback minimize biasa. Pasang via requirements.
- Tetap ada CLI: `python pc/audio_router.py --list`, `... --in-dev 1 --out-internal 2 --out-bt 3 --mode split`.

Idle ≈ 0% CPU (event-driven). Jalan ≈ 1-3% (satu thread audio + queue 8 blok).

## Android (`android/`)

Buka `android/` di Android Studio, build ke HP fisik, BT konek.

- UI Material3: kartu perangkat, toggle Mirror/Split, slider volume, tombol MULAI besar.
- Suara jalan di `DualAudioService` (foreground + notifikasi + tombol Stop). Tutup aplikasi aman.
- **Shortcut panel cepat**: tarik Quick Settings → edit tile → tambah "Dual Audio". Ketuk tile = start/stop tanpa buka aplikasi.
- Mode ganti live tanpa putus suara. Perlu izin `BLUETOOTH_CONNECT` (Android 12+) + `POST_NOTIFICATIONS` (Android 13+), diminta otomatis.

## Batasan

OS batasi rute audio sistem. Solusi ini kirim manual ke 2 output. Audio pihak ketiga (Spotify/YouTube) di Android butuh `AudioPlaybackCapture` (MediaProjection) — belum ada. Tambah bila perlu.

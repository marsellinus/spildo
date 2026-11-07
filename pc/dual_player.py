"""Dua player independen — tiap slot file sendiri + output device sendiri.

Decode: ffmpeg bila ada (mp3/m4a/ogg/dll), fallback stdlib wave khusus WAV.
Putar: satu thread + satu OutputStream per slot.
"""
import shutil
import subprocess
import threading
import wave

import numpy as np

try:
    import sounddevice as sd
except ImportError:
    sd = None

SR = 44100


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def decode_audio(path: str, sr: int = SR) -> np.ndarray:
    """Kembalikan stereo float32 (-1..1). ffmpeg utama, wave fallback."""
    if has_ffmpeg():
        return _decode_ffmpeg(path, sr)
    if path.lower().endswith(".wav"):
        return _decode_wav(path, sr)
    raise RuntimeError("ffmpeg tak ketemu (butuh untuk MP3). Install ffmpeg atau pakai file WAV.")


def _decode_ffmpeg(path: str, sr: int) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-ac", "2", "-ar", str(sr),
           "-f", "f32le", "-acodec", "pcm_f32le", "-"]
    raw = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if raw.returncode != 0 or not raw.stdout:
        raise RuntimeError(f"Gagal decode {path}: {raw.stderr.decode(errors='ignore')[:200]}")
    data = np.frombuffer(raw.stdout, dtype=np.float32).reshape(-1, 2).copy()
    if len(data) == 0:
        raise RuntimeError(f"File kosong / tak terbaca: {path}")
    return data


def _decode_wav(path: str, sr: int) -> np.ndarray:
    with wave.open(path, "rb") as w:
        nch, sw, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        if sw != 2:
            raise RuntimeError("WAV harus 16-bit bila tanpa ffmpeg.")
        if rate != sr:
            raise RuntimeError(f"WAV {rate}Hz != {sr}Hz, pasang ffmpeg untuk resample.")
        raw = w.readframes(n)
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    data = data.reshape(-1, nch)
    if nch == 1:
        data = np.column_stack((data, data))
    return np.ascontiguousarray(data[:, :2])


def apply_gain(buf: np.ndarray, gain: float) -> np.ndarray:
    return (buf * gain).astype(buf.dtype)


def list_outputs() -> list:
    """List (index, label) output device. Kosong bila sounddevice tak ada."""
    if sd is None:
        return []
    return [(i, f"{i}: {d['name']}") for i, d in enumerate(sd.query_devices())
            if d["max_output_channels"] > 0]


class SlotPlayer:
    """Satu file -> satu output device. play() non-blocking, stop() hentikan."""

    def __init__(self, device: int, samplerate: int = SR, blocksize: int = 2048):
        self.device = device
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.gain = 1.0
        self.loop = False
        self.on_error = None  # fn(str)
        self._data: np.ndarray | None = None
        self._file = ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.playing = False

    @property
    def file(self) -> str:
        return self._file

    @property
    def duration(self) -> float:
        return 0.0 if self._data is None else len(self._data) / self.samplerate

    def load(self, path: str):
        self._data = decode_audio(path, self.samplerate)
        self._file = path

    def _run(self):
        try:
            with sd.OutputStream(device=self.device, channels=2,
                                 samplerate=self.samplerate, blocksize=self.blocksize) as out:
                pos, n = 0, len(self._data)
                while not self._stop.is_set() and pos < n:
                    chunk = self._data[pos:pos + self.blocksize]
                    out.write(apply_gain(chunk, self.gain))
                    pos += len(chunk)
                    if pos >= n and self.loop and not self._stop.is_set():
                        pos = 0
        except Exception as e:  # noqa: BLE001 - kirim ke GUI
            if self.on_error:
                self.on_error(str(e))
        finally:
            self.playing = False

    def play(self):
        if self.playing:
            return
        if sd is None:
            raise RuntimeError("sounddevice belum terpasang. pip install -r pc/requirements.txt")
        if self._data is None:
            raise RuntimeError("Belum ada file. Pilih file dulu.")
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.playing = True

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self.playing = False

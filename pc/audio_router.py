import argparse
import sys
import queue
import threading
import numpy as np

try:
    import sounddevice as sd
except ImportError:
    sd = None


def process_audio(indata: np.ndarray, mode: str, gain1: float = 1.0, gain2: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """
    Split or duplicate stereo audio buffer.
    mode='mirror': out1=stereo, out2=stereo
    mode='split': out1=left channel duplicated, out2=right channel duplicated
    gain1/gain2: volume 0.0-1.5 tiap output.
    """
    if indata.shape[1] < 2:
        mono = indata[:, 0:1]
        indata = np.column_stack((mono, mono))

    if mode == "mirror":
        return (indata * gain1).astype(indata.dtype), (indata * gain2).astype(indata.dtype)
    elif mode == "split":
        # ponytail: downmix stereo ke dua mono output; ganti jika butuh matrix routing multi-kanal
        left = np.column_stack((indata[:, 0], indata[:, 0])) * gain1
        right = np.column_stack((indata[:, 1], indata[:, 1])) * gain2
        return left.astype(indata.dtype), right.astype(indata.dtype)
    else:
        raise ValueError(f"Mode tidak dikenal: {mode}")


def list_devices():
    if sd is None:
        print("sounddevice belum terpasang. Jalankan: pip install -r requirements.txt")
        return
    print(sd.query_devices())


def query_device_lists() -> tuple[list, list]:
    """Kembalikan (inputs, outputs) sebagai list (index, nama). Tanpa sounddevice -> dua list kosong."""
    if sd is None:
        return [], []
    inputs, outputs = [], []
    for i, d in enumerate(sd.query_devices()):
        label = f"{i}: {d['name']}"
        if d["max_input_channels"] > 0:
            inputs.append((i, label))
        if d["max_output_channels"] > 0:
            outputs.append((i, label))
    return inputs, outputs


class DualRouter:
    """Router non-blocking buat GUI. start() kembalikan None, stop() hentikan stream."""

    def __init__(self, dev_in: int, dev_out1: int, dev_out2: int, mode: str = "mirror",
                 samplerate: int = 44100, blocksize: int = 1024):
        self.dev_in = dev_in
        self.dev_out1 = dev_out1
        self.dev_out2 = dev_out2
        self.mode = mode
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.gain1 = 1.0
        self.gain2 = 1.0
        self.on_status = None  # fn(str) opsional buat pesan error dari thread
        self._q: queue.Queue = queue.Queue(maxsize=8)
        self._stop = threading.Event()
        self._thread = None
        self.running = False

    def set_mode(self, mode: str):
        self.mode = mode

    def set_gains(self, gain1: float, gain2: float):
        self.gain1, self.gain2 = gain1, gain2

    def _writer(self, out1, out2):
        while not self._stop.is_set():
            try:
                buf = self._q.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                buf1, buf2 = process_audio(buf, self.mode, self.gain1, self.gain2)
                out1.write(buf1)
                out2.write(buf2)
            except Exception as e:  # noqa: BLE001 - залапkan ke GUI, jangan matikan thread
                if self.on_status:
                    self.on_status(f"Output error: {e}")
                break

    def _callback(self, indata, frames, time_info, status):
        if status and self.on_status:
            self.on_status(str(status))
        try:
            self._q.put_nowait(indata.copy())
        except queue.Full:
            pass

    def start(self):
        if self.running:
            return
        if sd is None:
            raise RuntimeError("sounddevice belum terpasang. Jalankan: pip install -r requirements.txt")
        self._stop.clear()
        self._out1 = sd.OutputStream(device=self.dev_out1, channels=2,
                                     samplerate=self.samplerate, blocksize=self.blocksize)
        self._out2 = sd.OutputStream(device=self.dev_out2, channels=2,
                                     samplerate=self.samplerate, blocksize=self.blocksize)
        self._in = sd.InputStream(device=self.dev_in, channels=2,
                                  samplerate=self.samplerate, blocksize=self.blocksize,
                                  callback=self._callback)
        self._out1.start()
        self._out2.start()
        self._in.start()
        self._thread = threading.Thread(target=self._writer, args=(self._out1, self._out2), daemon=True)
        self._thread.start()
        self.running = True

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        for s in ("_in", "_out1", "_out2"):
            stream = getattr(self, s, None)
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:  # noqa: BLE001 - tutup paksa, abaikan
                    pass
                setattr(self, s, None)
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break
        self.running = False




def run_router(dev_in: int, dev_out1: int, dev_out2: int, mode: str = "mirror", samplerate: int = 44100, blocksize: int = 1024):
    if sd is None:
        print("sounddevice belum terpasang. Jalankan: pip install -r requirements.txt")
        sys.exit(1)

    # ponytail: queue sedalam 8 blok, frame dibuang saat penuh biar tak lag; naikkan bila CPU longgar
    q: queue.Queue = queue.Queue(maxsize=8)
    stop = threading.Event()

    def writer(out1, out2):
        while not stop.is_set():
            try:
                buf = q.get(timeout=0.1)
            except queue.Empty:
                continue
            buf1, buf2 = process_audio(buf, mode)
            out1.write(buf1)
            out2.write(buf2)

    def callback(indata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)
        try:
            q.put_nowait(indata.copy())
        except queue.Full:
            pass

    with sd.OutputStream(device=dev_out1, channels=2, samplerate=samplerate, blocksize=blocksize) as out1, \
         sd.OutputStream(device=dev_out2, channels=2, samplerate=samplerate, blocksize=blocksize) as out2:
        t = threading.Thread(target=writer, args=(out1, out2), daemon=True)
        t.start()
        with sd.InputStream(device=dev_in, channels=2, samplerate=samplerate, blocksize=blocksize, callback=callback):
            print(f"Routing aktif: In={dev_in} -> Out1={dev_out1}, Out2={dev_out2} [Mode={mode}]")
            print("Tekan Enter untuk berhenti...")
            input()
        stop.set()
        t.join(timeout=1.0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PC Dual Audio Router (Internal + Bluetooth)")
    parser.add_argument("--list", action="store_true", help="Tampilkan daftar audio device")
    parser.add_argument("--in-dev", type=int, help="Index input device (Stereo Mix / Loopback)")
    parser.add_argument("--out-internal", type=int, help="Index output speaker internal")
    parser.add_argument("--out-bt", type=int, help="Index output bluetooth")
    parser.add_argument("--mode", choices=["mirror", "split"], default="mirror", help="mirror (sama) atau split (kiri/kanan)")
    args = parser.parse_args()

    if args.list or len(sys.argv) == 1:
        list_devices()
        sys.exit(0)

    if args.in_dev is None or args.out_internal is None or args.out_bt is None:
        print("Error: --in-dev, --out-internal, dan --out-bt wajib diisi.")
        sys.exit(1)

    run_router(args.in_dev, args.out_internal, args.out_bt, args.mode)

import os
import tempfile
import wave

import numpy as np

from dual_player import SlotPlayer, _decode_wav, apply_gain, decode_audio

SR = 44100


def make_wav(path, freq_l=440.0, freq_r=880.0, secs=0.5):
    n = int(SR * secs)
    t = np.arange(n) / SR
    stereo = np.stack((np.sin(2 * np.pi * freq_l * t), np.sin(2 * np.pi * freq_r * t)), axis=1)
    pcm16 = (stereo * 16384).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm16.tobytes())


with tempfile.TemporaryDirectory() as tmp:
    f = os.path.join(tmp, "tes.wav")
    make_wav(f)

    # decode langsung (tanpa ffmpeg)
    d = _decode_wav(f, SR)
    assert d.shape == (int(SR * 0.5), 2), f"shape salah: {d.shape}"
    assert d.dtype == np.float32
    assert abs(d[0, 0]) < 0.01 and d[:, 1].max() > 0.4, "isi kanal L/R salah"

    # decode via jalur utama (ffmpeg bila ada, wave bila tidak)
    d2 = decode_audio(f, SR)
    assert d2.shape == d.shape, "decode utama beda"

    # gain murni numpy
    g = apply_gain(d, 0.5)
    assert np.allclose(g, d * 0.5, atol=1e-6), "gain salah"

    # SlotPlayer: load + durasi (tanpa butuh speaker)
    p = SlotPlayer(device=0)
    p.load(f)
    assert abs(p.duration - 0.5) < 0.01, f"durasi salah: {p.duration}"
    assert p.file == f
    try:
        SlotPlayer(device=0).play()
        raise AssertionError("play tanpa load harus RuntimeError")
    except RuntimeError:
        pass

print("dual player test OK (decode/gain/load/durasi).")

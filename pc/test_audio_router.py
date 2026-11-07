import numpy as np
from audio_router import process_audio

# Test mirror mode
data = np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32)
m1, m2 = process_audio(data, "mirror")
assert np.allclose(m1, data), "Mirror out1 gagal"
assert np.allclose(m2, data), "Mirror out2 gagal"

# Test split mode
s1, s2 = process_audio(data, "split")
# s1 must be left channel duplicated: [0.1, 0.1], [0.3, 0.3]
expected_s1 = np.array([[0.1, 0.1], [0.3, 0.3]], dtype=np.float32)
# s2 must be right channel duplicated: [0.2, 0.2], [0.4, 0.4]
expected_s2 = np.array([[0.2, 0.2], [0.4, 0.4]], dtype=np.float32)

assert np.allclose(s1, expected_s1), f"Split out1 gagal: {s1}"
assert np.allclose(s2, expected_s2), f"Split out2 gagal: {s2}"

# Test mono input -> diduplikasi jadi stereo di kedua output
mono = np.array([[0.5], [0.7]], dtype=np.float32)
m1, m2 = process_audio(mono, "mirror")
expected_mono = np.array([[0.5, 0.5], [0.7, 0.7]], dtype=np.float32)
assert np.allclose(m1, expected_mono), f"Mono mirror gagal: {m1}"
assert np.allclose(m2, expected_mono), f"Mono mirror gagal: {m2}"

# Test mode tak dikenal -> ValueError
try:
    process_audio(mono, "quad")
    raise AssertionError("Mode tak dikenal harus ValueError")
except ValueError:
    pass

print("PC audio router test OK (mirror/split/mono/invalid).")

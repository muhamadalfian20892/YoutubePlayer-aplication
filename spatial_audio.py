"""Lightweight spatial audio DSP and event-driven Windows WinMM waveOut output."""

import array
import ctypes
from ctypes import wintypes
import sys
import threading
import time
import warnings

try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import audioop as _audioop
except ImportError:
    _audioop = None


def _py_tomono(data: bytes, left_factor: float, right_factor: float) -> bytes:
    src = array.array("h")
    src.frombytes(data)
    out = array.array("h")
    for i in range(0, len(src) - 1, 2):
        val = int(src[i] * left_factor + src[i + 1] * right_factor)
        out.append(32767 if val > 32767 else (-32768 if val < -32768 else val))
    return out.tobytes()


def _py_tostereo(data: bytes, left_factor: float, right_factor: float) -> bytes:
    src = array.array("h")
    src.frombytes(data)
    out = array.array("h")
    for sample in src:
        lv = int(sample * left_factor)
        rv = int(sample * right_factor)
        out.append(32767 if lv > 32767 else (-32768 if lv < -32768 else lv))
        out.append(32767 if rv > 32767 else (-32768 if rv < -32768 else rv))
    return out.tobytes()


def _py_mul(data: bytes, factor: float) -> bytes:
    src = array.array("h")
    src.frombytes(data)
    out = array.array("h")
    for sample in src:
        val = int(sample * factor)
        out.append(32767 if val > 32767 else (-32768 if val < -32768 else val))
    return out.tobytes()


def _py_add(data1: bytes, data2: bytes) -> bytes:
    s1 = array.array("h")
    s2 = array.array("h")
    s1.frombytes(data1)
    s2.frombytes(data2)
    out = array.array("h")
    for a, b in zip(s1, s2):
        val = a + b
        out.append(32767 if val > 32767 else (-32768 if val < -32768 else val))
    return out.tobytes()


def _py_rms(data: bytes) -> int:
    src = array.array("h")
    src.frombytes(data)
    if not src:
        return 0
    total = sum(s * s for s in src)
    return int((total / len(src)) ** 0.5)


def _py_max_abs(data: bytes) -> int:
    src = array.array("h")
    src.frombytes(data)
    if not src:
        return 0
    return max(abs(s) for s in src)


def _tomono(data: bytes, lf: float, rf: float) -> bytes:
    return _audioop.tomono(data, 2, lf, rf) if _audioop else _py_tomono(data, lf, rf)


def _tostereo(data: bytes, lf: float, rf: float) -> bytes:
    return _audioop.tostereo(data, 2, lf, rf) if _audioop else _py_tostereo(data, lf, rf)


def _mul(data: bytes, factor: float) -> bytes:
    return _audioop.mul(data, 2, factor) if _audioop else _py_mul(data, factor)


def _add(data1: bytes, data2: bytes) -> bytes:
    return _audioop.add(data1, data2, 2) if _audioop else _py_add(data1, data2)


def _rms(data: bytes) -> int:
    return _audioop.rms(data, 2) if _audioop else _py_rms(data)


def _max_abs(data: bytes) -> int:
    return _audioop.max(data, 2) if _audioop else _py_max_abs(data)


def _apply_ramped_gain(pcm: bytes, g0: float, g1: float) -> bytes:
    """Applies gain cleanly, interpolating across 4 stereo-aligned slices if gain changes."""
    if not pcm:
        return pcm
    if abs(g1 - g0) <= 0.004:
        if g1 <= 0.0005:
            return b"\x00" * len(pcm)
        if abs(g1 - 1.0) <= 0.002:
            return pcm
        return _mul(pcm, g1)

    n = len(pcm)
    step = ((n // 4) // 4) * 4
    if step <= 0:
        return _mul(pcm, g1)

    bounds = (0, step, step * 2, step * 3, n)
    parts = []
    for idx in range(4):
        seg = pcm[bounds[idx] : bounds[idx + 1]]
        g = g0 + (g1 - g0) * ((idx + 1) / 4.0)
        if g <= 0.0005:
            parts.append(b"\x00" * len(seg))
        elif abs(g - 1.0) <= 0.002:
            parts.append(seg)
        else:
            parts.append(_mul(seg, g))
    return b"".join(parts)


class SpatialAudioProcessor:
    """Real-time 48 kHz Mid-Side spatial widener, bass/vocal/night DSP, NVDA ducking, mono, and RMS normalizer."""

    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = max(8000, int(sample_rate))
        # State lock is only held between process_chunk and reset; configure stays lock-free.
        self._state_lock = threading.Lock()

        # Fixed-size history rings (~120 ms per channel) prevent heap growth.
        self._hist_bytes = int(self.sample_rate * 0.12) * 2
        self._ring_l = bytearray(self._hist_bytes)
        self._ring_r = bytearray(self._hist_bytes)
        # Small fixed stereo history (64 bytes = 16 frames) for continuous C-speed bass/vocal filtering.
        self._lp_hist_bytes = 64
        self._lp_ring = bytearray(self._lp_hist_bytes)
        self._prev_mid_frame = b"\x00\x00"

        # Prime-spaced tap delays in bytes (even-aligned for 16-bit mono samples).
        self._d1 = max(2, int(self.sample_rate * 0.011) * 2)
        self._d2 = max(2, int(self.sample_rate * 0.019) * 2)
        self._d3 = max(2, int(self.sample_rate * 0.031) * 2)
        self._d4 = max(2, int(self.sample_rate * 0.047) * 2)

        self.spatial_enabled = False
        self.width = 175
        self.room_size = 35
        self.depth = 45
        self.mono_enabled = False
        self.normalization_enabled = False
        self.volume_percent = 100
        self.bass_boost = 0
        self.vocal_clarity = False
        self.night_mode = False
        self.duck_factor = 1.0
        self._params = (False, 175, 35, 45, False, False, 100, 0, False, False, 1.0)

        self._duck_until = 0.0
        self._duck_level = 1.0

        self._norm_gain = 1.0
        self._last_norm_gain = 1.0
        self._night_gain = 1.0
        self._last_night_gain = 1.0
        self._last_gain = None

    @staticmethod
    def _volume_gain(percent: int) -> float:
        if percent <= 0:
            return 0.0
        if percent >= 100:
            return 1.0
        return (percent / 100.0) ** 1.8

    def configure(
        self,
        spatial_enabled=None,
        width=None,
        room_size=None,
        depth=None,
        mono_enabled=None,
        normalization_enabled=None,
        volume_percent=None,
        bass_boost=None,
        vocal_clarity=None,
        night_mode=None,
        duck_factor=None,
    ):
        """Updates DSP parameters atomically without waiting on active PCM processing."""
        cur = self._params
        s_en = bool(spatial_enabled) if spatial_enabled is not None else cur[0]
        w_val = max(100, min(250, int(width))) if width is not None else cur[1]
        r_val = max(0, min(100, int(room_size))) if room_size is not None else cur[2]
        d_val = max(0, min(100, int(depth))) if depth is not None else cur[3]
        m_en = bool(mono_enabled) if mono_enabled is not None else cur[4]
        n_en = bool(normalization_enabled) if normalization_enabled is not None else cur[5]
        v_val = max(0, min(100, int(volume_percent))) if volume_percent is not None else cur[6]
        bb_val = max(0, min(100, int(bass_boost))) if bass_boost is not None else cur[7]
        vc_en = bool(vocal_clarity) if vocal_clarity is not None else cur[8]
        nm_en = bool(night_mode) if night_mode is not None else cur[9]
        dk_val = max(0.15, min(1.0, float(duck_factor))) if duck_factor is not None else cur[10]

        self.spatial_enabled = s_en
        self.width = w_val
        self.room_size = r_val
        self.depth = d_val
        self.mono_enabled = m_en
        self.normalization_enabled = n_en
        self.volume_percent = v_val
        self.bass_boost = bb_val
        self.vocal_clarity = vc_en
        self.night_mode = nm_en
        self.duck_factor = dk_val
        self._params = (s_en, w_val, r_val, d_val, m_en, n_en, v_val, bb_val, vc_en, nm_en, dk_val)

    def trigger_duck(self, duration_s: float = 1.6, level: float = 0.30):
        """Smoothly ducks music for `duration_s` seconds while NVDA speaks, then restores automatically."""
        lvl = max(0.15, min(1.0, float(level)))
        dur = max(0.1, min(6.0, float(duration_s)))
        self._duck_level = lvl
        self._duck_until = time.monotonic() + dur

    def reset(self):
        """Clears delay history, filter state, and cached volume ramp on seek or stop."""
        with self._state_lock:
            self._ring_l = bytearray(self._hist_bytes)
            self._ring_r = bytearray(self._hist_bytes)
            self._lp_ring = bytearray(self._lp_hist_bytes)
            self._prev_mid_frame = b"\x00\x00"
            self._norm_gain = 1.0
            self._last_norm_gain = 1.0
            self._night_gain = 1.0
            self._last_night_gain = 1.0
            self._last_gain = None
            self._duck_until = 0.0

    def process_chunk(self, pcm_bytes: bytes) -> bytes:
        """Processes 16-bit signed little-endian stereo PCM bytes."""
        if not pcm_bytes:
            return b""
        aligned_len = len(pcm_bytes) - (len(pcm_bytes) % 4)
        if aligned_len <= 0:
            return b""
        pcm = pcm_bytes[:aligned_len] if aligned_len != len(pcm_bytes) else pcm_bytes

        spatial, width, room_size, depth, mono, normalize, vol_pct, bass_boost, vocal_clarity, night_mode, base_duck = self._params
        active_duck = self._duck_level if time.monotonic() < self._duck_until else base_duck

        with self._state_lock:
            target_vol = self._volume_gain(vol_pct) * active_duck
            prev_vol = target_vol if self._last_gain is None else self._last_gain
            self._last_gain = target_vol

            if target_vol <= 0.0005 and prev_vol <= 0.0005:
                return b"\x00" * aligned_len

            if normalize:
                cur_rms = _rms(pcm)
                cur_peak = _max_abs(pcm)
                target_norm = self._norm_gain
                if cur_rms > 60:
                    target_norm = max(0.5, min(1.8, 4500.0 / cur_rms))
                if cur_peak > 0:
                    target_norm = min(target_norm, 28000.0 / cur_peak)
                alpha = 0.12 if target_norm < self._norm_gain else 0.025
                self._norm_gain += (target_norm - self._norm_gain) * alpha
                if cur_peak > 0:
                    self._norm_gain = min(self._norm_gain, 29000.0 / cur_peak)
                prev_norm = self._last_norm_gain
                self._last_norm_gain = self._norm_gain
                pcm = _apply_ramped_gain(pcm, prev_norm, self._norm_gain)
            else:
                self._norm_gain = 1.0
                self._last_norm_gain = 1.0

            # Bass Boost: 3-stage frame-shifted C-speed low-pass average using audioop
            if bass_boost > 0 and not mono:
                bb_amt = (bass_boost / 100.0) * 0.65
                self._lp_ring.extend(pcm)
                keep_lp = self._lp_hist_bytes + aligned_len
                if len(self._lp_ring) > keep_lp:
                    del self._lp_ring[:-keep_lp]
                end_lp = len(self._lp_ring)
                s4 = bytes(self._lp_ring[end_lp - aligned_len - 16 : end_lp - 16])
                s8 = bytes(self._lp_ring[end_lp - aligned_len - 32 : end_lp - 32])
                s16 = bytes(self._lp_ring[end_lp - aligned_len - 64 : end_lp - 64])
                low = _add(_mul(pcm, 0.28), _mul(s4, 0.28))
                low = _add(low, _mul(s8, 0.24))
                low = _add(low, _mul(s16, 0.20))
                headroom_bb = 1.0 / (1.0 + bb_amt * 0.55)
                pcm = _add(_mul(pcm, headroom_bb), _mul(low, bb_amt * headroom_bb))

            if mono:
                mono_ch = _tomono(pcm, 0.5, 0.5)
                out = _tostereo(mono_ch, 1.0, 1.0)
            elif vocal_clarity:
                # Center-vocal clarity: gentle 1-frame high-pass on Mid, boost Mid, tame Side background.
                mid = _tomono(pcm, 0.5, 0.5)
                side = _tomono(pcm, 0.5, -0.5)
                mid_delayed = self._prev_mid_frame + mid[:-2] if len(mid) >= 2 else mid
                if len(mid) >= 2:
                    self._prev_mid_frame = mid[-2:]
                mid_hp = _add(mid, _mul(mid_delayed, -0.32))
                mid_boost = _mul(mid_hp, 1.18)
                side_tame = _mul(side, 0.45)
                l_vc = _add(mid_boost, side_tame)
                r_vc = _add(mid_boost, _mul(side_tame, -1.0))
                out = _add(_tostereo(l_vc, 1.0, 0.0), _tostereo(r_vc, 0.0, 1.0))
            elif spatial:
                clen = aligned_len // 2
                mid = _tomono(pcm, 0.5, 0.5)
                side = _tomono(pcm, 0.5, -0.5)

                w = width / 100.0
                r = room_size / 100.0
                d = depth / 100.0

                headroom = 1.0 / (1.0 + max(0.0, w - 1.0) * 0.42 + r * 0.35 + d * 0.15)
                m_scaled = _mul(mid, headroom)
                s_scaled = _mul(side, w * headroom)

                l_dry = _add(m_scaled, s_scaled)
                r_dry = _add(m_scaled, _mul(s_scaled, -1.0))

                self._ring_l.extend(l_dry)
                self._ring_r.extend(r_dry)
                max_ring = self._hist_bytes + clen
                if len(self._ring_l) > max_ring:
                    del self._ring_l[:-max_ring]
                    del self._ring_r[:-max_ring]

                if (r > 0.01 or d > 0.01) and len(self._ring_l) >= clen + self._d4:
                    end = len(self._ring_l)
                    t1_r = bytes(self._ring_r[end - clen - self._d1 : end - self._d1])
                    t1_l = bytes(self._ring_l[end - clen - self._d1 : end - self._d1])
                    t2_l = bytes(self._ring_l[end - clen - self._d2 : end - self._d2])
                    t2_r = bytes(self._ring_r[end - clen - self._d2 : end - self._d2])
                    t3_r = bytes(self._ring_r[end - clen - self._d3 : end - self._d3])
                    t3_l = bytes(self._ring_l[end - clen - self._d3 : end - self._d3])
                    t4_l = bytes(self._ring_l[end - clen - self._d4 : end - self._d4])
                    t4_r = bytes(self._ring_r[end - clen - self._d4 : end - self._d4])

                    wet_l = _add(_mul(t1_r, 0.32 * d), _mul(t2_l, 0.24 * r))
                    wet_l = _add(wet_l, _mul(t3_r, -0.20 * r))
                    wet_l = _add(wet_l, _mul(t4_l, 0.15 * r))

                    wet_r = _add(_mul(t1_l, -0.32 * d), _mul(t2_r, 0.24 * r))
                    wet_r = _add(wet_r, _mul(t3_l, 0.20 * r))
                    wet_r = _add(wet_r, _mul(t4_r, -0.15 * r))

                    l_out = _add(l_dry, wet_l)
                    r_out = _add(r_dry, wet_r)
                else:
                    l_out = l_dry
                    r_out = r_dry

                out = _add(_tostereo(l_out, 1.0, 0.0), _tostereo(r_out, 0.0, 1.0))
            else:
                out = pcm

            if night_mode:
                n_rms = _rms(out)
                n_peak = _max_abs(out)
                target_night = self._night_gain
                if n_rms > 50:
                    target_night = max(0.35, min(1.6, 3600.0 / n_rms))
                if n_peak > 0:
                    target_night = min(target_night, 15000.0 / n_peak)
                n_alpha = 0.20 if target_night < self._night_gain else 0.04
                self._night_gain += (target_night - self._night_gain) * n_alpha
                if n_peak > 0:
                    self._night_gain = min(self._night_gain, 16000.0 / n_peak)
                prev_ng = self._last_night_gain
                self._last_night_gain = self._night_gain
                out = _apply_ramped_gain(out, prev_ng, self._night_gain)
            else:
                self._night_gain = 1.0
                self._last_night_gain = 1.0

            return _apply_ramped_gain(out, prev_vol, target_vol)


WAVE_MAPPER = 0xFFFFFFFF
WAVE_FORMAT_PCM = 1
WHDR_DONE = 0x00000001
WHDR_PREPARED = 0x00000002
CALLBACK_EVENT = 0x00050000
WAIT_OBJECT_0 = 0
THREAD_PRIORITY_ABOVE_NORMAL = 1


class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [
        ("wFormatTag", wintypes.WORD),
        ("nChannels", wintypes.WORD),
        ("nSamplesPerSec", wintypes.DWORD),
        ("nAvgBytesPerSec", wintypes.DWORD),
        ("nBlockAlign", wintypes.WORD),
        ("wBitsPerSample", wintypes.WORD),
        ("cbSize", wintypes.WORD),
    ]


class WAVEHDR(ctypes.Structure):
    _fields_ = [
        ("lpData", ctypes.c_void_p),
        ("dwBufferLength", wintypes.DWORD),
        ("dwBytesRecorded", wintypes.DWORD),
        ("dwUser", ctypes.c_void_p),
        ("dwFlags", wintypes.DWORD),
        ("dwLoops", wintypes.DWORD),
        ("lpNext", ctypes.c_void_p),
        ("reserved", ctypes.c_void_p),
    ]


class WAVEOUTCAPSW(ctypes.Structure):
    _fields_ = [
        ("wMid", wintypes.WORD),
        ("wPid", wintypes.WORD),
        ("vDriverVersion", wintypes.UINT),
        ("szPname", wintypes.WCHAR * 32),
        ("dwFormats", wintypes.DWORD),
        ("wChannels", wintypes.WORD),
        ("wReserved1", wintypes.WORD),
        ("dwSupport", wintypes.DWORD),
    ]


_winmm = None
_kernel32 = None


def _get_winmm():
    global _winmm
    if _winmm is not None:
        return _winmm
    if sys.platform != "win32":
        return None
    try:
        lib = ctypes.WinDLL("winmm")
        lib.waveOutGetNumDevs.argtypes = []
        lib.waveOutGetNumDevs.restype = wintypes.UINT
        lib.waveOutGetDevCapsW.argtypes = [ctypes.c_size_t, ctypes.POINTER(WAVEOUTCAPSW), wintypes.UINT]
        lib.waveOutGetDevCapsW.restype = wintypes.UINT
        lib.waveOutOpen.argtypes = [
            ctypes.POINTER(ctypes.c_void_p),
            wintypes.UINT,
            ctypes.POINTER(WAVEFORMATEX),
            ctypes.c_size_t,
            ctypes.c_size_t,
            wintypes.DWORD,
        ]
        lib.waveOutOpen.restype = wintypes.UINT
        lib.waveOutPrepareHeader.argtypes = [ctypes.c_void_p, ctypes.POINTER(WAVEHDR), wintypes.UINT]
        lib.waveOutPrepareHeader.restype = wintypes.UINT
        lib.waveOutWrite.argtypes = [ctypes.c_void_p, ctypes.POINTER(WAVEHDR), wintypes.UINT]
        lib.waveOutWrite.restype = wintypes.UINT
        lib.waveOutUnprepareHeader.argtypes = [ctypes.c_void_p, ctypes.POINTER(WAVEHDR), wintypes.UINT]
        lib.waveOutUnprepareHeader.restype = wintypes.UINT
        lib.waveOutPause.argtypes = [ctypes.c_void_p]
        lib.waveOutPause.restype = wintypes.UINT
        lib.waveOutRestart.argtypes = [ctypes.c_void_p]
        lib.waveOutRestart.restype = wintypes.UINT
        lib.waveOutReset.argtypes = [ctypes.c_void_p]
        lib.waveOutReset.restype = wintypes.UINT
        lib.waveOutClose.argtypes = [ctypes.c_void_p]
        lib.waveOutClose.restype = wintypes.UINT
        _winmm = lib
    except Exception:
        _winmm = None
    return _winmm


def _get_kernel32():
    global _kernel32
    if _kernel32 is not None:
        return _kernel32
    if sys.platform != "win32":
        return None
    try:
        k = ctypes.WinDLL("kernel32")
        k.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        k.CreateEventW.restype = ctypes.c_void_p
        k.SetEvent.argtypes = [ctypes.c_void_p]
        k.SetEvent.restype = wintypes.BOOL
        k.WaitForSingleObject.argtypes = [ctypes.c_void_p, wintypes.DWORD]
        k.WaitForSingleObject.restype = wintypes.DWORD
        k.CloseHandle.argtypes = [ctypes.c_void_p]
        k.CloseHandle.restype = wintypes.BOOL
        k.GetCurrentThread.argtypes = []
        k.GetCurrentThread.restype = ctypes.c_void_p
        k.SetThreadPriority.argtypes = [ctypes.c_void_p, ctypes.c_int]
        k.SetThreadPriority.restype = wintypes.BOOL
        _kernel32 = k
    except Exception:
        _kernel32 = None
    return _kernel32


class WinMMOutput:
    """Event-driven ring-buffered Windows waveOut PCM sink with ~100ms hardware latency."""

    NUM_SLOTS = 4
    SLOT_MS = 25
    MAX_FIFO_SECONDS = 2.0

    def __init__(self):
        # Strict lock order: _fifo_cond is NEVER held while acquiring _lock, and vice versa.
        self._lock = threading.Lock()
        self._fifo_cond = threading.Condition()

        self._handle = ctypes.c_void_p()
        self._event = None
        self._is_open = False
        self._device_id = WAVE_MAPPER

        self._slots = []
        self._slot_in_use = []
        self._slot_bytes = 0
        self._prebuffer_bytes = 0
        self._max_fifo_bytes = 0

        self._processor_fn = None
        self._fifo = bytearray()
        self._running = False
        self._paused = False
        self._paused_at = 0.0
        self._priming = True
        self._flush_gen = 0
        self._feeder_thread = None

    @staticmethod
    def list_devices() -> list:
        lib = _get_winmm()
        if not lib:
            return []
        devices = []
        try:
            count = lib.waveOutGetNumDevs()
            caps = WAVEOUTCAPSW()
            for idx in range(count):
                if lib.waveOutGetDevCapsW(idx, ctypes.byref(caps), ctypes.sizeof(caps)) == 0:
                    devices.append((idx, caps.szPname.strip()))
        except Exception:
            pass
        return devices

    @classmethod
    def match_device_id(cls, vlc_device_desc: str) -> int:
        if not vlc_device_desc:
            return WAVE_MAPPER
        target = vlc_device_desc.strip().lower()
        if not target or target == "default":
            return WAVE_MAPPER
        prefix = target[:24]
        for dev_id, pname in cls.list_devices():
            p_low = pname.lower()
            if p_low == target or target.startswith(p_low[:20]) or p_low.startswith(prefix):
                return dev_id
        return WAVE_MAPPER

    def is_open(self) -> bool:
        with self._lock:
            return self._is_open

    def open(
        self,
        device_id: int = WAVE_MAPPER,
        sample_rate: int = 44100,
        channels: int = 2,
        bits: int = 16,
        processor_fn=None,
    ) -> bool:
        if bits not in (8, 16, 24, 32) or channels not in (1, 2) or sample_rate < 8000:
            return False
        lib = _get_winmm()
        k32 = _get_kernel32()
        if not lib or not k32:
            return False

        self.close()

        block_align = (channels * bits) // 8
        slot_bytes = max(block_align, int(sample_rate * (self.SLOT_MS / 1000.0)) * block_align)
        prebuffer_bytes = slot_bytes * 2
        max_fifo_bytes = max(slot_bytes * 8, int(sample_rate * self.MAX_FIFO_SECONDS) * block_align)

        evt = k32.CreateEventW(None, False, False, None)
        if not evt:
            return False

        wfx = WAVEFORMATEX()
        wfx.wFormatTag = WAVE_FORMAT_PCM
        wfx.nChannels = channels
        wfx.nSamplesPerSec = sample_rate
        wfx.wBitsPerSample = bits
        wfx.nBlockAlign = block_align
        wfx.nAvgBytesPerSec = sample_rate * block_align
        wfx.cbSize = 0

        handle = ctypes.c_void_p()
        rc = lib.waveOutOpen(ctypes.byref(handle), wintypes.UINT(device_id), ctypes.byref(wfx), ctypes.c_size_t(evt), 0, CALLBACK_EVENT)
        if rc != 0 and device_id != WAVE_MAPPER:
            rc = lib.waveOutOpen(ctypes.byref(handle), wintypes.UINT(WAVE_MAPPER), ctypes.byref(wfx), ctypes.c_size_t(evt), 0, CALLBACK_EVENT)
            device_id = WAVE_MAPPER
        if rc != 0:
            k32.CloseHandle(evt)
            return False

        slots = []
        prep_ok = True
        for _ in range(self.NUM_SLOTS):
            buf = ctypes.create_string_buffer(slot_bytes)
            hdr = WAVEHDR()
            hdr.lpData = ctypes.addressof(buf)
            hdr.dwBufferLength = slot_bytes
            hdr.dwFlags = 0
            hdr.dwLoops = 0
            if lib.waveOutPrepareHeader(handle, ctypes.byref(hdr), ctypes.sizeof(hdr)) != 0:
                prep_ok = False
                break
            slots.append((hdr, buf))

        if not prep_ok:
            for hdr, _ in slots:
                if hdr.dwFlags & WHDR_PREPARED:
                    lib.waveOutUnprepareHeader(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
            lib.waveOutClose(handle)
            k32.CloseHandle(evt)
            return False

        with self._fifo_cond:
            self._processor_fn = processor_fn
            self._fifo = bytearray()
            self._priming = True
            self._paused = False
            self._paused_at = 0.0
            self._flush_gen = 0
            self._running = True

        with self._lock:
            self._handle = handle
            self._event = evt
            self._device_id = device_id
            self._slots = slots
            self._slot_in_use = [False] * self.NUM_SLOTS
            self._slot_bytes = slot_bytes
            self._prebuffer_bytes = prebuffer_bytes
            self._max_fifo_bytes = max_fifo_bytes
            self._is_open = True

        t = threading.Thread(target=self._feeder_loop, daemon=True, name="WinMMFeeder")
        self._feeder_thread = t
        t.start()
        return True

    def write(self, pcm_bytes: bytes) -> bool:
        if not pcm_bytes:
            return True
        lib = _get_winmm()
        k32 = _get_kernel32()
        need_restart = False
        with self._fifo_cond:
            if self._paused and (time.monotonic() - self._paused_at) > 0.15:
                self._paused = False
                self._paused_at = 0.0
                need_restart = True
            while self._running and len(self._fifo) >= self._max_fifo_bytes:
                self._fifo_cond.wait(timeout=0.05)
            if not self._running:
                return False
            self._fifo.extend(pcm_bytes)
            self._fifo_cond.notify_all()
        if need_restart and lib:
            with self._lock:
                if self._is_open and self._handle.value:
                    lib.waveOutRestart(self._handle)
        evt = self._event
        if k32 and evt:
            k32.SetEvent(evt)
        return True

    def _feeder_loop(self):
        lib = _get_winmm()
        k32 = _get_kernel32()
        if not lib or not k32:
            return
        try:
            k32.SetThreadPriority(k32.GetCurrentThread(), THREAD_PRIORITY_ABOVE_NORMAL)
        except Exception:
            pass

        while True:
            with self._fifo_cond:
                if not self._running:
                    break
                if self._paused:
                    self._fifo_cond.wait(timeout=0.04)
                    continue

            # Step 1: Find a free hardware slot without blocking inside _fifo_cond.
            free_idx = -1
            all_free = True
            evt = None
            with self._lock:
                if not self._is_open or not self._handle.value:
                    break
                evt = self._event
                for i in range(len(self._slots)):
                    if self._slot_in_use[i]:
                        hdr, _ = self._slots[i]
                        if hdr.dwFlags & WHDR_DONE:
                            self._slot_in_use[i] = False
                    if self._slot_in_use[i]:
                        all_free = False
                    elif free_idx == -1:
                        free_idx = i

            if free_idx == -1:
                if evt:
                    k32.WaitForSingleObject(evt, 30)
                else:
                    time.sleep(0.01)
                continue

            # Step 2: Pop one fixed-size slot from FIFO (respecting 50ms startup prebuffer).
            chunk = None
            gen = 0
            with self._fifo_cond:
                if not self._running:
                    break
                if self._paused:
                    continue
                need = self._prebuffer_bytes if self._priming else self._slot_bytes
                if len(self._fifo) < need:
                    self._fifo_cond.wait(timeout=0.015)
                    if not self._running or self._paused:
                        continue
                    need = self._prebuffer_bytes if self._priming else self._slot_bytes
                    if len(self._fifo) < need:
                        if all_free and len(self._fifo) < self._slot_bytes:
                            self._priming = True
                        continue

                chunk = bytes(self._fifo[: self._slot_bytes])
                del self._fifo[: self._slot_bytes]
                self._priming = False
                gen = self._flush_gen
                self._fifo_cond.notify_all()

            # Step 3 & 4: Process DSP and submit buffer to WinMM slot.
            try:
                proc_fn = self._processor_fn
                out_bytes = proc_fn(chunk) if proc_fn else chunk

                with self._lock:
                    if not self._is_open or not self._handle.value or free_idx >= len(self._slots):
                        break
                    # Discard stale chunk if flush() ran while processing.
                    if gen != self._flush_gen:
                        continue
                    hdr, buf = self._slots[free_idx]
                    copy_len = min(len(out_bytes), self._slot_bytes)
                    if copy_len > 0:
                        ctypes.memmove(hdr.lpData, out_bytes, copy_len)
                    hdr.dwBufferLength = copy_len
                    hdr.dwFlags &= ~WHDR_DONE
                    if lib.waveOutWrite(self._handle, ctypes.byref(hdr), ctypes.sizeof(hdr)) == 0:
                        self._slot_in_use[free_idx] = True
            except Exception as e:
                print(f"[SpatialAudio] Feeder warning: {e}")

    def pause(self):
        lib = _get_winmm()
        with self._fifo_cond:
            self._paused = True
            self._paused_at = time.monotonic()
            self._fifo_cond.notify_all()
        with self._lock:
            if lib and self._is_open and self._handle.value:
                lib.waveOutPause(self._handle)

    def resume(self):
        lib = _get_winmm()
        k32 = _get_kernel32()
        with self._fifo_cond:
            self._paused = False
            self._paused_at = 0.0
            self._fifo_cond.notify_all()
        with self._lock:
            if lib and self._is_open and self._handle.value:
                lib.waveOutRestart(self._handle)
            evt = self._event
        if k32 and evt:
            k32.SetEvent(evt)

    def flush(self):
        lib = _get_winmm()
        k32 = _get_kernel32()
        with self._fifo_cond:
            self._flush_gen += 1
            self._fifo.clear()
            self._priming = True
            self._paused = False
            self._paused_at = 0.0
            self._fifo_cond.notify_all()
        with self._lock:
            if lib and self._is_open and self._handle.value:
                lib.waveOutReset(self._handle)
                lib.waveOutRestart(self._handle)
                self._slot_in_use = [False] * len(self._slots)
            evt = self._event
        if k32 and evt:
            k32.SetEvent(evt)

    def close(self):
        lib = _get_winmm()
        k32 = _get_kernel32()
        with self._fifo_cond:
            self._running = False
            self._flush_gen += 1
            self._fifo.clear()
            self._fifo_cond.notify_all()

        evt = self._event
        if k32 and evt:
            k32.SetEvent(evt)

        t = self._feeder_thread
        if t and t.is_alive() and threading.current_thread() is not t:
            t.join(timeout=1.5)
        self._feeder_thread = None

        with self._lock:
            if lib and self._is_open and self._handle.value:
                try:
                    lib.waveOutReset(self._handle)
                    for hdr, _ in self._slots:
                        if hdr.dwFlags & WHDR_PREPARED:
                            lib.waveOutUnprepareHeader(self._handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
                    lib.waveOutClose(self._handle)
                except Exception:
                    pass
            if k32 and self._event:
                try:
                    k32.CloseHandle(self._event)
                except Exception:
                    pass
            self._handle = ctypes.c_void_p()
            self._event = None
            self._slots = []
            self._slot_in_use = []
            self._is_open = False

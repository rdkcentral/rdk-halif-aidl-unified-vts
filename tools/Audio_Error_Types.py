#!/usr/bin/env python3
#** *****************************************************************************
# *
# * If not stated otherwise in this file or this component's LICENSE file the
# * following copyright and licenses apply:
# *
# * Copyright 2025 RDK Management
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# * http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# * See the License for the specific language governing permissions and
# * limitations under the License.
# *
# * ******************************************************************************
# Audio_Error_Types.py
# --------------------------------------------------------------------------------------
# Audio error types and logic (registries + raw extraction + windowed application).
# --------------------------------------------------------------------------------------

from __future__ import annotations

import os
import random
import subprocess
from pathlib import Path

# ---- AUDIO generic error modes ----

def audio_frame_skip_duplication(seg: bytes):
    chunk = 1024; out = bytearray(); i = 0
    while i < len(seg):
        sg = seg[i:i+chunk]; r = random.random()
        if r >= 0.02:
            out.extend(sg)
            if r > 0.98: out.extend(sg)
        i += chunk
    return bytes(out)

def audio_frame_truncation(seg: bytes):
    cut = int(len(seg) * 0.03)
    return seg[:-cut] if cut > 0 else seg

def audio_entropy_bit_flip(seg: bytes):
    b = bytearray(seg)
    for _ in range(min(200, len(b)//50 + 1)):
        i = random.randint(0, len(b)-1)
        b[i] ^= (1 << random.randint(0,7))
    return bytes(b)

def audio_dynamic_range_corruption(seg: bytes):
    return audio_entropy_bit_flip(seg)

def audio_quantization_noise_injection(seg: bytes):
    b = bytearray(seg)
    for _ in range(min(200, len(b)//50 + 1)):
        i = random.randint(0, len(b)-1)
        b[i] = random.randint(0, 255)
    return bytes(b)

def audio_bitrate_field_corruption(seg: bytes):
    b = bytearray(seg)
    for i in range(5, min(len(b), 64), 7): b[i] ^= 0x03
    return bytes(b)

def audio_channel_mode_corruption(seg: bytes):
    b = bytearray(seg)
    for i in range(2, min(len(b), 64), 13): b[i] ^= 0x01
    return bytes(b)

# ---- AAC-specific ----

def aac_adts_header_corruption(seg: bytes):
    b = bytearray(seg); n = len(b); i = 0
    while i + 7 <= n:
        if b[i] == 0xFF and (b[i+1] & 0xF0) == 0xF0:
            protection_absent = (b[i+1] & 0x01)
            header_size = 7 if protection_absent else 9
            if i+2 < n: b[i+2] ^= 0x01
            if i+6 < n: b[i+6] ^= 0x01
            i += header_size
        else:
            i += 1
    return bytes(b)

def aac_pce_channel_map_tamper(seg: bytes):
    b = bytearray(seg); n = len(b); i = 0
    while i + 7 <= n:
        if b[i] == 0xFF and (b[i+1] & 0xF0) == 0xF0:
            protection_absent = (b[i+1] & 0x01)
            header_size = 7 if protection_absent else 9
            payload_start = i + header_size
            end = min(n, payload_start + 8)
            for j in range(payload_start, end): b[j] ^= random.choice([0x01, 0x03, 0x07])
            i += header_size
        else:
            i += 1
    return bytes(b)

# ---- MP3-specific ----

def mp3_frame_header_corruption(seg: bytes):
    b = bytearray(seg); n = len(b); i = 0
    while i + 4 <= n:
        if b[i] == 0xFF and (b[i+1] & 0xE0) == 0xE0:
            for j in range(4):
                if i+j < n: b[i+j] ^= (1 << (j % 8))
            i += 4
        else:
            i += 1
    return bytes(b)

def mp3_side_info_corruption(seg: bytes):
    b = bytearray(seg); n = len(b); i = 0
    while i + 20 <= n:
        if b[i] == 0xFF and (b[i+1] & 0xE0) == 0xE0:
            start = i + 4; end = min(n, start + 16)
            for j in range(start, end): b[j] ^= random.choice([0x01, 0x03, 0x07])
            i += 4
        else:
            i += 1
    return bytes(b)

# ---- AC-3 / E-AC-3 ----

def ac3_syncframe_header_corruption(seg: bytes):
    b = bytearray(seg); n = len(b); i = 0
    while True:
        p = seg.find(b"\x0b\x77", i)
        if p == -1: break
        for j in range(2, min(8, n-p)): b[p+j] ^= 0x01
        i = p + 2
    return bytes(b)

def ac3_coupling_exponent_strategy_flip(seg: bytes):
    b = bytearray(seg); n = len(b); i = 0
    while True:
        p = seg.find(b"\x0b\x77", i)
        if p == -1: break
        for j in range(10, min(14, n-p)): b[p+j] ^= 0x03
        i = p + 2
    return bytes(b)

def eac3_dependent_substream_corruption(seg: bytes):
    b = bytearray(seg); n = len(b); i = 0
    while True:
        p = seg.find(b"\x0b\x77", i)
        if p == -1: break
        for j in range(p + 10, min(p + 20, n)):
            b[j] ^= 0x1F
        i = p + 2
    return bytes(b)

def eac3_syncframe_header_corruption(seg: bytes):
    b = bytearray(seg); n = len(b); i = 0
    while True:
        p = seg.find(b"\x0b\x77", i)
        if p == -1: break
        for j in range(2, min(10, n-p)): b[p+j] ^= 0x01
        i = p + 2
    return bytes(b)

def eac3_coupling_exponent_strategy_flip(seg: bytes):
    b = bytearray(seg); n = len(b); i = 0
    while True:
        p = seg.find(b"\x0b\x77", i)
        if p == -1: break
        for j in range(14, min(18, n-p)): b[p+j] ^= 0x03
        i = p + 2
    return bytes(b)

# ---- FLAC ----

def flac_frame_header_corruption(seg: bytes):
    b = bytearray(seg); n = len(b); i = 0
    while i + 2 < n:
        if b[i] == 0xFF and (b[i+1] & 0xF8) == 0xF8:
            if i+2 < n: b[i+2] ^= 0x1F
            if i+3 < n: b[i+3] ^= 0x07
            i += 2
        else:
            i += 1
    return bytes(b)

def flac_residual_partition_corruption(seg: bytes):
    b = bytearray(seg)
    for i in range(128, len(b), 64): b[i] ^= 0xFF
    return bytes(b)

# ---- PCM (WAVE) ----

def pcm_channel_mask_mismatch(seg: bytes):
    b = bytearray(seg); fmt_idx = seg.find(b'fmt ')
    if fmt_idx != -1:
        if fmt_idx+22 < len(b): b[fmt_idx+22] ^= 0x01
        if fmt_idx+36 < len(b): b[fmt_idx+36] ^= 0x0F
    else:
        for i in range(0, len(b), 100): b[i] ^= 0x01
    return bytes(b)

def pcm_bitplane_fuzz(seg: bytes):
    b = bytearray(seg)
    for i in range(0, len(b), 2): b[i] ^= 0x01
    return bytes(b)

# ---- Vorbis (Ogg) ----

def vorbis_identification_setup_header_corruption(seg: bytes):
    b = bytearray(seg); idx = seg.find(b'vorbis')
    if idx != -1:
        for j in range(max(0, idx-8), min(len(b), idx+8)): b[j] ^= 0x03
    return bytes(b)

def vorbis_codebook_floor_residue_field_corruption(seg: bytes):
    b = bytearray(seg)
    for i in range(64, len(b), 113): b[i] ^= 0x55
    return bytes(b)

def vorbis_mode_window_type_flag_corruption(seg: bytes):
    b = bytearray(seg)
    for i in range(32, len(b), 97): b[i] ^= 0x21
    return bytes(b)

# ---- Opus (Ogg) ----

def opus_toc_mutation(seg: bytes):
    b = bytearray(seg); head = seg.find(b'OpusHead')
    if head != -1:
        if head+9 < len(b): b[head+9] ^= 0x01
        if head+10 < len(b): b[head+10] ^= 0x03
    if len(b) > 0: b[0] ^= 0x07
    return bytes(b)

def opus_frame_packing_corruption(seg: bytes):
    b = bytearray(seg)
    for i in range(0, len(b), 80):
        if i < len(b): b[i] ^= 0x0F
    return bytes(b)

# ---- AUDIO registry ----
_AUDIO_MODE_FN = {
    # Generic
    "frame-skip-duplication": audio_frame_skip_duplication,
    "frame-truncation": audio_frame_truncation,
    "entropy-bit-flip": audio_entropy_bit_flip,
    "dynamic-range-corruption": audio_dynamic_range_corruption,
    "quantization-noise-injection": audio_quantization_noise_injection,
    "bitrate-field-corruption": audio_bitrate_field_corruption,
    "channel-mode-corruption": audio_channel_mode_corruption,
    # AAC
    "aac-adts-header-corruption": aac_adts_header_corruption,
    "aac-PCE-channel-map-tamper": aac_pce_channel_map_tamper,
    # MP3
    "mp3-frame-header-corruption": mp3_frame_header_corruption,
    "mp3-side-info-corruption": mp3_side_info_corruption,
    # AC3/EAC3
    "ac3-syncframe-header-corruption": ac3_syncframe_header_corruption,
    "ac3-coupling-exponent-strategy-flip": ac3_coupling_exponent_strategy_flip,
    "eac3-dependent-substream-corruption": eac3_dependent_substream_corruption,
    "eac3-syncframe-header-corruption": eac3_syncframe_header_corruption,
    "eac3-coupling-exponent-strategy-flip": eac3_coupling_exponent_strategy_flip,
    # FLAC
    "flac-frame-header-corruption": flac_frame_header_corruption,
    "flac-residual-partition-corruption": flac_residual_partition_corruption,
    # PCM
    "pcm-channel-mask-mismatch": pcm_channel_mask_mismatch,
    "pcm-bitplane-fuzz": pcm_bitplane_fuzz,
    # Vorbis
    "vorbis-identification-setup-header-corruption": vorbis_identification_setup_header_corruption,
    "vorbis-codebook-floor-residue-field-corruption": vorbis_codebook_floor_residue_field_corruption,
    "vorbis-mode-window-type-flag-corruption": vorbis_mode_window_type_flag_corruption,
    # Opus
    "opus-toc-mutation": opus_toc_mutation,
    "opus-frame-packing-corruption": opus_frame_packing_corruption,
}

GENERIC_AUDIO_ERROR_MODES = [
    "frame-skip-duplication",
    "frame-truncation",
    "entropy-bit-flip",
    "dynamic-range-corruption",
    "quantization-noise-injection",
    "bitrate-field-corruption",
    "channel-mode-corruption",
]
AAC_AUDIO_SPECIFIC_MODES = [
    "aac-adts-header-corruption",
    "aac-PCE-channel-map-tamper",
]
MP3_AUDIO_SPECIFIC_MODES = [
    "mp3-frame-header-corruption",
    "mp3-side-info-corruption",
]
AC3_AUDIO_SPECIFIC_MODES = [
    "ac3-syncframe-header-corruption",
    "ac3-coupling-exponent-strategy-flip",
]
EAC3_AUDIO_SPECIFIC_MODES = [
    "eac3-dependent-substream-corruption",
    "eac3-syncframe-header-corruption",
    "eac3-coupling-exponent-strategy-flip",
]
FLAC_AUDIO_SPECIFIC_MODES = [
    "flac-frame-header-corruption",
    "flac-residual-partition-corruption",
]
PCM_AUDIO_SPECIFIC_MODES = [
    "pcm-channel-mask-mismatch",
    "pcm-bitplane-fuzz",
]
VORBIS_AUDIO_SPECIFIC_MODES = [
    "vorbis-identification-setup-header-corruption",
    "vorbis-codebook-floor-residue-field-corruption",
    "vorbis-mode-window-type-flag-corruption",
]
OPUS_AUDIO_SPECIFIC_MODES = [
    "opus-toc-mutation",
    "opus-frame-packing-corruption",
]
AUDIO_ERROR_MODES = sorted(list(set(
    GENERIC_AUDIO_ERROR_MODES + AAC_AUDIO_SPECIFIC_MODES + MP3_AUDIO_SPECIFIC_MODES + AC3_AUDIO_SPECIFIC_MODES +
    EAC3_AUDIO_SPECIFIC_MODES + FLAC_AUDIO_SPECIFIC_MODES + PCM_AUDIO_SPECIFIC_MODES + VORBIS_AUDIO_SPECIFIC_MODES + OPUS_AUDIO_SPECIFIC_MODES
)))

_DEF_AUDIO_DEMUX_MAP = {
    'aac': ('aac', '.aac'), 'mp3': ('mp3', '.mp3'), 'ac3': ('ac3', '.ac3'), 'eac3': ('eac3', '.eac3'),
    'flac': ('flac', '.flac'), 'pcm_s16le': ('wav', '.wav'), 'libvorbis': ('ogg', '.ogg'), 'libopus': ('ogg', '.ogg'),
}
_DEF_AUDIO_MUX_MAP = {
    'aac': ('adts', '.aac'), 'mp3': ('mp3', '.mp3'), 'ac3': ('ac3', '.ac3'), 'eac3': ('eac3', '.eac3'),
    'flac': ('flac', '.flac'), 'pcm_s16le': ('wav', '.wav'), 'libvorbis': ('ogg', '.ogg'), 'libopus': ('ogg', '.ogg'),
}

def _codec_to_audio_demux_and_ext(codec: str):
    return _DEF_AUDIO_DEMUX_MAP.get(codec, (None, None))

def _codec_to_audio_mux_and_ext(codec: str):
    return _DEF_AUDIO_MUX_MAP.get(codec, (None, None))

def _extract_raw_audio_by_codec(src_container: str, codec: str, raw_out_path: str):
    mux_fmt, _ext = _codec_to_audio_mux_and_ext(codec)
    if not mux_fmt:
        raise ValueError(f"Raw audio extraction not supported for codec: {codec}")
    cmd = ["ffmpeg", "-y", "-i", src_container, "-vn", "-c:a", "copy", "-f", mux_fmt, raw_out_path]
    subprocess.run(cmd, check=True)

def _apply_audio_mode_in_windows(mode: str, data: bytes, total_sec: int, windows: list) -> bytes:
    ln = len(data)
    def sec_to_byte(sec): return int(ln * (sec / float(max(total_sec,1))))
    windows_bytes = [(max(0,sec_to_byte(s)), min(ln,sec_to_byte(e))) for (s,e) in windows]
    windows_bytes.sort(); out = bytearray(); prev=0
    fn = _AUDIO_MODE_FN.get(mode)
    for (sb,se) in windows_bytes:
        if sb>prev: out.extend(data[prev:sb])
        seg = data[sb:se]
        try: segc = fn(seg) if fn else seg
        except Exception: segc = seg
        out.extend(segc); prev = se
    if prev < ln: out.extend(data[prev:])
    return bytes(out)


apply_audio_mode_in_windows = _apply_audio_mode_in_windows
extract_raw_audio_by_codec = _extract_raw_audio_by_codec
codec_to_audio_demux_and_ext = _codec_to_audio_demux_and_ext
codec_to_audio_mux_and_ext = _codec_to_audio_mux_and_ext

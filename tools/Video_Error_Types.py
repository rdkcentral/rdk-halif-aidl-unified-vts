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
#* ******************************************************************************
# Video_Error_Types.py
# --------------------------------------------------------------------------------------
# Video error types and logic (registries + windowed application).
# --------------------------------------------------------------------------------------

from __future__ import annotations

import os
import re
import math
import random
import struct

# ---- Generic video corruption modes ----

CORRUPTION_RANDOM_SEED = 12345
if CORRUPTION_RANDOM_SEED is not None:
    random.seed(CORRUPTION_RANDOM_SEED)

START_CODE_LONG = b"\x00\x00\x00\x01"; START_CODE_SHORT = b"\x00\x00\x01"

CURRENT_VIDEO_CODEC = None
CURRENT_FPS_HINT = None
CURRENT_ERROR_WINDOWS = None

def _log(msg: str):
    try: print(msg, flush=True)
    except Exception: pass

# ---- Generic video error types implementations ----

def light_fuzz_all(data: bytes):
    for _ in range(100):
        idx = random.randint(0, max(0, len(data)-1)); data = _flip_bytes(data, idx, 1)
    _log("Generic: light_fuzz_all flips=100"); return data

def entropy_bit_flip(data: bytes):
    b = bytearray(data); touched = 0
    step = max(50, len(b)//200)
    for i in range(step, len(b)-step, step):
        if random.random() < 0.25:
            b[i] ^= (1 << random.randint(0,7)); touched += 1
    _log(f"Generic: entropy_bit_flip bytes={touched}"); return bytes(b)

def partial_frame_truncation(data: bytes):
    newlen = int(len(data) * random.uniform(0.85, 0.98)); _log(f"Generic: partial_frame_truncation newlen={newlen}")
    return data[:newlen]

def gop_truncation_duplication(data: bytes):
    cut_point = random.randint(len(data)//5, min(len(data)//2, len(data)-1))
    dup = data[cut_point:cut_point + min(300000, len(data)-cut_point)]
    out = data[:cut_point] + dup + data[max(0, cut_point - min(200000, cut_point)):cut_point]
    _log("Generic: gop_truncation_duplication applied"); return out

def pts_dts_corruption(data: bytes, drop_interval=5):
    """Corrupt PTS/DTS ordering in a codec-aware way.
    - HEVC/H.264: use existing NAL-level strategy.
    - MPEG-PS (mpeg1video/mpeg2video): mutate only the 5-byte PTS/DTS fields,
      preserving marker bits and header sizes (ffplay-friendly; no payload duplication).
    """
    try:
        codec_hint = (CURRENT_VIDEO_CODEC or '').lower()
        if codec_hint in ('libx265', 'hevc', 'h265', 'hevc_nvenc'):
            starts = _find_start_codes(data)
            hevc_nals = _parse_hevc_nals(data) if starts else []
            slice_nals = [(t, s, e) for (t, s, e) in hevc_nals if t not in (HEVC_VPS, HEVC_SPS, HEVC_PPS, 39, 40, 35)]
            out = bytearray(data)
            dup_count = 0
            for i, (t, s, e) in enumerate(slice_nals):
                if i % max(1, int(drop_interval)) == 0 and (e - s) > 16:
                    seg = data[s:e]
                    insert_at = min(len(out) - 1, s + max(2048, (e - s)))
                    out[insert_at:insert_at] = seg
                    dup_count += 1
            _log(f"Generic: pts_dts_corruption (HEVC-safe) duplicates={dup_count}")
            return bytes(out)
        elif codec_hint in ('libx264', 'h264', 'h264_nvenc'):
            nals = _parse_nals_h264(data)
            slice_nals = [(t, s, e) for (t, s, e) in nals if t in (1, 2, 5)]
            out = bytearray(data)
            ins_count = 0
            for i, (t, s, e) in enumerate(slice_nals):
                if i % max(1, int(drop_interval)) == 0 and (e - s) > 24:
                    filler = (START_CODE_LONG if data[s:s+4] == START_CODE_LONG else START_CODE_SHORT) + bytes([12]) + os.urandom(32)
                    insert_at = min(e - 1, s + 64)
                    out[insert_at:insert_at] = filler
                    ins_count += 1
            _log(f"Generic: pts_dts_corruption (H264-safe) fillers={ins_count}")
            return bytes(out)
        elif codec_hint in ('mpeg1video', 'mpeg2video', 'mpegvideo', 'mpeg'):
            b = bytearray(data)
            i = 0
            edits = 0
            while True:
                p = data.find(b'\x00\x00\x01', i)
                if p == -1 or p + 4 >= len(b):
                    break
                stream_id = b[p+3]
                if 0xE0 <= stream_id <= 0xEF:  # video PES
                    if p + 9 < len(b):
                        flags2 = b[p+7]
                        hdr_data_len = b[p+8]
                        cur = p + 9
                        pts_dts_flags = (flags2 >> 6) & 0x03
                        def _mutate_pts_field(idx, is_dts=False):
                            tag = 0x30 if is_dts else 0x20
                            if idx + 4 < len(b):
                                b[idx] = (b[idx] & 0x0F) | tag  # enforce high nibble
                                for k in range(5):
                                    pos = idx + k
                                    val = b[pos] | 0x01  # keep marker bit set
                                    val ^= 0x06          # flip low bits
                                    b[pos] = val
                        if pts_dts_flags == 0x2 and cur + 4 < len(b):
                            _mutate_pts_field(cur, is_dts=False)
                            edits += 5
                        elif pts_dts_flags == 0x3 and cur + 9 < len(b):
                            _mutate_pts_field(cur, is_dts=False)
                            _mutate_pts_field(cur + 5, is_dts=True)
                            edits += 10
                i = p + 4
            _log(f"Generic: pts_dts_corruption (MPEG-PS) bytes={edits}")
            return bytes(b)
        else:
            starts = _find_start_codes(data)
            hevc_nals = _parse_hevc_nals(data) if starts else []
            is_hevc = any(t in (HEVC_VPS, HEVC_SPS, HEVC_PPS) for t,_,_ in hevc_nals)
            if is_hevc and hevc_nals:
                slice_nals = [(t,s,e) for (t,s,e) in hevc_nals if t not in (HEVC_VPS, HEVC_SPS, HEVC_PPS, 39, 40, 35)]
                out = bytearray(data)
                dup_count = 0
                for i, (t, s, e) in enumerate(slice_nals):
                    if i % max(1, int(drop_interval)) == 0 and (e - s) > 16:
                        seg = data[s:e]
                        insert_at = min(len(out) - 1, s + max(2048, (e - s)))
                        out[insert_at:insert_at] = seg
                        dup_count += 1
                _log(f"Generic: pts_dts_corruption (HEVC-safe) duplicates={dup_count}")
                return bytes(out)
            else:
                nals = _parse_nals_h264(data)
                slice_nals = [(t,s,e) for (t,s,e) in nals if t in (1,2,5)]
                out = bytearray(data)
                ins_count = 0
                for i, (t, s, e) in enumerate(slice_nals):
                    if i % max(1, int(drop_interval)) == 0 and (e - s) > 24:
                        filler = (START_CODE_LONG if data[s:s+4] == START_CODE_LONG else START_CODE_SHORT) + bytes([12]) + os.urandom(32)
                        insert_at = min(e - 1, s + 64)
                        out[insert_at:insert_at] = filler
                        ins_count += 1
                _log(f"Generic: pts_dts_corruption (H264-safe) fillers={ins_count}")
                return bytes(out)
    except Exception:
        _log("pts_dts_corruption: heuristic failed, returning original segment (no-op)")
        return data

# ---- H.264 helpers ----

def _find_start_codes(data: bytes):
    starts = set(); i = 0
    while True:
        j = data.find(START_CODE_LONG, i)
        if j == -1: break
        starts.add(j); i = j + 4
    i = 0
    while True:
        j = data.find(START_CODE_SHORT, i)
        if j == -1: break
        if not (j > 0 and data[j-1:j+3] == START_CODE_LONG): starts.add(j)
        i = j + 3
    return sorted(starts)

def _parse_nals_h264(data: bytes):
    starts = _find_start_codes(data);
    nals = []
    for i, s in enumerate(starts):
        header_idx = s + (4 if data[s:s+4] == START_CODE_LONG else 3)
        if header_idx >= len(data): continue
        end = starts[i+1] if i+1 < len(starts) else len(data)
        nal_type = data[header_idx] & 0x1f
        nals.append((nal_type, s, end))
    return nals

def _flip_bytes(data: bytes, offset: int, count: int):
    b = bytearray(data)
    for i in range(count):
        if offset + i < len(b): b[offset + i] ^= random.randint(1, 255)
    return bytes(b)

# ---- H.264-specific modes  ----

def h264_bitflip_slice(data: bytes, flips=40):
    nals = _parse_nals_h264(data)
    slice_nals = [(t, s, e) for (t, s, e) in nals if t in (1, 2)]
    if not slice_nals:
        _log("H264: bitflip_slice no slices"); return data
    slice_nals = slice_nals[:20] if len(slice_nals) > 20 else slice_nals
    total_flips = 0
    for _ in range(3):
        t, s, e = random.choice(slice_nals)
        header = s + (4 if data[s:s+4] == START_CODE_LONG else 3)
        if e - header > 20:
            off = random.randint(header + 10, min(e - 10, header + 200))
            data = _flip_bytes(data, off, flips); total_flips += flips
    _log(f"H264: bitflip_slice flips={total_flips}"); return data

def h264_overwrite_macroblock(data: bytes):
    nals = _parse_nals_h264(data); slice_nals = [n for n in nals if n[0] in (1, 2)]
    for _ in range(20):
        if not slice_nals: break
        _, s, e = random.choice(slice_nals)
        pos = random.randint(s+8, max(s+8, e-8)); length = random.randint(4, 32)
        b = bytearray(data)
        for i in range(length):
            if pos + i < len(b): b[pos+i] = random.randint(0, 255)
        data = bytes(b)
    _log("H264: overwrite_macroblock applied"); return data

def h264_insert_noise_pframe(data: bytes):
    nals = _parse_nals_h264(data); slice_nals = [n for n in nals if n[0] == 1]
    if not slice_nals:
        _log("H264: insert_noise_pframe no P-slices"); return data
    _, s, e = random.choice(slice_nals)
    header = s + (4 if data[s:s+4] == START_CODE_LONG else 3)
    insert_at = min(header+20, e-1)
    data = data[:insert_at] + os.urandom(24) + data[insert_at:]
    _log(f"H264: insert_noise_pframe @{insert_at}"); return data

def h264_temporal_duplication(data: bytes):
    nals = _parse_nals_h264(data); out = bytearray()
    for t, s, e in nals:
        out.extend(data[s:e])
        if t in (1, 2) and random.random() < 0.18:
            dup = bytearray(data[s:e])
            for _ in range(6):
                idx = random.randint(4, max(4, len(dup)-1)); dup[idx] ^= 0xFF
            out.extend(dup)
    _log("H264: temporal_duplication applied"); return bytes(out)

def h264_drop_partial_slices(data: bytes):
    nals = _parse_nals_h264(data); out = bytearray()
    for t, s, e in nals:
        nal = data[s:e]
        header = s + (4 if data[s:s+4] == START_CODE_LONG else 3)
        if t in (1, 2) and random.random() < 0.12:
            cut = random.randint(20, min(200, len(nal)-4)); nal = nal[:-cut]
        out.extend(nal)
    _log("H264: drop_partial_slices applied"); return bytes(out)

def h264_mixed_soft_corruption(data: bytes):
    d = data
    d = h264_bitflip_slice(d, flips=20)
    d = h264_insert_noise_pframe(d)
    d = h264_drop_partial_slices(d)
    for _ in range(8):
        idx = random.randint(0, max(0, len(d)-1)); d = _flip_bytes(d, idx, 1)
    _log("H264: mixed_soft_corruption applied"); return d

def h264_nal_header_corruption(data: bytes):
    nals = _parse_nals_h264(data)
    for t, s, e in nals:
        if t in (1, 2) and random.random() < 0.25:
            header = s + (4 if data[s:s+4] == START_CODE_LONG else 3)
            data = _flip_bytes(data, header, 1)
    _log("H264: nal_header_corruption applied"); return data

def h264_macroblock_skipping(data: bytes):
    nals = _parse_nals_h264(data); slice_nals = [n for n in nals if n[0] in (1, 2)]
    for _ in range(10):
        if not slice_nals: break
        _, s, e = random.choice(slice_nals)
        pos = random.randint(s+8, e-8); length = random.randint(8, 64)
        b = bytearray(data)
        for i in range(length):
            if pos + i < len(b): b[pos+i] = 0
        data = bytes(b)
    _log("H264: macroblock_skipping applied"); return data

def h264_motion_vector_corruption(data: bytes):
    nals = _parse_nals_h264(data)
    for t, s, e in nals:
        if t in (1, 2):
            for _ in range(5):
                off = random.randint(s+10, max(s+10, e-10)); data = _flip_bytes(data, off, 1)
    _log("H264: motion_vector_corruption applied"); return data

def h264_slice_reordering(data: bytes):
    nals = _parse_nals_h264(data)
    spspps = [data[s:e] for t, s, e in nals if t in (7, 8)]
    slices_full = [(t, s, e) for t, s, e in nals if t in (1, 2)]
    if not slices_full:
        _log("H264: slice_reordering no slices"); return data
    head = slices_full[:30]; tail = slices_full[30:]
    slice_payloads = [data[s:e] for _, s, e in head]
    random.shuffle(slice_payloads)
    out = bytearray()
    for pkt in spspps: out.extend(pkt)
    for sl in slice_payloads: out.extend(sl)
    for _, s, e in tail: out.extend(data[s:e])
    for t, s, e in nals:
        if t not in (1, 2, 7, 8): out.extend(data[s:e])
    _log(f"H264: slice_reordering shuffled={len(head)}"); return bytes(out)

def h264_nal_injection(data: bytes):
    nals = _parse_nals_h264(data); out = bytearray()
    for t, s, e in nals:
        out.extend(data[s:e])
        if t in (1, 2) and random.random() < 0.15:
            filler = START_CODE_LONG + bytes([1 & 0x1f]) + os.urandom(12)
            out.extend(filler)
    _log("H264: nal_injection applied"); return bytes(out)

def h264_cross_slice_corruption(data: bytes):
    d = data
    for _ in range(60):
        idx = random.randint(0, max(0, len(d)-5)); d = _flip_bytes(d, idx, random.randint(1, 3))
    _log("H264: cross_slice_corruption flips~60"); return d

def h264_sps_pps_corruption(data: bytes):
    matches = [m.start() for m in re.finditer(b'\x00\x00\x01', data)]
    new_data = bytearray(data)
    for pos in matches:
        if pos + 4 < len(data):
            nal_type = data[pos + 4] & 0x1F
            if nal_type in [7, 8]:
                idx = matches.index(pos)
                end = matches[idx+1] if idx+1 < len(matches) else len(data)
                start = pos + 5; end = min(end, start + 10)
                for i in range(start, end): new_data[i] ^= 0x01
    _log("H264: sps_pps_corruption applied"); return bytes(new_data)

def h264_sei_corruption(data: bytes):
    nals = _parse_nals_h264(data)
    for nal_type, s, e in nals:
        if nal_type == 6:
            header = s + (4 if data[s:s+4] == START_CODE_LONG else 3)
            if e - header > 4: data = _flip_bytes(data, header + 1, min(16, e - header - 1))
    _log("H264: sei_corruption applied"); return data

def h264_fake_reference_frame(data: bytes):
    nals = _parse_nals_h264(data); out = bytearray()
    for t, s, e in nals:
        out.extend(data[s:e])
        if t in (1, 2) and random.random() < 0.15:
            dummy = START_CODE_LONG + bytes([(1 & 0x1f)]) + os.urandom(20)
            out.extend(dummy)
    _log("H264: fake_reference_frame applied"); return bytes(out)

def h264_slice_boundary_offset(data: bytes):
    nals = _parse_nals_h264(data); out = bytearray()
    for t, s, e in nals:
        nal = data[s:e]
        if t in (1, 2) and random.random() < 0.2:
            if random.random() < 0.5:
                nal = nal[:10] + os.urandom(8) + nal[10:]
            else:
                if len(nal) > 20: nal = nal[:-8]
        out.extend(nal)
    _log("H264: slice_boundary_offset applied"); return bytes(out)

# ---- HEVC/H.265 helpers & modes ----

def _parse_hevc_nals(data: bytes):
    starts = _find_start_codes(data); nals = []
    for i, s in enumerate(starts):
        hdr = s + (4 if data[s:s+4] == START_CODE_LONG else 3)
        if hdr >= len(data): continue
        end = starts[i+1] if i+1 < len(starts) else len(data)
        nal_hdr = data[hdr]
        nal_type = (nal_hdr & 0x7E) >> 1
        nals.append((nal_type, s, end))
    return nals

HEVC_VPS=32; HEVC_SPS=33; HEVC_PPS=34

def hevc_nal_header_corruption(data: bytes):
    nals = _parse_hevc_nals(data)
    b = bytearray(data); touched=0
    for nal_type, s, e in nals:
        hdr = s + (4 if data[s:s+4] == START_CODE_LONG else 3)
        if nal_type not in (HEVC_VPS, HEVC_SPS, HEVC_PPS) and e - hdr > 2:
            b[hdr] ^= 0x03; touched += 1
    _log(f"HEVC: nal-header-corruption bytes={touched}"); return bytes(b)

def hevc_vps_corruption(data: bytes):
    nals = _parse_hevc_nals(data); b = bytearray(data); touched=0
    for nal_type, s, e in nals:
        if nal_type == HEVC_VPS:
            start = s + (4 if data[s:s+4] == START_CODE_LONG else 3) + 2
            end = min(e, start + 16)
            for i in range(start, end): b[i] ^= 0x01; touched += 1
    _log(f"HEVC: vps-corruption bytes={touched}"); return bytes(b)

def hevc_tile_entry_point_corruption(data: bytes):
    nals = _parse_hevc_nals(data); out = bytearray()
    for nal_type, s, e in nals:
        seg = data[s:e]
        hdr = (4 if data[s:s+4] == START_CODE_LONG else 3)
        if nal_type not in (HEVC_VPS, HEVC_SPS, HEVC_PPS):
            if len(seg) > hdr + 40:
                pos = s + hdr + random.randint(20, 40)
                segb = bytearray(seg); segb[pos - s] ^= 0xFF
                seg = bytes(segb)
        out.extend(seg)
    _log("HEVC: tile-entry-point-corruption applied"); return bytes(out)

def hevc_scaling_list_corruption(data: bytes):
    nals = _parse_hevc_nals(data); b = bytearray(data); touched=0
    for nal_type, s, e in nals:
        if nal_type in (HEVC_SPS, HEVC_PPS):
            start = s + (4 if data[s:s+4] == START_CODE_LONG else 3) + 12
            end = min(e, start + 24)
            for i in range(start, end, 2): b[i] ^= 0x07; touched += 1
    _log(f"HEVC: scaling-list-corruption bytes={touched}"); return bytes(b)

# ---- MPEG-2 helpers & modes ----

def _find_mpeg2_starts(data: bytes):
    starts = []
    for m in re.finditer(b"\x00\x00\x01", data):
        starts.append(m.start())
    return starts

MPEG2_SEQ=0xB3; MPEG2_GOP=0xB8

def mpeg2_sequence_header_corruption(data: bytes):
    starts = _find_mpeg2_starts(data); b = bytearray(data); touched=0
    for i, s in enumerate(starts):
        if s+3 < len(b) and b[s+3] == MPEG2_SEQ:
            end = starts[i+1] if i+1 < len(starts) else len(b)
            for j in range(s+8, min(s+24, end)):
                b[j] ^= 0x01; touched += 1
    _log(f"MPEG2: sequence-header-corruption bytes={touched}"); return bytes(b)

def mpeg2_gop_header_corruption(data: bytes):
    """Aggressively corrupt MPEG-2 GOP header and the very next picture/slice payloads.
    """
    starts = _find_mpeg2_starts(data)
    b = bytearray(data)
    gop_count = 0
    total_touched = 0
    for i, s in enumerate(starts):
        if s + 3 < len(b) and b[s+3] == MPEG2_GOP:
            gop_count += 1
            end = starts[i+1] if i+1 < len(starts) else len(b)
            hdr_start = s + 4
            # Perturb time_code bytes
            for off in range(hdr_start + 1, min(hdr_start + 5, end)):
                b[off] = (b[off] | 0x80) ^ 0x3F
                total_touched += 1
            # Toggle closed_gop & broken_link
            last_idx = min(end - 1, hdr_start + 5)
            b[last_idx] ^= 0x03
            total_touched += 1
            # Corrupt next 1–2 picture headers (start code 0x00)
            pics_done = 0
            for j in range(i+1, len(starts)):
                ps = starts[j]
                if ps + 3 < len(b) and b[ps+3] == 0x00:
                    pend = starts[j+1] if (j+1) < len(starts) else len(b)
                    ph_start = ps + 4
                    for off in range(ph_start + 2, min(ph_start + 20, pend), 2):
                        b[off] ^= 0xAA
                        total_touched += 1
                    pics_done += 1
                    if pics_done >= 2:
                        break
            # Corrupt payload of first ~30 slice start-codes (0x01..0xAF) after GOP
            slices_done = 0
            for j in range(i+1, len(starts)):
                ss = starts[j]
                if ss + 3 < len(b):
                    sc = b[ss+3]
                    if 0x01 <= sc <= 0xAF:  # slice start codes range
                        send = starts[j+1] if (j+1) < len(starts) else len(b)
                        sl_start = ss + 4
                        # Damage first 96 bytes of slice payload sparsely
                        span_end = min(sl_start + 96, send)
                        for off in range(sl_start + 4, span_end, 7):
                            b[off] ^= 0x15
                            total_touched += 1
                        slices_done += 1
                        if slices_done >= 30:
                            break
            if gop_count >= 3:
                break
    _log(f"MPEG2: gop-header-corruption total_bytes={total_touched} gops={gop_count}")
    return bytes(b)

def mpeg2_quant_matrix_corruption(data: bytes):
    """Forcefully corrupt MPEG-2 quant matrices (intra & non-intra) and early slice payloads.
    """
    starts = _find_mpeg2_starts(data)
    b = bytearray(data)
    seq_done = 0
    touched = 0
    for i, s in enumerate(starts):
        if s + 3 < len(b) and b[s+3] == MPEG2_SEQ:
            seq_done += 1
            end = starts[i+1] if i+1 < len(starts) else len(b)
            region_start = min(s + 24, end)
            region_end = min(end, region_start + 128)
            # Intra matrix: 0xFF/0x00 alternating
            if region_end - region_start >= 64:
                val = 0xFF
                for j in range(region_start, region_start + 64):
                    if j < region_end:
                        b[j] = val
                        val ^= 0xFF
                        touched += 1
            # Non-intra matrix: 0xE0/0x1F alternating
            if region_end - region_start >= 128:
                val2 = 0xE0
                for j in range(region_start + 64, region_start + 128):
                    if j < region_end:
                        b[j] = val2
                        val2 = 0x1F if val2 == 0xE0 else 0xE0
                        touched += 1
            # Light tail perturbation (just in case matrices absent)
            tail_start = min(region_start + 128, end)
            for j in range(tail_start, min(tail_start + 24, end), 3):
                b[j] ^= 0x0F
                touched += 1
            if seq_done >= 2:
                break
    # Amplify blockiness by perturbing early slice payloads across file
    slices_done = 0
    for k, ss in enumerate(starts):
        if ss + 3 < len(b):
            sc = b[ss+3]
            if 0x01 <= sc <= 0xAF:  # slice codes
                send = starts[k+1] if (k+1) < len(starts) else len(b)
                sl_start = ss + 4
                span_end = min(sl_start + 96, send)
                for off in range(sl_start + 6, span_end, 6):
                    b[off] ^= 0x1F
                    touched += 1
                slices_done += 1
                if slices_done >= 50:
                    break
    _log(f"MPEG2: quant-matrix-corruption bytes={touched} seqs={seq_done} slices={slices_done}")
    return bytes(b)

def mpeg2_motion_vector_field_corruption(data: bytes):
    # Safer PES-aware corruption: skip PES headers and only touch payload bytes
    starts = _find_mpeg2_starts(data)
    b = bytearray(data)
    touched = 0
    n = len(b)
    for i, p in enumerate(starts):
        # compute end of current packet/segment using next start code
        end = starts[i+1] if i+1 < len(starts) else n
        if p + 4 >= n:
            continue
        stream_id = b[p+3]
        # video stream ids 0xE0..0xEF
        if 0xE0 <= stream_id <= 0xEF:
            # MPEG-2 PES optional fields layout: after start code & stream_id (4 bytes)
            # there is a 2-byte PES_packet_length, then 2 bytes of flags, then 1 byte header_data_length
            # payload begins at p + 9 + header_data_length
            # Guard all indices
            if p + 9 < n:
                hdr_data_len = b[p+8]
                payload_start = p + 9 + int(hdr_data_len)
            else:
                payload_start = p + 9
            # keep inside bounds and within this packet slice only
            payload_start = max(payload_start, p + 14)  # ensure we skip typical header region
            payload_end = min(end, payload_start + 1024)  # limit how far we corrupt per packet
            # Nudge into slice/picture payload (avoid first few bytes that often contain picture headers)
            payload_start = min(payload_end, payload_start + 24)
            # Flip a sparse pattern to disturb motion vectors while keeping PES readable
            for off in range(payload_start, payload_end, 11):
                if off < n:
                    b[off] ^= 0x03
                    touched += 1
    _log(f"MPEG2: motion-vector-field-corruption (PES-safe) bytes={touched}")
    return bytes(b)

# ---- VP9 helpers ----

# ===================== VP9 IVF-safe corruption  =====================
# The original VP9 corruption functions operated on raw bytes without respecting the IVF
# container structure, which could damage frame-size fields or the DKIF header, leading to
# playback stopping early (e.g., ~2s duration) or hard decode failures like
# "Invalid frame marker". The following helpers parse IVF and corrupt only frame payloads,
# keeping per-frame size fields (and DKIF header) consistent. This yields visible artifacts
# and decoder warnings while remaining playable.

import struct

def _ivf_parse_frames(data: bytes):
    """Return (header32, frames_list) where each frame is [size_le, pts_le, payload_bytes].
    If not IVF, return (None, None) to fall back to original bytes-level behavior.
    """
    if len(data) < 32 or data[:4] != b'DKIF':
        return None, None
    header = data[:32]
    off = 32
    frames = []
    n = len(data)
    while off + 12 <= n:
        sz = struct.unpack_from('<I', data, off)[0]
        pts = struct.unpack_from('<Q', data, off + 4)[0]
        off += 12
        if off + sz > n:
            # Stop cleanly; don't run past end if prior corruption shortened file
            break
        payload = bytearray(data[off:off+sz])
        frames.append([sz, pts, payload])
        off += sz
    return header, frames

def _ivf_rebuild(header: bytes, frames):
    out = bytearray(header)
    for sz, pts, payload in frames:
        out += struct.pack('<I', int(sz))
        out += struct.pack('<Q', int(pts))
        out += bytes(payload)
    return bytes(out)

def _vp9_ivf_edit(data: bytes, per_frame_editor):
    """Generic IVF-safe editor: applies per_frame_editor(idx, payload_bytearray) -> None.
    Ensures DKIF header and per-frame length fields remain valid. If a global
    CURRENT_FPS_HINT is available, also normalizes the IVF timebase to 1/<fps>
    and rewrites frame PTS as 0..N-1 in that timebase. If CURRENT_ERROR_WINDOWS
    is provided, only frames whose timestamp falls inside any window are edited.
    """
    header, frames = _ivf_parse_frames(data)
    if header is None or not frames:
        _log('VP9: IVF parser did not detect DKIF, skipping IVF-safe edit.')
        return data
    # Normalize timebase and PTS using hint (makes window mapping deterministic)
    fps_hint = globals().get('CURRENT_FPS_HINT', None)
    try:
        if fps_hint:
            import struct
            hb = bytearray(header)
            denom = int(round(float(fps_hint))) if float(fps_hint) > 0 else 30
            num = 1
            hb[16:20] = struct.pack('<I', denom)
            hb[20:24] = struct.pack('<I', num)
            hb[24:28] = struct.pack('<I', len(frames))
            header = bytes(hb)
            for i, rec in enumerate(frames):
                rec[1] = i  # pts = frame index in 1/denom units
    except Exception:
        pass
    # Decide which frames are inside windows
    windows = globals().get('CURRENT_ERROR_WINDOWS', None)
    def _in_windows(idx):
        if not windows:
            return True
        try:
            fps = float(globals().get('CURRENT_FPS_HINT') or 0) or 30.0
            t = idx / fps
            for (ws, we) in windows:
                if ws <= t <= we:
                    return True
            return False
        except Exception:
            return True
    edited = 0
    for i, rec in enumerate(frames):
        if not _in_windows(i):
            continue
        sz, pts, payload = rec
        if sz <= 3:
            continue
        try:
            per_frame_editor(i, payload)
            rec[0] = len(payload)
            edited += 1
        except Exception:
            pass
    _log(f"VP9: IVF-safe editor touched_frames={edited} total_frames={len(frames)}")
    return _ivf_rebuild(header, frames)

# ---- VP9 modes  ----

def vp9_superframe_index_corruption(data: bytes):
    """Forge a suspicious-but-playable superframe index at the tail of every 3rd frame.
    We overwrite only the last few bytes of the frame payload with a marker and an
    inconsistent index (frames count / sizes), which provokes decoder warnings while
    leaving the IVF frame size intact. We never touch the first header bytes.
    """
    import os
    def _edit(idx, payload):
        if idx % 3 != 0:
            return
        n = len(payload)
        if n < 24:
            return  # too small
        # Construct a bogus index: marker with top bits 110xxxxx (typical VP9 superframe
        # marker shape), exaggerated frames and size-bytes fields, and tiny size entries.
        fake_marker = 0xCF  # 11001111
        bytes_per_size_minus1 = 0x03  # pretend 4 bytes per size (excessive)
        frames_in_superframe_minus1 = 0x03  # pretend 4 subframes
        sz_bytes = (bytes_per_size_minus1 + 1)
        frames_ct = (frames_in_superframe_minus1 + 1)
        sizes = bytearray()
        # Write improbable small sizes to ensure index/sizes mismatch
        for k in range(frames_ct):
            sizes += int(1 + (k % 2)).to_bytes(sz_bytes, 'little')
        forged = bytes([fake_marker, bytes_per_size_minus1, frames_in_superframe_minus1]) + bytes(sizes)
        # Replace up to 20 bytes at tail, keep total payload length constant
        repl = forged[:min(20, len(forged), max(8, n // 64))]
        payload[-len(repl):] = repl
        return
    return _vp9_ivf_edit(data, _edit)

def vp9_prob_table_desync(data: bytes):
    """Corrupt bytes in the early payload region of every 4th frame, starting after the
    first two bytes (keep frame marker intact)."""
    def _edit(idx, payload):
        if idx % 4 != 0:
            return
        start = 2
        end = min(len(payload), 96)
        for pos in range(start + 6, end, 7):
            payload[pos] ^= 0x33
    return _vp9_ivf_edit(data, _edit)

def vp9_loop_filter_max(data: bytes):
    """Stronger IVF-safe corruption that mimics extreme loop-filter behavior and also
    perturbs early compressed-header areas enough to elicit decoder warnings, while
    keeping the uncompressed header and superframe tail intact. Applied every 5th frame.
    """
    import os
    SYNC = bytes([0x49, 0x83, 0x42])  # VP9 keyframe sync code
    def _edit(idx, payload):
        if idx % 5 != 0:
            return
        n = len(payload)
        if n < 64:
            return
        # Preserve header: skip first bytes (frame marker/profile/reserved-zero) and
        # any sync code. Start corruption after a safe margin.
        safe_start = 32
        sp = payload.find(SYNC, 0, 96)
        if sp != -1:
            safe_start = max(safe_start, sp + 8)
        safe_end = max(safe_start + 32, n - 20)  # keep last ~20 bytes intact (superframe index)
        window_end = min(safe_start + 128, safe_end)
        if window_end <= safe_start:
            return
        # 1) Heavier XOR/OR bursts to bias values aggressively
        for pos in range(safe_start + 4, window_end, 9):
            if pos < n:
                payload[pos] ^= 0x7D
            if pos + 3 < n and pos + 3 < window_end:
                payload[pos + 3] = (payload[pos + 3] | 0x70) & 0x7F
        # 2) Insert a small random blob near the early compressed-header region
        ins_len = 8
        ins_at = min(window_end - 4, safe_start + 16)
        blob = os.urandom(ins_len)
        payload[ins_at:ins_at] = blob
        # 3) Add a secondary light fuzz deeper in the frame body
        tail_start = min(n - 24, max(window_end, safe_start + 96))
        for pos in range(tail_start, min(n - 16, tail_start + 64), 11):
            payload[pos] ^= 0x15
        return
    return _vp9_ivf_edit(data, _edit)

def vp9_resolution_change_stress(data: bytes):
    """Stress decoders by subtly varying per-frame payload sizes: for selected frames,
    insert small random chunks or truncate a few tail bytes, updating the IVF size field.
    This simulates erratic header/payload structure changes and typically produces visible
    artifacts and decoder warnings while staying playable.
    """
    import os, random
    def _edit(idx, payload):
        if idx % 10 == 0 and len(payload) > 40:
            # Insert 8–16 random bytes near the middle
            ins = os.urandom(random.randint(8, 16))
            pos = min(len(payload) - 10, max(10, len(payload)//2))
            payload[pos:pos] = ins
        elif idx % 10 == 5 and len(payload) > 40:
            # Truncate 8–12 bytes from the tail
            cut = random.randint(8, 12)
            del payload[-cut:]
        else:
            # Light header-area fuzz (skip first 2 bytes)
            for j in range(2, min(24, len(payload)), 5):
                payload[j] ^= 0x01
    return _vp9_ivf_edit(data, _edit)


# ===== AV1 IVF-safe corruption helpers & modes =====

def _av1_ivf_edit(data: bytes, per_frame_editor):
    """
    IVF-safe editor for AV1 frames. Applies per_frame_editor(idx, payload_bytearray)
    and keeps DKIF header & per-frame size fields consistent.
    Respects CURRENT_FPS_HINT and CURRENT_ERROR_WINDOWS like VP9 helper does.
    """
    header, frames = _ivf_parse_frames(data)
    if header is None or not frames:
        _log('AV1: IVF parser did not detect DKIF, skipping IVF-safe edit.')
        return data
    # Normalize timebase/pts using hint
    fps_hint = globals().get('CURRENT_FPS_HINT', None)
    try:
        if fps_hint:
            import struct as _s
            hb = bytearray(header)
            denom = int(round(float(fps_hint))) if float(fps_hint) > 0 else 30
            num = 1
            hb[16:20] = _s.pack('<I', denom)
            hb[20:24] = _s.pack('<I', num)
            hb[24:28] = _s.pack('<I', len(frames))
            header = bytes(hb)
            for i, rec in enumerate(frames):
                rec[1] = i  # pts as frame index
    except Exception:
        pass
    windows = globals().get('CURRENT_ERROR_WINDOWS', None)
    def _in_windows(idx):
        if not windows:
            return True
        try:
            fps = float(globals().get('CURRENT_FPS_HINT') or 0) or 30.0
            t = idx / fps
            for (ws, we) in windows:
                if ws <= t <= we:
                    return True
            return False
        except Exception:
            return True
    edited = 0
    for i, rec in enumerate(frames):
        if not _in_windows(i):
            continue
        sz, pts, payload = rec
        if sz <= 8:
            continue
        try:
            per_frame_editor(i, payload)
            rec[0] = len(payload)
            edited += 1
        except Exception:
            pass
    _log(f"AV1: IVF-safe editor touched_frames={edited} total_frames={len(frames)}")
    return _ivf_rebuild(header, frames)

def av1_obu_header_fuzz(data: bytes):
    """
    IVF-safe adaptation: we do NOT flip OBU header reserved bits.
    Instead, lightly fuzz early payload bytes per frame AFTER a safe margin.
    """
    def _edit(idx, payload: bytearray):
        n = len(payload)
        if n < 48:
            return
        safe_start = 16     # skip OBU header region(s) at frame start
        safe_end   = max(safe_start + 24, n - 20)  # keep tail intact
        for pos in range(safe_start, min(safe_start + 96, safe_end), 13):
            payload[pos] ^= 0x07
    return _av1_ivf_edit(data, _edit)

def av1_cdf_update_corruption(data: bytes):
    """
    IVF-safe: touch bytes in the compressed header/body region but never the very first header byte(s).
    """
    def _edit(idx, payload: bytearray):
        n = len(payload)
        if n < 64:
            return
        start = 24   # stay clear of first header bytes within frame
        end   = min(n - 20, start + 128)
        for pos in range(start + 8, end, 17):
            payload[pos] ^= 0x55
    return _av1_ivf_edit(data, _edit)

def av1_film_grain_param_overflow(data: bytes):
    """
    IVF-safe: bias film-grain-like areas by adding a constant to a sparse set of bytes
    while avoiding the header and tail.
    """
    def _edit(idx, payload: bytearray):
        n = len(payload)
        if n < 64:
            return
        start = 32
        end   = min(n - 20, start + 160)
        for pos in range(start, end, 29):
            payload[pos] = (payload[pos] + 200) & 0xFF
    return _av1_ivf_edit(data, _edit)

def av1_tile_group_size_mismatch(data: bytes):
    """
    IVF-safe: perturb tile-group areas without changing payload length.
    We flip sparse bytes within a safe region of each frame to simulate mismatch-like stress
    while keeping OBU sizes intact.
    """
    import random
    def _edit(idx, payload: bytearray):
        n = len(payload)
        if n < 96:
            return
        safe_start = 32
        safe_end = max(safe_start + 64, n - 24)
        if safe_end <= safe_start:
            return
        # Flip a few bytes in two windows to avoid header/tail
        for pos in range(safe_start + 16, min(safe_start + 96, safe_end), 17):
            payload[pos] ^= 0x1F
        for pos in range(max(safe_end - 96, safe_start + 64), safe_end, 19):
            payload[pos] ^= 0x07
    return _av1_ivf_edit(data, _edit)

# ---- Video Mode registry ----
_MODE_FN = {
    # Generic video error types
    "light-fuzz-all": light_fuzz_all,
    "entropy-bit-flip": entropy_bit_flip,
    "partial-frame-truncation": partial_frame_truncation,
    "gop-truncation-duplication": gop_truncation_duplication,
    "pts-dts-corruption": pts_dts_corruption,

    # H.264-specific
    "h264-bitflip-slice": h264_bitflip_slice,
    "h264-overwrite-macroblock": h264_overwrite_macroblock,
    "h264-insert-noise-pframe": h264_insert_noise_pframe,
    "h264-temporal-duplication": h264_temporal_duplication,
    "h264-drop-partial-slices": h264_drop_partial_slices,
    "h264-mixed-soft-corruption": h264_mixed_soft_corruption,
    "h264-nal-header-corruption": h264_nal_header_corruption,
    "h264-macroblock-skipping": h264_macroblock_skipping,
    "h264-motion-vector-corruption": h264_motion_vector_corruption,
    "h264-slice-reordering": h264_slice_reordering,
    "h264-nal-injection": h264_nal_injection,
    "h264-cross-slice-corruption": h264_cross_slice_corruption,
    "h264-sps-pps-corruption": h264_sps_pps_corruption,
    "h264-sei-corruption": h264_sei_corruption,
    "h264-fake-reference-frame": h264_fake_reference_frame,
    "h264-slice-boundary-offset": h264_slice_boundary_offset,

    # HEVC/H.265
    "hevc-nal-header-corruption": hevc_nal_header_corruption,
    "hevc-vps-corruption": hevc_vps_corruption,
    "hevc-tile-entry-point-corruption": hevc_tile_entry_point_corruption,
    "hevc-scaling-list-corruption": hevc_scaling_list_corruption,

    # MPEG-2
    "mpeg2-sequence-header-corruption": mpeg2_sequence_header_corruption,
    "mpeg2-gop-header-corruption": mpeg2_gop_header_corruption,
    "mpeg2-quant-matrix-corruption": mpeg2_quant_matrix_corruption,
    "mpeg2-motion-vector-field-corruption": mpeg2_motion_vector_field_corruption,

    # VP9
    "vp9-superframe-index-corruption": vp9_superframe_index_corruption,
    "vp9-prob-table-desync": vp9_prob_table_desync,
    "vp9-loop-filter-max": vp9_loop_filter_max,
    "vp9-resolution-change-stress": vp9_resolution_change_stress,

    # AV1
    "av1-obu-header-fuzz": av1_obu_header_fuzz,
    "av1-film-grain-param-overflow": av1_film_grain_param_overflow,
    "av1-cdf-update-corruption": av1_cdf_update_corruption,
    "av1-tile-group-size-mismatch": av1_tile_group_size_mismatch,
}

ALL_VIDEO_ERROR_MODES = sorted(_MODE_FN.keys())

GENERIC_VIDEO_MODES = [
    "light-fuzz-all",
    "entropy-bit-flip",
    "partial-frame-truncation",
    "gop-truncation-duplication",
    "pts-dts-corruption",
]

H264_CODEC_SPECIFIC_MODES = [
    "h264-bitflip-slice","h264-overwrite-macroblock","h264-insert-noise-pframe","h264-temporal-duplication",
    "h264-drop-partial-slices","h264-mixed-soft-corruption","h264-nal-header-corruption","h264-macroblock-skipping",
    "h264-motion-vector-corruption","h264-slice-reordering","h264-nal-injection","h264-cross-slice-corruption",
    "h264-sps-pps-corruption","h264-sei-corruption","h264-fake-reference-frame","h264-slice-boundary-offset",
]

HEVC_CODEC_SPECIFIC_MODES = [
    "hevc-nal-header-corruption", "hevc-vps-corruption",
    "hevc-tile-entry-point-corruption", "hevc-scaling-list-corruption"
]
MPEG2_CODEC_SPECIFIC_MODES = [
    "mpeg2-sequence-header-corruption", "mpeg2-gop-header-corruption",
    "mpeg2-quant-matrix-corruption", "mpeg2-motion-vector-field-corruption"
]
VP9_CODEC_SPECIFIC_MODES = [
    "vp9-superframe-index-corruption", "vp9-prob-table-desync",
    "vp9-loop-filter-max", "vp9-resolution-change-stress"
]
AV1_CODEC_SPECIFIC_MODES = [
    "av1-obu-header-fuzz", "av1-film-grain-param-overflow",
    "av1-cdf-update-corruption", "av1-tile-group-size-mismatch"
]

def _apply_video_mode_in_windows(mode: str, data: bytes, total_sec: int, windows: list) -> bytes:
    ln = len(data)
    # Special-case VP9 IVF-safe modes: apply on full clip and let _vp9_ivf_edit
    # pick frames inside CURRENT_ERROR_WINDOWS based on PTS/fps.
    try:
        codec = (globals().get('CURRENT_VIDEO_CODEC', '') or '').lower()
        if (codec == 'libvpx-vp9' and mode.startswith('vp9-')) or (codec == 'libsvtav1' and mode.startswith('av1-')):
            globals()['CURRENT_ERROR_WINDOWS'] = windows
            fn = _MODE_FN.get(mode)
            return fn(data) if fn else data
    except Exception:
        pass
    # Generic byte-window slicer for other codecs
    def sec_to_byte(sec):
        return int(ln * (sec / float(max(total_sec, 1))))
    windows_bytes = [(max(0, sec_to_byte(s)), min(ln, sec_to_byte(e))) for (s, e) in windows]
    windows_bytes.sort()
    out = bytearray()
    prev = 0
    fn = _MODE_FN.get(mode)
    for (sb, se) in windows_bytes:
        if sb > prev:
            out.extend(data[prev:sb])
        seg = data[sb:se]
        try:
            segc = fn(seg) if fn else seg
        except Exception:
            segc = seg
        out.extend(segc)
        prev = se
    if prev < ln:
        out.extend(data[prev:])
    return bytes(out)


apply_video_mode_in_windows = _apply_video_mode_in_windows


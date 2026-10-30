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
# VTS_Main_and_Error_Stream_Generator_Tool
# -------------------------------------------------------------------------------------------------
# -------------------------------------------------------------------------------------------------

import os, sys, re, json, math, random, subprocess
from pathlib import Path
from typing import Optional
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from itertools import product


# ---- Error type modules ----
import Audio_Error_Types as AET
import Video_Error_Types as VET

# ---- RAW output filename helper ----
def _make_raw_error_name(base_path: str, mode: str, stats: dict, output_dir: str = ''):
    '''Build RAW error output filename consistent with other outputs.
    Pattern: <stem_with_mode>_aX_vY_<dur>sec<ext> stored under output_dir.
    Inserts mode just before trailing bitrate token if present.
    '''
    p = Path(base_path)
    stem = p.stem
    ext = p.suffix

    # Insert mode before bitrate token (e.g. _20M or _128k)
    m = re.match(r'^(.*)_(\d+[kM])$', stem)
    if m:
        stem2 = f"{m.group(1)}_{mode}_{m.group(2)}"
    else:
        stem2 = f"{stem}_{mode}"

    a = int(stats.get('audio_frames', 0) or 0)
    v = int(stats.get('video_frames', 0) or 0)
    d = int(stats.get('duration_sec', 0) or 0)
    stem2 = f"{stem2}_a{a}_v{v}_{d}sec"

    out_dir = Path(output_dir) if output_dir else p.parent
    return str(out_dir / (stem2 + ext))

def _allowed_video_error_modes(codecs=None):
    '''Return list of allowed video error modes for the given codec(s).
    Accepts None, a single codec string, or a list/tuple.
    '''
    if codecs is None:
        codec = (getattr(VET, 'CURRENT_VIDEO_CODEC', None) or '')
    elif isinstance(codecs, str):
        codec = codecs
    elif isinstance(codecs, (list, tuple)) and codecs:
        codec = codecs[0]
    else:
        codec = ''
    codec = (codec or '').lower()

    modes = list(getattr(VET, 'GENERIC_VIDEO_MODES', []))
    if codec.startswith('libx264') or codec in ('h264', 'avc'):
        modes += list(getattr(VET, 'H264_CODEC_SPECIFIC_MODES', []))
    elif codec.startswith('libx265') or codec in ('hevc', 'h265'):
        modes += list(getattr(VET, 'HEVC_CODEC_SPECIFIC_MODES', []))
    elif 'mpeg2' in codec or codec in ('mpeg2video', 'mpegvideo'):
        modes += list(getattr(VET, 'MPEG2_CODEC_SPECIFIC_MODES', []))
    elif 'vp9' in codec or codec in ('libvpx-vp9', 'vp9'):
        modes += list(getattr(VET, 'VP9_CODEC_SPECIFIC_MODES', []))
    elif 'av1' in codec or codec in ('libsvtav1', 'libaom-av1', 'av1'):
        modes += list(getattr(VET, 'AV1_CODEC_SPECIFIC_MODES', []))

    allm = getattr(VET, 'ALL_VIDEO_ERROR_MODES', None)
    if isinstance(allm, (list, tuple)) and allm:
        modes = [m for m in modes if m in allm]

    seen = set(); out = []
    for m in modes:
        if m not in seen:
            seen.add(m); out.append(m)
    return out


# ---- FFmpeg command normaliser ----

def _normalise_ffmpeg_cmd(cmd):
    """Ensure all items in ffmpeg cmd are strings (flatten single-item lists)."""
    norm = []
    for x in cmd or []:
        if isinstance(x, (list, tuple)):
            if len(x) == 1:
                norm.append(str(x[0]))
            else:
                # flatten nested lists conservatively
                norm.extend(str(i) for i in x)
        else:
            norm.append(str(x))
    return norm

try:
    from Combopicker import Combopicker as _CombopickerReal
except Exception:
    _CombopickerReal = None

class _CombopickerFallback(ttk.Frame):
    def __init__(self, master, values, height=10, width=22, **kwargs):
        super().__init__(master, **kwargs)
        self._values = list(values)
        self._lb = tk.Listbox(self, selectmode=tk.MULTIPLE, exportselection=False,
                               height=min(max(6, height), max(6, len(values))), width=width,
                               font=("Segoe UI", 13))
        for v in self._values:
            self._lb.insert(tk.END, str(v))
        self._lb.pack(fill='both', expand=True)
    def get_selected_list(self):
        return [self._values[i] for i in self._lb.curselection()]
    def set_values(self, values):
        self._values = list(values)
        self._lb.delete(0, tk.END)
        for v in self._values:
            self._lb.insert(tk.END, str(v))
    def bind(self, sequence=None, func=None, add=None):
        return self._lb.bind(sequence, func, add)

def Combopicker(master, values, height=10, width=22):
    if _CombopickerReal is None:
        return _CombopickerFallback(master, values, height=height, width=width)
    try:
        return _CombopickerReal(master, values=values, entrywidth=width)
    except TypeError:
        return _CombopickerReal(master, values=values)

# ---- Tk Listbox selection isolation helper (prevents cross-deselection) ----
def _ensure_listbox_export_off(widget):
    try:
        import tkinter as _tk
        if isinstance(widget, _tk.Listbox):
            try:
                widget.configure(exportselection=False)
            except Exception:
                pass
    except Exception:
        pass
    # Recurse into children
    try:
        for _child in widget.winfo_children():
            _ensure_listbox_export_off(_child)
    except Exception:
        pass

def _derive_duration_from_frames(frames_count: int, vid_dict=None, aud_dict=None) -> int:
    """Derive an approximate duration (seconds) from a frames count.
    Used only for naming/stats when user selects frame-count mode and leaves Duration empty.
    - If video FPS known: ceil(frames / fps)
    - Else if audio sample-rate known: ceil(frames*1024 / sr)
    - Else: 0
    """
    try:
        fc = int(frames_count)
    except Exception:
        return 0
    if fc <= 0:
        return 0
    try:
        if vid_dict and vid_dict.get('Framerate'):
            fps = float(vid_dict.get('Framerate'))
            if fps > 0:
                return int(math.ceil(fc / fps))
    except Exception:
        pass
    try:
        if aud_dict and aud_dict.get('Sample Rate'):
            sr = float(aud_dict.get('Sample Rate'))
            if sr > 0:
                return int(math.ceil((fc * 1024.0) / sr))
    except Exception:
        pass
    return 0

# ---- UI Parameters Selection ----
video_params = {
    "Resolution": ["3840x2160", "2560x1440", "1920x1080", "1280x720", "960x540", "720x576", "720x480", "640x360", "320x240"],
    "Codec": ["libx264", "libx265", "mpeg1video", "mpeg2video", "mpeg4", "libvpx-vp9", "wmv2", "libsvtav1"],
    "Profile": ["main", "main10", "None"],
    "Framerate": [23.976, 24, 25, 29.97, 30, 50, 59.94, 60],
    "Dynamic Range": ["SDR", "HDR10", "HDR10+", "HLG"],
    "Color Space": ["BT.601","BT.709", "BT.2020"],
    "pixel Format": ["yuv444p", "yuv422p", "yuv420p"],
    "Frame Type": ["Progressive", "Interlaced"],
    "Bitrate": ["300k", "700k", "1M", "1.5M", "2.5M", "5M", "8M", "10M", "12M", "15M", "18M", "20M", "25M", "35M", "60M"],
}

audio_params = {
    "Codec": ["aac", "mp3", "ac3", "eac3", "flac", "pcm_s16le", "wma", "libvorbis", "libopus"],
    "Sample Rate": [8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000, 64000, 88200, 96000],
    "Channels": [1, 2, 3, 6, 8],
    "Bitrate": ["32k", "64k", "128k", "256k", "512k", "1024k"],
}

samplerate_mapping = {8000:"8k",11025:"11.025k",12000:"12k",16000:"16k",22050:"22.05k",24000:"24k",32000:"32k",44100:"44.1k",48000:"48k",64000:"64k",88200:"88.2k",96000:"96k"}

fileformat_mapping = {
    "libx264": "h264", "libx265": "h265", "mpeg1video": "mpg", "mpeg2video": "mpg", "mpeg4": "mpeg4",
    "libsvtav1": "av1", "wmv2": "wmv", "libvpx-vp9":"vp9",
    "aac": "aac", "mp3": "mp3", "ac3": "ac3", "eac3": "eac3", "pcm_s16le": "wav",
    "flac": "flac", "libvorbis": "ogg", "wma": "wma", "libopus" : "opus"
}


# ---- Elementary (raw) stream mapping ----
# Raw file format in UI produces elementary streams (one track only).
# If both video and audio are enabled, raw output is not supported.
RAW_VIDEO_ES_MAP = {
    'libx264': ('h264', '.h264'),
    'libx265': ('hevc', '.h265'),
    'mpeg1video': ('mpeg', '.mpg'),
    'mpeg2video': ('mpeg', '.mpg'),
    'mpeg4': ('m4v','.m4v'),
    'libvpx-vp9': ('ivf', '.ivf'),
    'libsvtav1': ('ivf', '.ivf'),
    # WMV is typically stored in ASF; keep extension as .wmv for user expectation.
    'wmv2': ('asf', '.wmv'),
}

RAW_AUDIO_ES_MAP = {
    'aac': ('adts', '.aac'),
    'mp3': ('mp3', '.mp3'),
    'ac3': ('ac3', '.ac3'),
    'eac3': ('eac3', '.eac3'),
    'flac': ('flac', '.flac'),
    # PCM elementary (no WAV container)
    'pcm_s16le': ('wav', '.wav'),
    # WMA is commonly in ASF container
    'wma': ('asf', '.wma'),
    'libvorbis': ('ogg', '.ogg'),
    # ffmpeg has an 'opus' muxer on most builds; fall back to ogg if unavailable
    'libopus': ('opus', '.opus'),
}

# ---- Codec aliases (UI -> FFmpeg encoder names) ----
AUDIO_CODEC_ALIAS = {
    'wma': 'wmav2',
}

# ---- PCM bitrate helper (for naming) ----

def _pcm_bitrate_token(sample_rate: int, channels: int, bits_per_sample: int = 16) -> str:
    """Return PCM bitrate token like '768k'."""
    try:
        bps = int(sample_rate) * int(channels) * int(bits_per_sample)
        kbps = int(round(bps / 1000.0))
        return f"{kbps}k"
    except Exception:
        return ''

def _get_raw_es_format_and_ext(vid_dict=None, aud_dict=None):
    """Return (mux_format, extension) for elementary stream output."""
    if vid_dict and aud_dict:
        raise ValueError('Raw format supports only Video OR Audio (not both).')
    if vid_dict:
        codec = vid_dict.get('Codec')
        if codec not in RAW_VIDEO_ES_MAP:
            raise ValueError(f"Raw elementary output not supported for video codec: {codec}")
        return RAW_VIDEO_ES_MAP[codec]
    if aud_dict:
        codec = aud_dict.get('Codec')
        if codec not in RAW_AUDIO_ES_MAP:
            raise ValueError(f"Raw elementary output not supported for audio codec: {codec}")
        mux, ext = RAW_AUDIO_ES_MAP[codec]
        # if codec == 'libopus' and mux == 'opus' and not _ffmpeg_has_muxer('opus'):
        #     mux = 'ogg'
        return mux, ext
    raise ValueError('Either vid_dict or aud_dict must be provided for raw output.')

video_test_sources = ["testsrc","testsrc2","smptebars","rgbtestsrc","pal100bars","color_red","color_blue","color_green","color_yellow","color_white","color_black"]

audio_test_sources = ["sine","anoisesrc","sweep"]

# ---- FFmpeg presence ----
def _ffmpeg_exists():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        subprocess.run(["ffprobe", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False

# ---- FFmpeg encoder option probe ----
def _ffmpeg_encoder_has_option(encoder_name: str, option_keyword: str) -> bool:
    """Return True if ffmpeg -h encoder=<name> output mentions the option keyword."""
    try:
        res = subprocess.run(["ffmpeg", "-hide_banner", "-h", f"encoder={encoder_name}"],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        out = res.stdout or ""
        return option_keyword in out
    except Exception:
        return False

# ---- FFmpeg muxer presence probe ----
def _ffmpeg_has_muxer(fmt: str) -> bool:
    """Return True if ffmpeg has the given muxer (container) available."""
    try:
        res = subprocess.run(["ffmpeg", "-hide_banner", "-h", f"muxer={fmt}"],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        out = (res.stdout or '').lower()
        if 'unknown type' in out or 'not found' in out or 'is not known' in out:
            return False
        res2 = subprocess.run(["ffmpeg", "-hide_banner", "-muxers"],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        out2 = (res2.stdout or '').lower()
        return fmt.lower() in out2
    except Exception:
        return False

# ---- Stream probe helpers (detect if a file contains audio/video streams) ----
_STREAM_PROBE_CACHE = {}  # (path, mtime, size) -> {'has_video':bool,'has_audio':bool}

def _probe_stream_types(file_path: str):
    """Return {'has_video': bool, 'has_audio': bool} for the given media file.

    Uses ffprobe. Results are cached based on file mtime/size.
    """
    try:
        p = Path(file_path)
        if (not file_path) or (not p.exists()):
            return {'has_video': False, 'has_audio': False}
        key = (str(p), p.stat().st_mtime, p.stat().st_size)
        if key in _STREAM_PROBE_CACHE:
            return _STREAM_PROBE_CACHE[key]
        res = subprocess.run([
            'ffprobe', '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams',
            str(p)
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        data = json.loads(res.stdout or '{}')
        has_v = False
        has_a = False
        for s in (data.get('streams') or []):
            ct = (s.get('codec_type') or '').lower()
            if ct == 'video':
                has_v = True
            elif ct == 'audio':
                has_a = True
        info = {'has_video': has_v, 'has_audio': has_a}
        _STREAM_PROBE_CACHE[key] = info
        return info
    except Exception:
        return {'has_video': False, 'has_audio': False}

# ---- Duration probe helper ----
def _probe_duration_sec(file_path: str) -> int:
    """Return rounded-up duration in seconds for a given media file using ffprobe. 0 if unknown."""
    try:
        from pathlib import Path as _P
        import subprocess, json, math
        p = _P(file_path)
        if not p.exists():
            return 0
        res = subprocess.run([
            'ffprobe','-v','quiet','-print_format','json','-show_entries','format=duration', str(p)
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        data = json.loads(res.stdout or '{}')
        dur = float(data.get('format',{}).get('duration', 0) or 0)
        return int(math.ceil(dur)) if dur > 0 else 0
    except Exception:
        return 0

# ---- Color params ----
def get_color_params(video_selection):
    """Return color encoding params.

    Always returns: pix_fmt, color_primaries, color_trc, colorspace.
    This avoids KeyError for codecs like mpeg1/mpeg2/wmv2/av1.
    """
    codec = video_selection.get("Codec", "libx264")
    profile = video_selection.get("Profile", "main")
    dynamic_range = video_selection.get("Dynamic Range", "SDR")
    colorspace_ui = video_selection.get("Color Space", "BT.709")

    # Allow HDR only for these codecs libx265, libsvtav1, and VP9
    if dynamic_range in ["HDR10", "HDR10+", "HLG"] and codec not in ["libx265", "libsvtav1", "libvpx-vp9"]:
        return None, f"Invalid combination: HDR requires libx265, libsvtav1, or libvpx-vp9"

    # Profile validation only for x264/x265
    if codec in ["libx264", "libx265"]:
        if profile == "None":
            return None, f"Invalid combination: Profile cannot be None for {codec}"
        if dynamic_range in ["HDR10", "HDR10+", "HLG"] and profile != "main10":
            return None, f"Invalid combination: HDR requires main10 profile"

    hdr_modes = {"HDR10", "HDR10+", "HLG"}
    pix_fmt = "yuv420p10le" if dynamic_range in hdr_modes else video_selection.get("pixel Format", "yuv420p")

    def _cs_tokens(cs_ui: str):
        cs_ui = (cs_ui or '').strip()
        if cs_ui == "BT.709":
            return "bt709", "bt709", "bt709"
        if cs_ui == "BT.2020":
            return "bt2020", "bt709", "bt2020nc"
        if cs_ui == "BT.601":
            return "smpte170m", "bt709", "smpte170m"
        return "bt709", "bt709", "bt709"

    cp, trc, csp = _cs_tokens(colorspace_ui)

    if dynamic_range in ("HDR10", "HDR10+"):
        cp, trc, csp = "bt2020", "smpte2084", "bt2020nc"
    elif dynamic_range == "HLG":
        cp, trc, csp = "bt2020", "arib-std-b67", "bt2020nc"

    color_param = {
        "pix_fmt": pix_fmt,
        "color_primaries": cp,
        "color_trc": trc,
        "colorspace": csp,
    }

    # x265 HDR extras
    if codec == "libx265" and dynamic_range in hdr_modes:
        color_param.update({
            "x265_params": "hdr10=1:hdr10_opt=1:repeat-headers=1:colormatrix=bt2020nc",
            "master_display": "G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,50)",
            "max_cll": "1000,400",
        })

    return color_param, None

# ---- Scale helper (ensure requested output resolution and even dimensions) ----
def _build_scale_filter(target_res: str) -> str:
    """Return scale filter for target resolution and make sure width/height are even.
    This fixes inputs like 853x480 or 640x359 that would otherwise fail with yuv420p encoders.
    """
    try:
        w,h = (target_res or '').lower().split('x')
        w=int(w); h=int(h)
        # enforce even dims for encoders requiring mod2 (common for 4:2:0)
        if w % 2: w -= 1
        if h % 2: h -= 1
        return f"scale={w}:{h}"
    except Exception:
        # fallback: make input dims even without changing size
        return 'scale=trunc(iw/2)*2:trunc(ih/2)*2'

# ---- Command builder ----
def generate_ffmpeg_command(
    vid_dict=None, aud_dict=None, video_input="", audio_input="",
    video_source="testsrc", audio_source="sine",
    duration_sec=10, frames_count=None, volume=1.0, file_format="", output_dir="", error_enabled=False):
    if not _ffmpeg_exists():
        raise RuntimeError("FFmpeg/ffprobe not found in PATH.")
    if not output_dir:
        output_dir = os.path.dirname(os.path.realpath(__file__))
    if not vid_dict and not aud_dict:
        raise ValueError("Both vid_dict and aud_dict cannot be empty")

    file_format_norm = (file_format or '').strip().lower()


    # If frame-count mode is used with lavfi sources, ensure lavfi duration is >0
    src_duration = duration_sec
    if frames_count and (not src_duration or float(src_duration) <= 0):
        try:
            src_duration = _derive_duration_from_frames(frames_count, vid_dict=vid_dict, aud_dict=aud_dict)
        except Exception:
            src_duration = 0
        if not src_duration or int(src_duration) <= 0:
            src_duration = 1

    # WMA cannot be muxed into MP4/TS/WEBM reliably. If user forced those, fall back to ASF (.wma).

    if aud_dict and aud_dict.get('Codec') == 'wma' and file_format_norm in ('mp4','ts','webm'):

        file_format = ''

        file_format_norm = ''
    if file_format_norm == 'raw':
        file_format = 'raw'
        if vid_dict and aud_dict:
            raise ValueError('Raw File Format supports only Video OR Audio. Disable one of them.')
    if (file_format or "").strip().lower() == "webm":
        # Ensure video codec is VP9 or AV1
        if vid_dict and vid_dict.get("Codec") not in ["libvpx-vp9", "libsvtav1"]:
            raise ValueError(f"Invalid video codec '{vid_dict.get('Codec')}' for WebM. Use VP9 or AV1.")
        # Ensure audio codec is Vorbis or Opus (if audio is enabled)
        if aud_dict and aud_dict.get("Codec") not in ["libvorbis", "libopus"]:
            raise ValueError(f"Invalid audio codec '{aud_dict.get('Codec')}' for WebM. Use Vorbis or Opus.")
    if (file_format or "").strip().lower() == "ts":
        # Ensure video codec is H264, H265 or MPEG
        if vid_dict and vid_dict.get("Codec") not in ["libx264", "libx265", "mpeg1video", "mpeg2video"]:
            raise ValueError(f"Invalid video codec '{vid_dict.get('Codec')}' for Ts Format. Use H264, H265 or MPEG.")
        # Ensure audio codec is AAC, MP3, AC3, EAC3 (if audio is enabled)
        if aud_dict and aud_dict.get("Codec") not in ["aac", "mp3", "ac3", "eac3"]:
            raise ValueError(f"Invalid audio codec '{aud_dict.get('Codec')}' for Ts format. Use AAC, MP3, AC3, EAC3.")

    cmd = ["ffmpeg", "-y"]

    # Respect Enable Video/Audio when input file contains multiple streams

    stream_disable_cmd = []

    if vid_dict and not aud_dict:

        stream_disable_cmd = ['-an','-sn','-dn']

    elif aud_dict and not vid_dict:

        stream_disable_cmd = ['-vn','-sn','-dn']

    output_file_parts = ["vts"]
    video_src_cmd, video_opt_cmd = [], []
    audio_src_cmd, audio_opt_cmd = [], []
    if vid_dict:
        color_param, err = get_color_params(vid_dict)
        if err: raise ValueError(err)
        framerate = float(vid_dict["Framerate"])
        if video_input:
            # Loop the input to reach requested duration if needed
            try:
                _v_dur = _probe_duration_sec(video_input)
            except Exception:
                _v_dur = 0
            # Use infinite stream_loop; -t at output will trim to requested duration
            video_src_cmd = ["-stream_loop","-1","-i", video_input] if duration_sec and (duration_sec > (_v_dur or 0)) else ["-i", video_input]
        else:
            coloropt = ""; vsrc = video_source
            if ("color" in video_source):
                coloropt = ":c=" + video_source.split("_")[1]; vsrc = "color"
            video_src_cmd = ["-f", "lavfi", "-i", f"{vsrc}=rate={framerate}:size={vid_dict['Resolution']}:duration={src_duration}{coloropt}"]
        video_opt_cmd = [
            "-c:v", vid_dict["Codec"],
            "-b:v", vid_dict["Bitrate"],
            "-r", str(framerate),
            "-pix_fmt", color_param["pix_fmt"],
            "-color_primaries", color_param["color_primaries"],
            "-color_trc", color_param["color_trc"],
            "-colorspace", color_param["colorspace"]
        ]
        # ---- Fast encode params for VP9/AV1 (adds to existing options) ----
        _codec = (vid_dict.get('Codec') or '').strip()
        if _codec == 'libvpx-vp9':
         video_opt_cmd += [
          '-deadline', 'realtime',
          '-cpu-used', '8',
          '-row-mt', '1',
          '-tile-rows','1',
          '-tile-columns', '2',
          '-threads', '8'
         ]
         
        elif _codec == 'libsvtav1':
         # libsvtav1 speed knobs
         video_opt_cmd += [
          '-preset', '8',
          '-svtav1-params', 'lp=0'
         ]

         # Always scale to the requested output resolution (and make it encoder-safe)
        vf_chain = [_build_scale_filter(vid_dict.get('Resolution',''))]

        if vid_dict["Frame Type"] == "Interlaced":
            if vid_dict["Codec"] in ("libx264", "libx265"):
                vf_chain.append("tinterlace=interleave_top")
                video_opt_cmd += ["-flags", "+ildct+ilme"]
            if vid_dict["Codec"] == "libx264":
                video_opt_cmd += ["-x264-params", "tff=1"]
            elif vid_dict["Codec"] == "mpeg2video":
                vf_chain.append("tinterlace=interleave_top")
                video_opt_cmd += ["-flags", "+ildct+ilme", "-top", "1"]
        if vf_chain:
                    video_opt_cmd += ["-vf", ",".join(vf_chain)]

        if color_param.get("x265_params"):
            video_opt_cmd += ["-x265-params", color_param["x265_params"]]
            use_separate_hdr_flags = _ffmpeg_encoder_has_option("libx265", "master-display") and _ffmpeg_encoder_has_option("libx265", "max-cll")
            if use_separate_hdr_flags:
                video_opt_cmd += ["-master-display", color_param["master_display"], "-max-cll", color_param["max_cll"]]
        gop_size_frames = int(math.ceil(vid_dict.get("gop_size", 1) * framerate))
        key_frames = int(math.ceil(vid_dict.get("key_sec", 1) * framerate))
        video_opt_cmd += ["-g", str(gop_size_frames), "-keyint_min", str(key_frames), "-sc_threshold", "0"]
        res_label = vid_dict["Resolution"].split("x")[1]
        res_label += "p" if vid_dict["Frame Type"] == "Progressive" else "i"
        # Use applied values for colorspace & pix_fmt
        applied_pix_fmt = color_param.get("pix_fmt", vid_dict.get("pixel Format", ""))
        applied_colorspace = color_param.get("colorspace")
        if not applied_colorspace:
            ui_cs = vid_dict.get("Color Space", "")
            if ui_cs == "BT.709":
                applied_colorspace = "bt709"
            elif ui_cs == "BT.2020":
                applied_colorspace = "bt2020nc"
            elif ui_cs == "BT.601":
                applied_colorspace = "smpte170m"
        # Applied colorspace/pixel format tokens (applied values only)
        # NOTE: For HDR modes we always encode as yuv420p10le, but the output filename should use simplified pixel format token 'yuv420p' regardless of UI selection (yuv420p/yuv422p/yuv444p).
        dr_norm = (vid_dict.get('Dynamic Range','') or '').strip().lower()
        hdr_modes = {'hdr10','hdr10+','hlg'}
        filename_pix_fmt = 'yuv420p' if dr_norm in hdr_modes else (applied_pix_fmt or '')
        cs_norm = (applied_colorspace or '').lower()
        if cs_norm == 'bt709':
            cs_token = 'BT709'
        elif cs_norm == 'bt2020':
            cs_token = 'BT2020'
        elif cs_norm in ('bt2020_nc', 'bt2020nc'): 
            cs_token = 'BT2020'
        elif cs_norm == 'smpte170m': 
            cs_token = 'BT601'
        else:
            cs_token = (applied_colorspace or '').replace('.', '').replace('_','')
        pf_token = (filename_pix_fmt or '').replace(':', '')

        output_file_parts += [
            vid_dict['Codec'].replace("libx", "h").replace("mpeg1video", "mpeg1").replace("mpeg2video", "mpeg2").replace("libvpx-vp9", "vp9").replace("libsvtav1", "av1").replace("wmv2", "wmv"),
            res_label,
            vid_dict['Dynamic Range'].lower(),
            f"{framerate}f",
            cs_token,   # applied colorspace
            pf_token,   # applied pixel format
            vid_dict['Bitrate']
        ]

    if aud_dict:
        if audio_input:
            # Loop the input to reach requested duration if needed
            try:
                _a_dur = _probe_duration_sec(audio_input)
            except Exception:
                _a_dur = 0
            audio_src_cmd = ["-stream_loop","-1","-i", audio_input] if duration_sec and (duration_sec > (_a_dur or 0)) else ["-i", audio_input]
        else:
            if audio_source == "sine":
                audio_src_cmd = ["-f", "lavfi", "-i", f"{audio_source}=frequency=1000:sample_rate={aud_dict['Sample Rate']}:duration={src_duration}"]
            elif audio_source == "anoisesrc":
                audio_src_cmd = ["-f", "lavfi", "-i", f"{audio_source}=sample_rate={aud_dict['Sample Rate']}:duration={src_duration}:c=pink"]
            elif audio_source == "sweep":
                audio_src_cmd = ["-f", "lavfi", "-i", f"aevalsrc=sin(2*PI*(20+(20000-20)*t/{duration_sec})*t):s={aud_dict['Sample Rate']}"]
        enc_a = AUDIO_CODEC_ALIAS.get(aud_dict['Codec'], aud_dict['Codec'])
        audio_opt_cmd = ["-c:a", enc_a, "-ar", str(aud_dict["Sample Rate"]), "-ac", str(aud_dict["Channels"]) ]
        if aud_dict["Codec"] not in ("flac", "pcm_s16le") and aud_dict.get("Bitrate"):
            audio_opt_cmd += ["-b:a", aud_dict["Bitrate"]]
        audio_opt_cmd += ["-filter:a", f"volume={volume}"]
        output_file_parts += [
            aud_dict['Codec'].replace("pcm_s16le", "pcm").replace("libvorbis", "vorbis").replace("libopus", "opus"),
            samplerate_mapping[int(aud_dict['Sample Rate'])], f"{aud_dict['Channels']}ch",
        ]
        # Always reflect bitrate token in filename when selected.
        if aud_dict.get("Bitrate"):
            if aud_dict.get("Codec") == 'pcm_s16le':
                br_tok = _pcm_bitrate_token(int(aud_dict.get('Sample Rate', 48000)), int(aud_dict.get('Channels', 2)), 16)
                if br_tok: output_file_parts.append(br_tok)
            else:
                output_file_parts.append(aud_dict["Bitrate"])
    if file_format_norm != 'raw' and not file_format:
            if vid_dict and aud_dict:
                if vid_dict["Codec"] in ["libvpx-vp9", "libsvtav1"] and aud_dict["Codec"] in ["libvorbis", "libopus"]:
                    file_format = "webm"
                elif vid_dict["Codec"] in ["mpeg1video", "mpeg2video", "wmv2"]:
                    file_format = "mp4"
                else:
                    file_format = "mp4"
            elif vid_dict:
                if vid_dict["Codec"] in ["libvpx-vp9", "libsvtav1"]:
                    file_format = "webm"
                elif vid_dict["Codec"] in ["mpeg1video", "mpeg2video", "wmv2"]:
                    file_format = "mp4"
                else:
                    file_format = "mp4"
            elif aud_dict:
                if aud_dict["Codec"] in ["libvorbis", "libopus"]:
                    file_format = "webm"
                elif aud_dict["Codec"] in ["wma"]:
                    file_format = "wma"
                else:
                    file_format = "mp4"
    # ---- Output path / container or elementary stream tail ----
    if file_format_norm == 'raw':
        raw_mux, raw_ext = _get_raw_es_format_and_ext(vid_dict, aud_dict)
        output_file = "_".join(output_file_parts) + raw_ext
        output_path = os.path.join(output_dir, output_file)
        # RAW + Error single-track only
        if error_enabled and vid_dict and aud_dict:
            raise ValueError('RAW error supports only Video OR Audio (not both)')
        # Apply RAW error corruption
        # NOTE: RAW error corruption is byte-level (VET/AET) and is handled outside ffmpeg.
        # Keep ffmpeg command clean here.
        # RAW duration / frames
        if frames_count:
            frame_tail = []
            if vid_dict: frame_tail += ['-frames:v', str(frames_count)]
            if aud_dict: frame_tail += ['-frames:a', str(frames_count)]
            tail = stream_disable_cmd + frame_tail + ['-f', raw_mux, output_path]
        else:
            tail = stream_disable_cmd + ['-t', str(duration_sec), '-f', raw_mux, output_path]
        cmd += video_src_cmd + audio_src_cmd + video_opt_cmd + audio_opt_cmd + tail
        return cmd, output_path

    # -------- NON-RAW path --------
    output_file = "_".join(output_file_parts) + "." + file_format
    output_path = os.path.join(output_dir, output_file)
    if frames_count:
        frame_tail = []
        if vid_dict: frame_tail += ['-frames:v', str(frames_count)]
        if aud_dict: frame_tail += ['-frames:a', str(frames_count)]
        cmd += video_src_cmd + audio_src_cmd + video_opt_cmd + audio_opt_cmd + stream_disable_cmd + frame_tail + [output_path]
    else:
        cmd += video_src_cmd + audio_src_cmd + video_opt_cmd + audio_opt_cmd + stream_disable_cmd + ['-t', str(duration_sec), output_path]
    return cmd, output_path


# ---- Fallback stats helper (for cases where ffprobe cannot count packets) ----
def _fallback_stats_from_params(duration_sec: int, vid_dict=None, aud_dict=None):
    try:
        v_frames = 0
        a_frames = 0
        if vid_dict and vid_dict.get('Framerate'):
            fps = float(vid_dict.get('Framerate'))
            v_frames = int(round(fps * float(duration_sec)))
        if aud_dict and aud_dict.get('Sample Rate'):
            sr = int(aud_dict.get('Sample Rate'))
            a_frames = int(round((sr * float(duration_sec)) / 1024.0))
        return {'duration_sec': int(duration_sec or 0), 'audio_frames': a_frames, 'video_frames': v_frames}
    except Exception:
        return {'duration_sec': int(duration_sec or 0), 'audio_frames': 0, 'video_frames': 0}

# ---- Probe & rename helpers ----
def get_stream_info(file_path):
    """Return {'duration_sec', 'audio_frames', 'video_frames'}.

    For elementary/raw bitstreams (e.g. .h264/.h265/.aac) ffprobe may require an explicit demuxer.
    This function retries with demuxer hints based on file extension.
    """
    p = Path(file_path)
    ext = p.suffix.lower()

    demux_hint = {
        '.h264': 'h264',
        '.264': 'h264',
        '.h265': 'hevc',
        '.hevc': 'hevc',
        '.ivf': 'ivf',
        '.aac': 'adts',
        '.ac3': 'ac3',
        '.eac3': 'eac3',
        '.mp3': 'mp3',
        '.ogg': 'ogg',
        '.opus': 'opus',
        '.mpg': 'mpeg',
        '.mpeg': 'mpeg',
        '.wmv': 'asf',
        '.wma': 'asf',
    }.get(ext)

    base_in = []
    if demux_hint:
        base_in = ['-f', demux_hint]

    try:
        # Duration
        duration_sec = 0
        try:
            result_d = subprocess.run([
                'ffprobe', '-v', 'quiet',
                '-print_format', 'json',
                '-show_entries', 'format=duration',
                *base_in,
                str(p)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
            data_d = json.loads(result_d.stdout or '{}')
            duration = float(data_d.get('format', {}).get('duration', 0.0) or 0.0)
            duration_sec = math.ceil(duration) if duration > 0 else 0
        except Exception:
            duration_sec = 0

        # Video packets
        video_packets = 0
        try:
            result_v = subprocess.run([
                'ffprobe', '-v', 'quiet', '-count_packets',
                '-select_streams', 'v:0',
                '-print_format', 'json',
                '-show_entries', 'stream=codec_type,nb_read_packets',
                *base_in,
                str(p)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
            data_v = json.loads(result_v.stdout or '{}')
            for s in data_v.get('streams', []):
                if s.get('codec_type') == 'video':
                    video_packets = int(s.get('nb_read_packets', 0) or 0)
        except Exception:
            video_packets = 0

        # Audio packets
        audio_packets = 0
        try:
            result_a = subprocess.run([
                'ffprobe', '-v', 'quiet', '-count_packets',
                '-select_streams', 'a:0',
                '-print_format', 'json',
                '-show_entries', 'stream=codec_type,nb_read_packets',
                *base_in,
                str(p)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
            data_a = json.loads(result_a.stdout or '{}')
            for s in data_a.get('streams', []):
                if s.get('codec_type') == 'audio':
                    audio_packets = int(s.get('nb_read_packets', 0) or 0)
        except Exception:
            audio_packets = 0

        return {'duration_sec': duration_sec, 'audio_frames': audio_packets, 'video_frames': video_packets}

    except Exception:
        return None

def rename_file_with_stats(filename: str, stats: dict) -> str:
    if not filename:
        return ""
    outputfile = Path(filename)
    if not outputfile.exists() or not stats:
        return str(outputfile)
    base = outputfile.stem; ext = outputfile.suffix
    new_filename = f"{base}_a{stats['audio_frames']}_v{stats['video_frames']}_{int(stats.get('duration_sec') or 0)}sec{ext}"
    new_path = outputfile.with_name(new_filename)
    if new_path.exists():
        try: os.remove(new_path)
        except Exception: pass
    try:
        os.rename(outputfile, new_path)
    except Exception:
        return str(outputfile)
    return str(new_path)

# ---- Error label helpers ----
def _rename_error_output(original_path: str, base_stem: str, suffix: str, stats: dict) -> str:
    """Rename final error outputs to match naming patterns for video-only, audio-only,
    and combined A/V streams. Always include the 'vts' prefix as requested.

    Examples (single-stream still prefixed with vts):
      - Video-only:
        vts_h265_2160p_hdr10_60.0f_BT2020_yuv422p_vps-corruption_18M_a0_v3600_60sec.mp4
      - Audio-only:
        vts_aac_48k_2ch_frame-skip-duplication_256k_a2814_v0_60sec.mp4
    """
    import os, re
    from pathlib import Path
    p = Path(original_path)
    if not p.exists():
        return original_path

    tokens = base_stem.split('_') if base_stem else []

    VIDEO_CODECS = {'h264','h265','mpeg1','mpeg2', 'mpeg4','vp9','wmv','av1'}
    AUDIO_CODECS = {'aac','mp3','ac3','eac3','flac','pcm','vorbis','opus','wma'}
    def is_bitrate(t):
        return bool(re.fullmatch(r"\d+(?:k|M)", t))
    def is_res(t):
        return bool(re.fullmatch(r"\d{3,4}[pi]", t))
    def is_fps(t):
        return bool(re.fullmatch(r"\d+(?:\.\d+)?f", t))
    def is_colorspace(t):
        return (t or '').lower().startswith('bt')
    def is_pixfmt(t):
        return t.startswith('yuv')
    def is_dr(t):
        return t in {'sdr','hdr10','hdr10+','hlg'}

    # Parse base stem
    idx = 0
    if tokens and tokens[0] == 'vts':
        idx = 1

    v_block = {}
    if idx < len(tokens) and tokens[idx] in VIDEO_CODECS:
        i = idx
        v_block['codec'] = tokens[i]; i += 1
        if i < len(tokens) and is_res(tokens[i]): v_block['res'] = tokens[i]; i += 1
        if i < len(tokens) and is_dr(tokens[i]): v_block['dr'] = tokens[i]; i += 1
        if i < len(tokens) and is_fps(tokens[i]): v_block['fps'] = tokens[i]; i += 1
        if i < len(tokens) and is_colorspace(tokens[i]): v_block['cs'] = tokens[i]; i += 1
        if i < len(tokens) and is_pixfmt(tokens[i]): v_block['pf'] = tokens[i]; i += 1
        vb = None
        while i < len(tokens):
            if is_bitrate(tokens[i]): vb = tokens[i]; i += 1; break
            i += 1
        if vb: v_block['br'] = vb
        idx = i

    a_block = {}
    if idx < len(tokens) and tokens[idx] in AUDIO_CODECS:
        j = idx
        a_block['codec'] = tokens[j]; j += 1
        if j < len(tokens) and re.fullmatch(r"\d+(?:\.\d+)?k", tokens[j]): a_block['sr'] = tokens[j]; j += 1
        if j < len(tokens) and re.fullmatch(r"\d+ch", tokens[j]): a_block['ch'] = tokens[j]; j += 1
        ab = None
        while j < len(tokens):
            if is_bitrate(tokens[j]): ab = tokens[j]; j += 1; break
            j += 1
        if ab: a_block['br'] = ab
        idx = j

    # Decode suffix and decide which side the error label belongs to
    labels = [s for s in (suffix or '').split('__') if s]
    video_err_label = None
    audio_err_label = None
    if labels:
        if len(labels) >= 2:
            video_err_label, audio_err_label = labels[0], labels[1]
        else:
            only = labels[0]
            try:
                # registries from modules
                ALL_VIDEO_ERROR_MODES = VET.ALL_VIDEO_ERROR_MODES
                AUDIO_ERROR_MODES = AET.AUDIO_ERROR_MODES
                if only in VET.ALL_VIDEO_ERROR_MODES and only not in AET.AUDIO_ERROR_MODES:
                    video_err_label = only
                elif only in AET.AUDIO_ERROR_MODES and only not in VET.ALL_VIDEO_ERROR_MODES:
                    audio_err_label = only
                else:
                    if a_block: audio_err_label = only
                    else: video_err_label = only
            except Exception:
                if a_block: audio_err_label = only
                else: video_err_label = only

    # Build new tokens — always start with 'vts'
    new_tokens = ['vts']
    if v_block and a_block:
        new_tokens += [
            v_block.get('codec',''), v_block.get('res',''), v_block.get('dr',''),
            v_block.get('fps',''), v_block.get('cs',''), v_block.get('pf','')
        ]
        if video_err_label:
            new_tokens.append(video_err_label)
        if v_block.get('br'): new_tokens.append(v_block['br'])
        new_tokens += [a_block.get('codec',''), a_block.get('sr',''), a_block.get('ch','')]
        if audio_err_label:
            new_tokens.append(audio_err_label)
        if a_block.get('br'): new_tokens.append(a_block['br'])
    elif v_block:
        new_tokens += [
            v_block.get('codec',''), v_block.get('res',''), v_block.get('dr',''),
            v_block.get('fps',''), v_block.get('cs',''), v_block.get('pf','')
        ]
        if video_err_label:
            new_tokens.append(video_err_label)
        if v_block.get('br'): new_tokens.append(v_block['br'])
    elif a_block:
        new_tokens += [a_block.get('codec',''), a_block.get('sr',''), a_block.get('ch','')]
        if audio_err_label:
            new_tokens.append(audio_err_label)
        if a_block.get('br'): new_tokens.append(a_block['br'])
    else:
        # Unable to parse — keep original
        return original_path

    # Append stats tail
    try:
        a_frames = int(stats.get('audio_frames', 0)) if stats else 0
        v_frames = int(stats.get('video_frames', 0)) if stats else 0
        dur = int(stats.get('duration_sec', 0)) if stats else 0
    except Exception:
        a_frames = 0; v_frames = 0; dur = 0
    new_tokens += [f"a{a_frames}", f"v{v_frames}", f"{dur}sec"]

    # Sanitize and rename
    new_tokens = [t for t in new_tokens if t]
    new_stem = '_'.join(new_tokens)
    new_path = p.with_name(new_stem + p.suffix)
    try:
        if new_path.exists():
            os.remove(new_path)
    except Exception:
        pass
    try:
        os.rename(p, new_path)
        return str(new_path)
    except Exception:
        return original_path

# ---- Windows helper ----

def _compute_error_windows(total_sec: int):
    total = max(1, int(total_sec))
    template_on = [(1,10),(21,25),(31,35),(51,60)]
    win = []
    for s60, e60 in template_on:
        s0 = int(round(total * (s60/60.0)))
        e0 = int(round(total * (e60/60.0)))
        s0 = max(0, min(s0, total)); e0 = max(0, min(e0, total))
        if e0 > s0:
            win.append((s0, e0))
    win.sort(key=lambda x: x[0])
    merged = []
    for w in win:
        if not merged or w[0] > merged[-1][1]:
            merged.append(list(w))
        else:
            merged[-1][1] = max(merged[-1][1], w[1])
    return [(int(s), int(e)) for s,e in merged]

# ---- Remux helpers ----
def _remux_from_raw_h264(raw_path: str, dst_path: str, audio_src: Optional[str] = None):
    audio_src = audio_src  # reference for linters
    if audio_src and Path(audio_src).exists():
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "h264", "-i", raw_path,
            "-i", audio_src,
            "-map", "0:v:0", "-map", "1:a?", "-c:v", "copy", "-c:a", "copy",
            dst_path
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "h264", "-i", raw_path, "-c:v", "copy", dst_path
        ]
    try:
        subprocess.run(cmd, check=True); return True
    except subprocess.CalledProcessError:
        mkv = str(Path(dst_path).with_suffix('.mkv'))
        try:
            subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "h264", "-i", raw_path, "-c:v", "copy", mkv], check=True)
            return True
        except Exception:
            return False

def _remux_video_audio_raw(v_raw: Optional[str] = None, v_fmt: Optional[str] = None,
 a_raw: Optional[str] = None, a_demux: Optional[str] = None,
 final_out: str = '', final_fmt: str = '', fps_hint: float = None):
    _ = final_fmt # used
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-fflags", "+genpts"]
    if v_raw and v_fmt:
        cmd += ["-f", v_fmt, "-i", v_raw]
    if fps_hint:
        cmd += ["-r", str(fps_hint)]
    if a_raw and a_demux:
        cmd += ["-f", a_demux, "-i", a_raw]
    elif a_raw:
        cmd += ["-i", a_raw]
    maps = []
    if v_raw:
        maps += ["-map", "0:v:0?"]
    if a_raw and v_raw:
        maps += ["-map", "1:a:0?"]
    elif a_raw:
        maps += ["-map", "0:a:0?"]
    flags = []
    if (final_fmt or '').lower() == 'mp4':
        flags = ["-movflags", "+faststart"]
    bsf = []
    if (final_fmt or '').lower() == 'mp4' and (a_demux or '') == 'adts':
        bsf += ["-bsf:a", "aac_adtstoasc"]
    if (final_fmt or '').lower() == 'mp4' and (v_fmt or '') == 'hevc':
        bsf += ["-bsf:v", "extract_extradata,hevc_metadata=aud=insert"]
    extra = []
    if (final_fmt or '').lower() == 'ts':
        extra = ['-mpegts_flags', '+resend_headers']
    if (a_demux or "").lower() == "eac3":
        audio_codec_param = ["-c:a", "eac3"]
    else:
        audio_codec_param = ["-c:a", "copy"]

    cmd += maps + ['-c:v', 'copy'] + audio_codec_param + bsf + flags + extra + [final_out]
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        return False

# ---- Tk UI ----

def _get_selected_lists(mapper: dict):
    out = {}
    for k, picker in mapper.items():
        try: vals = picker.get_selected_list()
        except Exception: vals = []
        out[k] = [v for v in vals if str(v) != '']
    return out

def _safe_var_str(var):
    """Safely read a Tk variable (StringVar/IntVar/etc.) as a stripped string.
    Returns '' if var is None or var.get() is None.
    """
    try:
        val = var.get() if var is not None else ''
    except Exception:
        val = ''
    return ('' if val is None else str(val)).strip()

def _expand_video_combos(sel: dict):
    res_list = sel.get('Resolution', [])
    codec_list = sel.get('Codec', [])
    fps_list = sel.get('Framerate', [])
    prof_list = sel.get('Profile', []) or ['main']
    dr_list = sel.get('Dynamic Range', []) or ['SDR']
    cs_list = sel.get('Color Space', []) or ['BT.709']
    pf_list = sel.get('pixel Format', []) or ['yuv420p']
    ft_list = sel.get('Frame Type', []) or ['Progressive']
    br_list = sel.get('Bitrate', []) or ['5M']
    combos = []
    for (res, codec, fps, prof, dr, cs, pf, ft, br) in product(res_list or [''], codec_list or [''], fps_list or [''], prof_list, dr_list, cs_list, pf_list, ft_list, br_list):
        vd = {
            'Resolution': res,
            'Codec': codec,
            'Framerate': fps,
            'Profile': prof,
            'Dynamic Range': dr,
            'Color Space': cs,
            'pixel Format': pf,
            'Frame Type': ft,
            'Bitrate': br,
        }
        combos.append(vd)
    return [c for c in combos if c['Codec'] and c['Resolution'] and c['Framerate']]

def _expand_audio_combos(sel: dict):
    codec_list = sel.get('Codec', [])
    sr_list = sel.get('Sample Rate', [])
    ch_list = sel.get('Channels', [])
    br_list = sel.get('Bitrate', [])
    if not sr_list: sr_list = [48000]
    if not ch_list: ch_list = [2]
    combos = []
    for (codec, sr, ch, br) in product(codec_list or [''], sr_list, ch_list, br_list or [None]):
        ad = {'Codec': codec, 'Sample Rate': int(sr), 'Channels': int(ch)}
        if br: ad['Bitrate'] = br
        combos.append(ad)
    return [a for a in combos if a['Codec']]

# ---- Build UI ----

def build_ui():
    root = tk.Tk(); root.title("VTS Main & Error Stream Generator"); root.geometry("1200x980"); root.minsize(1024,820)
    style = ttk.Style(); style.configure("TLabel", font=("Segoe UI", 13)); style.configure("TEntry", font=("Segoe UI", 13)); style.configure("TCombobox", font=("Segoe UI", 13)); style.configure("Custom.TButton", font=("Segoe UI", 12, "bold"))

    # Shared state to always point to current pickers (video/audio)
    state = {}
    # Persist selections tab-wise
    state.setdefault('selected_video_errors', [])
    state.setdefault('selected_audio_errors', [])

    toggle_frame = ttk.Frame(root, padding=10); toggle_frame.pack(anchor='w', fill='x')
    video_enabled = tk.BooleanVar(value=True); audio_enabled = tk.BooleanVar(value=True)
    ttk.Checkbutton(toggle_frame, text="Enable Video", variable=video_enabled).grid(row=0, column=0, sticky='w', padx=5, pady=5)
    ttk.Checkbutton(toggle_frame, text="Enable Audio", variable=audio_enabled).grid(row=0, column=1, sticky='w', padx=15, pady=5)

    io_frame = ttk.Frame(root, padding=10); io_frame.pack(anchor='w', fill='x')
    duration_var = tk.StringVar(value="")
    frame_count_var = tk.StringVar(value=""); fileformat_var = tk.StringVar(value=""); output_path_var = tk.StringVar()
    ttk.Label(io_frame, text="Duration (sec):").grid(row=0, column=0, sticky='w', padx=5, pady=5)
    entry_duration = ttk.Entry(io_frame, textvariable=duration_var, width=10); entry_duration.grid(row=0, column=1, sticky='w', padx=5, pady=5)
    ttk.Label(io_frame, text="(or)").grid(row=0, column=2, sticky='w', padx=5, pady=5)
    ttk.Label(io_frame, text="Number of Frames:").grid(row=0, column=3, sticky='w', padx=5, pady=5)
    frame_count_var = tk.StringVar(value="")
    entry_frames = ttk.Entry(io_frame, textvariable=frame_count_var, width=10)
    entry_frames.grid(row=0, column=4, sticky='w', padx=5, pady=5)
    ttk.Label(io_frame, text="File Format").grid(row=1, column=0, sticky='w', padx=5, pady=5)
    file_format_combo = ttk.Combobox(io_frame, textvariable=fileformat_var, values=["mp4","ts","webm","raw"], state="readonly", width=10); file_format_combo.grid(row=1, column=1, sticky='w', padx=5, pady=5)

    def select_output_directory():
        p = filedialog.askdirectory(title="Select output directory")
        if p: output_path_var.set(str(Path(p).resolve().as_posix()))
    ttk.Button(io_frame, text="Output Directory", command=select_output_directory, style="Custom.TButton").grid(row=2, column=0, padx=5, pady=5, sticky='w')
    ttk.Label(io_frame, textvariable=output_path_var, font=("Segoe UI", 10)).grid(row=2, column=1, sticky='w', padx=10, pady=8)

    notebook = ttk.Notebook(root); notebook.pack(fill='both', expand=True, padx=10, pady=10)
    style.configure("TNotebook", tabposition="n"); style.configure("TNotebook.Tab", padding=[15,8], font=("Segoe UI", 11, "bold"))

    # Video tab
    video_frame = ttk.Frame(notebook, padding=15, borderwidth=2, relief="groove"); notebook.add(video_frame, text="Video Parameters")
    video_frame.columnconfigure(0, weight=0); video_frame.columnconfigure(1, weight=1, minsize=260); video_frame.columnconfigure(2, weight=0); video_frame.columnconfigure(3, weight=1, minsize=260)

    video_mode_var = tk.StringVar(value="Main Stream Generator")
    ttk.Label(video_frame, text="Video Stream Type:", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky='w', padx=10, pady=8)
    video_mode_combo = ttk.Combobox(video_frame, values=["Main Stream Generator", "Error Stream Generator"], state="readonly", textvariable=video_mode_var, width=22); video_mode_combo.grid(row=0, column=1, sticky='w', padx=10, pady=8)

    video_options = {}; row = 1; col = 0; frame_type_row = None
    for key, options in video_params.items():
        ttk.Label(video_frame, text=key + ":", font=("Segoe UI", 12, "bold")).grid(row=row, column=col, sticky='w', padx=10, pady=8)
        cp = Combopicker(video_frame, options, height=10, width=24)
        cp.grid(row=row, column=col+1, sticky='nsew', padx=10, pady=8)
        if key == 'Frame Type': frame_type_row = row
        video_options[key] = cp
        col = (col + 2) % 4; row += 1 if col == 0 else 0
    if col: row += 1

    ttk.Label(video_frame, text="GOP Size (sec):", font=("Segoe UI", 12)).grid(row=row, column=0, sticky='w', padx=10, pady=8)
    gop_size_var = tk.StringVar(value="1"); ttk.Entry(video_frame, textvariable=gop_size_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=8); row += 1

    ttk.Label(video_frame, text="Keyframe Interval (sec):", font=("Segoe UI", 12)).grid(row=row, column=0, sticky='w', padx=10, pady=8)
    keyint_var = tk.StringVar(value="1"); ttk.Entry(video_frame, textvariable=keyint_var, width=10).grid(row=row, column=1, sticky='w', padx=10, pady=8); row += 1

    error_row = (frame_type_row + 1) if frame_type_row is not None else row
    error_label_col = 2; error_picker_col = 3
    error_label = ttk.Label(video_frame, text="Video Error Types", font=("Segoe UI", 12, "bold"))
    error_label.grid(row=error_row, column=error_label_col, sticky='w', padx=10, pady=8)

    error_in_video_frame = ttk.Frame(video_frame)
    error_in_video_frame.grid(row=error_row, column=error_picker_col, sticky='nsew', padx=10, pady=8)
    error_in_video_frame.grid_columnconfigure(0, weight=1); error_in_video_frame.grid_rowconfigure(0, weight=1)

    error_picker = Combopicker(error_in_video_frame, VET.GENERIC_VIDEO_MODES, height=10, width=30)
    error_picker.grid(row=0, column=0, sticky='nsew')

    _ensure_listbox_export_off(error_in_video_frame)
    # Bind events to persist video error selections
    try:
        error_picker.bind('<<ListboxSelect>>', _persist_video_error_selection)
        error_picker.bind('<ButtonRelease-1>', _persist_video_error_selection)
        error_picker.bind('<KeyRelease>', _persist_video_error_selection)
    except Exception:
        pass
    def _persist_video_error_selection(*_):
        try:
            picker = state.get('error_picker')
            state['selected_video_errors'] = picker.get_selected_list() if picker else []
        except Exception:
            pass

    _ensure_listbox_export_off(error_in_video_frame)
    state['error_picker'] = error_picker

    try: error_label.grid_remove(); error_in_video_frame.grid_remove()
    except Exception: pass

    # Audio tab
    audio_frame = ttk.Frame(notebook, padding=15, borderwidth=2, relief="groove"); notebook.add(audio_frame, text="Audio Parameters")

    audio_options = {}; row_a = 0

    audio_mode_var = tk.StringVar(value="Main Stream Generator")
    ttk.Label(audio_frame, text="Audio Stream Type:", font=("Segoe UI", 12, "bold")).grid(row=row_a, column=0, sticky='w', padx=10, pady=8)
    audio_mode_combo = ttk.Combobox(audio_frame, values=["Main Stream Generator", "Error Stream Generator"], state="readonly", textvariable=audio_mode_var, width=22); audio_mode_combo.grid(row=row_a, column=1, sticky='w', padx=10, pady=8)
    row_a += 1

    for key, options in audio_params.items():
        ttk.Label(audio_frame, text=key + ":", font=("Segoe UI", 12, "bold")).grid(row=row_a, column=0, sticky='w', padx=10, pady=8)
        cp_a = Combopicker(audio_frame, options, height=10, width=30)
        cp_a.grid(row=row_a, column=1, sticky='nsew', padx=10, pady=8)
        audio_options[key] = cp_a
        row_a += 1

    audio_error_label = ttk.Label(audio_frame, text="Audio Error Types", font=("Segoe UI", 12, "bold"))
    audio_error_label.grid(row=row_a, column=0, sticky='w', padx=10, pady=8)

    audio_error_frame = ttk.Frame(audio_frame)
    audio_error_frame.grid(row=row_a, column=1, sticky='nsew', padx=10, pady=8)
    audio_error_frame.grid_columnconfigure(0, weight=1)
    audio_error_picker = Combopicker(audio_error_frame, AET.GENERIC_AUDIO_ERROR_MODES, height=12, width=40)
    audio_error_picker.grid(row=0, column=0, sticky='nsew')

    _ensure_listbox_export_off(audio_error_frame)
    # Bind events to persist audio error selections
    try:
        audio_error_picker.bind('<<ListboxSelect>>', _persist_audio_error_selection)
        audio_error_picker.bind('<ButtonRelease-1>', _persist_audio_error_selection)
        audio_error_picker.bind('<KeyRelease>', _persist_audio_error_selection)
    except Exception:
        pass

    def _persist_audio_error_selection(*_):
        try:
            picker = state.get('audio_error_picker')
            state['selected_audio_errors'] = picker.get_selected_list() if picker else []
        except Exception:
            pass

    _ensure_listbox_export_off(audio_error_frame)
    state['audio_error_picker'] = audio_error_picker

    try: audio_error_label.grid_remove(); audio_error_frame.grid_remove()
    except Exception: pass

    row_a += 1

    ttk.Label(audio_frame, text="Volume", font=("Segoe UI", 12)).grid(row=row_a, column=0, sticky='w', padx=10, pady=8)
    volume_var = tk.StringVar(value="1"); ttk.Entry(audio_frame, textvariable=volume_var, width=10).grid(row=row_a, column=1, sticky='w', padx=10, pady=8)

    # ---- Input / Test Sources TAB (ADDED) ----
    sources_frame = ttk.Frame(notebook, padding=15, borderwidth=2, relief="groove"); notebook.add(sources_frame, text="Input / Test Sources")

    # Variables
    video_input_var = tk.StringVar(value="")
    audio_input_var = tk.StringVar(value="")
    # Display selected filenames (UI confirmation)
    video_input_name_var = tk.StringVar(value="No video file selected")
    audio_input_name_var = tk.StringVar(value="No audio file selected")

    # ---- Auto-refresh selected file labels (Video/Audio) ----
    def _refresh_audio_input_label(*_):
        """Keep Audio selected label in sync.
        Priority:
          1) If explicit Audio file selected -> show its filename
          2) Else if (Audio-only OR Both-enabled) and Video file selected AND it has audio -> show audio source from that video file
          3) Else -> default
        """
        try:
            vpath = (video_input_var.get() or '').strip()
            apath = (audio_input_var.get() or '').strip()

            # Explicit audio file selected
            if apath:
                info = _probe_stream_types(apath)
                if info.get('has_video') and (not info.get('has_audio')):
                    audio_input_name_var.set('Selected file has only video. Choose appropriate file')
                    return
                try:
                    audio_input_name_var.set(Path(apath).name)
                except Exception:
                    audio_input_name_var.set(apath)
                return

            a_only = bool(audio_enabled.get()) and (not bool(video_enabled.get()))
            both_on = bool(audio_enabled.get()) and bool(video_enabled.get())

            # No explicit audio file: show selected audio source from video when applicable
            if (a_only or both_on) and vpath:
                info = _probe_stream_types(vpath)
                if info.get('has_audio'):
                    audio_input_name_var.set(f"Selected audio source: {Path(vpath).name}")
                else:
                    audio_input_name_var.set("Selected video file has no audio")
            else:
                audio_input_name_var.set("No audio file selected")
        except Exception:
            pass

    def _refresh_video_input_label(*_):
        """Keep Video selected label in sync.
        Priority:
          1) If explicit Video file selected -> show its filename
          2) Else if (Video-only OR Both-enabled) and Audio file selected AND it has video -> show video source from that audio file
          3) Else -> default
        """
        try:
            vpath = (video_input_var.get() or '').strip()
            apath = (audio_input_var.get() or '').strip()

            # Explicit video file selected
            if vpath:
                info = _probe_stream_types(vpath)
                if info.get('has_audio') and (not info.get('has_video')):
                    video_input_name_var.set('Selected file has only audio. Choose appropriate file')
                    return
                try:
                    video_input_name_var.set(Path(vpath).name)
                except Exception:
                    video_input_name_var.set(vpath)
                return

            v_only = bool(video_enabled.get()) and (not bool(audio_enabled.get()))
            both_on = bool(audio_enabled.get()) and bool(video_enabled.get())

            # No explicit video file: show selected video source from audio when applicable
            if (v_only or both_on) and apath:
                info = _probe_stream_types(apath)
                if info.get('has_video'):
                    video_input_name_var.set(f"Selected video source: {Path(apath).name}")
                else:
                    video_input_name_var.set("Selected audio file has no video")
            else:
                video_input_name_var.set("No video file selected")
        except Exception:
            pass

    # Trace changes to keep labels updated
    try:
        audio_input_var.trace_add('write', _refresh_audio_input_label)
        video_input_var.trace_add('write', _refresh_audio_input_label)
        audio_enabled.trace_add('write', _refresh_audio_input_label)
        video_enabled.trace_add('write', _refresh_audio_input_label)
        audio_input_var.trace_add('write', _refresh_video_input_label)
        video_input_var.trace_add('write', _refresh_video_input_label)
        audio_enabled.trace_add('write', _refresh_video_input_label)
        video_enabled.trace_add('write', _refresh_video_input_label)
    except Exception:
        pass
    video_source_var = tk.StringVar(value=video_test_sources[0])
    audio_source_var = tk.StringVar(value=audio_test_sources[0])

    # Layout
    sources_frame.columnconfigure(0, weight=0); sources_frame.columnconfigure(1, weight=1)

    # Test Source selectors
    ttk.Label(sources_frame, text="Video Test Source:", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky='w', padx=10, pady=8)
    ttk.Combobox(sources_frame, textvariable=video_source_var, values=video_test_sources, state="readonly", width=22).grid(row=0, column=1, sticky='w', padx=10, pady=8)

    ttk.Label(sources_frame, text="Audio Test Source:", font=("Segoe UI", 12, "bold")).grid(row=1, column=0, sticky='w', padx=10, pady=8)
    ttk.Combobox(sources_frame, textvariable=audio_source_var, values=audio_test_sources, state="readonly", width=22).grid(row=1, column=1, sticky='w', padx=10, pady=8)

    # File selectors
    def _select_video_file():
        p = filedialog.askopenfilename(title="Select Video File")
        if p:
            video_input_var.set(str(Path(p).resolve().as_posix()))
            try:
                video_input_name_var.set(Path(p).name)
            except Exception:
                video_input_name_var.set(str(p))
        _refresh_video_input_label(); _refresh_audio_input_label()

    def _select_audio_file():
        p = filedialog.askopenfilename(title="Select Audio File")
        if p:
            audio_input_var.set(str(Path(p).resolve().as_posix()))
            try:
                audio_input_name_var.set(Path(p).name)
            except Exception:
                audio_input_name_var.set(str(p))
        _refresh_audio_input_label(); _refresh_video_input_label()

    def _clear_video_file():
        video_input_var.set('')
        _refresh_video_input_label()
        _refresh_audio_input_label()
    def _clear_audio_file():
        audio_input_var.set('')
        _refresh_audio_input_label()
        _refresh_video_input_label()

    ttk.Button(sources_frame, text="Select Video File", command=_select_video_file, style="Custom.TButton").grid(row=2, column=0, sticky='w', padx=10, pady=8)
    ttk.Button(sources_frame, text="Clear Video File", command=_clear_video_file, style="Custom.TButton").grid(row=2, column=2, sticky='w', padx=10, pady=8)
    ttk.Label(sources_frame, textvariable=video_input_name_var, font=("Segoe UI", 10)).grid(row=2, column=1, sticky='w', padx=10, pady=8)
    ttk.Button(sources_frame, text="Select Audio File", command=_select_audio_file, style="Custom.TButton").grid(row=3, column=0, sticky='w', padx=10, pady=8)
    ttk.Button(sources_frame, text="Clear Audio File", command=_clear_audio_file, style="Custom.TButton").grid(row=3, column=2, sticky='w', padx=10, pady=8)
    ttk.Label(sources_frame, textvariable=audio_input_name_var, font=("Segoe UI", 10)).grid(row=3, column=1, sticky='w', padx=10, pady=8)

    # Hidden Entry widgets (to preserve variable bindings without cluttering UI)
    _vi_entry = ttk.Entry(sources_frame, textvariable=video_input_var, width=40); _vi_entry.grid(row=2, column=1, sticky='w', padx=10, pady=8); _vi_entry.grid_remove()
    _ai_entry = ttk.Entry(sources_frame, textvariable=audio_input_var, width=40); _ai_entry.grid(row=3, column=1, sticky='w', padx=10, pady=8); _ai_entry.grid_remove()
 
    # ===== Video error picker refresh =====
    def _current_codec_selection():
        try:
            return video_options.get('Codec').get_selected_list()
        except Exception:
            return []
    
    def _allowed_video_error_modes(selected_codecs: list):
        allowed = set(VET.GENERIC_VIDEO_MODES)
        sc = set(selected_codecs or [])
        try:
            is_err = (video_mode_var.get() == 'Error Stream Generator')
        except Exception:
            is_err = False
        if is_err and (('libvpx-vp9' in sc) or ('libsvtav1' in sc)):
            only = set()
            if 'libx264' in sc: only |= set(VET.H264_CODEC_SPECIFIC_MODES)
            if 'libx265' in sc: only |= set(VET.HEVC_CODEC_SPECIFIC_MODES)
            if 'mpeg2video' in sc: only |= set(VET.MPEG2_CODEC_SPECIFIC_MODES)
            if 'libvpx-vp9' in sc: only |= set(VET.VP9_CODEC_SPECIFIC_MODES)
            if 'libsvtav1' in sc: only |= set(VET.AV1_CODEC_SPECIFIC_MODES)
            return sorted(list(only))
        if 'libx264' in sc: allowed |= set(VET.H264_CODEC_SPECIFIC_MODES)
        if 'libx265' in sc: allowed |= set(VET.HEVC_CODEC_SPECIFIC_MODES)
        if 'mpeg2video' in sc: allowed |= set(VET.MPEG2_CODEC_SPECIFIC_MODES)
        if 'libvpx-vp9' in sc: allowed |= set(VET.VP9_CODEC_SPECIFIC_MODES)
        if 'libsvtav1' in sc: allowed |= set(VET.AV1_CODEC_SPECIFIC_MODES)
        return sorted(list(allowed))
    
    def _update_error_picker_values_fast(picker, new_vals):
        if hasattr(picker, 'set_values'):
            try:
                picker.set_values(new_vals)
                return True
            except Exception:
                return False
        return False
    
    def _refresh_error_types():
        selected_codecs = _current_codec_selection()
        new_vals = _allowed_video_error_modes(selected_codecs)
        try:
            if video_mode_var.get() == 'Error Stream Generator' and (('libvpx-vp9' in selected_codecs) or ('libsvtav1' in selected_codecs)):
                new_vals = [m for m in new_vals if m not in VET.GENERIC_VIDEO_MODES]
        except Exception:
            pass
        picker = state.get('error_picker', error_picker)
        if _update_error_picker_values_fast(picker, new_vals):
            label = 'Video Error Types'
            try:
                is_err = (video_mode_var.get() == 'Error Stream Generator')
            except Exception:
                is_err = False
            if is_err and (('libvpx-vp9' in selected_codecs) or ('libsvtav1' in selected_codecs)):
                parts = []
                if 'libvpx-vp9' in selected_codecs: parts.append('VP9')
                if 'libsvtav1' in selected_codecs: parts.append('AV1')
                if 'libx264' in selected_codecs: parts.append('H.264')
                if 'libx265' in selected_codecs: parts.append('HEVC')
                if 'mpeg2video' in selected_codecs: parts.append('MPEG-2')
                if parts: label += ' (' + ' + '.join(parts) + ')'
            else:
                label += ' (Generic'
                if 'libx264' in selected_codecs: label += ' + H.264'
                if 'libx265' in selected_codecs: label += ' + HEVC'
                if 'mpeg2video' in selected_codecs: label += ' + MPEG-2'
                if 'libvpx-vp9' in selected_codecs: label += ' + VP9'
                if 'libsvtav1' in selected_codecs: label += ' + AV1'
                label += ')'
            state['error_picker'] = picker
            error_label.configure(text=label)
            return
        # Reapply persisted selections
        try:
            saved = state.get('selected_video_errors', [])
            common = [m for m in saved if m in new_vals]
            if hasattr(picker, '_lb'):
                for i, v in enumerate(new_vals):
                    if v in common:
                        try:
                            picker._lb.selection_set(i)
                        except Exception:
                            pass
        except Exception:
            pass
        # Rebuild picker if fast path didn't apply
        try:
            old_selected = picker.get_selected_list()
        except Exception:
            old_selected = []
        for child in error_in_video_frame.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass
        new_picker = Combopicker(error_in_video_frame, new_vals, height=10, width=30)
        new_picker.grid(row=0, column=0, sticky='nsew')
        try:
            common = [m for m in old_selected if m in new_vals]
            if hasattr(new_picker, '_lb'):
                for i, v in enumerate(new_vals):
                    if v in common:
                        new_picker._lb.selection_set(i)
        except Exception:
            pass
        label = 'Video Error Types'
        try:
            is_err = (video_mode_var.get() == 'Error Stream Generator')
        except Exception:
            is_err = False
        if is_err and (('libvpx-vp9' in selected_codecs) or ('libsvtav1' in selected_codecs)):
            parts = []
            if 'libvpx-vp9' in selected_codecs: parts.append('VP9')
            if 'libsvtav1' in selected_codecs: parts.append('AV1')
            if 'libx264' in selected_codecs: parts.append('H.264')
            if 'libx265' in selected_codecs: parts.append('HEVC')
            if 'mpeg2video' in selected_codecs: parts.append('MPEG-2')
            if parts: label += ' (' + ' + '.join(parts) + ')'
        else:
            label += ' (Generic'
            if 'libx264' in selected_codecs: label += ' + H.264'
            if 'libx265' in selected_codecs: label += ' + HEVC'
            if 'mpeg2video' in selected_codecs: label += ' + MPEG-2'
            if 'libvpx-vp9' in selected_codecs: label += ' + VP9'
            if 'libsvtav1' in selected_codecs: label += ' + AV1'
            label += ')'
        error_label.configure(text=label)
        state['error_picker'] = new_picker
        try:
            saved = state.get('selected_video_errors', [])
            common = [m for m in saved if m in new_vals]
            if hasattr(new_picker, '_lb'):
                for i, v in enumerate(new_vals):
                    if v in common:
                        try:
                            new_picker._lb.selection_set(i)
                        except Exception:
                            pass
        except Exception:
            pass
    
    def _instant_refresh_event(*_):
        try:
            root.after_idle(_refresh_error_types)
        except Exception:
            _refresh_error_types()
    
    def _bind_codec_instant_refresh():
        codec_widget = video_options.get('Codec')
        if codec_widget is None:
            return
        events = ['<<ComboboxSelected>>','<<ListboxSelect>>','<ButtonPress-1>','<ButtonRelease-1>','<KeyRelease>','<Return>','<space>','<FocusOut>']
        for ev in events:
            try:
                codec_widget.bind(ev, _instant_refresh_event)
            except Exception:
                pass
        try:
            root.bind_all('<<ComboboxSelected>>', _instant_refresh_event)
            root.bind_all('<<ListboxSelect>>', _instant_refresh_event)
        except Exception:
            pass
    
    _bind_codec_instant_refresh()
    _last_codec_sel = {'vals': []}

    def _watch_codec_selection():
        try:
            current = _current_codec_selection()
        except Exception:
            current = []
        if current != _last_codec_sel['vals']:
            _last_codec_sel['vals'] = list(current)
            _refresh_error_types()
        try:
            root.after(75, _watch_codec_selection)
        except Exception:
            pass
    try:
        root.after(0, _watch_codec_selection)
    except Exception:
        _watch_codec_selection()

# ===== Audio picker refresh =====

    def _current_audio_codec_selection():
        try: return audio_options.get('Codec').get_selected_list()
        except Exception: return []

    def _allowed_audio_error_modes(selected_codecs: list):
        allowed = set(AET.GENERIC_AUDIO_ERROR_MODES)
        sc = set(selected_codecs or [])
        if 'aac' in sc: allowed |= set(AET.AAC_AUDIO_SPECIFIC_MODES)
        if 'mp3' in sc: allowed |= set(AET.MP3_AUDIO_SPECIFIC_MODES)
        if 'ac3' in sc: allowed |= set(AET.AC3_AUDIO_SPECIFIC_MODES)
        if 'eac3' in sc: allowed |= set(AET.EAC3_AUDIO_SPECIFIC_MODES)
        if 'flac' in sc: allowed |= set(AET.FLAC_AUDIO_SPECIFIC_MODES)
        if 'pcm_s16le' in sc: allowed |= set(AET.PCM_AUDIO_SPECIFIC_MODES)
        if 'libvorbis' in sc: allowed |= set(AET.VORBIS_AUDIO_SPECIFIC_MODES)
        if 'libopus' in sc: allowed |= set(AET.OPUS_AUDIO_SPECIFIC_MODES)
        return sorted(list(allowed))

    def _update_audio_error_picker_values_fast(picker, new_vals):
        if hasattr(picker, 'set_values'):
            try:
                picker.set_values(new_vals); return True
            except Exception:
                return False
        return False

    def _refresh_audio_error_types():
        selected_codecs = _current_audio_codec_selection()
        new_vals = _allowed_audio_error_modes(selected_codecs)
        picker = state.get('audio_error_picker', audio_error_picker)
        if _update_audio_error_picker_values_fast(picker, new_vals):
            label = "Audio Error Types (Generic"
            if 'aac' in selected_codecs: label += " + AAC"
            if 'mp3' in selected_codecs: label += " + MP3"
            if 'ac3' in selected_codecs: label += " + AC3"
            if 'eac3' in selected_codecs: label += " + EAC3"
            if 'pcm_s16le' in selected_codecs: label += " + PCM"
            if 'flac' in selected_codecs: label += " + Flac"
            if 'libvorbis' in selected_codecs: label += " + Vorbis"
            if 'libopus' in selected_codecs: label += " + Opus"
            label += ")"
            state['audio_error_picker'] = picker
            audio_error_label.configure(text=label); return
        # Reapply persisted selections
        try:
            saved = state.get('selected_audio_errors', [])
            common = [m for m in saved if m in new_vals]
            if hasattr(picker, '_lb'):
                for i, v in enumerate(new_vals):
                    if v in common:
                        try: picker._lb.selection_set(i)
                        except Exception: pass
        except Exception:
            pass
        try: old_selected = picker.get_selected_list()
        except Exception: old_selected = []
        for child in audio_error_frame.winfo_children():
            try: child.destroy()
            except Exception: pass
        new_picker = Combopicker(audio_error_frame, new_vals, height=12, width=40)
        new_picker.grid(row=0, column=0, sticky='nsew')
        try:
            common = [m for m in old_selected if m in new_vals]
            if hasattr(new_picker, '_lb'):
                for i, v in enumerate(new_vals):
                    if v in common: new_picker._lb.selection_set(i)
        except Exception: pass
        label = "Audio Error Types (Generic"
        if 'aac' in selected_codecs: label += " + AAC"
        if 'mp3' in selected_codecs: label += " + MP3"
        if 'ac3' in selected_codecs: label += " + AC3"
        if 'eac3' in selected_codecs: label += " + EAC3"
        if 'pcm_s16le' in selected_codecs: label += " + PCM"
        if 'flac' in selected_codecs: label += " + Flac"
        if 'libvorbis' in selected_codecs: label += " + Vorbis"
        if 'libopus' in selected_codecs: label += " + Opus"
        label += ")"
        audio_error_label.configure(text=label)
        state['audio_error_picker'] = new_picker

        # Reapply persisted selections
        try:
            saved = state.get('selected_audio_errors', [])
            common = [m for m in saved if m in new_vals]
            if hasattr(new_picker, '_lb'):
                for i, v in enumerate(new_vals):
                    if v in common:
                        try: new_picker._lb.selection_set(i)
                        except Exception: pass
        except Exception:
            pass

    def _instant_audio_refresh_event(*_):
        try: root.after_idle(_refresh_audio_error_types)
        except Exception: _refresh_audio_error_types()

    def _bind_audio_codec_instant_refresh():
        codec_widget = audio_options.get('Codec')
        if codec_widget is None: return
        events = ['<<ComboboxSelected>>','<<ListboxSelect>>','<ButtonPress-1>','<ButtonRelease-1>','<KeyRelease>','<Return>','<space>','<FocusOut>']
        for ev in events:
            try: codec_widget.bind(ev, _instant_audio_refresh_event)
            except Exception: pass
        try:
            root.bind_all('<<ComboboxSelected>>', _instant_audio_refresh_event)
            root.bind_all('<<ListboxSelect>>', _instant_audio_refresh_event)
        except Exception: pass
    _bind_audio_codec_instant_refresh()

    _last_audio_codec_sel = {'vals': []}

    def _watch_audio_codec_selection():
        try: current = _current_audio_codec_selection()
        except Exception: current = []
        if current != _last_audio_codec_sel['vals']:
            _last_audio_codec_sel['vals'] = list(current)
            _refresh_audio_error_types()
        try: root.after(75, _watch_audio_codec_selection)
        except Exception: pass
    try: root.after(0, _watch_audio_codec_selection)
    except Exception: _watch_audio_codec_selection()

    # ===== Actions =====
    def generate_ffmpeg_action():
        try:
            if not (video_enabled.get() or audio_enabled.get()):
                messagebox.showwarning("Error", "Enable at least Video or Audio"); return
            duration_val = _safe_var_str(duration_var)
            frames_val = _safe_var_str(frame_count_var)
            if duration_val and frames_val:
                messagebox.showerror("Input Error", "Select either Duration OR Frames, not both.")
                return
            if not duration_val and not frames_val:
                messagebox.showerror("Input Error", "Enter either Duration OR Frames.")
                return
            duration_sec = int(float(duration_val)) if duration_val else None
            frames_count = int(frames_val) if frames_val else None
            if duration_sec is None and frames_count is not None:
                duration_sec = _derive_duration_from_frames(frames_count, vid_dict=vid_combos[0] if 'vid_combos' in locals() and vid_combos else None, aud_dict=aud_combos[0] if 'aud_combos' in locals() and aud_combos else None)
            gop_sec = float(gop_size_var.get().strip() or 1)
            key_sec = float(keyint_var.get().strip() or 1)
            volume = float(volume_var.get().strip() or 1.0)
            output_dir = output_path_var.get().strip() or str(Path.cwd())
            vid_combos = []; aud_combos = []
            if video_enabled.get():
                sel_v = _get_selected_lists(video_options); vid_combos = _expand_video_combos(sel_v)
                if not vid_combos:
                    messagebox.showerror("Video", "Please select Video Codec, Resolution, and Framerate."); return
                for v in vid_combos: v['gop_size'] = gop_sec; v['key_sec'] = key_sec
            if audio_enabled.get():
                sel_a = _get_selected_lists(audio_options); aud_combos = _expand_audio_combos(sel_a)
            file_fmt = fileformat_var.get().strip()
            if (file_fmt or '').strip().lower() == 'raw' and video_enabled.get() and audio_enabled.get():
                messagebox.showwarning('Raw File Format', 'Raw (elementary) output is supported only for Video-only OR Audio-only. Please disable one.');
                return
            success_main = 0
            v_input = video_input_var.get().strip()
            a_input = audio_input_var.get().strip()
            # Cross-use embedded tracks when in Video-only or Audio-only mode
            # Apply ONLY if the selected file contains BOTH audio and video. Otherwise show an error.
            if video_enabled.get() and (not audio_enabled.get()) and (not v_input) and a_input:
                info = _probe_stream_types(a_input)
                if info.get('has_video') and info.get('has_audio'):
                    v_input = a_input
                elif info.get('has_audio') and (not info.get('has_video')):
                    messagebox.showerror('Input Error', 'Selected only audio file but no video track present. Please select a video file with video.'); return
            if audio_enabled.get() and (not video_enabled.get()) and (not a_input) and v_input:
                info = _probe_stream_types(v_input)
                if info.get('has_audio') and info.get('has_video'):
                    a_input = v_input
                elif info.get('has_video') and (not info.get('has_audio')):
                    messagebox.showerror('Input Error', 'Selected only video file but no audio track present. Please select an audio file with audio.'); return

            # Auto-fill missing input when both Audio and Video are enabled
            # If only one of the files is selected and it contains BOTH audio and video,
            # reuse it for the unselected side instead of using synthetic sources.

            if video_enabled.get() and audio_enabled.get():
                if v_input and (not a_input):
                    info = _probe_stream_types(v_input)
                    if info.get('has_audio') and info.get('has_video'):
                        a_input = v_input
                elif a_input and (not v_input):
                    info = _probe_stream_types(a_input)
                    if info.get('has_audio') and info.get('has_video'):
                        v_input = a_input
                # Refresh labels if helpers exist
                try:
                    _refresh_video_input_label()
                    _refresh_audio_input_label()
                except Exception:
                    pass

            v_source = video_source_var.get().strip() or video_test_sources[0]
            a_source = audio_source_var.get().strip() or audio_test_sources[0]
            if vid_combos and aud_combos:
                for v, a in product(vid_combos, aud_combos):
                    cmd, outfile = generate_ffmpeg_command(
                        v, a,
                        video_input=v_input, audio_input=a_input,
                        video_source=v_source, audio_source=a_source,
                        duration_sec=duration_sec, frames_count=frames_count, volume=volume,
                        file_format=file_fmt, output_dir=output_dir,
                    )
                    print("Running:", " ".join(cmd)); subprocess.run(cmd, check=True)
                    stats = get_stream_info(outfile)
                    if stats and int(stats.get('duration_sec',0) or 0) == 0:
                        stats['duration_sec'] = int(duration_sec or 0)
                    if (not stats) or (int(stats.get('audio_frames',0))==0 and int(stats.get('video_frames',0))==0):
                        stats = _fallback_stats_from_params(duration_sec, v, a)
                    new_name = rename_file_with_stats(outfile, stats)
                    print(f'[Main] Generated: {new_name}'); success_main += 1
            elif vid_combos:
                for v in vid_combos:
                    cmd, outfile = generate_ffmpeg_command(
                        v, None,
                        video_input=v_input, audio_input=a_input,
                        video_source=v_source, audio_source=a_source,
                        duration_sec=duration_sec, frames_count=frames_count, volume=volume,
                        file_format=file_fmt, output_dir=output_dir,
                    )
                    print("Running:", " ".join(cmd)); subprocess.run(cmd, check=True)
                    stats = get_stream_info(outfile)
                    if stats and int(stats.get('duration_sec',0) or 0) == 0:
                        stats['duration_sec'] = int(duration_sec or 0)
                    if (not stats) or (int(stats.get('audio_frames',0))==0 and int(stats.get('video_frames',0))==0):
                        stats = _fallback_stats_from_params(duration_sec, v, None)
                    new_name = rename_file_with_stats(outfile, stats)
                    print(f'[Main] Generated: {new_name}'); success_main += 1
            elif aud_combos:
                for a in aud_combos:
                    cmd, outfile = generate_ffmpeg_command(
                        None, a,
                        video_input=v_input, audio_input=a_input,
                        video_source=v_source, audio_source=a_source,
                        duration_sec=duration_sec, frames_count=frames_count, volume=volume,
                        file_format=file_fmt, output_dir=output_dir,
                    )
                    print("Running:", " ".join(cmd)); subprocess.run(cmd, check=True)
                    stats = get_stream_info(outfile)
                    if stats and int(stats.get('duration_sec',0) or 0) == 0:
                        stats['duration_sec'] = int(duration_sec or 0)
                    if (not stats) or (int(stats.get('audio_frames',0))==0 and int(stats.get('video_frames',0))==0):
                        stats = _fallback_stats_from_params(duration_sec, None, a)
                    new_name = rename_file_with_stats(outfile, stats)
                    print(f'[Main] Generated: {new_name}'); success_main += 1
            if success_main == 0:
                messagebox.showwarning("Generation", "No streams generated."); return
            print(f"Main streams generated: {success_main} \n Output: {output_dir}")
            messagebox.showinfo("Done", f"Main streams generated: {success_main}\nOutput directory:\n{output_dir}")
        except Exception as e:
            messagebox.showerror("Generation failed", str(e))

    def run_error_generation_action():
        try:
            video_err = video_enabled.get() and (video_mode_var.get() == "Error Stream Generator")
            audio_err = audio_enabled.get() and (audio_mode_var.get() == "Error Stream Generator")
            if not (video_err or audio_err):
                messagebox.showwarning("Mode", "Select Error Stream Generator in Video or Audio tab."); return
            final_out_dir = output_path_var.get().strip() or str(Path.cwd())
            tmp_dir = str(Path(final_out_dir) / ".tmp_vts"); Path(tmp_dir).mkdir(parents=True, exist_ok=True)
            #duration_sec_ui = int(float(duration_var.get().strip() or 10))
            duration_val = _safe_var_str(duration_var)
            frames_val = _safe_var_str(frame_count_var)
            if duration_val and frames_val:
                messagebox.showerror("Input Error", "Select either Duration OR Frames, not both.")
                return
            if not duration_val and not frames_val:
                messagebox.showerror("Input Error", "Enter either Duration OR Frames.")
                return
            duration_sec_ui = int(float(duration_val)) if duration_val else None
            frames_count_ui = int(frames_val) if frames_val else None
            if duration_sec_ui is None and frames_count_ui is not None:
                # derive duration for naming/stats when user chose frame-count mode
                # actual encoding still uses -frames option
                duration_sec_ui = _derive_duration_from_frames(frames_count_ui, vid_dict=vid_combos[0] if 'vid_combos' in locals() and vid_combos else None, aud_dict=aud_combos[0] if 'aud_combos' in locals() and aud_combos else None)
            gop_sec = float(gop_size_var.get().strip() or 1)
            key_sec = float(keyint_var.get().strip() or 1)
            volume = float(volume_var.get().strip() or 1.0)
            vid_combos = []; aud_combos = []
            if video_enabled.get():
                sel_v = _get_selected_lists(video_options); vid_combos = _expand_video_combos(sel_v)
                if vid_combos:
                    for v in vid_combos: v['gop_size'] = gop_sec; v['key_sec'] = key_sec
            if audio_enabled.get():
                sel_a = _get_selected_lists(audio_options); aud_combos = _expand_audio_combos(sel_a)
            picker_v = state.get('error_picker', None)
            picker_a = state.get('audio_error_picker', None)
            modes_v_all = picker_v.get_selected_list() if (video_err and picker_v) else []
            modes_a_all = picker_a.get_selected_list() if (audio_err and picker_a) else []
            if video_err and not modes_v_all:
                messagebox.showwarning("Video Error Types", "Select at least one video error type."); video_err = False
            if audio_err and not modes_a_all:
                messagebox.showwarning("Audio Error Types", "Select at least one audio error type."); audio_err = False
            if not (video_err or audio_err): return
            base_param_sets = []
            if vid_combos and aud_combos:
                base_param_sets = [(v, a) for v,a in product(vid_combos, aud_combos)]
            elif vid_combos:
                base_param_sets = [(v, None) for v in vid_combos]
            elif aud_combos:
                base_param_sets = [(None, a) for a in aud_combos]
            else:
                messagebox.showerror("Params", "Please select at least video or audio parameters for Error mode."); return
            # If frame-count mode selected, derive duration for naming/stats
            if frames_count_ui and (not duration_sec_ui or int(duration_sec_ui) == 0):
                duration_sec_ui = _derive_duration_from_frames(frames_count_ui, vid_dict=vid_combos[0] if vid_combos else None, aud_dict=aud_combos[0] if aud_combos else None)
                if not duration_sec_ui:
                    duration_sec_ui = 0

            final_count = 0
            # FIX: ensure selected_fmt always defined
            # FIX: ensure vid_dict and aud_dict always defined
            # FIX: ensure v_input and a_input always defined
            # FIX: ensure v_source and a_source always defined
            v_source = v_source if 'v_source' in locals() else 'testsrc'
            a_source = a_source if 'a_source' in locals() else 'sine'
            v_input = v_input if 'v_input' in locals() else None
            a_input = a_input if 'a_input' in locals() else None
            vid_dict = vid_dict if 'vid_dict' in locals() else None
            aud_dict = aud_dict if 'aud_dict' in locals() else None
            selected_fmt = (fileformat_var.get().strip() if 'fileformat_var' in locals() else (selected_fmt if 'selected_fmt' in locals() else ''))

            
            # ================= RAW ERROR STREAM HANDLING (INSIDE COMBO LOGIC) =================
            # NOTE: VET/AET corruption modes are byte-level, not FFmpeg filters.
            # For RAW error streams we:
            #   1) Generate a clean RAW elementary stream
            #   2) Apply selected error modes in windows on the raw bytes
            #   3) Write corrupted RAW outputs (no remux)
            if selected_fmt == 'raw':
                # Enforce RAW rule: Video OR Audio only
                if vid_combos and aud_combos:
                    messagebox.showerror(
                        "RAW Error Stream",
                        "RAW error streams support only Video OR Audio. Please select only one.")
                    return

                v_input = video_input_var.get().strip() or None
                a_input = audio_input_var.get().strip() or None
                v_source = video_source_var.get().strip() or video_test_sources[0]
                a_source = audio_source_var.get().strip() or audio_test_sources[0]

                picker_v = state.get('error_picker', None)
                picker_a = state.get('audio_error_picker', None)
                modes_v_all = picker_v.get_selected_list() if (video_err and picker_v) else []
                modes_a_all = picker_a.get_selected_list() if (audio_err and picker_a) else []

                # derive duration if needed for windows
                total_sec = int(duration_sec_ui or 0)
                if total_sec <= 0:
                    total_sec = int(duration_sec_ui or 10)
                windows = _compute_error_windows(total_sec)

                # RAW Video-only
                if vid_combos:
                    if not modes_v_all:
                        messagebox.showwarning("Video Error Types", "Select at least one video error type for RAW.")
                        return
                    for vid_dict in vid_combos:
                        codec = (vid_dict.get('Codec') if vid_dict else None)
                        allowed = _allowed_video_error_modes([codec] if codec else [])
                        modes_v = [m for m in modes_v_all if m in allowed] if allowed else list(modes_v_all)
                        if not modes_v:
                            messagebox.showwarning("Video Error Types", f"No applicable video error types for {codec}.")
                            continue

                        base_cmd, base_path = generate_ffmpeg_command(
                            vid_dict=vid_dict,
                            aud_dict=None,
                            video_input=v_input,
                            audio_input=None,
                            video_source=v_source,
                            audio_source='sine',
                            duration_sec=duration_sec_ui,
                            frames_count=frames_count_ui,
                            volume=volume,
                            file_format='raw',
                            output_dir=tmp_dir,
                            error_enabled=False
                        )
                        base_cmd = _normalise_ffmpeg_cmd(base_cmd)
                        print('[ErrorMode][RAW][Video] Base:', ' '.join(base_cmd))
                        subprocess.run(base_cmd, check=True)

                        raw_bytes = Path(base_path).read_bytes()
                        VET.CURRENT_VIDEO_CODEC = codec
                        try:
                            VET.CURRENT_FPS_HINT = float(vid_dict.get('Framerate')) if vid_dict and vid_dict.get('Framerate') else None
                        except Exception:
                            VET.CURRENT_FPS_HINT = None

                        for mv in modes_v:
                            vdata = VET.apply_video_mode_in_windows(mv, raw_bytes, total_sec, windows)
                            stats = get_stream_info(base_path) or {}
                            if int(stats.get('duration_sec',0) or 0) == 0:
                                stats['duration_sec'] = int(duration_sec_ui or duration_sec or 0)
                            out_file = _make_raw_error_name(base_path, mv, stats, output_dir=final_out_dir)
                            Path(out_file).write_bytes(vdata)
                            print('[ErrorMode][RAW][Video] Corrupted:', out_file)
                            final_count += 1

                    if final_count == 0:
                        messagebox.showwarning("Error Mode", "No RAW video error streams produced.")
                    else:
                        messagebox.showinfo("RAW Error Streams", f"RAW error streams generated: {final_count} \nOutput directory:{final_out_dir}")
                    return

                # RAW Audio-only
                if aud_combos:
                    if not modes_a_all:
                        messagebox.showwarning("Audio Error Types", "Select at least one audio error type for RAW.")
                        return
                    for aud_dict in aud_combos:
                        a_codec = aud_dict.get('Codec') if aud_dict else None
                        allowed_by_codec = set(getattr(AET, 'GENERIC_AUDIO_ERROR_MODES', []))
                        if a_codec == 'aac': allowed_by_codec |= set(getattr(AET, 'AAC_AUDIO_SPECIFIC_MODES', []))
                        if a_codec == 'mp3': allowed_by_codec |= set(getattr(AET, 'MP3_AUDIO_SPECIFIC_MODES', []))
                        if a_codec == 'ac3': allowed_by_codec |= set(getattr(AET, 'AC3_AUDIO_SPECIFIC_MODES', []))
                        if a_codec == 'eac3': allowed_by_codec |= set(getattr(AET, 'EAC3_AUDIO_SPECIFIC_MODES', []))
                        if a_codec == 'flac': allowed_by_codec |= set(getattr(AET, 'FLAC_AUDIO_SPECIFIC_MODES', []))
                        if a_codec == 'pcm_s16le': allowed_by_codec |= set(getattr(AET, 'PCM_AUDIO_SPECIFIC_MODES', []))
                        if a_codec == 'libvorbis': allowed_by_codec |= set(getattr(AET, 'VORBIS_AUDIO_SPECIFIC_MODES', []))
                        if a_codec == 'libopus': allowed_by_codec |= set(getattr(AET, 'OPUS_AUDIO_SPECIFIC_MODES', []))
                        modes_a = [m for m in modes_a_all if m in allowed_by_codec] if allowed_by_codec else list(modes_a_all)
                        if not modes_a:
                            messagebox.showwarning("Audio Error Types", f"No applicable audio error types for {a_codec}.")
                            continue

                        base_cmd, base_path = generate_ffmpeg_command(
                            vid_dict=None,
                            aud_dict=aud_dict,
                            video_input=None,
                            audio_input=a_input,
                            video_source='testsrc',
                            audio_source=a_source,
                            duration_sec=duration_sec_ui,
                            frames_count=frames_count_ui,
                            volume=volume,
                            file_format='raw',
                            output_dir=tmp_dir,
                            error_enabled=False
                        )
                        base_cmd = _normalise_ffmpeg_cmd(base_cmd)
                        print('[ErrorMode][RAW][Audio] Base:', ' '.join(base_cmd))
                        subprocess.run(base_cmd, check=True)

                        raw_bytes = Path(base_path).read_bytes()
                        for ma in modes_a:
                            adata = AET.apply_audio_mode_in_windows(ma, raw_bytes, total_sec, windows)
                            out_file = str(Path(final_out_dir) / f"{Path(base_path).stem}__{ma}{Path(base_path).suffix}")
                            Path(out_file).write_bytes(adata)
                            print('[ErrorMode][RAW][Audio] Corrupted:', out_file)
                            final_count += 1

                    if final_count == 0:
                        messagebox.showwarning("Error Mode", "No RAW audio error streams produced.")
                    else:
                        messagebox.showinfo("RAW Error Streams", f"RAW error streams generated: {final_count} \nOutput directory:{final_out_dir}")
                    return

            # ================= END RAW ERROR STREAM HANDLING =================

            v_outfile = None

            v_input = video_input_var.get().strip()
            a_input = audio_input_var.get().strip()
            # Cross-use embedded tracks when in Video-only or Audio-only mode
            # Apply ONLY if the selected file contains BOTH audio and video. Otherwise show an error.
            if video_enabled.get() and (not audio_enabled.get()) and (not v_input) and a_input:
                info = _probe_stream_types(a_input)
                if info.get('has_video') and info.get('has_audio'):
                    v_input = a_input
                elif info.get('has_audio') and (not info.get('has_video')):
                    messagebox.showerror('Input Error', 'Selected only audio file but no video track present. Please select a video file with video.'); return
            if audio_enabled.get() and (not video_enabled.get()) and (not a_input) and v_input:
                info = _probe_stream_types(v_input)
                if info.get('has_audio') and info.get('has_video'):
                    a_input = v_input
                elif info.get('has_video') and (not info.get('has_audio')):
                    messagebox.showerror('Input Error', 'Selected only video file but no audio track present. Please select an audio file with audio.'); return
            # Auto-fill missing input when both Audio and Video are enabled
            # If only one of the files is selected and it contains BOTH audio and video,
            # reuse it for the unselected side instead of using synthetic sources.
            if video_enabled.get() and audio_enabled.get():
                if v_input and (not a_input):
                    info = _probe_stream_types(v_input)
                    if info.get('has_audio') and info.get('has_video'):
                        a_input = v_input
                elif a_input and (not v_input):
                    info = _probe_stream_types(a_input)
                    if info.get('has_audio') and info.get('has_video'):
                        v_input = a_input
                # Refresh labels if helpers exist
                try:
                    _refresh_video_input_label()
                    _refresh_audio_input_label()
                except Exception:
                    pass

            v_source = video_source_var.get().strip() or video_test_sources[0]
            a_source = audio_source_var.get().strip() or audio_test_sources[0]
            for (vid_dict, aud_dict) in base_param_sets:
                selected_fmt = fileformat_var.get().strip() or ""
                if (selected_fmt or '').strip().lower() == 'raw':
                    continue
                base_cmd, base_path = generate_ffmpeg_command(
                    vid_dict, aud_dict,
                    video_input=v_input, audio_input=a_input,
                    video_source=v_source, audio_source=a_source,
                    duration_sec=duration_sec_ui, frames_count=frames_count_ui, volume=volume,
                    file_format=selected_fmt, output_dir=tmp_dir,
                )
                print("[ErrorMode] Base gen:", " ".join(base_cmd)); subprocess.run(base_cmd, check=True)
                stats_base = get_stream_info(base_path)
                total_sec = (stats_base['duration_sec'] if stats_base else duration_sec_ui)
                windows = _compute_error_windows(total_sec)
                print(f"[ErrorMode] Windows (sec): {windows} (total={total_sec}s)")
                v_raw_path = v_fmt = v_ext = None
                a_raw_path = a_demux = a_ext = None
                video_err_local = False; audio_err_local = False
                if video_err and vid_dict:
                    codec = vid_dict['Codec']
                    # Dynamic video raw mapping with muxer fallback
                    fmt_mpeg = 'mpeg'
                    ext_m1  = '.mpg'
                    ext_m2  = '.mpg'
                    v_map = {
                            'libx264': ('h264', '.h264'),
                            'libx265': ('hevc', '.h265'),
                            'libvpx-vp9': ('ivf', '.ivf'),
                            'libsvtav1': ('ivf', '.ivf'),
                            'mpeg1video': (fmt_mpeg, ext_m1),
                            'mpeg2video': (fmt_mpeg, ext_m2),
                            'mpeg4': ('m4v','.m4v'),
                            'wmv2': ('asf', '.asf'),
                            }
                    v_fmt, v_ext = v_map.get(codec, (None, None))
                    if v_fmt:
                        v_raw_path = str(Path(tmp_dir) / (Path(base_path).stem + v_ext))
                        subprocess.run(["ffmpeg", "-y", "-i", base_path, "-c:v", "copy", "-an", "-f", v_fmt, v_raw_path], check=True)
                        print(f"[ErrorMode] Video raw extracted: {v_raw_path} ({v_fmt})"); video_err_local = True
                    else:
                        messagebox.showwarning("Video Error", f"Raw conversion not supported for codec: {codec}")
                    modes_v_allowed = _allowed_video_error_modes([codec])
                    modes_v_allowed = [m for m in modes_v_all if m in modes_v_allowed]
                    invalid = [m for m in modes_v_all if m not in modes_v_allowed]
                    if invalid:
                        messagebox.showwarning("Video Error Types", f"Some selected video error types are not applicable to {codec} and were skipped: {', '.join(invalid)}")
                if (not video_err) and vid_dict and v_raw_path is None:
                    try:
                        codec_main = vid_dict['Codec']
                        # Dynamic video raw mapping (main) with muxer fallback
                        fmt_mpeg = 'mpeg'
                        ext_m1  = '.mpg'
                        ext_m2  = '.mpg'
                        v_map_main = {
                                    'libx264': ('h264', '.h264'),
                                    'libx265': ('hevc', '.h265'),
                                    'libvpx-vp9': ('ivf', '.ivf'),
                                    'libsvtav1': ('ivf', '.ivf'),
                                    'mpeg1video': (fmt_mpeg, ext_m1),
                                    'mpeg2video': (fmt_mpeg, ext_m2),
                                    'mpeg4': ('m4v','.m4v'),
                                    'wmv2': ('asf', '.asf'),
                                    }
                        v_fmt, v_ext = v_map_main.get(codec_main, (None, None))
                        if v_fmt:
                            v_raw_path = str(Path(tmp_dir) / (Path(base_path).stem + v_ext))
                            subprocess.run(["ffmpeg", "-y", "-i", base_path, "-c:v", "copy", "-an", "-f", v_fmt, v_raw_path], check=True)
                            print(f"[ErrorMode] Video raw prepared from base (no corruption): {v_raw_path} ({v_fmt})")
                    except Exception as ex:
                        print(f"[ErrorMode] Video raw preparation skipped ({ex})")
                if audio_err and aud_dict and aud_dict.get('Codec'):
                    a_codec = aud_dict.get('Codec')
                    mux_fmt, a_ext = AET.codec_to_audio_mux_and_ext(a_codec)
                    a_demux, _ = AET.codec_to_audio_demux_and_ext(a_codec)
                    if mux_fmt and a_demux:
                        a_raw_path = str(Path(tmp_dir) / (Path(base_path).stem + a_ext))
                        AET.extract_raw_audio_by_codec(base_path, a_codec, a_raw_path)
                        print(f"[ErrorMode] Audio raw extracted: {a_raw_path} (mux={mux_fmt}, demux={a_demux})"); audio_err_local = True
                    else:
                        messagebox.showwarning("Audio Error", f"Unsupported audio codec for corruption: {a_codec}")
                    allowed_by_codec = set(AET.GENERIC_AUDIO_ERROR_MODES)
                    if a_codec == 'aac': allowed_by_codec |= set(AET.AAC_AUDIO_SPECIFIC_MODES)
                    if a_codec == 'mp3': allowed_by_codec |= set(AET.MP3_AUDIO_SPECIFIC_MODES)
                    if a_codec == 'ac3': allowed_by_codec |= set(AET.AC3_AUDIO_SPECIFIC_MODES)
                    if a_codec == 'eac3': allowed_by_codec |= set(AET.EAC3_AUDIO_SPECIFIC_MODES)
                    if a_codec == 'flac': allowed_by_codec |= set(AET.FLAC_AUDIO_SPECIFIC_MODES)
                    if a_codec == 'pcm_s16le': allowed_by_codec |= set(AET.PCM_AUDIO_SPECIFIC_MODES)
                    if a_codec == 'libvorbis': allowed_by_codec |= set(AET.VORBIS_AUDIO_SPECIFIC_MODES)
                    if a_codec == 'libopus': allowed_by_codec |= set(AET.OPUS_AUDIO_SPECIFIC_MODES)
                    invalid_a = [m for m in modes_a_all if m not in allowed_by_codec]
                    if invalid_a:
                        messagebox.showwarning("Audio Error Types", f"Some selected audio error types are not applicable to {a_codec} and were skipped: {', '.join(invalid_a)}")
                    modes_a_filtered = [m for m in modes_a_all if m in allowed_by_codec]
                else:
                    modes_a_filtered = []
                corrupted_pairs = []
                if video_err_local and v_raw_path and modes_v_allowed:
                    orig_v = Path(v_raw_path).read_bytes()
                    VET.CURRENT_VIDEO_CODEC = (vid_dict.get('Codec') if vid_dict else None)
                    try:
                        VET.CURRENT_FPS_HINT = float(vid_dict.get('Framerate')) if vid_dict and vid_dict.get('Framerate') else None
                    except Exception:
                        VET.CURRENT_FPS_HINT = None
                    for mv in modes_v_allowed:
                        vdata = VET.apply_video_mode_in_windows(mv, orig_v, total_sec, windows)
                        VET.CURRENT_ERROR_WINDOWS = None
                        v_outfile = str(Path(tmp_dir) / f"{Path(base_path).stem}__{mv}{v_ext}")
                        Path(v_outfile).write_bytes(vdata)
                        if audio_err_local and a_raw_path and modes_a_filtered:
                            orig_a = Path(a_raw_path).read_bytes()
                            for ma in modes_a_filtered:
                                adata = AET.apply_audio_mode_in_windows(ma, orig_a, total_sec, windows)
                                a_out = str(Path(tmp_dir) / f"{Path(base_path).stem}__{ma}{a_ext}")
                                Path(a_out).write_bytes(adata)
                                corrupted_pairs.append((v_outfile, a_out, a_demux, f"__{mv}__{ma}"))
                        else:
                            if audio_enabled.get() and aud_dict:
                                # Keep MAIN audio from the clean base container when only video is corrupted
                                corrupted_pairs.append((v_outfile, base_path, None, f"__{mv}"))
                            else:
                                corrupted_pairs.append((v_outfile, None, None, f"__{mv}"))
                elif audio_err_local and a_raw_path and modes_a_filtered:
                    orig_a = Path(a_raw_path).read_bytes()
                    for ma in modes_a_filtered:
                        adata = AET.apply_audio_mode_in_windows(ma, orig_a, total_sec, windows)
                        a_out = str(Path(tmp_dir) / f"{Path(base_path).stem}__{ma}{a_ext}")
                        Path(a_out).write_bytes(adata)
                        vfile_for_audio_only = v_raw_path if v_raw_path else None
                        corrupted_pairs.append((vfile_for_audio_only, a_out, a_demux, f"__{ma}"))
                if not corrupted_pairs:
                    messagebox.showwarning("Error Mode", "No corrupted raws produced for this parameter set."); continue
                final_fmt = selected_fmt or "mp4"
                for v_out, a_out, ademux, suffix in corrupted_pairs:
                    chosen_final_fmt = final_fmt
                    # Force TS for MPEG1/2 error streams; 
                    try:
                         if vid_dict and vid_dict.get('Codec') in ('mpeg1video','mpeg2video') and ('pts-dts-corruption' in suffix or 'mpeg2-motion-vector-field-corruption' in suffix):
                             chosen_final_fmt = 'ts'
                    except Exception:
                        pass
                    # Force TS for HEVC parameter-set corruption modes to avoid MP4 hvcc/extradata failures
                    try:
                        if vid_dict and vid_dict.get('Codec') == 'libx265' and (
                            'hevc-scaling-list-corruption' in suffix or
                            'hevc-vps-corruption' in suffix
                        ):
                            chosen_final_fmt = 'ts'
                    except Exception:
                        pass
                    if chosen_final_fmt == "webm":
                        # WebM supports only VP9/AV1 video and Vorbis/Opus audio.
                        if v_out and v_fmt in ('h264','hevc'):
                            chosen_final_fmt = "mp4"
                        if a_out and chosen_final_fmt == "webm":
                            if ademux is not None:
                                if ademux not in ('ogg',):
                                    chosen_final_fmt = "mp4"
                            else:
                                # Audio comes from a container (base file). Decide using selected audio codec.
                                if not (aud_dict and aud_dict.get('Codec') in ('libvorbis','libopus')):
                                    chosen_final_fmt = "mp4"
                    # Additional guard: avoid invalid MP4 muxes
                    mp4_ok_audio_demux = ('adts','mp3','ac3','eac3')
                    mp4_ok_audio_codec = ('aac','mp3','ac3','eac3')
                    if a_out and chosen_final_fmt == 'mp4':
                        # When audio is provided as RAW (ademux set), validate using demux.
                        # When audio comes from a container (ademux None), validate using selected codec.
                        ok_mp4_audio = (ademux in mp4_ok_audio_demux) if (ademux is not None) else (aud_dict and aud_dict.get('Codec') in mp4_ok_audio_codec)
                        if not ok_mp4_audio:
                            if aud_dict and aud_dict.get('Codec') == 'aac':
                                chosen_final_fmt = 'mp4'
                            else:
                                chosen_final_fmt = 'webm' if (ademux or '') in ('ogg',) else 'mkv'
                    base_stem = Path(base_path).stem
                    final_out = Path(final_out_dir) / f"{base_stem}{suffix}.{chosen_final_fmt}"
                    if v_out and v_fmt == 'h264' and not a_out:
                        ok = _remux_from_raw_h264(v_out, str(final_out), audio_src=base_path if audio_enabled.get() else None)
                    else:
                        ok = _remux_video_audio_raw(v_out, v_fmt if v_out else None, a_out, ademux if a_out else None, str(final_out), chosen_final_fmt)
                    if ok:
                        stats = get_stream_info(str(final_out))
                        if not stats or stats.get('video_frames', 0) == 0:
                            stats = _fallback_stats_from_params(duration_sec if 'duration_sec' in locals() else total_sec, vid_dict, aud_dict)
                        new_name = _rename_error_output(str(final_out), base_stem, suffix, stats or {'audio_frames':0,'video_frames':0,'duration_sec':total_sec})
                        print(f'[ErrorMode] Final corrupted stream: {new_name}'); final_count += 1
                    else:
                        messagebox.showwarning("Remux", f"Failed to mux: {final_out}")
            if final_count == 0:
                messagebox.showwarning("Error Mode", "No final corrupted outputs produced."); return
            print(f"Error streams generated: {final_count} \n Output: {final_out_dir}")
            messagebox.showinfo("Corrupted Streams", f"Error streams generated: {final_count}\nOutput directory:\n{final_out_dir}\nIntermediates in:\n{tmp_dir}")
            print("Tip: Use ffplay with '-loglevel debug -err_detect aggressive -vf showinfo' to see decoder warnings.")
            # Example: ffplay -loglevel debug -err_detect aggressive -vf showinfo <outputfile>
        except Exception as e:
            messagebox.showerror("Error Generation failed", str(e))
    # Button bar
    button_frame = ttk.Frame(root, padding=15); button_frame.pack(fill='x')
    primary_btn = ttk.Button(button_frame, text="🎬 Generate Stream(s)", style="Custom.TButton", command=generate_ffmpeg_action)
    primary_btn.pack(pady=10)

    def on_mode_change(*_):
        try:
            if video_mode_var.get() == "Error Stream Generator" and video_enabled.get():
                error_label.grid(); error_in_video_frame.grid()
            else:
                error_label.grid_remove(); error_in_video_frame.grid_remove()
        except Exception:
            pass
        try:
            if audio_mode_var.get() == "Error Stream Generator" and audio_enabled.get():
                audio_error_label.grid(); audio_error_frame.grid()
            else:
                audio_error_label.grid_remove(); audio_error_frame.grid_remove()
        except Exception:
            pass
        if (video_mode_var.get() == "Error Stream Generator" and video_enabled.get()) or \
           (audio_mode_var.get() == "Error Stream Generator" and audio_enabled.get()):
            primary_btn.configure(text="⚠️ Generate Error Stream(s)", command=run_error_generation_action)
        else:
            primary_btn.configure(text="🎬 Generate Stream(s)", command=generate_ffmpeg_action)

    video_mode_combo.bind("<<ComboboxSelected>>", on_mode_change)
    audio_mode_combo.bind("<<ComboboxSelected>>", on_mode_change)

    def on_toggle(*_): on_mode_change()
    video_enabled.trace_add('write', on_toggle); audio_enabled.trace_add('write', on_toggle)

    # Final sweep to ensure all Listboxes keep independent selections
    _ensure_listbox_export_off(root)
    return locals()

if __name__ == "__main__":
    if not _ffmpeg_exists():
        print("FFmpeg/ffprobe not found in PATH. Please install FFmpeg and retry."); sys.exit(1)
    try:
        ui = build_ui(); ui['on_mode_change'](); ui['root'].mainloop()
    except tk.TclError:
        print("Tkinter failed to open a window (likely no DISPLAY). Run this script on a system with a GUI."); sys.exit(1)

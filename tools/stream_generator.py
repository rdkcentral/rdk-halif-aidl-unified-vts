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

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import itertools
from pathlib import Path
import math
import os
import json
import sys
from Combopicker import Combopicker

# -------------------------------
# Default parameter options
# -------------------------------
video_params = {
    "Resolution": ["3840x2160", "2560x1440", "1920x1080", "1280x720", "960x540", "720x480", "720x576", "640x360", "320x240"],
    "Codec": ["libx264", "libx265", "mpeg1video", "mpeg2video", "vp9"],
    "Profile": ["main", "main10", "None"],
    "Framerate": [23.976, 24, 25, 29.97, 30, 50, 59.94, 60],
    "Dynamic Range": ["SDR", "HDR10", "HDR10+", "HLG"],
    "Color Space": ["BT.601", "BT.709", "BT.2020"],
    "pixel Format": ["yuv444p", "yuv422p", "yuv420p"],
    "Frame Type": ["Progressive", "Interlaced"],
    "Bitrate": ["300k", "700k", "1M", "1.5M", "2.5M", "5M", "8M", "10M", "12M", "15M", "18M", "20M" , "25M", "35M", "60M"]
}

audio_params = {
    "Codec": ["aac", "mp3", "ac3", "flac", "pcm_s16le","eac3","libopus"],
    "Sample Rate": [8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000, 64000, 88200, 96000],
    "Channels": [1, 2, 3, 6, 8],
    "Bitrate": ["32k", "64k", "128k", "256k", "512k", "1024k"]
}

samplerate_mapping = {
    8000: "8k",
    11025: "11.025k",
    12000: "12k",
    16000: "16k",
    22050: "22.05k",
    24000: "24k",
    32000: "32k",
    44100: "44.1k",
    48000: "48k",
    64000: "64k",
    88200: "88.2k",
    96000: "96k"
}

fileformat_mapping = {
    "libx264": "h264",
    "libx265": "h265",
    "mpeg1video": "mpg",
    "mpeg2video": "mpg",
    "av1": "av1",
    "wmv": "wmv",
    "vp9":"vp9",
    "aac": "aac",
    "mp3": "mp3",
    "ac3": "ac3",
    "eac3" : "ec3",
    "opus":"opus",
    "pcm_s16le": "wav",
    "flac": "flac",
    "wma": "wma"
}

video_test_sources = ["testsrc", "testsrc2", "smptebars", "rgbtestsrc", "pal100bars", "color_red", "color_blue", "color_green", "color_yellow", "color_white", "color_black"]
audio_test_sources = ["sine", "anoisesrc", "sweep"]

duration = 5  # seconds

# Color parameters generator (from previous logic)
def get_color_params(video_selection):
    codec = video_selection.get("Codec", "libx264")
    profile = video_selection.get("Profile", "main")
    dynamic_range = video_selection.get("Dynamic Range", "SDR")
    colorspace = video_selection.get("Color Space", "BT.709")

    # Validation
    if dynamic_range in ["HDR10", "HDR10+", "HLG"] and codec != "libx265":
        return None, f"Invalid combination: HDR requires libx265"
    if codec in ["libx264", "libx265"]:
        if profile == "None":
            return None, f"Invalid combination: Profile cannot be None for {codec}"
        if dynamic_range in ["HDR10", "HDR10+", "HLG"] and profile != "main10":
            return None, f"Invalid combination: HDR requires main10 profile"

    # Pixel format selection
    if dynamic_range in ["HDR10", "HDR10+", "HLG"]:
        pix_fmt = "yuv420p10le"
    else:
        pix_fmt =  video_selection.get("pixel Format", "yuv420p")


    color_param = {
        "pix_fmt": pix_fmt
    }

    # Color mapping
    if dynamic_range == "SDR":
        color_param.update({
            "color_trc": "bt709"
        })
        if colorspace == "BT.709":
            color_param.update({
                "color_primaries": "bt709",
                "colorspace": "bt709"
            })
        if colorspace == "BT.2020":
            color_param.update({
                "color_primaries": "bt2020",
                "colorspace": "bt2020_ncl"
            })

    elif dynamic_range == "HDR10":
        color_param.update({
            "color_primaries": "bt2020",
            "color_trc": "smpte2084",
            "colorspace": "bt2020nc"
        })
    elif dynamic_range == "HDR10+":
        color_param.update({
            "color_primaries": "bt2020",
            "color_trc": "smpte2084",
            "colorspace": "bt2020nc",
            "x265_params": "hdr10=1:hdr10_opt=1:repeat-headers=1:colormatrix=bt2020nc",
            "master_display": "G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,50)",
            "max_cll": "1000,400"
        })
    elif dynamic_range == "HLG":
        color_param.update({
            "color_primaries": "bt2020",
            "color_trc": "arib-std-b67",
            "colorspace": "bt2020nc"
        })

    return color_param, None

def generate_ffmpeg_command(vid_dict=None, aud_dict=None, video_input="", audio_input="",
                            video_source="testsrc", audio_source="sine",
                            duration_sec=100, volume=1.0, file_format="mp4", output_dir=""):
    """
    Generate ffmpeg command and output filename based on video/audio dict availability
    """

    if not output_dir:
        output_dir = os.path.dirname(os.path.realpath(__file__))

    if not vid_dict and not aud_dict:
        raise ValueError("Both vid_dict and aud_dict cannot be empty")

    cmd = ["ffmpeg", "-y"]
    output_file_parts = ["vts"]
    video_src_cmd = []
    video_opt_cmd = []
    audio_src_cmd = []
    audio_opt_cmd = []

    # ---------- VIDEO ----------
    if vid_dict:
        color_param, err = get_color_params(vid_dict)
        if err:
            print(err)
            return None, None

        framerate = float(vid_dict["Framerate"])

        # Video input
        if video_input:
            video_src_cmd = ["-i", video_input]
        else:
            coloropt = ""
            if ("color" in video_source):
                coloropt = ":c=" + video_source.split("_")[1]
                video_source = "color"

            video_src_cmd = ["-f", "lavfi", "-i", f"{video_source}=rate={framerate}:size={vid_dict['Resolution']}:duration={duration_sec}{coloropt}"]

        # Options
        video_opt_cmd = ["-c:v", vid_dict["Codec"],
                "-b:v", vid_dict["Bitrate"],
                "-r", str(framerate),
                "-pix_fmt", color_param["pix_fmt"],
                "-color_primaries", color_param["color_primaries"],
                "-color_trc", color_param["color_trc"],
                "-colorspace", color_param["colorspace"]]

        if(vid_dict["Frame Type"] == "Interlaced"):
            if vid_dict["Codec"] == "libx264" or vid_dict["Codec"] == "libx265":
                video_opt_cmd += ["-vf", "tinterlace=interleave_top", "-x264opts", "tff=1", "-flags", "+ildct+ilme"]
            elif vid_dict["Codec"] == "mpeg2video":
                video_opt_cmd += ["-vf", "tinterlace=interleave_top", "-flags", "+ildct+ilme", "-top", "1"]

        if "x265_params" in color_param:
            video_opt_cmd += ["-x265-params", color_param["x265_params"],
                    "-master-display", color_param["master_display"],
                    "-max-cll", color_param["max_cll"]]

        gop_size_frames = int(math.ceil(vid_dict["gop_size"] * float(vid_dict["Framerate"])))
        key_frames = int(math.ceil(vid_dict["key_sec"] * float(vid_dict["Framerate"])))

        video_opt_cmd += ["-g", str(gop_size_frames), "-keyint_min", str(key_frames), "-sc_threshold", "0"]

        # File name parts
        res_label = vid_dict["Resolution"].split("x")[1]
        if(vid_dict["Frame Type"] == "Progressive"):
            res_label += "p"
        else:
            res_label += "i"
        #res_label = vid_dict["Resolution"].replace("x", "p")
        output_file_parts += [
            vid_dict['Codec'].replace("libx", "h").replace("video", ""),  # h264, h265
            res_label,
            vid_dict['Dynamic Range'].lower(),
            f"{framerate}f",
            vid_dict['Color Space'].replace(".", ""),
            vid_dict['pixel Format'].replace(":", ""),
            vid_dict['Bitrate']
        ]

    # ---------- AUDIO ----------
    if aud_dict:
        #num_audio_frames = int(duration_sec * int(aud_dict.get("Sample Rate", 48000)))

        # Audio input
        if audio_input:
            audio_src_cmd = ["-i", audio_input]
        else:
            if(audio_source == "sine"):
                audio_src_cmd = ["-f", "lavfi", "-i", f"{audio_source}=frequency=1000:sample_rate={aud_dict['Sample Rate']}:duration={duration_sec}"]
            elif(audio_source == "anoisesrc"):
                audio_src_cmd = ["-f", "lavfi", "-i", f"{audio_source}=sample_rate={aud_dict['Sample Rate']}:duration={duration_sec}:c=pink"]
            elif(audio_source == "sweep"):
                audio_src_cmd = ["-f", "lavfi", "-i", f"aevalsrc=sin(2*PI*(20+(20000-20)*t/10)*t):s={aud_dict['Sample Rate']}"]

        # Options
        audio_opt_cmd = ["-c:a", aud_dict["Codec"],
                "-ar", str(aud_dict["Sample Rate"]),
                "-ac", str(aud_dict["Channels"]),
                "-b:a", aud_dict["Bitrate"],
                "-filter:a", f"volume={volume}"]

        if (aud_dict["Codec"] == "opus"):
            audio_opt_cmd+= ["-l"]

        # File name parts
        output_file_parts += [
            aud_dict['Codec'],
            samplerate_mapping[int(aud_dict['Sample Rate'])],
            f"{aud_dict['Channels']}ch",
            aud_dict['Bitrate']
        ]

    # ---------- COMMON ----------
    #output_file_parts.append(f"{duration_sec}sec")
    output_file = "_".join(output_file_parts) + "." + file_format
    output_path = os.path.join(output_dir, output_file)

    cmd += video_src_cmd
    cmd += audio_src_cmd
    cmd += video_opt_cmd
    cmd += audio_opt_cmd

    cmd += ["-t", str(duration_sec), output_path]

    return cmd, output_path

def get_stream_info(file_path):
    """
    Extracts the duration, video frame count, and audio frame count from a media file.

    Args:
        file_path (str): The path to the media file.

    Returns:
        dict: A dictionary containing 'duration_sec', 'audio_frames', and 'video_frames'.
              Returns None if an error occurs.
    """
    try:
        command = [
            "ffprobe",
            "-v", "quiet",
            "-count_frames",
            "-select_streams", "v:0",
            "-print_format", "json",
            "-show_entries", "format=duration:stream=codec_type,nb_read_frames",
            file_path
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        data = json.loads(result.stdout)

        duration = float(data['format']['duration'])
        duration_sec = math.ceil(duration)

        video_frames = 0
        audio_frames = 0

        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                video_frames = int(stream.get('nb_read_frames', 0))

        command = [
            "ffprobe",
            "-v", "quiet",
            "-count_packets",
            "-select_streams", "a:0",
            "-print_format", "json",
            "-show_entries", "stream=codec_type,nb_read_packets",
            file_path
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        data = json.loads(result.stdout)

        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'audio':
                audio_frames = int(stream.get('nb_read_packets', 0))

        return {
            'duration_sec': duration_sec,
            'audio_frames': audio_frames,
            'video_frames': video_frames
        }

    except FileNotFoundError:
        print("Error: 'ffprobe' not found. Ensure FFmpeg is installed and in your system's PATH.", file=sys.stderr)
        return None
    except subprocess.CalledProcessError as e:
        print(f"ffprobe failed with error: {e.stderr}", file=sys.stderr)
        return None
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error parsing ffprobe output: {e}", file=sys.stderr)
        return None

def rename_file_with_stats(filename: str, stats: dict) -> str:
    """
    Rename filename by appending audio frames, video frames, and duration.

    Example:
      input:  vts_264_1920p1080_sdr.mp4
      stats:  {'duration_sec': 60, 'audio_frames': 100, 'video_frames': 100}
      output: vts_264_1920p1080_sdr_a100_v100_60sec.mp4
    """
    if not os.path.exists(filename):
        return
    outputfile = Path(filename)   # safely handle path
    if not outputfile.exists():
        raise FileNotFoundError(f"File not found: {outputfile}")

    # Build new name
    base = outputfile.stem
    ext = outputfile.suffix

    new_filename = f"{base}_a{stats['audio_frames']}_v{stats['video_frames']}_{int(stats['duration_sec'])}sec{ext}"
    new_path = outputfile.with_name(new_filename)

    if new_path.exists():
        os.remove(new_path)

    os.rename(outputfile, new_path)
    return str(new_path)

# -------------------------------
# Generate and run FFmpeg commands
# -------------------------------
def run_ffmpeg(video_options, audio_options, video_enabled, audio_enabled, video_source,
               audio_source, volume, input_files, durationEntry, gopSecEntry, keySecEntry, actualFileFormat, output_directory):
    if not video_enabled and not audio_enabled:
        messagebox.showwarning("Error", "Enable at least Video or Audio")
        return

    duration = int(durationEntry)
    gop_size_sec = float(gopSecEntry)
    key_sec = float(keySecEntry)
    volume_level = float(volume)

    # Prepare selected options
    vid_keys = list(video_params.keys())
    aud_keys = list(audio_params.keys())

    selected_vid_options = [video_options[k].get_selected_list() for k in vid_keys]
    selected_aud_options = [audio_options[k].get_selected_list() for k in aud_keys]

    # Generate all combinations
    vid_combos = list(itertools.product(*selected_vid_options)) if video_enabled else [()]
    aud_combos = list(itertools.product(*selected_aud_options)) if audio_enabled else [()]

    for vid_combo in vid_combos:
        for aud_combo in aud_combos:
            fileFormat = ""

            vid_dict = dict(zip(vid_keys, vid_combo)) if video_enabled else {}
            aud_dict = dict(zip(aud_keys, aud_combo)) if audio_enabled else {}

            if(actualFileFormat == None or actualFileFormat == ""):
                if(video_enabled and audio_enabled):
                    fileFormat = "mp4"
                elif(video_enabled):
                    fileFormat = fileformat_mapping[vid_dict["Codec"]]
                elif(audio_enabled):
                    fileFormat = fileformat_mapping[aud_dict["Codec"]]
            else:
                fileFormat = actualFileFormat

            if(vid_dict):
                vid_dict["gop_size"] = gop_size_sec
                vid_dict["key_sec"] = key_sec
            cmd, outputfile = generate_ffmpeg_command(vid_dict, aud_dict, input_files["video"], input_files["audio"], video_source, "sine", duration, volume_level, fileFormat, output_directory)
            if not cmd or not outputfile:
                continue
            print("Running:", " ".join(cmd))
            subprocess.run(cmd)
            stream_info = get_stream_info(outputfile)
            new_name = rename_file_with_stats(outputfile, stream_info)

    messagebox.showinfo("Done", "Stream(s) generated successfully!")

# -------------------------------
# File selection
# -------------------------------
def select_file(file_type):
    path = filedialog.askopenfilename(title=f"Select {file_type} file")
    path = str(Path(path).resolve().as_posix())
    return path

# -------------------------------
# Folder selection
# -------------------------------
def select_folder(file_type):
    path = filedialog.askdirectory(title=f"Select {file_type} directory")
    if not path:
        return ""
    path = str(Path(path).resolve().as_posix())
    return path

# -------------------------------
# Build UI
# -------------------------------
root = tk.Tk()
root.title("VTS Test Stream Generator")
root.geometry("920x720")

# Global font style
style = ttk.Style()
style.configure("TLabel", font=("Segoe UI", 12))
style.configure("TCheckbutton", font=("Segoe UI", 12))
style.configure("TEntry", font=("Segoe UI", 12))

# Enable toggles in a frame
toggle_frame = ttk.Frame(root, padding=10)
toggle_frame.pack(anchor='w', fill='x')

video_enabled = tk.BooleanVar(value=True)
audio_enabled = tk.BooleanVar(value=True)

ttk.Checkbutton(toggle_frame, text="Enable Video", variable=video_enabled).grid(row=0, column=0, sticky='w', padx=5, pady=5)
ttk.Checkbutton(toggle_frame, text="Enable Audio", variable=audio_enabled).grid(row=0, column=1, sticky='w', padx=15, pady=5)

# Duration row
duration_frame = ttk.Frame(root, padding=10)
duration_frame.pack(anchor='w', fill='x')

duration_var = tk.StringVar(value="10")  # default value
ttk.Label(duration_frame, text="Duration (sec):").grid(row=0, column=0, sticky='w', padx=5, pady=5)
duration = ttk.Entry(duration_frame, textvariable=duration_var, width=10, font=("Segoe UI", 11))
duration.grid(row=0, column=1, sticky='w', padx=5, pady=5)

fileformat_var = tk.StringVar(value="mp4")  # default value
ttk.Label(duration_frame, text="File Format").grid(row=1, column=0, sticky='w', padx=5, pady=5)
file_format = ttk.Entry(duration_frame, textvariable=fileformat_var, width=10, font=("Segoe UI", 11))
file_format.grid(row=1, column=1, sticky='w', padx=5, pady=5)

output_path = tk.StringVar()

def select_directory():
    output_path.set(select_folder("Video"))

style = ttk.Style()
style.configure(
    "Customd.TButton",
    font=("Segoe UI", 11)
)

ttk.Button(duration_frame, text="Output Directory", command=select_directory, style="Customd.TButton").grid(
    row=2, column=0, padx=5, pady=5, sticky="w"
)
ttk.Label(duration_frame, textvariable=output_path, font=("Segoe UI", 10)).grid(
    row=2, column=1, sticky='w', padx=10, pady=8
)

# Notebook for tabs
notebook = ttk.Notebook(root)
notebook.pack(fill='both', expand=True, padx=10, pady=10)

style = ttk.Style()
style.configure("TNotebook", tabposition="n")  # tabs on top
style.configure("TNotebook.Tab", padding=[15, 8], font=("Segoe UI", 11, "bold"))

# Make active tab more visible
style.map("TNotebook.Tab",
          background=[("selected", "#d9d9d9")],
          expand=[("selected", [1, 1, 1, 0])])

# -------------------------------
# Video Parameters Tab
# -------------------------------
video_frame = ttk.Frame(notebook, padding=15, borderwidth=2, relief="groove")
notebook.add(video_frame, text="Video Parameters")

video_options = {}
row = 0
col = 0
for key, options in video_params.items():

    ttk.Label(video_frame, text=key + ":", font=("Segoe UI", 12, "bold")).grid(
        row=row, column=col, sticky='w', padx=10, pady=8
    )

    COMBOPICKER = Combopicker(video_frame, options)
    COMBOPICKER.grid(
        row=row, column=col+1, sticky='w', padx=10, pady=8
    )
    col += 2
    col = col % 4
    video_options[key] = COMBOPICKER

    if col == 0:
        row += 1

if col:
    row += 1
ttk.Label(video_frame, text="GOP Size (sec):", font=("Segoe UI", 12)).grid(
    row=row, column=0, sticky="w", padx=10, pady=8
)
gop_size_var = tk.StringVar(value="1")  # default value
gop_size_entry = ttk.Entry(video_frame, textvariable=gop_size_var, width=10, font=("Segoe UI", 11))
gop_size_entry.grid(
    row=row, column=1, sticky="w", padx=10, pady=8
)
row += 1

ttk.Label(video_frame, text="Keyframe Interval (sec):", font=("Segoe UI", 12)).grid(
    row=row, column=0, sticky="w", padx=10, pady=8
)
keyint_var = tk.StringVar(value="1")  # default value
keyint_entry = ttk.Entry(video_frame, textvariable=keyint_var, width=10, font=("Segoe UI", 11))
keyint_entry.grid(
    row=row, column=1, sticky="w", padx=10, pady=8
)
row += 1

# -------------------------------
# Audio Parameters Tab
# -------------------------------
audio_frame = ttk.Frame(notebook, padding=15, borderwidth=2, relief="groove")
notebook.add(audio_frame, text="Audio Parameters")

audio_options = {}
row = 0
for key, options in audio_params.items():
    ttk.Label(audio_frame, text=key + ":", font=("Segoe UI", 12, "bold")).grid(
        row=row, column=0, sticky='w', padx=10, pady=8
    )

    COMBOPICKER = Combopicker(audio_frame, options)
    COMBOPICKER.grid(
        row=row, column=1, sticky='w', padx=10, pady=8
    )
    audio_options[key] = COMBOPICKER

    row += 1

ttk.Label(audio_frame, text="Volume", font=("Segoe UI", 12)).grid(
    row=row, column=0, sticky="w", padx=10, pady=8
)
volume_var = tk.StringVar(value="1")  # default value
volume_entry = ttk.Entry(audio_frame, textvariable=volume_var, width=10, font=("Segoe UI", 11))
volume_entry.grid(
    row=row, column=1, sticky="w", padx=10, pady=8
)
row += 1
# -------------------------------
# Input / Test Sources Tab
# -------------------------------
input_frame = ttk.Frame(notebook, padding=15, borderwidth=2, relief="groove")
notebook.add(input_frame, text="Input / Test Sources")

ttk.Label(input_frame, text="Video Test Source:", font=("Segoe UI", 12)).grid(
    row=0, column=0, sticky='w', padx=10, pady=8
)
video_source_var = tk.StringVar(value=video_test_sources[0])
ttk.Combobox(input_frame, values=video_test_sources, textvariable=video_source_var, width=30, font=("Segoe UI", 11)).grid(
    row=0, column=1, padx=10, pady=8, sticky="w"
)

ttk.Label(input_frame, text="Audio Test Source:", font=("Segoe UI", 12)).grid(
    row=1, column=0, sticky='w', padx=10, pady=8
)
audio_source_var = tk.StringVar(value=audio_test_sources[0])
ttk.Combobox(input_frame, values=audio_test_sources, textvariable=audio_source_var, width=30, font=("Segoe UI", 11)).grid(
    row=1, column=1, padx=10, pady=8, sticky="w"
)

video_file_path = tk.StringVar()
audio_file_path = tk.StringVar()

def select_video_file():
    video_file_path.set(select_file("Video"))

def select_audio_file():
    audio_file_path.set(select_file("Audio"))

style = ttk.Style()
style.configure(
    "Customb.TButton",
    font=("Segoe UI", 12)
)

ttk.Button(input_frame, text="Select Video File", command=select_video_file, style="Customb.TButton").grid(
    row=2, column=0, padx=10, pady=8, sticky="w"
)
ttk.Label(input_frame, textvariable=video_file_path, font=("Segoe UI", 10)).grid(
    row=2, column=1, sticky='w', padx=10, pady=8
)

ttk.Button(input_frame, text="Select Audio File", command=select_audio_file, style="Customb.TButton").grid(
    row=3, column=0, padx=10, pady=8, sticky="w"
)
ttk.Label(input_frame, textvariable=audio_file_path, font=("Segoe UI", 10)).grid(
    row=3, column=1, sticky='w', padx=10, pady=8
)

# -------------------------------
# Generate Button
# -------------------------------
button_frame = ttk.Frame(root, padding=15)
button_frame.pack(fill="x")

style = ttk.Style()
style.configure(
    "Custom.TButton",
    font=("Segoe UI", 12, "bold")
)

generate_btn = ttk.Button(
    button_frame,
    text="🎬 Generate Stream(s)",
    command=lambda: run_ffmpeg(
        video_options,
        audio_options,
        video_enabled.get(),
        audio_enabled.get(),
        video_source_var.get(),
        audio_source_var.get(),
        volume_entry.get(),
        {"video": video_file_path.get(), "audio": audio_file_path.get()},
        duration.get(),
        gop_size_entry.get(),
        keyint_entry.get(),
        file_format.get(),
        output_path.get()
    ),
    style="Custom.TButton"
)

generate_btn.pack(pady=10)

root.mainloop()

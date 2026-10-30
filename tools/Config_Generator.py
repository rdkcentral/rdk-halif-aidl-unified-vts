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

import os
import yaml

def generate_yaml_config(input_folder, output_file="config.yaml"):
    """
    Reads mp4,webm,ts,mkv files from a folder and generates a YAML configuration file.

    Args:
        input_folder (str): The path to the folder containing the video streams.
        output_file (str): The name of the YAML file to be created.
    """
    # Check if the PyYAML library is installed
    try:
        import yaml
    except ImportError:
        print("The PyYAML library is not installed.")
        print("Please install it using: pip install PyYAML")
        return

    # Check if the input folder exists
    if not os.path.isdir(input_folder):
        print(f"Error: The folder '{input_folder}' does not exist.")
        return

    # Get a list of all .mp4 and webm files in the folder
    streams = [f for f in os.listdir(input_folder) if f.endswith(('.mp4','.webm','.ts','.mkv'))]

    # Sort the files for consistent output
    streams.sort()

    if not streams:
        print(f"No mp4 or webm or ts or mkv files found in the folder '{input_folder}'.")
        # Create an empty YAML file with the base structure if no files are found
        yaml_data = {
            "AVModule": {
                "stream_download_path": "http://<>/streams",
                "input_streams_path": "assets/streams/input",
                "player": "gstreamer",
                "L4Test": []
            }
        }
    else:
        # Build the L4Test list of dictionaries
        l4_test_list = []
        tcid_counter = 1001
        for stream_name in streams:
            # Generate a Test Case ID (tcid) based on an incrementing counter
            tcid = f"VTS_L4_AVFORMAT_{tcid_counter}"
            tcid_counter += 1

            l4_test_list.append({
                "tcid": tcid,
                "action": "normal_play",
                "stream_name": stream_name
            })

        # Create the full YAML data structure
        yaml_data = {
            "AVModule": {
                "stream_download_path": "http://<>/streams",
                "input_streams_path": "assets/streams/input",
                "player": "gstreamer",
                "L4Test": l4_test_list
            }
        }

    # Write the data to the YAML file
    try:
        with open(output_file, 'w') as file:
            yaml.dump(yaml_data, file, sort_keys=False)
        print(f"Successfully generated '{output_file}' with {len(streams)} streams.")
    except Exception as e:
        print(f"An error occurred while writing the YAML file: {e}")

# Example usage:
if __name__ == "__main__":
    # Specify the folder where your mp4,webm,ts,mkv files are located
    # You can change this path to your actual folder
    videos_folder = "/home/<PATH>/"

    # Call the function to generate the YAML file
    generate_yaml_config(videos_folder, videos_folder+"config.yaml")

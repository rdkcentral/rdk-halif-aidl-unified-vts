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
import sys
from pathlib import Path
import re

dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(dir_path, "../"))

from vts_helper import VTSTestHelperClass
from raft.framework.core.logModule import logModule
from raft.framework.plugins.ut_raft import utHelperClass
from raft.framework.plugins.ut_raft.utPlayer import utPlayer
from raft.framework.plugins.ut_raft.utBaseUtils import utBaseUtils
from raft.framework.plugins.ut_raft.utSuiteNavigator import UTSuiteNavigatorClass
from raft.framework.plugins.ut_raft.configRead import ConfigRead


class L4TestClass(VTSTestHelperClass):
    """Test class for running L4 AV module tests (playback + trick modes)."""

    def __init__(self, log: logModule = None):
        super().__init__(
            module_name="VTS",
            test_name="L4_AVModule",
            qc_id="L4_001",
            test_suites=["VTS_L4_AVMODULE"],
            l4_yaml_path=os.path.join(os.path.dirname(os.path.realpath(__file__)), "vts_l4_test_info.yaml"),
            setup_file_name="vts_l4_test_setup.yaml",
            test_config_file_name="vts_l4_test_setup.yaml",
            log=log
        )

    def testFunction(self):
        """
        The main test function to run L4 tests, looping through each test case.

        Returns:
            bool: Final result of the test.
        """
        if not self.test_prepare_function():
            self.log.error("Test preparation failed")
            return False

        final_result = True
        outputs = []
        results = []
        test_suite_name = "VTS_L4_AVMODULE"
        self.waitTime = self.cpe.get("wait_time")
        self.module_name = "AVModule"
        socVendor = self.cpe.get("soc_vendor")
        self.restart_required = False

        self.player_session = self.dut.getConsoleSession("ssh_player")

        self.vts_player =  utPlayer(self.player_session, socVendor)

        self.player_session.prompt = self.prompt

        self.utilities = utBaseUtils()
        self.ut_menu = []
        ut_menu = UTSuiteNavigatorClass(self.test_config, None, self.player_session)
        self.ut_menu.append(ut_menu)

        self.utilities.change_directory(self.player_session, self.run_path)

        # Read L4 test info YAML to get test cases
        if not os.path.exists(self.l4_yaml_path):
            self.log.error(f"L4 input YAML file {self.l4_yaml_path} does not exist")
            return False

        with open(self.l4_yaml_path, 'r') as f:
            data = yaml.safe_load(f) or {}

        av_root = data.get("AVModule", {})

        # Collect include_* keys
        include_pattern = re.compile(r"include_\d+")
        include_files = [av_root[k] for k in av_root.keys() if include_pattern.fullmatch(k)]

        # Resolve relative paths relative to repo root or current dir path
        resolved_include_files = []
        for inc in include_files:
            if not os.path.isabs(inc):
                # Try relative to repository root (two levels up) then current dir
                candidate1 = os.path.join(dir_path, inc)
                candidate2 = os.path.join(os.getcwd(), inc)
                if os.path.exists(candidate1):
                    resolved_include_files.append(candidate1)
                elif os.path.exists(candidate2):
                    resolved_include_files.append(candidate2)
                else:
                    self.log.warn(f"Include file not found: {inc}")
            else:
                if os.path.exists(inc):
                    resolved_include_files.append(inc)
                else:
                    self.log.warn(f"Include file not found: {inc}")

        # Base tests from primary file
        l4_tests = list(av_root.get("L4", []))

        # Merge from included files (supports 'L4' and legacy 'L4Test')
        seen_tcids = {tc.get('tcid') for tc in l4_tests if tc.get('tcid')}
        for inc_file in resolved_include_files:
            try:
                with open(inc_file, 'r') as f_inc:
                    inc_data = yaml.safe_load(f_inc) or {}
                inc_av = inc_data.get("AVModule", {})
                for key in ("L4", "L4Test"):
                    extra_list = inc_av.get(key, [])
                    if isinstance(extra_list, list):
                        for tc in extra_list:
                            tcid = tc.get('tcid')
                            if not tcid:
                                continue
                            if tcid in seen_tcids:
                                self.log.info(f"Skipping duplicate TCID from include {inc_file}: {tcid}")
                                continue
                            l4_tests.append(tc)
                            seen_tcids.add(tcid)
                self.log.info(f"Merged tests from include file: {inc_file}")
            except Exception as e:
                self.log.error(f"Failed processing include file {inc_file}: {e}")
        manual_verification = False


        for i, ut_menu in enumerate(self.ut_menu):
            self.log.info(f"[Instance {i}] Starting test case...")
            ut_menu.start()

        for test_case in l4_tests:
            tcid = test_case.get("tcid")
            action = test_case.get("action")
            stream_name = test_case.get("stream_name")
            target_stream_name = stream_name
            self.log.testStart(test_suite_name, tcid)

            if self.restart_required:
                for i, ut_menu in enumerate(self.ut_menu):
                    self.log.info(f"[Instance {i}] Starting test case...")
                    ut_menu.start()

            # Map action to test case name
            action_to_test_case = {
                "normal_play": "NormalPlay",
                "trick_play": "playBackWithTrickModes",
                "audio_switch": "AudioTrackSwitch",
                "video_switch": "VideoTrackSwitch"
            }
            test_case_name = action_to_test_case.get(action, action)

            self.log.stepStart(f"Test Suite: {test_suite_name} TCID: {tcid} Action: {test_case_name} Stream: {target_stream_name}")

            # Generate YAML files for this test case
            test_config_path = os.path.join(dir_path, "vts_l4_av_test_config.yaml")
            stream_config_path = os.path.join(dir_path, "vts_l4_av_stream_config.yaml")
            if not self.generate_l4_yaml_files_for_test_case(test_case, test_config_path, stream_config_path, stream_name):
                self.log.error(f"Failed to generate YAML files for TCID: {tcid}")
                final_result = False
                continue

            # Copy YAML files and stream to DUT
            if not self.copy_yaml_and_stream(test_config_path, stream_config_path, stream_name, tcid):
                self.log.error(f"Failed to copy YAML files or stream for TCID: {tcid}")
                final_result = False
                continue

            self.stream_info = ConfigRead(stream_config_path, "AVStreams")
            stream_ext = self.get_stream_extension(stream_name)
            duration = self.stream_info.get(f"{tcid}_{stream_ext}.duration")
            if duration is None:
                self.log.info(f"No stream duration found for {tcid}_{stream_ext} in stream config")
                wait_time = self.wait_time  # fallback
            else:
                wait_time = duration + 10 #

            output = ut_menu.select(test_suite_name, test_case_name, None, wait_time, False)
            outputs.append(output)

            # Decide manual vs auto based on device config flag first
            playback_verification_flag = self.cpe.get("playback_manual_verification", 1)

            if playback_verification_flag == 1:
                # Manual verification enabled: only proceed if the prompt appears
                if "Is the stream playback good (Y/N)?" in output:
                    failed = not self.testVerifyAVPlayback(True)
                    if failed:
                        self.player_session.write("N")
                        self.log.info("Playback verification failed.")
                    else:
                        self.player_session.write("Y")
                        self.log.info("Playback verification passed.")

            # Capture the summary from the same console used by ut_menu.
            if "Run Summary:" not in output:
                output += self.player_session.read_until("Run Summary:", timeout=60)
            if "Run Summary:" in output and "Elapsed time =" not in output:
                output += self.player_session.read_until("Elapsed time =", timeout=60)
            result = ut_menu.collect_results(output, True)
            if result is None:
                final_result = False
                run_summary_found = "Run Summary:" in output
                if not run_summary_found:
                    self.log.error("Run Summary not found.")
                    #if the run summary is not found, we need to restart the ut_menu because hal test binary may crashed , we can add some options to check when to restart menu
                    self.restart_required = True
                self.log.error(f"Failed to collect results for TCID: {tcid}")
            results.append(result)
            self.log.stepResult(result, f"Test Suite: {test_suite_name} TCID: {tcid} Action: {test_case_name}")

            # Clean up streams after each test case
            self.test_clean_all_assets()

            self.log.testResult(f'{test_suite_name} Finished')

            if self.restart_required:
                for i, ut_menu in enumerate(self.ut_menu):
                    self.log.info("Stopping VTS player...")
                    self.vts_player.stop()
                    self.log.info(f"[Instance {i}] Stopping test case...")
                    ut_menu.stop()


        self.test_cleanup()
        return final_result

if __name__ == "__main__":
    summaryLogName = os.path.splitext(os.path.basename(__file__))[0] + "_summary"
    summaryLog = logModule("L4Test", level=logModule.INFO)
    test = L4TestClass(summaryLog)
    test.run(False)

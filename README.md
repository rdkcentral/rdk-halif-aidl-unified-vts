# Unified Vendor Testing Suite For AIDL HAL

This document outlines the steps to build and run the Unified Vendor Testing Suite (VTS) for AIDL HAL, targeting Linux or ARM platforms. The test suite depends on the Linux Binder with AIDL support and requires specific setup, build, and execution steps.

## Table of Contents

- [Unified Vendor Testing Suite For AIDL HAL](#unified-vendor-testing-suite-for-aidl-hal)
  - [Acronyms, Terms and Abbreviations](#acronyms-terms-and-abbreviations)
  - [Setup](#setup)
  - [Build Linux Binder](#build-linux-binder)
  - [Build Unified VTS](#build-unified-vts)
  - [Run Tests Manually](#run-tests-manually)
  - [Setting Python environment for L1, L2, L3 and L4 automation test cases](#setting-python-environment-for-l1-l2-l3-and-l4-automation-test-cases)
  - [Running L1, L2, L3 and L4 Automation test cases](#running-l1-l2-l3-and-l4-automation-test-cases)
  - [Test Components List](#components-list)

## Acronyms, Terms and Abbreviations

| Acronym / Term | Description |
|----------------|-------------|
| **AIDL** | Android Interface Definition Language |
| **HAL** | Hardware Abstraction Layer |
| **L1** | Level 1 Test Cases (Interface / basic validation tests) |
| **L2** | Level 2 Test Cases (Functional tests) |
| **L3** | Level 3 Test Cases (Integration tests) |
| **L4** | Level 4 Test Cases (Layer & System Testing) |
| **RDK** | Reference Design Kit |
| **UT-Core** | RDK Unified Test Core Framework |
| **VTS** | Vendor Test Suite |
| **YAML** | Yet Another Markup Language (configuration format) |

## Setup

### Configure Personal Access Token (PAT) for HTTPS access

The build scripts use HTTPS URLs to clone repositories. To avoid being prompted for credentials during the build, configure a GitHub Personal Access Token (PAT) in your `~/.netrc` file:

1. Generate a PAT on GitHub with `repo` (read) scope, preferably the `classic` one:
   - <https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#personal-access-tokens-classic>

2. Add your credentials to `~/.netrc`:

```bash
echo "machine github.com login <your-github-username> password <your-PAT>" >> ~/.netrc
chmod 600 ~/.netrc
```

- Replace `<your-github-username>` with your GitHub username and `<your-PAT>` with the token generated above.
- The `chmod 600` restricts the file to owner-only access, which is required by Git.

### Configure SSH for GitHub (alternative)

- To avoid conflict between your organization GitHub and RDK Central GitHub, add the following in your ssh config (`~/.ssh/config`):

<!-- -->

    Host github.code.rdkcentral.com
      Hostname github.com
      User
      IdentityFile ~/.ssh/

- The instruction to generate SSH key for GitHub:

  - <https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account>

## Build Linux Binder

The Linux Binder with `AIDL` support is built automatically by `build.sh` — no manual steps are required. `build.sh` clones `linux_binder_idl` and builds the binder libraries for the selected target.

For reference, full build instructions are available in the [linux_binder_idl](https://github.com/rdkcentral/linux_binder_idl) repository.

## Build Unified VTS

### Prerequisites for ut-core

VTS relies on the ut-core framework. Please ensure all required packages for ut-core are installed. See the instructions here: [Packages for ut-core](https://github.com/rdkcentral/ut-core/wiki/UT-Core-Building-using-Docker-or-Vagrant#script-for-installing-basic-packages-for-ut-core)

### Prerequisite for build.sh

#### Install repo Tool

The `repo` tool is required to manage multiple repositories. Install it on your build server with:

```bash
mkdir -p ~/.local/bin
curl -o ~/.local/bin/repo https://storage.googleapis.com/git-repo-downloads/repo
chmod a+rx ~/.local/bin/repo
```

Ensure `~/.local/bin` is on your `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Add the `export` line to your `~/.bashrc` or `~/.profile` to make it permanent.

Verify the installation:

```bash
repo --version
```

### Clone the Repository

```bash
git clone https://github.com/rdkcentral/rdk-halif-aidl-unified-vts.git

cd rdk-halif-aidl-unified-vts
```

### Environment Variables

#### For Linux (x86) target

No environment variables are required. `build.sh` uses the host gcc automatically.

#### For ARM target

Source the RDK ARM toolchain before running the build:

```bash
source /opt/toolchains/rdk-glibc-x86_64-arm-toolchain/environment-setup-armv7vet2hf-neon-oe-linux-gnueabi
```

`build.sh` automatically:
- Builds the AIDL host tools (x86) required by the build system
- Cross-compiles the ARM binder libraries using the sourced toolchain
- Builds all HAL modules for ARM

#### Optional variables

```bash
# Override UT Core version (default: 5.1.0)
export UT_CORE_VERSION=5.1.0

# Optional. RDK HALIF AIDL version to build against (default: main). Set this
# only if you need a released version instead of the latest main branch.
export RDK_HALIF_AIDL_VERSION=0.22.0

# Override UT log level (default: WARNING)
export UT_LOG_LEVEL=3

# Enable AV L4 test cases (requires GStreamer)
export ENABLE_AV_L4_TEST=1
export GST_LIB_PATH=/path/to/gstreamer_pkg

# Enable Plane Control test cases (requires EGL)
export ENABLE_PLANE_CONTROL_TEST=1
export EGL_LIB_PATH=/path/to/egl_pkg
```

By default, UT logs are set to WARNING level. For more details on log level filtering, refer to [UT-Core Log Level Documentation](https://github.com/rdkcentral/ut-control/blob/2.1.0/README.md#log-level-filtering)

### Run the Build

Run the build script for Target ARM:

```bash
./build.sh Target=arm
```

Run the build script for Target Linux:

```bash
./build.sh Target=linux
```

The `build.sh` script automatically:

- Clones `rdk-halif-aidl`, vendor test modules, and the UT-Core framework
- Builds the Linux Binder libraries for the selected target (x86 or ARM)
- Builds all HAL modules from versioned snapshots in `versions_released.yaml`
- Compiles the VTS test suite
- Packages the binaries into `build/vts_unified.tar.gz`

To clean the build:

```bash
./build.sh clean Target=linux
./build.sh clean Target=arm
```

## Run Tests Manually

- In order to run the test cases manually on target device:

Copy the tarball `build/vts_unified.tar.gz` to the target device (e.g., using scp):

```bash
scp build/vts_unified.tar.gz root@target-device:/home/root/

```

- Extract on Target Device:

Log into the target device and extract the tarball:

```bash
ssh root@target-device
cd /home/root
tar -zxf vts_unified.tar.gz
cd bin
```

- Run the Test:

Execute the run.sh script as root by using the platform specific profile.

```bash
sudo ./run.sh -p profiles/hfp-vdevice.yaml
```

**Note:** For running the AV Module L3, L4 test cases manually make sure the test streams are copied into `bin/assets/streams/input` folder on target device.

## Setting Python environment for L1, L2, L3 and L4 automation test cases

- For running the L1, L2, L3 and L4 test suite, a host PC with a Python environment is required.
- Install Python Environment and Activation Scripts as detailed in [Python Installation](https://github.com/rdkcentral/ut-raft/wiki/Guide-for-Setting-up-the-Python-RAFT-Testing-Suite)

## Running L1, L2, L3 and L4 Automation test cases

- To run the VTS `L1`, `L2` test cases follow the `L1` `L2` Test Procedure document - [vts_L1_L2_TestProcedure.md](docs/vts_L1_L2_TestProcedure.md)

- To run the AV Module `L3` test cases follow the `L3` Test Procedure document - [vts_avmodule_L3_TestProcedure.md](docs/vts_avmodule_L3_TestProcedure.md)

- To run the AV  Module `L4` test cases follow the `L4` Test Procedure document - [vts_avmodule_L4_TestProcedure.md](docs/vts_avmodule_L4_TestProcedure.md)

## Components list

Each individual component and their respective test repositories are listed below:

| #| Component Name | Repositories |
| -| ---------------| -------------|
| 1|AV Buffer       |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-avbuffer)|
| 2|Audio Decoder   |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-audiodecoder)|
| 3|Audio Sink      |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-audiosink)|
| 4|Video Decoder   |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-videodecoder)|
| 5|Video Sink      |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-videosink)|
| 6|AV Clock        |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-avclock)|
| 7|Plane Control   |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-planecontrol)|
| 8|HDMI CEC        |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-cec)|
| 9|HDMI Input      |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-hdmiinput)|
|10|HDMI Output     |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-hdmioutput)|
|11|Deep Sleep      |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-deepsleep)|
|12|Device Info     |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-device-info)|
|13|Boot            |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-boot)|
|14|Flash           |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-flash)|
|15|Indicator       |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-indicator)|
|16|Audio Mixer     |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-audiomixer)|
|17|CDM             |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-cdm)|
|18|Broadcast       |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-broadcast)|
|19|Composite Input |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-compositeinput)|
|20|Panel           |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-panel)|
|21|Motion Sensor   |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-motion-sensor)|
|22|Thermal Sensor  |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-thermal-sensor)|
|23|Far Field Voice |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-test-farfieldvoice)|
|24|L4 Vendor Test  |[Test Repo](https://github.com/rdkcentral/rdk-halif-aidl-L4-Vendor)|

**Note:** Building for ARM requires the RDK toolchains to be installed. For more information, see [RDK Docker Toolchain](https://github.com/rdkcentral/ut-core/wiki/FAQ:-RDK-Docker-Toolchain).

# Unified Vendor Testing Suite For AIDL HAL

This document outlines the steps to build and run the Unified Vendor Testing Suite (VTS) for AIDL HAL, targeting Linux or ARM platforms. The test suite depends on the Linux Binder with AIDL support and requires specific setup, build, and execution steps.

test 
## Table of Contents

- [Unified Vendor Testing Suite For AIDL HAL](#unified-vendor-testing-suite-for-aidl-hal)
  - [Acronyms, Terms and Abbreviations](#acronyms-terms-and-abbreviations)
  - [Setup](#setup)
  - [Build linux binder for Target Linux](#build-linux-binder-for-target-linux)
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

1. Generate a PAT on GitHub with `repo` (read) scope:
   - <https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens>

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

## Build linux binder for Target Linux

The test suite depends on the Linux binder with `AIDL` support. Follow these steps to build it:

For detail build instruction, please refer to [Linux Binder](https://github.com/rdkcentral/linux_binder_idl/tree/1.0.0)

Here outline the simplest steps are

```bash
git clone -b 1.0.0 'https://github.com/rdkcentral/linux_binder_idl.git'

cd linux_binder_idl

./build-linux-binder-aidl.sh 64
```

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

Source the appropriate tool chains for the cross compilation

Set below environment variable:

- AIDL_BIN: Path to the `AIDL` compiler (e.g., /path/to/linux_binder_idl/out/aidl).

- LINUX_BINDER_OUT_DIR: Path to the Linux binder output directory (e.g., /path/to/linux_binder_idl/local).

- UT_CORE_VERSION: Specific version of the UT-Core framework (e.g., 5.1.0). Defaults to the latest tagged version.

- RDK_HALIF_AIDL_VERSION: Specific version of the AIDL HALIF Specification (e.g, 0.15.0). Defaults to the latest HEAD.

Example:

```bash
export UT_CORE_VERSION=5.1.0
export RDK_HALIF_AIDL_VERSION=0.15.0
export AIDL_BIN=/path/linux_binder_idl/out/aidl
export LINUX_BINDER_OUT_DIR=/path/linux_binder_idl/local/
```

By default, UT logs are set to WARNING level. For more details on log level filtering, refer to [UT-Core Log Level Documentation](https://github.com/rdkcentral/ut-control/blob/2.1.0/README.md#log-level-filtering)

```bash
export UT_LOG_LEVEL=3
```



Run the build script for Target ARM:

```bash
./build.sh Target=arm
```

Run the build script for Target Linux:

```bash
./build.sh Target=linux
```

The build.sh script:

- Clones the `rdk-halif-aidl` repository, Vendor test modules and UT-Core framework.

- Compiles the test suite.

- Generates binaries and packages the binaries in the `build/vts_unified.tar.gz.bz` directory.

## Run Tests Manually

- In order to run the test cases manually on target device:

Copy the tarball `build/vts_unified.tar.gz.bz` to the target device (e.g., using scp):

```bash
scp build/vts_unified.tar.gz.bz root@target-device:/home/root/

```

- Extract on Target Device:

Log into the target device and extract the tarball:

```bash
ssh root@target-device
cd /home/root
tar -zxf vts_unified.tar.gz.bz
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
